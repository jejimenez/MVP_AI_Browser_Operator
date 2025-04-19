import csv
import os
import re
import json
import sys
from abacus_client import AbacusAIClient
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from otp import generate_otp
from HTMLSummarizer import html_to_json_visible
import time

# Existing functions (unchanged)
def parse_csv(file_path):
    xray_pattern = r'!xray-attachment://[a-f0-9-]+\|width=\d+,height=\d+!'
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        parsed_rows = []
        for row in reader:
            cleaned_action = re.sub(xray_pattern, '', row['Action']).strip()
            cleaned_data = re.sub(xray_pattern, '', row['Data']).strip()
            cleaned_expected = re.sub(xray_pattern, '', row['Expected Result']).strip()
            parsed_rows.append({
                "steps": cleaned_action,
                "data": cleaned_data,
                "expected": cleaned_expected
            })
        return parsed_rows

def login(page, username, password, otp_secret, url=os.getenv('URL')):
    try:
        page.goto(url)
        page.fill("input[name='email']", username)
        page.fill("input[name='password']", password)
        page.click("button[type='submit']")
        page.wait_for_selector("input[name='mfaCode']", timeout=10000)
        otp = generate_otp(otp_secret)
        if not otp:
            raise Exception("OTP generation failed")
        page.fill("input[name='mfaCode']", otp)
        page.click("button[type='submit']")
        page.wait_for_url("**/#/systemDashboard/*", timeout=20000)
        print("Login successful")
    except Exception as e:
        print(f"Login failed: {e}")
        raise

def parse_step_with_llm(xray_steps, client):
    try:
        code_prompt = """You are provided with a list of step groups from an Xray test case, where each group contains 'steps', 'data', and 'expected' fields. Write the entire test case in Gherkin language as a single Feature with one Scenario. Combine all steps from the step groups into a single sequential Scenario, ensuring that each step represents a single user action (e.g., a single click, navigation, or input). For navigation paths (e.g., "Administration → Apps → Installed"), create separate steps for each level of navigation (e.g., "Given I navigate to Administration", "Given I navigate to Apps", "Given I navigate to Installed"). Use the 'data' field to inform additional steps (e.g., default values or input constraints) and the 'expected' field to create validation steps (e.g., "Then I should see..."). Do not split the steps into multiple scenarios; all steps should be part of one continuous Scenario under a single Feature named according to the content of the steps and validations. Only return the Gherkin steps without any additional text or explanation. The output should start with "Feature:" and only contain valid Gherkin syntax: """
        llm_prompt = code_prompt + str(xray_steps)
        response = client.send_prompt(prompt=llm_prompt)
        return response["result"]["content"] if response else None
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

def gherkin_to_playwright_with_llm(gherkin_line, json_dom, client):
    playwright_prompt = f"""Given the following JSON representation of a webpage’s DOM:

{json_dom}

And the following Gherkin step describing a user action or validation:

'{gherkin_line}'

Generate a structured list of valid Python Playwright instructions using the SYNC API. Use methods such as page.click(), page.fill(), page.wait_for_selector(), or page.query_selector() as appropriate. Use the JSON data to identify the correct element selectors based on attributes like id, class, href, aria-label, or data attributes.

Return a JSON object with two keys:
- "high_precision": A list of instructions using high-precision locators. Prioritize unique attributes like href, id, or data attributes (e.g., data-testid) to form the selector (e.g., a[href='#/administration/general/settings']). Avoid using :has-text() unless the 'text_source' is 'visible' and no simpler unique selector exists.
- "low_precision": A list of instructions using low-precision locators as a fallback. Use less specific attributes like class or text (e.g., a[class='css-rxojpe']:has-text('Administration')). Only use :has-text() if the 'text_source' is 'visible'.

For clickable elements like buttons or links:
- In the high_precision list, prefer using a single, unique attribute (e.g., href, id, or data-testid). If the element has a 'text' field and its 'text_source' is 'visible', you may use :has-text('text') to refine the selector only if the selector without :has-text() is not unique. If the 'text_source' is 'aria-label', do not use :has-text() because the text is not visible in the DOM.
- In the low_precision list, use class or text-based selectors as a fallback. Use :has-text() only if 'text_source' is 'visible'.

For actions (e.g., 'navigate to'), include page.wait_for_selector() before the action with a timeout of 10000ms to confirm the element’s presence, but only if the selector is not guaranteed to be immediately available (e.g., for dynamic content). If the step involves validation (e.g., "Then I should see"), use page.query_selector() to check for the element's presence and return an assert statement (e.g., assert page.query_selector('selector') is not None). If multiple instructions are required within a list, separate them with a semicolon and a space (e.g., "page.wait_for_selector('selector'); page.click('selector')"). If no unique matching element is found, return an empty list for that precision level (e.g., "high_precision": []). Ensure each instruction is executable, targets only elements with visible=true, and matches the Playwright sync API syntax. Return the resulting JSON object as a string without any additional commentary. Do not include backticks (```) or any other extraneous characters. Be executable without modification.
"""
    # Call the LLM with the prompt
    response = client.send_prompt(prompt=playwright_prompt)  # Adjust based on your actual client API
    # Parse the JSON response
    try:
        result = json.loads(response["content"])
        high_precision = result.get("high_precision", [])
        low_precision = result.get("low_precision", [])
        return {"high_precision": high_precision, "low_precision": low_precision}
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response: {e}")
        return {"high_precision": [], "low_precision": []}


def handle_quotes(instruction):
    """
    Handles different quote patterns in Playwright instructions to ensure proper escaping
    """
    # Replace triple quotes with single quotes
    instruction = instruction.replace('"""', "'")

    # Handle cases where double quotes are inside the string
    if '"' in instruction:
        # If the string contains both single and double quotes, escape the double quotes
        if "'" in instruction:
            instruction = instruction.replace('"', '\\"')
        # If only double quotes, wrap the entire string in single quotes
        else:
            if instruction.startswith('"') and instruction.endswith('"'):
                instruction = f"'{instruction[1:-1]}'"

    return instruction


def gherkin_to_array(gherkin_output):
    lines = [handle_quotes(line.strip()) for line in gherkin_output.split('\n') if line.strip() and not line.strip().startswith("Feature:") and not line.strip().startswith("Scenario:") and not line.strip().startswith("```gherkin") and not line.strip() == "```"]
    return lines

def get_html(page):
    page.wait_for_load_state('networkidle')
    page.wait_for_selector('#application')
    specific_divs = page.evaluate("""
        () => {
            const sidebar = document.querySelector('.application-sidebar-wrapper') || document.querySelector('#application-sidebar-wrapper');
            const pageWrapper = document.querySelector('.page-wrapper') || document.querySelector('#page-wrapper');
            return {
                sidebar: sidebar ? sidebar.outerHTML : null,
                pageWrapper: pageWrapper ? pageWrapper.outerHTML : null
            };
        }
    """)
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Extracted Components</title>
    </head>
    <body>
        {specific_divs['sidebar'] or '<!-- Sidebar not found -->'}
        {specific_divs['pageWrapper'] or '<!-- Page wrapper not found -->'}
    </body>
    </html>
    """
    return html_template

def extract_div_with_id(html_content, div_id="application"):
    soup = BeautifulSoup(html_content, "html.parser")
    target_div = soup.find("div", id=div_id)
    return str(target_div) if target_div else ""

def rgb_to_hex(rgb_str):
    if not rgb_str or "rgb" not in rgb_str:
        return None
    rgb = [int(x) for x in rgb_str.replace("rgb(", "").replace(")", "").split(",")]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".lower()


def show_browser_message(page, message, duration=5000):
    """
    Shows a message in the browser using JavaScript injection.
    """
    # Create unique ID for the banner to avoid duplicates
    banner_id = f'banner_{hash(message)}'

    js_code = f"""
        // Remove existing banner if any
        const existingBanner = document.getElementById('{banner_id}');
        if (existingBanner) {{
            existingBanner.remove();
        }}

        // Create new banner
        const banner = document.createElement('div');
        banner.id = '{banner_id}';
        banner.textContent = {repr(message)};

        // Apply styles
        banner.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: #fff;
            padding: 10px 20px;
            border-radius: 8px;
            z-index: 999999;
            font-size: 16px;
            font-family: sans-serif;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            pointer-events: none;
            opacity: 0.9;
        `;

        // Add to document
        document.body.appendChild(banner);

        // Remove after duration
        setTimeout(() => {{
            const bannerToRemove = document.getElementById('{banner_id}');
            if (bannerToRemove) {{
                bannerToRemove.remove();
            }}
        }}, {duration});
    """

    try:
        # Inject and execute the JavaScript code
        page.add_script_tag(content=js_code, type="text/javascript")

        # Execute the script
        page.evaluate("() => {" + js_code + "}")

        # Alternative method if the above doesn't work
        # page.evaluate(f"(() => {{ {js_code} }})()")
    except Exception as e:
        print(f"Error showing browser message: {str(e)}")

def run_steps_from_json(page, json_file="training_data.jsonl"):
    results = []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            steps = [json.loads(line.strip()) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: {json_file} not found. Please run in default mode first to generate it.")
        return results

    for step_data in steps:
        gherkin_step = step_data["step"]
        instruction = step_data["instruction"]
        print(f"Executing: {gherkin_step}")

        success = False
        used_precision = None
        error_message = None

        # Try high_precision instructions first
        for high_precision_instr in instruction.get("high_precision", []):
            print(f"Trying high-precision: {high_precision_instr}")
            try:
                exec(high_precision_instr)
                success = True
                used_precision = "high_precision"
                print(f"Success (high-precision): {gherkin_step} -> {high_precision_instr}")
                break
            except Exception as e:
                print(f"Failed (high-precision): {high_precision_instr} -> {str(e)}")
                error_message = str(e)

        # If high_precision fails, try low_precision instructions
        if not success:
            for low_precision_instr in instruction.get("low_precision", []):
                print(f"Trying low-precision: {low_precision_instr}")
                try:
                    exec(low_precision_instr)
                    success = True
                    used_precision = "low_precision"
                    print(f"Success (low-precision): {gherkin_step} -> {low_precision_instr}")
                    break
                except Exception as e:
                    print(f"Failed (low-precision): {low_precision_instr} -> {str(e)}")
                    error_message = str(e)

        # Record the result
        if success:
            results.append({
                "step": gherkin_step,
                "status": "Success",
                "used_precision": used_precision
            })
        else:
            results.append({
                "step": gherkin_step,
                "status": f"Fail: {error_message or 'No successful instruction'}"
            })
            print(f"Failed: {gherkin_step} -> No successful instruction")
            break  # Stop on failure, consistent with original behavior

    return results

def sanitize_playwright_instruction(instruction):
    # Remove any non-printable or special characters
    if instruction.startswith("`") and instruction.endswith("`"):
        sanitized_instruction = instruction[1:-1]
    sanitized_instruction = re.sub(r'[^\x20-\x7E]', '', instruction)
    return sanitized_instruction

def sanitize_json(obj):
    """Sanitize JSON data to handle Unicode and ensure valid JSONL output."""
    if isinstance(obj, str):
        return obj.encode("ascii", "ignore").decode("ascii")
    elif isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json(item) for item in obj]
    return obj

# Main execution
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    page = browser.new_page()
    client = AbacusAIClient()
    results = []
    training_data = []
    xray_to_gherkin_training_data = []

    # Login
    login(page, os.getenv('USR'), os.getenv('PW'), os.getenv('SECRET'))
    page.wait_for_load_state('networkidle')
    page.wait_for_selector('#application')

    # Check for mode (default or JSON)
    mode = os.getenv('MODE', 'default')  # Use environment variable to set mode
    if len(sys.argv) > 1:
        mode = sys.argv[1]  # Alternatively, use command-line argument

    if mode == 'json':
        # Run steps from JSONL and debug
        print("Running in JSON mode...")
        results = run_steps_from_json(page)
    else:
        # Default mode: Process CSV and generate steps
        print("Running in default mode...")
        csv_steps = parse_csv("NJ-86377_NoIterations.csv")
        #print(csv_steps)
        #parsed_steps = parse_step_with_llm(csv_steps, client)
        #print("Gherkin Output:\n", parsed_steps)

        # Save Xray-to-Gherkin training data
        '''
        if parsed_steps:
            xray_to_gherkin_training_data.append({
                "input": csv_steps,
                "output": parsed_steps
            })
            with open("xray_to_gherkin_training_data.jsonl", mode='w', encoding='utf-8') as jsonl_file:
                for entry in xray_to_gherkin_training_data:
                    jsonl_file.write(json.dumps(entry) + '\n')
            print("Xray-to-Gherkin training data saved to 'xray_to_gherkin_training_data.jsonl'")
        '''
        # Gherkin to Playwright
        #gherkin_lines = gherkin_to_array(parsed_steps)
        gherkin_lines = ['Given I navigate to Administration', 
         'And I navigate to Apps', 
         'And I navigate to Installed', 
         'And I navigate to NinjaOne PSA', 
         'And I navigate to General Tab', 
         'Then I should see NinjaOne PSA administration view in General Tab', 
         'Given I click on Edit in the Settings section', 
         'Then the Settings modal window should pop up', 
         'Given I choose or type a Default Invoice due days', 
         'And the Default Invoice due days should accept a numeric value from 0 to 9999', 
         'And by default, this field should get 30 when creating a new division', 
         'When I click on the Save button', 
         'Then I should see a saving message', 
         'And there should be no errors']
        print("Processed Gherkin Steps:\n", gherkin_lines)
        step_counter = 0
        for step in gherkin_lines:
            print('-----------------------------------')
            show_browser_message(page, f"Executing: {step}")
            step_counter += 1
            html = get_html(page)
            json_dom = html_to_json_visible(html)
            #json_dom = page.accessibility.snapshot() # trying with the playwright snapshots
            #ai_instructions = gherkin_to_playwright_with_llm(step, json_dom, client)
            ai_instructions = client.jsondom_to_playwright_agent(step, json_dom)
            print(f"Step: {step}")
            print(f"Instructions: {ai_instructions}")

            # Add to training data
            training_data.append(sanitize_json({
                "snapshot": json.dumps(json_dom),
                "step": step,
                "instruction": ai_instructions
            }))

            # Execute instructions with high_precision and low_precision approach
            success = False
            used_precision = None
            error_message = None

            # Try high_precision instructions as a single sequence
            high_precision_instructions = ai_instructions.get("high_precision", [])
            if high_precision_instructions:
                print(f"Trying high-precision instructions: {high_precision_instructions}")
                try:
                    for instruction in high_precision_instructions:
                        exec(instruction)
                    success = True
                    used_precision = "high_precision"
                    print(f"Success (high-precision): {step} -> {high_precision_instructions}")
                except Exception as e:
                    error_message = str(e)
                    print(f"Failed (high-precision): {high_precision_instructions} -> {error_message}")

            # If high_precision fails, try low_precision instructions as a single sequence
            if not success:
                low_precision_instructions = ai_instructions.get("low_precision", [])
                if low_precision_instructions:
                    print(f"Trying low-precision instructions: {low_precision_instructions}")
                    try:
                        for instruction in low_precision_instructions:
                            exec(instruction)
                        success = True
                        used_precision = "low_precision"
                        print(f"Success (low-precision): {step} -> {low_precision_instructions}")
                    except Exception as e:
                        error_message = str(e)
                        print(f"Failed (low-precision): {low_precision_instructions} -> {error_message}")

            # Record the result
            if success:
                results.append({"step": step, "status": "Success", "used_precision": used_precision})
            else:
                results.append({"step": step, "status": f"Fail: {error_message or 'No successful instruction'}"})
                print(f"Failed: {step} -> No successful instruction")
                # Save training data to JSONL file before breaking
                with open("training_data.jsonl", mode='w', encoding='utf-8') as jsonl_file:
                    for entry in training_data:
                        jsonl_file.write(json.dumps(entry, ensure_ascii=False) + '\n')
                break

            if step.find("PSA") != -1:
                print("passed the 'PSA' step")
                #break

        # Save training data to JSONL file
        with open("training_data.jsonl", mode='w', encoding='utf-8') as jsonl_file:
            for entry in training_data:
                jsonl_file.write(json.dumps(entry, ensure_ascii=False) + '\n')
        print("Training data saved to 'training_data.jsonl'")

    page.wait_for_timeout(2000)
    browser.close()

# Print results after browser is closed
for result in results:
    print(result)