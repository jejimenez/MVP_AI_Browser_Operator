from playwright.sync_api import sync_playwright

def rgb_to_hex(rgb_str):
    """Convert 'rgb(r, g, b)' string to hex color (e.g., '#721c24')."""
    if not rgb_str or "rgb" not in rgb_str:
        return None
    rgb = [int(x) for x in rgb_str.replace("rgb(", "").replace(")", "").split(",")]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".lower()

def execute_test(steps, url="https://automationintesting.online/"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)  # Visible browser
        page = browser.new_page()
        page.goto(url)
        results = []
        
        for step in steps:
            action = step["action"]
            element = step["element"]
            text = step["text"]
            condition = step["condition"]
            
            if action == "click" and text:
                try:
                    if element == "button":
                        page.click(f'button:text("{text}")')
                    else:
                        page.click(f'text="{text}"')
                    screenshot = page.screenshot(path=f"step_{len(results)}.png")
                    results.append({"action": "click", "image": f"step_{len(results)}.png"})
                except Exception as e:
                    results.append({"action": "click", "image": None, "status": f"Fail: {str(e)}"})
            
            elif action == "check" and text:
                try:
                    # Use contains-text selector (partial match)
                    locator = page.locator(f'text=/{text}/i')  # Case-insensitive partial match
                    is_visible = locator.count() > 0
                    
                    actual_text = None
                    color_rgb = None
                    color_hex = None
                    if is_visible:
                        actual_text = locator.first.inner_text()
                        color_rgb = page.eval_on_selector(
                            f'text=/{text}/i',
                            "el => window.getComputedStyle(el).color"
                        )
                        color_hex = rgb_to_hex(color_rgb)  # Convert to hex
                    
                    screenshot = page.screenshot(path=f"step_{len(results)}.png")
                    # Success if text is found and color matches #721c24
                    success = (
                        is_visible and 
                        text.lower() in actual_text.lower() and
                        (condition is None or color_hex == condition["color"])
                    )
                    results.append({
                        "action": "check",
                        "image": f"step_{len(results)}.png",
                        "status": "Success" if success else "Fail",
                        "details": f"Expected: '{text}', Found: '{actual_text}', Color: {color_hex} (RGB: {color_rgb})"
                    })
                except Exception as e:
                    results.append({"action": "check", "image": None, "status": f"Fail: {str(e)}"})
        
        page.wait_for_timeout(2000)  # Pause to observe
        browser.close()
        return results
""""
# Example usage
test_case = "Click in the button with the text 'Book this room'. Then click in Book. Chek if the message 'size must be between' appears in red"
from parceTestCase import parse_test_case
parsed = parse_test_case(test_case)
results = execute_test(parsed, url="http://localhost:8000")
for result in results:
    print(result)
"""