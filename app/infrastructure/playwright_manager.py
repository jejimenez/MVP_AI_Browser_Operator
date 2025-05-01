# app/infrastructure/playwright_manager.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from app.domain.exceptions import SecurityException
from typing import Set, Pattern
import re

from playwright.async_api import async_playwright, Browser, Page, Playwright
import logging

from app.utils.logger import get_logger
from app.domain.exceptions import (
    BrowserException,
    NavigationException,
    ElementNotFoundException,
    ScreenshotException
)

logger = get_logger(__name__)

@dataclass
class BrowserConfig:
    """Configuration for browser session."""
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 30000  # milliseconds
    screenshot_dir: str = "screenshots"
    trace_dir: str = "traces"

@dataclass
class ExecutionResult:
    """Result of a step execution."""
    success: bool
    screenshot_path: Optional[str]
    error_message: Optional[str] = None
    page_url: Optional[str] = None
    execution_time: float = 0.0
    result: Any = None 

class BrowserManagerInterface(ABC):
    """Abstract interface for browser management."""

    @abstractmethod
    async def start(self) -> None:
        """Start browser session."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop browser session."""
        pass

    @abstractmethod
    async def execute_step(self, instruction: str) -> ExecutionResult:
        """Execute a single instruction."""
        pass

    @abstractmethod
    async def get_page_content(self) -> str:
        """Get current page DOM content."""
        pass

class PlaywrightManager(BrowserManagerInterface):
    """Manages Playwright browser sessions and interactions."""

    ALLOWED_ACTIONS: Set[Pattern] = {
        # Navigation
        re.compile(r"goto\(['\"](https?://[^'\"]+)['\"]"),

        # Click actions
        re.compile(r"click\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"dblclick\(['\"]([^'\"]+)['\"]\)"),
        # New locator().click() pattern
        re.compile(r"locator\(['\"](.+?)['\"]\)\.click\(\)"),

        # Form interactions
        re.compile(r"fill\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        re.compile(r"type\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        re.compile(r"press\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        re.compile(r"check\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"uncheck\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"select_option\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        # New locator().fill/type patterns
        re.compile(r"locator\(['\"](.+?)['\"]\)\.fill\(['\"](.+?)['\"]\)"),
        re.compile(r"locator\(['\"](.+?)['\"]\)\.type\(['\"](.+?)['\"]\)"),
        re.compile(
            r"locator\(['\"][^'\"]+['\"]\)"
            r"(?:\.filter\(\{[^\}]+\}\))?"
            r"(?:\.locator\(['\"][^'\"]+['\"]\))*"
            r"\.(click|fill|type|press)\((?:['\"][^'\"]*['\"](?:,\s*['\"][^'\"]*['\"])?)*\)"
        ),

        # Mouse interactions
        re.compile(r"hover\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"focus\(['\"]([^'\"]+)['\"]\)"),
        # New locator().hover/focus patterns
        re.compile(r"locator\(['\"]([^'\"]+)['\"]\)\.hover\(\)"),
        re.compile(r"locator\(['\"]([^'\"]+)['\"]\)\.focus\(\)"),

        # Wait actions
        re.compile(r"wait_for_selector\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"wait_for_load_state\(['\"](load|domcontentloaded|networkidle)['\"](?:\s*,\s*timeout=\d+)?\)"),
        # New locator().wait_for patterns
        re.compile(r"locator\(['\"]([^'\"]+)['\"]\)\.wait_for\(\)"),

        # Keyboard
        re.compile(r"keyboard\.press\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"keyboard\.type\(['\"]([^'\"]+)['\"]\)"),

        # Expect assertions (for verification)
        re.compile(r"expect\(page\.locator\(['\"]([^'\"]+)['\"]\)\)\.to_be_visible\(\)"),
        re.compile(r"expect\(page\.locator\(['\"]([^'\"]+)['\"]\)\)\.to_have_text\(['\"]([^'\"]+)['\"]\)"),
        # New locator() expect patterns
        re.compile(r"expect\(locator\(['\"]([^'\"]+)['\"]\)\)\.to_be_visible\(\)"),
        re.compile(r"expect\(locator\(['\"]([^'\"]+)['\"]\)\)\.to_have_text\(['\"]([^'\"]+)['\"]\)"),

        re.compile(r"url\(\)")
    }

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        start_url: Optional[str] = None
    ):
        """
        Initialize PlaywrightManager.

        Args:
            config (Optional[BrowserConfig]): Browser configuration
            start_url (Optional[str]): Initial URL to navigate to
        """
        self.config = config or BrowserConfig()
        self.start_url = start_url
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._setup_directories()

    def _setup_directories(self) -> None:
        """Create necessary directories for artifacts."""
        Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.trace_dir).mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """
        Start browser session.

        Raises:
            BrowserException: If browser fails to start
        """
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless
            )
            self._page = await self._browser.new_page()
            self._context = await self._browser.new_context(
                java_script_enabled=True,  # Explicitly enable JavaScript
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                #viewport={"width": 1280, "height": 720},
                locale="en-US",
                timezone_id="America/New_York",
                ignore_https_errors=True  # Optional for SSL issues
            )
            await self._configure_page()

            if self.start_url:
                await self.navigate_to(self.start_url)
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            await self.stop()
            raise BrowserException(f"Browser startup failed: {str(e)}")

    async def _configure_page(self) -> None:
        """Configure page settings."""
        if self._page:
            await self._page.set_viewport_size({
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            })
            self._page.set_default_timeout(self.config.timeout)

    async def stop(self) -> None:
        """Clean up browser resources."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error during browser cleanup: {str(e)}")
        finally:
            self._browser = None
            self._playwright = None
            self._page = None

    async def navigate_to(self, url: str) -> None:
        """
        Navigate to specified URL.

        Args:
            url (str): URL to navigate to

        Raises:
            NavigationException: If navigation fails
        """
        if not self._page:
            raise BrowserException("Browser not initialized")

        try:
            await self._page.goto(url, wait_until="networkidle")
        except Exception as e:
            raise NavigationException(f"Navigation failed: {str(e)}")


    def _is_instruction_allowed(self, instruction: str) -> bool:
        """
        Check if the instruction matches any allowed pattern.

        Args:
            instruction (str): The Playwright instruction to check

        Returns:
            bool: True if instruction is allowed, False otherwise
        """
        # Remove common prefixes
        clean_instruction = instruction.replace('await ', '').replace('page.', '')

        # Check against allowed patterns
        return any(
            pattern.match(clean_instruction) is not None
            for pattern in self.ALLOWED_ACTIONS
        )
    
    async def execute_step(self, instruction: str) -> ExecutionResult:
        """
        Execute a Playwright instruction and capture the result.

        Args:
            instruction (str): Playwright instruction to execute

        Returns:
            ExecutionResult: Result of execution including screenshot

        Raises:
            BrowserException: If browser is not initialized
            ElementNotFoundException: If required element is not found
            SecurityException: If instruction is not allowed
        """
        if not self._page:
            raise BrowserException("Browser not initialized")

        start_time = datetime.now()
        screenshot_path = None
        result_value = None  # Add this to store return values

        try:
            # Clean up instruction
            clean_instruction = instruction.replace('await ', '').replace('page.', '')
            logger.debug(f"Executing instruction: {clean_instruction}")

            # Check if instruction is allowed
            if not self._is_instruction_allowed(clean_instruction):
                raise SecurityException(f"Instruction not allowed: {clean_instruction}")

            # Special handling for navigation
            if "goto" in clean_instruction:
                url = clean_instruction.split("'")[1]
                await self._page.goto(url, wait_until='networkidle', timeout=30000)

                # Additional waiting for page readiness
                try:
                    # Wait for network to be really idle
                    await self._page.wait_for_load_state('networkidle', timeout=5000)
                    # Wait for DOM content
                    await self._page.wait_for_load_state('domcontentloaded')

                    # Site-specific waiting
                    if "google.com" in url:
                        await self._page.wait_for_selector('input[name="q"]', timeout=10000)

                    # Verify page loaded correctly
                    current_url = self._page.url
                    if not current_url or "about:blank" in current_url:
                        raise ElementNotFoundException("Page did not load properly")

                except Exception as wait_error:
                    logger.warning(f"Additional waiting failed: {str(wait_error)}")

            # Handle instructions that return values
            elif clean_instruction == "url()":
                result_value = self._page.url

            else:
                # Execute non-navigation instructions
                exec_locals = {
                    "page": self._page,
                    "expect": self._page.expect_event,
                    "keyboard": self._page.keyboard
                }

                # Execute with proper context
                result_value = await eval(f"page.{clean_instruction}", {"page": self._page})

                # For certain actions, wait for network idle
                if any(action in clean_instruction for action in ['click', 'type', 'press', 'fill']):
                    try:
                        await self._page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception as wait_error:
                        logger.debug(f"Post-action waiting skipped: {str(wait_error)}")

            # Take screenshot after execution
            screenshot_path = await self._take_screenshot()

            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                success=True,
                screenshot_path=screenshot_path,
                page_url=self._page.url,
                execution_time=execution_time,
                result=result_value  # Add the result to the return value
            )

        except SecurityException as e:
            logger.error(f"Security violation: {str(e)}")
            return ExecutionResult(
                success=False,
                screenshot_path=None,
                error_message=str(e),
                page_url=self._page.url if self._page else None,
                execution_time=(datetime.now() - start_time).total_seconds(),
                result=None
            )

        except Exception as e:
            logger.error(f"Step execution failed: {str(e)}")
            try:
                # Take screenshot of failure state
                screenshot_path = await self._take_screenshot("error")
            except Exception as screenshot_error:
                logger.error(f"Failed to take error screenshot: {str(screenshot_error)}")

            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                success=False,
                screenshot_path=screenshot_path,
                error_message=str(e),
                page_url=self._page.url if self._page else None,
                execution_time=execution_time,
                result=None
            )

    async def _take_screenshot(self, prefix: str = "step") -> Optional[str]:
        """
        Take a screenshot of the current page state.

        Args:
            prefix (str): Prefix for screenshot filename

        Returns:
            Optional[str]: Path to screenshot file

        Raises:
            ScreenshotException: If screenshot fails
        """
        if not self._page:
            raise BrowserException("Browser not initialized")

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{prefix}_{timestamp}.png"
            filepath = str(Path(self.config.screenshot_dir) / filename)

            await self._page.screenshot(path=filepath, full_page=True)
            return filepath
        except Exception as e:
            logger.error(f"Screenshot failed: {str(e)}")
            raise ScreenshotException(f"Failed to take screenshot: {str(e)}")

    async def get_page_content(self) -> str:
        """
        Get current page DOM content.

        Returns:
            str: Page DOM content

        Raises:
            BrowserException: If browser is not initialized
        """
        if not self._page:
            raise BrowserException("Browser not initialized")

        try:
            return await self._page.content()
        except Exception as e:
            raise BrowserException(f"Failed to get page content: {str(e)}")
    """
    async def get_page_snapshot(self) -> str:
        try:
            if not self.page:
                logger.warning("No active page found when trying to get page snapshot")
                return ""

            # Get the full HTML content
            full_html = await self.page.content()

            # Get summarized version using HTMLSummarizer
            logger.debug("Generating summarized HTML snapshot")
            summarized_html = html_to_json_visible(full_html)

            logger.debug(f"Generated HTML snapshot: {summarized_html[:2000]}...")  # Log first 200 chars
            return summarized_html

        except Exception as e:
            logger.error(f"Error getting page snapshot: {str(e)}")
            return ""
    """
    async def __aenter__(self) -> 'PlaywrightManager':
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


# Factory function for creating browser managers
def create_browser_manager(
    browser_type: str = "playwright",
    config: Optional[BrowserConfig] = None,
    start_url: Optional[str] = None
) -> BrowserManagerInterface:
    """
    Factory function to create browser managers.

    Args:
        browser_type (str): Type of browser manager to create
        config (Optional[BrowserConfig]): Browser configuration
        start_url (Optional[str]): Initial URL to navigate to

    Returns:
        BrowserManagerInterface: Initialized browser manager

    Raises:
        ValueError: If browser_type is not supported
    """
    managers = {
        "playwright": PlaywrightManager
    }

    if browser_type not in managers:
        raise ValueError(f"Unsupported browser manager type: {browser_type}")

    return managers[browser_type](config=config, start_url=start_url)