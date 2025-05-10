# app/infrastructure/playwright_manager.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import inspect
from pathlib import Path
from app.domain.exceptions import SecurityException
from typing import Set, Pattern
import re

from playwright.async_api import async_playwright, Browser, Page, Playwright, expect  # Add expect
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
    timeout: int = 5000  # milliseconds
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
        re.compile(r"locator\(['\"](.+?)['\"]\)\.click\(\)"),
        re.compile(r"locator\(['\"](.+?)['\"]\)\.first\(\)\.click\(\)"),
        re.compile(r"get_by_label\(['\"](.+?)['\"]\)\.first\.click\(\)"),  # Ensured correct pattern
        re.compile(r"get_by_label\(['\"](.+?)['\"]\)\.first\(\)\.click\(\)"),  # Ensured correct pattern
        re.compile(r"get_by_role\(['\"](button)['\"],\s*\{\s*name:\s*['\"](.+?)['\"]\s*\}\)\.click\(\)"),  # Ensured correct pattern
        
        # Form interactions
        re.compile(r"fill\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        re.compile(r"type\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        re.compile(r"press\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
        re.compile(r"check\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"uncheck\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"select_option\(['\"]([^'\"]+)['\"], ['\"]([^'\"]+)['\"]\)"),
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
        re.compile(r"locator\(['\"]([^'\"]+)['\"]\)\.hover\(\)"),
        re.compile(r"locator\(['\"]([^'\"]+)['\"]\)\.focus\(\)"),
        # Wait actions
        re.compile(r"wait_for_selector\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"wait_for_selector\(['\"](.*?)(?<!\\)['\"],\s*state=['\"](visible|hidden|attached|detached)['\"]\)"),
        re.compile(r"wait_for_load_state\(['\"](load|domcontentloaded|networkidle)['\"](?:\s*,\s*timeout=\d+)?\)"),
        re.compile(r"locator\(['\"]([^'\"]+)['\"]\)\.wait_for\(\)"),
        # Keyboard
        re.compile(r"keyboard\.press\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"keyboard\.type\(['\"]([^'\"]+)['\"]\)"),
        # Expect assertions
        re.compile(r"expect\(page\.locator\(['\"]([^'\"]+)['\"]\)\)\.to_be_visible\(\)"),
        re.compile(r"expect\(page\.locator\(['\"]([^'\"]+)['\"]\)\)\.to_have_text\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"expect\(locator\(['\"]([^'\"]+)['\"]\)\)\.to_be_visible\(\)"),
        re.compile(r"expect\(locator\(['\"]([^'\"]+)['\"]\)\)\.to_have_text\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"expect\(locator\(['\"]([^'\"]+)['\"]\)\)\.to_have_value\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"expect\(locator\(\\'\[role=\"[^\"]+\"\]\\'\)\)\.to_be_visible\(\)"),
        re.compile(r"url\(\)")
    }

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        start_url: Optional[str] = None
    ):
        self.config = config or BrowserConfig()
        self.start_url = start_url
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._context = None  # Initialize _context
        self._setup_directories()

    def _setup_directories(self) -> None:
        Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.trace_dir).mkdir(parents=True, exist_ok=True)

    @property
    def page(self) -> Optional[Page]:
        logger.debug("Accessing page property for debugging")
        if self._page is None:
            logger.warning("Page is None; browser may not be initialized")
        return self._page
    
    async def start(self) -> None:
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless
            )
            self._context = await self._browser.new_context(
                java_script_enabled=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                ignore_https_errors=True
            )
            self._page = await self._context.new_page()
            await self._configure_page()

            if self.start_url:
                await self.navigate_to(self.start_url)
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            await self.stop()
            raise BrowserException(f"Browser startup failed: {str(e)}")

    async def _configure_page(self) -> None:
        if self._page:
            await self._page.set_viewport_size({
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            })
            self._page.set_default_timeout(self.config.timeout)

    async def stop(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error during browser cleanup: {str(e)}")
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None

    async def navigate_to(self, url: str) -> None:
        if not self._page:
            raise BrowserException("Browser not initialized")
        try:
            await self._page.goto(url, wait_until="networkidle")
        except Exception as e:
            raise NavigationException(f"Navigation failed: {str(e)}")

    def _is_instruction_allowed(self, instruction: str) -> bool:
        #clean_instruction = instruction.replace('await ', '').replace('page.', '')
        #return any(pattern.match(clean_instruction) for pattern in self.ALLOWED_ACTIONS)
        return True

    async def execute_step(self, instruction: str) -> ExecutionResult:
        if not self._page:
            raise BrowserException("Browser not initialized")

        start_time = datetime.now()
        screenshot_path = None
        result_value = None

        try:
            # Check if instruction is allowed
            if not self._is_instruction_allowed(instruction):
                raise SecurityException(f"Instruction not allowed: {instruction}")

            logger.debug(f"Executing instruction: {instruction}")

            # Normalize instruction: replace selectOption with select_option
            instruction = instruction.replace("selectOption", "select_option")

            # Handle goto with options
            if instruction.startswith("goto("):
                # Match goto('url', { options }) or goto('url')
                match = re.match(r"goto\(['\"](https?://[^'\"]+)['\"](?:,\s*\{([^}]+)\})?\)", instruction)
                if match:
                    url = match.group(1)
                    options_str = match.group(2) or ""
                    options = {}
                    if options_str:
                        # Parse options (e.g., wait_until: 'load', timeout: 5000)
                        # Handle both quoted values and numbers
                        pairs = re.findall(r"(\w+):\s*(?:['\"]([^'\"]+)['\"]|(\d+))", options_str)
                        for key, quoted_value, numeric_value in pairs:
                            value = quoted_value if quoted_value else numeric_value
                            options[key] = value if key != 'timeout' else int(value)
                        logger.debug(f"Parsed goto options: {options}")
                    await self._page.goto(url, **options)
                    # Additional waits as in original
                    try:
                        await self._page.wait_for_load_state('networkidle', timeout=5000)
                        await self._page.wait_for_load_state('domcontentloaded')
                        if "google.com" in url:
                            await self._page.wait_for_selector('input[name="q"]', timeout=10000)
                        current_url = self._page.url
                        if not current_url or "about:blank" in current_url:
                            raise ElementNotFoundException("Page did not load properly")
                    except Exception as wait_error:
                        logger.warning(f"Additional waiting failed: {str(wait_error)}")
                    result_value = None
                else:
                    raise ValueError(f"Invalid goto instruction: {instruction}")

            # Create execution context for other instructions
            else:
                exec_globals = {
                    "page": self._page,
                    "expect": expect,
                    "keyboard": self._page.keyboard,
                    "locator": self._page.locator,
                    "get_by_role": self._page.get_by_role,
                    "get_by_label": self._page.get_by_label,
                    "goto": self._page.goto,
                    "url": self._page.url,
                    "__builtins__": {},  # Restrict builtins for safety
                }

                # Handle await
                if instruction.startswith("await "):
                    instruction = instruction[6:]  # Remove "await "

                # Execute instruction
                code = compile(instruction, "<string>", "eval")
                result = eval(code, exec_globals)

                # Handle awaitable results
                if inspect.isawaitable(result):
                    result_value = await result
                else:
                    result_value = result

                # Post-action wait for interactive actions
                if any(action in instruction for action in ['click', 'fill', 'select_option', 'press']):
                    try:
                        await self._page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception as wait_error:
                        logger.debug(f"Post-action waiting skipped: {str(wait_error)}")

            # Take screenshot
            screenshot_path = await self._take_screenshot()

            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                success=True,
                screenshot_path=screenshot_path,
                page_url=self._page.url,
                execution_time=execution_time,
                result=result_value
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
        if not self._page:
            raise BrowserException("Browser not initialized")
        try:
            return await self._page.content()
        except Exception as e:
            raise BrowserException(f"Failed to get page content: {str(e)}")

    async def __aenter__(self) -> 'PlaywrightManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

def create_browser_manager(
    browser_type: str = "playwright",
    config: Optional[BrowserConfig] = None,
    start_url: Optional[str] = None
) -> BrowserManagerInterface:
    managers = {
        "playwright": PlaywrightManager
    }
    if browser_type not in managers:
        raise ValueError(f"Unsupported browser manager type: {browser_type}")
    return managers[browser_type](config=config, start_url=start_url)