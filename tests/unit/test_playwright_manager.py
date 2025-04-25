# tests/unit/test_playwright_manager.py

import pytest
from app.infrastructure.playwright_manager import (
    create_browser_manager,
    BrowserConfig,
    ExecutionResult,
    BrowserException
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

@pytest.mark.asyncio
async def test_browser_manager_start():
    """Test browser manager startup."""
    config = BrowserConfig(
        headless=True,
        viewport_width=1280,
        viewport_height=720,
        timeout=30000
    )

    browser_manager = create_browser_manager(config=config)

    try:
        await browser_manager.start()
        assert browser_manager._browser is not None
        assert browser_manager._page is not None
    finally:
        await browser_manager.stop()

@pytest.mark.asyncio
async def test_browser_navigation():
    """Test browser navigation with step execution."""
    browser_manager = create_browser_manager()

    try:
        await browser_manager.start()
        result = await browser_manager.execute_step(
            "goto('https://example.com', wait_until='networkidle')"
        )
        assert result.success
        assert result.screenshot_path is not None

        content = await browser_manager.get_page_content()
        assert "Example Domain" in content
    finally:
        await browser_manager.stop()

@pytest.mark.asyncio
async def test_browser_interaction():
    """Test browser interactions."""
    browser_manager = create_browser_manager()

    try:
        await browser_manager.start()
        # Navigate to page
        await browser_manager.execute_step(
            "goto('https://example.com', wait_until='networkidle')"
        )

        # Test click
        result = await browser_manager.execute_step(
            "click('a')"
        )
        assert result.success
        assert result.screenshot_path is not None

    finally:
        await browser_manager.stop()

@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager functionality."""
    async with create_browser_manager() as browser_manager:
        result = await browser_manager.execute_step(
            "goto('https://example.com', wait_until='networkidle')"
        )
        assert result.success
        assert result.screenshot_path is not None

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in browser manager."""
    browser_manager = create_browser_manager()

    with pytest.raises(BrowserException):
        # Should raise exception when trying to execute step without starting
        await browser_manager.execute_step("click('button')")

    await browser_manager.start()
    try:
        # Should return failed result for invalid selector
        result = await browser_manager.execute_step(
            "click('#non-existent-element')"
        )
        assert not result.success
        assert result.error_message is not None
        assert result.screenshot_path is not None
    finally:
        await browser_manager.stop()

@pytest.mark.asyncio
async def test_screenshot_functionality():
    """Test screenshot functionality."""
    browser_manager = create_browser_manager()

    try:
        await browser_manager.start()
        result = await browser_manager.execute_step(
            "goto('https://example.com', wait_until='networkidle')"
        )
        
        assert result.success
        assert result.screenshot_path is not None
        assert result.screenshot_path.endswith('.png')
        assert result.execution_time > 0
    finally:
        await browser_manager.stop()