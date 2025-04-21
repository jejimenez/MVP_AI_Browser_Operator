from playwright.sync_api import sync_playwright

def login(page, username, password, otp_secret, url="http://your-app.com/login"):
    """
    Log in to the application using username, password, and OTP.
    
    Args:
        page: Playwright page object.
        username (str): Login username.
        password (str): Login password.
        otp_secret (str): Base32-encoded OTP secret.
        url (str): Login page URL.
    """
    try:
        page.goto(url)
        page.fill("input[name='username']", username)  # Adjust selector
        page.fill("input[name='password']", password)  # Adjust selector
        page.click("button[type='submit']")  # Adjust selector
        
        # Wait for OTP field (assumes 2FA page appears after initial login)
        page.wait_for_selector("input[name='otp']", timeout=10000)  # Adjust selector
        otp = generate_otp(otp_secret)
        if not otp:
            raise Exception("OTP generation failed")
        
        page.fill("input[name='otp']", otp)  # Adjust selector
        page.click("button[type='submit']")  # Adjust selector
        
        # Wait for successful login (e.g., dashboard or redirect)
        page.wait_for_url("**/dashboard**", timeout=10000)  # Adjust URL pattern
        print("Login successful")
    except Exception as e:
        print(f"Login failed: {e}")
        raise