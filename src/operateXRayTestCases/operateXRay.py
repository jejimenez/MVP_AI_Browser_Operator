import csv
import os
import re
import json
import sys
from abacus_client import AbacusAIClient
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from otp import generate_otp
import time
from HTMLSummarizer import HTMLSummarizer, html_to_wan, html_to_wan_visible

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

def parse_step_with_llm(step_text, client):
    try:
        code_prompt = """Write the following test case in Gherkin language. Break down each action into the smallest possible steps, ensuring that each step represents a single user action (e.g., a single click, navigation, or input). For navigation paths (e.g., "Administration → Apps → Installed"), create separate steps for each level of navigation (e.g., "Given I navigate to Administration", "Given I navigate to Apps", "Given I navigate to Installed"). Only return the Gherkin steps without any additional text or explanation. Do not include any introductory or concluding statements. The output should start with "Feature:" and only contain valid Gherkin syntax: """
        llm_prompt = code_prompt + str(step_text)
        response = client.send_prompt(prompt=llm_prompt)
        return response["result"]["content"] if response else None
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

def gherkin_to_playwright_with_llm(gherkin_line, wan_output, client):
    prompt = f"""Given the following Web Abstract Notation (WAN) output representing the visible HTML structure of a webpage:

{wan_output}

And the following Gherkin step describing a user action or validation:

'{gherkin_line}'

Generate Playwright instruction(s) in Python using the SYNC API (e.g., page.click(), page.fill(), page.wait_for_selector(), no 'await') to execute the Gherkin step. Use the WAN output to identify the correct element selectors based on attributes like id, class, href, aria-label, or data attributes. If the step involves validation (e.g., "Then I should see"), use page.query_selector() to check for the element's presence and return an assert statement. If multiple instructions are needed, separate them with a semicolon and a space (e.g., "page.wait_for_selector('selector'); page.click('selector')"). Return the instructions as a single string without any explanation, comments, or additional text. If only one instruction is needed, return it as a single string (e.g., "page.click('selector')"). Ensure each instruction is executable and matches the Playwright sync API syntax.
"""
    response = client.send_prompt(prompt)
    
    if response and "result" in response and "content" in response["result"]:
        with open("prompt.test", mode='w') as output:
            print(prompt, file=output)
            print(response)
        raw_instruction = response["result"]["content"]
        if raw_instruction.startswith("```python\n"):
            raw_instruction = raw_instruction[len("```python\n"):].rstrip("'\n```").strip("'")
        elif raw_instruction.startswith("```"):
            raw_instruction = raw_instruction[len("```"):].rstrip("'\n```").strip("'")
        instruction = raw_instruction.strip().strip("'").strip('"')
        instruction = instruction.replace("\\'", "'").replace('\\"', '"')
        instruction = instruction.replace("await page.locator(", "page.click(").replace(").click()", ")")
        instructions = [instr.strip() for instr in instruction.split('; ') if instr.strip()]

        return instructions if instructions else [f'# Error: {gherkin_line}']
    return [f'# Error: {gherkin_line}']


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
    
    processed_lines = []
    for line in lines:
        if "→" in line and "navigate to" in line.lower():
            nav_path = line.split("navigate to", 1)[1].strip()
            nav_steps = [step.strip() for step in nav_path.split("→")]
            for step in nav_steps:
                processed_lines.append(f"Given I navigate to {step}")
        else:
            processed_lines.append(line)
    
    return processed_lines

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

# New function to run steps from JSON
def run_steps_from_json(page, json_file="training_data.jsonl"):
    results = []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            steps = [json.loads(line.strip()) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: {json_file} not found. Please run in default mode first to generate it.")
        return results

    for step_data in steps:
        gherkin_step = step_data["gherkin_step"]
        instruction = step_data["playwright_instruction"]
        print(f"Executing: {gherkin_step} -> {instruction}")
        try:
            exec(instruction)
            results.append({"step": gherkin_step, "status": "Success"})
            print(f"Success: {gherkin_step}")
        except Exception as e:
            results.append({"step": gherkin_step, "status": f"Fail: {str(e)}"})
            print(f"Failed: {gherkin_step} -> {str(e)}")
            break

    return results

def sanitize_playwright_instruction(instruction):
    # Remove any non-printable or special characters
    if instruction.startswith("`") and instruction.endswith("`"):
        sanitized_instruction = instruction[1:-1]
    sanitized_instruction = re.sub(r'[^\x20-\x7E]', '', instruction)
    return sanitized_instruction

# Main execution
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    page = browser.new_page()
    client = AbacusAIClient()
    results = []
    training_data = []

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
        parsed_steps = parse_step_with_llm(csv_steps, client)
        print("Gherkin Output:\n", parsed_steps)
        
        # Gherkin to Playwright
        gherkin_lines = gherkin_to_array(parsed_steps)
        print("Processed Gherkin Steps:\n", gherkin_lines)
        
        step_counter = 0
        for step in gherkin_lines:
            print('-----------------------------------')
            show_browser_message(page, f"""🚀 Executing: {step}""")
            step_counter += 1
            html = get_html(page)
            summarized_html = html_to_wan_visible(html)
            #instructions = gherkin_to_playwright_with_llm(step, summarized_html, client)
            #sample_inputs = { "wan_output": summarized_html, "gherkin_step": step}
            ai_instructions = client.wan_to_playwright_agent(summarized_html, step)
            print(f"instruction: {ai_instructions}")
            #instructions = sanitize_playwright_instruction(ai_instructions['segments'][0]['segment'])
            print(f"Step: {step}")
            print(f"Instructions: {ai_instructions}")
            
            # Add to training data
            training_data.append({
                "wan_output": summarized_html,
                "gherkin_step": step,
                "playwright_instruction": ai_instructions
            })
            
            try:
                for instruction in ai_instructions:
                #if 1 == 1:
                    #instruction = instructions
                    print('-------------------')
                    print(f"\t\t\t: {instruction}")
                    if instruction.startswith('# Error'):
                        raise Exception(f"Failed to generate instruction for step: {step}")
                    exec(instruction)
                results.append({"step": step, "status": "Success"})
                print(f"Executed: {step} -> {ai_instructions}")
            except Exception as e:
                results.append({"step": step, "status": f"Fail: {str(e)}"})
                print(f"Failed: {step} -> {str(e)}")

                # Save training data to JSONL file
                with open("training_data.jsonl", mode='w', encoding='utf-8') as jsonl_file:
                    for entry in training_data:
                        jsonl_file.write(json.dumps(entry) + '\n')
                break
            
            if step.find("PSA") != -1:
                print("Stopping execution after encountering 'PSA'.")
                #break
        
        # Save training data to JSONL file
        with open("training_data.jsonl", mode='w', encoding='utf-8') as jsonl_file:
            for entry in training_data:
                jsonl_file.write(json.dumps(entry) + '\n')
        print("Training data saved to 'training_data.jsonl'")

    page.wait_for_timeout(2000)
    browser.close()

# Print results after browser is closed
for result in results:
    print(result)