import pytest
from bs4 import BeautifulSoup
import os
from playwright.async_api import async_playwright, Page
import json

@pytest.fixture
def index_html():
    """Load and parse the index.html file."""
    with open('app/index.html', 'r') as f:
        return BeautifulSoup(f.read(), 'html.parser')

@pytest.fixture
async def browser_page():
    """Create a browser page for testing."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        yield page
        await browser.close()

class TestIndexHTML:
    def test_html_structure(self, index_html):
        """Test the basic HTML structure of index.html."""
        # Test title
        assert index_html.title.text == "AI Browser Operator - Web Test Automation"
        
        # Test main elements
        assert index_html.find('h1', class_='text-4xl')
        assert index_html.find('form', id='apiForm')
        assert index_html.find('div', id='logContainer')
        
        # Test form elements
        form = index_html.find('form', id='apiForm')
        assert form.find('select', id='aiClientSelect')
        assert form.find('input', id='url')
        assert form.find('textarea', id='instructions')
        assert form.find('button', type='submit')

    def test_css_styles(self, index_html):
        """Test that required CSS styles are present."""
        style = index_html.find('style')
        assert style is not None
        
        # Check for key CSS classes
        css_content = style.string
        assert '.test-results' in css_content
        assert '.step-container' in css_content
        assert '.screenshot-image' in css_content

    @pytest.mark.asyncio
    async def test_form_submission(self, browser_page: Page):
        """Test the form submission functionality."""
        # Load the page
        await browser_page.goto('http://localhost:8000')
        
        # Fill the form
        await browser_page.select_option('#aiClientSelect', 'grok')
        await browser_page.fill('#url', 'https://example.com')
        await browser_page.fill('#instructions', 'Navigate to homepage')
        
        # Mock the API response
        await browser_page.route('/api/operator/execute', lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                "request_id": "test-123",
                "tenant_id": "test_tenant",
                "execution_time": "2024-01-01T00:00:00",
                "success": True,
                "steps_results": [
                    {
                        "step": "Navigate to homepage",
                        "success": True,
                        "screenshot_url": "test.png",
                        "duration": 1.5,
                        "error": None
                    }
                ],
                "total_duration": 1.5,
                "error_message": None
            })
        ))
        
        # Submit the form
        await browser_page.click('button[type="submit"]')
        
        # Wait for the log entry to appear
        await browser_page.wait_for_selector('.log-entry')
        
        # Check the log content
        log_entry = await browser_page.text_content('.log-entry')
        assert "Test Case Execution" in log_entry
        assert "Navigate to homepage" in log_entry

    @pytest.mark.asyncio
    async def test_error_handling(self, browser_page: Page):
        """Test error handling for invalid URL."""
        # Load the page
        await browser_page.goto('http://localhost:8000')
        
        # Fill the form with invalid URL
        await browser_page.select_option('#aiClientSelect', 'grok')
        await browser_page.fill('#url', 'example.com')  # Missing http/https
        await browser_page.fill('#instructions', 'Navigate to homepage')
        
        # Mock the API response with 422 error
        await browser_page.route('/api/operator/execute', lambda route: route.fulfill(
            status=422,
            content_type='application/json',
            body=json.dumps({
                "detail": "Invalid URL format"
            })
        ))
        
        # Submit the form
        await browser_page.click('button[type="submit"]')
        
        # Wait for the error message
        await browser_page.wait_for_selector('.log-entry')
        
        # Check the error message
        log_entry = await browser_page.text_content('.log-entry')
        assert "The URL must start with" in log_entry
        assert "http://" in log_entry or "https://" in log_entry

    @pytest.mark.asyncio
    async def test_screenshot_display(self, browser_page: Page):
        """Test that screenshots are properly displayed."""
        # Load the page
        await browser_page.goto('http://localhost:8000')
        
        # Fill the form
        await browser_page.select_option('#aiClientSelect', 'grok')
        await browser_page.fill('#url', 'https://example.com')
        await browser_page.fill('#instructions', 'Navigate to homepage')
        
        # Mock the API response with screenshot
        await browser_page.route('/api/operator/execute', lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                "request_id": "test-123",
                "tenant_id": "test_tenant",
                "execution_time": "2024-01-01T00:00:00",
                "success": True,
                "steps_results": [
                    {
                        "step": "Navigate to homepage",
                        "success": True,
                        "screenshot_url": "test.png",
                        "duration": 1.5,
                        "error": None
                    }
                ],
                "total_duration": 1.5,
                "error_message": None
            })
        ))
        
        # Mock the screenshot response
        await browser_page.route('/screenshots/test.png', lambda route: route.fulfill(
            status=200,
            content_type='image/png',
            body=b''  # Empty image for testing
        ))
        
        # Submit the form
        await browser_page.click('button[type="submit"]')
        
        # Wait for the screenshot to appear
        await browser_page.wait_for_selector('.screenshot-image')
        
        # Check that the screenshot is displayed
        screenshot = await browser_page.query_selector('.screenshot-image')
        assert screenshot is not None
        assert await screenshot.get_attribute('src') == '/screenshots/test.png' 