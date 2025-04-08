import csv
import os
import re
from abacus_client import AbacusAIClient
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from otp import generate_otp
import time
from HTMLSummarizer import HTMLSummarizer, html_to_wan, html_to_wan_visible

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

def gherkin_to_array(gherkin_output):
    lines = [line.strip() for line in gherkin_output.split('\n') if line.strip() and not line.strip().startswith("Feature:") and not line.strip().startswith("Scenario:") and not line.strip().startswith("```gherkin") and not line.strip() == "```"]
    
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

# Main execution
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    page = browser.new_page()
    client = AbacusAIClient()
    results = []
    
    # Login
    login(page, os.getenv('USR'), os.getenv('PW'), os.getenv('SECRET'))
    page.wait_for_load_state('networkidle')
    page.wait_for_selector('#application')
    
    # Process test cases
    csv_steps = parse_csv("NJ-86377_NoIterations.csv")
    parsed_steps = parse_step_with_llm(csv_steps, client)
    print("Gherkin Output:\n", parsed_steps)
    
    # Gherkin to Playwright
    gherkin_lines = gherkin_to_array(parsed_steps)
    print("Processed Gherkin Steps:\n", gherkin_lines)
    # Add a counter to track iterations
    step_counter = 0
    with open("training.test", mode='w') as output:
        for step in gherkin_lines:
            print('-----------------------------------')
            step_counter += 1  # Increment the counter
            html = get_html(page)
            summarized_html = html_to_wan_visible(html)
            print(html, file=output)
            instructions = gherkin_to_playwright_with_llm(step, summarized_html, client)
            print(f"Step: {step}")
            print(f"Instructions (Array): {instructions}")
            try:
                for instruction in instructions:
                    print('-------------------')
                    print(f"\t\t\t: {instruction}")
                    if instruction.startswith('# Error'):
                        raise Exception(f"Failed to generate instruction for step: {step}")
                    exec(instruction)
                results.append({"step": step, "status": "Success"})
                print(f"Executed: {step} -> {instructions}")
            except Exception as e:
                results.append({"step": step, "status": f"Fail: {str(e)}"})
                print(f"Failed: {step} -> {str(e)}")
                break
                # Stop after the second iteration
            if step.find("PSA") != -1:
                print("Stopping execution after the second iteration.")
                break
    
    page.wait_for_timeout(2000)
    browser.close()



# Print results after browser is closed
for result in results:
    print(result)