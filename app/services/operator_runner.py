# app/services/operator_runner.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json
import uuid

from app.infrastructure.playwright_manager import (
    create_browser_manager,
    BrowserManagerInterface,
    BrowserConfig,
    ExecutionResult
)
from app.infrastructure.ai_generators import (
    create_nl_to_gherkin_generator,
    create_playwright_generator,
    GherkinStep  # New dataclass from ai_generators.py
)
from app.utils.logger import get_logger
from app.domain.exceptions import (
    OperatorExecutionException,
    StepExecutionException,
    StepGenerationException,
    ValidationException
)
from app.utils.html_summarizer import html_to_json_visible

logger = get_logger(__name__)

@dataclass
class StepExecutionResult:
    """Represents the result of a single step execution."""
    natural_language_step: str
    gherkin_step: GherkinStep  # Changed to use GherkinStep
    execution_result: ExecutionResult
    playwright_instruction: str
    snapshot_before: str
    start_time: datetime
    end_time: datetime
    duration: float

@dataclass
class OperatorCaseResult:
    """Represents the result of a test case execution."""
    success: bool
    steps_results: List[StepExecutionResult]
    start_time: datetime
    end_time: datetime
    total_duration: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

class OperatorRunnerInterface(ABC):
    """Abstract interface for test runners."""

    @abstractmethod
    async def run_operator_case(self, url: str, natural_language_steps: str) -> OperatorCaseResult:
        """Execute a complete test case from natural language description."""
        pass

class OperatorRunnerService(OperatorRunnerInterface):
    """Service for executing test cases from natural language."""

    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        ai_client_type: str = "abacus"
    ):
        self.browser_config = browser_config or BrowserConfig()
        self.nl_to_gherkin = create_nl_to_gherkin_generator(ai_client_type)
        self.playwright_generator = create_playwright_generator(ai_client_type)
        self._browser_manager: Optional[BrowserManagerInterface] = None
        self._browser_initialized = False

    async def _initialize_browser(self) -> None:
        """Initialize browser with error handling."""
        if not self._browser_initialized:
            try:
                logger.debug("Creating browser manager")
                self._browser_manager = create_browser_manager(config=self.browser_config)
                logger.debug("Starting browser")
                await self._browser_manager.start()
                self._browser_initialized = True
                logger.info("Browser initialized successfully")
            except Exception as e:
                self._browser_manager = None
                self._browser_initialized = False
                logger.error(f"Browser initialization failed: {str(e)}")
                raise OperatorExecutionException(f"Failed to initialize browser: {str(e)}")

    async def _cleanup_browser(self) -> None:
        """Safely cleanup browser resources."""
        if self._browser_manager is not None:
            try:
                logger.debug("Stopping browser")
                await self._browser_manager.stop()
            except Exception as e:
                logger.error(f"Browser cleanup failed: {str(e)}")
            finally:
                self._browser_manager = None
                self._browser_initialized = False
                logger.debug("Browser cleanup completed")

    async def _ensure_browser_ready(self) -> None:
        """Ensure browser is initialized and ready."""
        if not self._browser_initialized or self._browser_manager is None:
            await self._initialize_browser()

    async def run_operator_case(self, url: str, natural_language_steps: str) -> OperatorCaseResult:
        """Execute a complete test case with enhanced error handling."""
        start_time = datetime.now()
        steps_results = []
        success = True
        error_message = None
        metadata = {"request_id": str(uuid.uuid4())}

        try:
            # 1. Generate structured Gherkin steps
            logger.info("Generating structured Gherkin steps from natural language")
            try:
                gherkin_steps = await self.nl_to_gherkin.generate_steps(natural_language_steps)
                if not gherkin_steps:
                    raise ValidationException("No steps were generated from the natural language input")
            except Exception as e:
                raise StepGenerationException(f"Step generation failed: {str(e)}")

            # 2. Initialize browser and navigate
            await self._ensure_browser_ready()

            # 3. Navigate to initial URL with enhanced retry logic
            logger.info(f"Navigating to URL: {url}")
            max_retries = 3
            navigation_success = False

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Navigation attempt {attempt + 1}/{max_retries}")

                    # Attempt navigation
                    nav_result = await self._browser_manager.execute_step(
                        f"goto('{url}', wait_until='networkidle')"
                    )

                    if not nav_result.success:
                        raise OperatorExecutionException("Navigation command failed")

                    # Verify current URL
                    url_result = await self._browser_manager.execute_step("url()")
                    current_url = url_result.result

                    # URL verification with detailed logging
                    if not current_url:
                        logger.warning("Current URL is empty")
                        continue

                    if "about:blank" in current_url:
                        logger.warning("Page stuck at about:blank")
                        continue

                    if url not in current_url:
                        logger.warning(f"Expected URL not found. Expected: {url}, Got: {current_url}")
                        continue

                    # Additional waiting for page readiness
                    try:
                        await self._wait_for_page_ready()
                        navigation_success = True
                        logger.info(f"Successfully navigated to {current_url}")
                        break
                    except Exception as wait_error:
                        logger.warning(f"Page readiness check failed: {str(wait_error)}")
                        continue

                except Exception as e:
                    logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                    continue

            # Check if navigation was successful
            if not navigation_success:
                raise OperatorExecutionException(
                    f"Failed to navigate to {url} after {max_retries} attempts"
                )

            # 4. Execute steps
            nl_steps_list = [s.strip() for s in natural_language_steps.split('\n') if s.strip()]
            for idx, step in enumerate(gherkin_steps):
                logger.info(f"Executing step {idx + 1}/{len(gherkin_steps)}: {step.gherkin}")
                if idx == 0 and step.action == "navigate" and "am on" in step.gherkin.lower():
                    # Skip first step if it's just asserting the initial state
                    logger.debug("Skipping first navigation step as it's asserting initial state")
                    continue
                try:
                    step_result = await self._execute_single_step(
                        natural_language_step=nl_steps_list[idx] if idx < len(nl_steps_list) else "",
                        gherkin_step=step
                    )
                    steps_results.append(step_result)

                    if not step_result.execution_result.success:
                        success = False
                        error_message = step_result.execution_result.error_message
                        break
                except StepExecutionException as e:
                    success = False
                    error_message = str(e)
                    break

        except StepGenerationException as e:
            success = False
            error_message = f"Step generation error: {str(e)}"
            logger.error(error_message)
        except OperatorExecutionException as e:
            success = False
            error_message = str(e)
            logger.error(error_message)
        except Exception as e:
            success = False
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Test case execution failed: {error_message}", exc_info=True)
        finally:
            await self._cleanup_browser()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return OperatorCaseResult(
            success=success,
            steps_results=steps_results,
            start_time=start_time,
            end_time=end_time,
            total_duration=duration,
            error_message=error_message,
            metadata=metadata
        )
    
    async def _wait_for_page_ready(self) -> None:
        """Wait for page to be fully loaded and rendered."""
        try:
            # Wait for network to be idle
            await self._browser_manager.execute_step("wait_for_load_state('networkidle')")

            # Wait for no network requests for 500ms
            await self._browser_manager.execute_step("wait_for_load_state('networkidle', timeout=500)")

            # Wait for DOM to be ready
            await self._browser_manager.execute_step("wait_for_load_state('domcontentloaded')")
        except Exception as e:
                logger.warning(f"Page ready wait failed: {str(e)}")

    async def _execute_single_step(
        self,
        natural_language_step: str,
        gherkin_step: GherkinStep
    ) -> StepExecutionResult:
        start_time = datetime.now()
        try:
            # Get current page snapshot
            snapshot_before = await self._browser_manager.get_page_content()
            snapshot_json = html_to_json_visible(snapshot_before)

            #logger.debug(f"snapshot_before > {snapshot_before}")
            logger.debug(f"snapshot_json > {snapshot_json}")

            try:
                # Generate Playwright instruction JSON
                instruction_json = await self.playwright_generator.generate_instruction(
                    json.dumps(snapshot_json, indent=2),
                    gherkin_step.gherkin
                )

                # Parse and try instructions
                try:
                    instruction_data = json.loads(instruction_json)
                    
                    # Try each instruction in order until one succeeds
                    last_error = None
                    executed_instruction = None
                    
                    # Try high precision instructions first
                    for instruction in instruction_data.get("high_precision", []):
                        try:
                            logger.debug(f"Trying high precision instruction > {instruction}")
                            execution_result = await self._browser_manager.execute_step(instruction)
                            if execution_result.success:
                                executed_instruction = instruction
                                break
                        except Exception as e:
                            last_error = e
                            logger.debug(f"High precision instruction failed: {str(e)}")
                            continue

                    # If no high precision instruction succeeded, try low precision
                    if not executed_instruction:
                        for instruction in instruction_data.get("low_precision", []):
                            try:
                                logger.debug(f"Trying low precision instruction > {instruction}")
                                execution_result = await self._browser_manager.execute_step(instruction)
                                if execution_result.success:
                                    executed_instruction = instruction
                                    break
                            except Exception as e:
                                last_error = e
                                logger.debug(f"Low precision instruction failed: {str(e)}")
                                continue

                    if not executed_instruction:
                        raise StepGenerationException(
                            f"All instructions failed. Last error: {str(last_error)}"
                        )

                    logger.debug(f"Successfully executed instruction > {executed_instruction}")

                except json.JSONDecodeError as e:
                    raise StepGenerationException(f"Invalid JSON response: {str(e)}")
                except Exception as e:
                    raise StepGenerationException(f"Failed to execute instructions: {str(e)}")

            except StepGenerationException as e:
                # Create a failed execution result for generation failure
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                return StepExecutionResult(
                    natural_language_step=natural_language_step,
                    gherkin_step=gherkin_step,
                    execution_result=ExecutionResult(
                        success=False,
                        error_message=f"Step generation/execution failed: {str(e)}",
                        screenshot_path=None,
                        page_url=self._browser_manager._page.url if self._browser_manager._page else None,
                        execution_time=duration
                    ),
                    playwright_instruction=instruction_json,  # Store the raw JSON for debugging
                    snapshot_before=snapshot_before,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration
                )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return StepExecutionResult(
                natural_language_step=natural_language_step,
                gherkin_step=gherkin_step,
                execution_result=execution_result,
                playwright_instruction=executed_instruction,  # Store the successful instruction
                snapshot_before=snapshot_before,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )

        except Exception as e:
            logger.error(f"Step execution failed: {str(e)}", exc_info=True)
            raise StepExecutionException(f"Step execution failed: {str(e)}")

class OperatorRunnerFactory:
    """Factory for creating operator runners with different configurations."""

    @staticmethod
    def create_runner(
        browser_config: Optional[BrowserConfig] = None,
        ai_client_type: str = "abacus",
        headless: bool = True,
        **kwargs
    ) -> OperatorRunnerInterface:
        """
        Create an operator runner with the specified configuration.

        Args:
            browser_config: Optional browser configuration
            ai_client_type: Type of AI client to use ("abacus" by default)
            headless: Whether to run browser in headless mode
            **kwargs: Additional configuration options

        Returns:
            OperatorRunnerInterface: Configured operator runner
        """
        if browser_config is None:
            browser_config = BrowserConfig(
                headless=headless,
                viewport_width=kwargs.get('viewport_width', 1920),
                viewport_height=kwargs.get('viewport_height', 1080),
                timeout=kwargs.get('timeout', 30000),
                screenshot_dir=kwargs.get('screenshot_dir', 'screenshots'),
                trace_dir=kwargs.get('trace_dir', 'traces')
            )

        return OperatorRunnerService(
            browser_config=browser_config,
            ai_client_type=ai_client_type
        )

    @staticmethod
    def create_debug_runner(**kwargs) -> OperatorRunnerInterface:
        """
        Create a runner configured for debugging (non-headless, longer timeouts).
        """
        browser_config = BrowserConfig(
            headless=False,
            viewport_width=kwargs.get('viewport_width', 1280),
            viewport_height=kwargs.get('viewport_height', 530),
            timeout=60000,  # Longer timeout for debugging
            screenshot_dir='debug_screenshots',
            trace_dir='debug_traces',
            **kwargs
        )
        return OperatorRunnerService(browser_config=browser_config)

    @staticmethod
    def create_test_runner(**kwargs) -> OperatorRunnerInterface:
        """
        Create a runner configured for testing (headless, shorter timeouts).
        """
        browser_config = BrowserConfig(
            headless=True,
            timeout=15000,  # Shorter timeout for tests
            screenshot_dir='test_screenshots',
            trace_dir='test_traces',
            **kwargs
        )
        return OperatorRunnerService(browser_config=browser_config)
    
    @staticmethod
    def create_production_runner(**kwargs) -> OperatorRunnerInterface:
        """Create a runner configured for production use."""
        browser_config = BrowserConfig(
            headless=True,
            timeout=45000,  # Longer timeout for production
            screenshot_dir='production_screenshots',
            trace_dir='production_traces',
            **kwargs
        )
        return OperatorRunnerService(browser_config=browser_config)

    @staticmethod
    def create_mobile_runner(**kwargs) -> OperatorRunnerInterface:
        """Create a runner configured for mobile viewport."""
        browser_config = BrowserConfig(
            headless=True,
            viewport_width=375,
            viewport_height=812,  # iPhone X dimensions
            **kwargs
        )
        return OperatorRunnerService(browser_config=browser_config)

def create_operator_runner(
    browser_config: Optional[BrowserConfig] = None,
    ai_client_type: str = "abacus"
) -> OperatorRunnerInterface:
    return OperatorRunnerService(
        browser_config=browser_config,
        ai_client_type=ai_client_type
    )