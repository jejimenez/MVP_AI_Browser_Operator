# app/infrastructure/playwright_manager.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass
import asyncio
import base64
from datetime import datetime
import os
from pathlib import Path

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
        """
        if not self._page:
            raise BrowserException("Browser not initialized")

        start_time = datetime.now()
        try:
            # Execute the instruction
            exec_locals = {
                "page": self._page,
                "expect": self._page.expect_event
            }
            await eval(f"page.{instruction}", {"page": self._page})

            # Take screenshot after execution
            screenshot_path = await self._take_screenshot()

            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                success=True,
                screenshot_path=screenshot_path,
                page_url=self._page.url,
                execution_time=execution_time
            )

        except Exception as e:
            logger.error(f"Step execution failed: {str(e)}")
            # Take screenshot of failure state
            screenshot_path = await self._take_screenshot("error")

            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                success=False,
                screenshot_path=screenshot_path,
                error_message=str(e),
                page_url=self._page.url if self._page else None,
                execution_time=execution_time
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