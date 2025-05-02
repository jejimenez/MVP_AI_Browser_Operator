# app/services/operator_runner.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json
import uuid
import os
import asyncio
from app.infrastructure.html_summarizer import HTMLSummarizer
from playwright.async_api import TimeoutError as PlaywrightTimeoutError  # New import

from app.infrastructure.playwright_manager import (
    create_browser_manager,
    BrowserManagerInterface,
    BrowserConfig,
    ExecutionResult
)
from app.infrastructure.ai_generators import (
    create_nl_to_gherkin_generator,
    create_playwright_generator,
    GherkinStep
)
from app.infrastructure.interfaces import HTMLSummarizerInterface
from app.infrastructure.snapshot_storage import SnapshotStorage
from app.utils.logger import get_logger
from dotenv import load_dotenv
from app.domain.exceptions import (
    OperatorExecutionException,
    StepExecutionException,
    StepGenerationException,
    ValidationException
)

logger = get_logger(__name__)
load_dotenv()

@dataclass
class StepExecutionResult:
    """Represents the result of a single step execution."""
    natural_language_step: str
    gherkin_step: GherkinStep  # Changed to use GherkinStep
    execution_result: ExecutionResult
    playwright_instruction: str
    snapshot_json: str
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
    async def run_operator_case(
        self,
        url: str,
        natural_language_steps: List[str],
        headless: Optional[bool] = None  # Optional headless parameter
    ) -> OperatorCaseResult:
        """Run a test case with natural language steps."""
        pass

class OperatorRunnerService(OperatorRunnerInterface):
    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        ai_client_type: str = "abacus",
        html_summarizer: Optional[HTMLSummarizerInterface] = None,
        snapshot_storage: Optional[SnapshotStorage] = None
    ):
        self.browser_config = browser_config or BrowserConfig()
        self.nl_to_gherkin = create_nl_to_gherkin_generator(ai_client_type)
        self.playwright_generator = create_playwright_generator(ai_client_type)
        self.html_summarizer = html_summarizer or HTMLSummarizer()
        self.snapshot_storage = snapshot_storage or SnapshotStorage()
        self._browser_manager: Optional[BrowserManagerInterface] = None
        self._browser_initialized = False

    async def _initialize_browser(self, headless: Optional[bool] = None) -> None:
        if not self._browser_initialized:
            try:
                # Override browser_config.headless if headless is provided
                effective_config = self.browser_config
                if headless is not None:
                    effective_config = BrowserConfig(
                        headless=headless,
                        viewport_width=self.browser_config.viewport_width,
                        viewport_height=self.browser_config.viewport_height,
                        timeout=self.browser_config.timeout,
                        screenshot_dir=self.browser_config.screenshot_dir,
                        trace_dir=self.browser_config.trace_dir
                    )
                
                logger.debug("Creating browser manager")
                self._browser_manager = create_browser_manager(config=effective_config)
                logger.debug("Starting browser")
                await self._browser_manager.start()
                self._browser_initialized = True
                logger.info(f"Browser initialized in {'headless' if effective_config.headless else 'headed'} mode")
            except Exception as e:
                self._browser_initialized = False
                logger.error(f"Browser initialization failed: {str(e)}")
                raise OperatorExecutionException(f"Failed to initialize browser: {str(e)}")
            
    async def _cleanup_browser(self) -> None:
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

    async def _ensure_browser_ready(self, headless: Optional[bool] = None) -> None:
        if not self._browser_initialized or self._browser_manager is None:
            await self._initialize_browser(headless=headless)

    async def run_operator_case(self, url: str, natural_language_steps: str, headless: Optional[bool] = None) -> OperatorCaseResult:
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
            await self._ensure_browser_ready(headless=headless)

            # 3. Navigate to initial URL with enhanced retry logic
            logger.info(f"Navigating to URL: {url}")
            max_retries = 3
            navigation_success = False

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Navigation attempt {attempt + 1}/{max_retries}")
                    # Use 'load' instead of 'networkidle' for more reliable navigation

                    nav_result = await self._browser_manager.execute_step(
                        f"goto('{url}', {{ wait_until: 'load', timeout: {self.browser_config.timeout} }})"
                    )
                    await self._browser_manager.execute_step(
                        f"page.wait_for_load_state('networkidle', timeout={self.browser_config.timeout})"
                    ) 

                    if not nav_result.success:
                        logger.warning(f"Navigation command failed: {nav_result.error_message}")
                        raise OperatorExecutionException("Navigation command failed")

                    """
                    # Verify current URL
                    url_result = await self._browser_manager.execute_step("url()")
                    current_url = url_result.result

                    if not current_url:
                        logger.warning("Current URL is empty")
                        continue

                    if "about:blank" in current_url:
                        logger.warning("Page stuck at about:blank")
                        continue

                    if url not in current_url:
                        logger.warning(f"Expected URL not found. Expected: {url}, Got: {current_url}")
                        continue
                    """   

                    # Wait for page readiness
                    try:
                        #await self._wait_for_page_ready()
                        navigation_success = True
                        logger.info(f"Successfully navigated to {url}")
                        break
                    except PlaywrightTimeoutError as wait_error:
                        logger.warning(f"Page readiness check failed: {str(wait_error)}")
                        continue
                except Exception as e:
                    logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)  # Increased delay for stability
                    continue
                    
            if not navigation_success:
                raise OperatorExecutionException(
                    f"Failed to navigate to {url} after {max_retries} attempts"
                )

            # 4. Execute steps
            nl_steps_list = [s.strip() for s in natural_language_steps.split('\n') if s.strip()]
            for idx, step in enumerate(gherkin_steps):
                logger.info(f"Executing step {idx + 1}/{len(gherkin_steps)}: {step.gherkin}")
                if idx == 0 and step.action == "navigate" and "am on" in step.gherkin.lower():
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
        try:
            # Wait for page load
            await self._browser_manager.execute_step(
                f"wait_for_load_state('load', timeout={self.browser_config.timeout})"
            )
            # Wait for DOM content
            await self._browser_manager.execute_step(
                f"wait_for_load_state('domcontentloaded', timeout={self.browser_config.timeout})"
            )
        except PlaywrightTimeoutError as e:
            logger.warning(f"Page ready wait failed: {str(e)}")
            raise

    async def _execute_single_step(
        self,
        natural_language_step: str,
        gherkin_step: GherkinStep
    ) -> StepExecutionResult:
        start_time = datetime.now()
        snapshot_json = None
        execution_result = None
        executed_instruction = None

        try:
            # Get current page snapshot
            snapshot_before = await self._browser_manager.get_page_content()
            if not snapshot_before:
                raise StepExecutionException("Empty page snapshot received")
            snapshot_json = self.html_summarizer.summarize_html(snapshot_before)

            # Save snapshot
            try:
                self.snapshot_storage.save_snapshot(snapshot_json)
                logger.debug("Training data saved via SnapshotStorage")
            except IOError as e:
                logger.warning(f"Failed to save snapshot: {str(e)}")

            #logger.debug(f"snapshot_json > {snapshot_json}")

            try:
                # Generate Playwright instruction JSON
                instruction_json = await self.playwright_generator.generate_instruction(
                    json.dumps(snapshot_json, indent=2),
                    gherkin_step.gherkin
                )

                # Parse and try instructions
                try:
                    instruction_data = json.loads(instruction_json)
                    last_error = None

                    for instruction in instruction_data.get("high_precision", []):
                        logger.debug(f"Trying high precision instruction > {instruction}")
                        execution_result = await self._browser_manager.execute_step(instruction)
                        if not execution_result.success:
                            logger.debug(f"High precision instruction failed: {execution_result.error_message}")
                            end_time = datetime.now()
                            duration = (end_time - start_time).total_seconds()
                            return StepExecutionResult(
                                natural_language_step=natural_language_step,
                                gherkin_step=gherkin_step,
                                execution_result=execution_result,
                                playwright_instruction=instruction,
                                snapshot_json=snapshot_json,
                                start_time=start_time,
                                end_time=end_time,
                                duration=duration
                            )
                        executed_instruction = instruction
                        logger.debug(f"Successfully executed instruction > {instruction}")
                        break

                    if not executed_instruction:
                        for instruction in instruction_data.get("low_precision", []):
                            logger.debug(f"Trying low precision instruction > {instruction}")
                            execution_result = await self._browser_manager.execute_step(instruction)
                            if not execution_result.success:
                                logger.debug(f"Low precision instruction failed: {execution_result.error_message}")
                                end_time = datetime.now()
                                duration = (end_time - start_time).total_seconds()
                                return StepExecutionResult(
                                    natural_language_step=natural_language_step,
                                    gherkin_step=gherkin_step,
                                    execution_result=execution_result,
                                    playwright_instruction=instruction,
                                    snapshot_json=snapshot_json,
                                    start_time=start_time,
                                    end_time=end_time,
                                    duration=duration
                                )
                            executed_instruction = instruction
                            logger.debug(f"Successfully executed instruction > {instruction}")
                            break

                    if not executed_instruction:
                        raise StepExecutionException(
                            f"No valid instructions executed. Last error: {last_error or 'Unknown error'}"
                        )

                except json.JSONDecodeError as e:
                    raise StepGenerationException(f"Invalid JSON response: {str(e)}")
                except Exception as e:
                    raise StepExecutionException(f"Failed to execute instructions: {str(e)}")

            except StepGenerationException as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                execution_result = ExecutionResult(
                    success=False,
                    screenshot_path=None,
                    error_message=f"Step generation/execution failed: {str(e)}",
                    page_url=self._browser_manager._page.url if self._browser_manager._page else None,
                    execution_time=duration
                )
                return StepExecutionResult(
                    natural_language_step=natural_language_step,
                    gherkin_step=gherkin_step,
                    execution_result=execution_result,
                    playwright_instruction=None,
                    snapshot_json=snapshot_json,
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
                playwright_instruction=executed_instruction,
                snapshot_json=snapshot_json,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )

        except Exception as e:
            logger.error(f"Step execution failed: {str(e)}", exc_info=True)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            execution_result = ExecutionResult(
                success=False,
                screenshot_path=None,
                error_message=str(e),
                page_url=self._browser_manager._page.url if self._browser_manager._page else None,
                execution_time=duration
            )
            return StepExecutionResult(
                natural_language_step=natural_language_step,
                gherkin_step=gherkin_step,
                execution_result=execution_result,
                playwright_instruction=executed_instruction,
                snapshot_json=snapshot_json,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )
        
class OperatorRunnerFactory:
    @staticmethod
    def create_runner(
        browser_config: Optional[BrowserConfig] = None,
        ai_client_type: Optional[str] = None,
        headless: bool = True,
        html_summarizer: Optional[HTMLSummarizerInterface] = None,
        snapshot_storage: Optional[SnapshotStorage] = None,
        **kwargs
    ) -> OperatorRunnerInterface:
        if browser_config is None:
            browser_config = BrowserConfig(
                headless=headless,
                viewport_width=kwargs.get('viewport_width', 1920),
                viewport_height=kwargs.get('viewport_height', 1080),
                timeout=kwargs.get('timeout', 30000),
                screenshot_dir=kwargs.get('screenshot_dir', 'screenshots'),
                trace_dir=kwargs.get('trace_dir', 'traces')
            )
        ai_client_type = ai_client_type or os.getenv("AI_CLIENT_TYPE", "abacus")
        from app.infrastructure.html_summarizer import HTMLSummarizer
        html_summarizer = html_summarizer or HTMLSummarizer()
        snapshot_storage = snapshot_storage or SnapshotStorage()
        return OperatorRunnerService(
            browser_config=browser_config,
            ai_client_type=ai_client_type,
            html_summarizer=html_summarizer,
            snapshot_storage=snapshot_storage
        )

    @staticmethod
    def create_debug_runner(
        ai_client_type: Optional[str] = None,
        **kwargs
    ) -> OperatorRunnerInterface:
        browser_config = BrowserConfig(
            headless=False,
            viewport_width=kwargs.get('viewport_width', 1280),
            viewport_height=kwargs.get('viewport_height', 530),
            timeout=kwargs.get('timeout', 30000),  # Increased timeout
            screenshot_dir='debug_screenshots',
            trace_dir='debug_traces',
            **kwargs
        )
        ai_client_type = ai_client_type or os.getenv("AI_CLIENT_TYPE", "abacus")
        from app.infrastructure.html_summarizer import HTMLSummarizer
        snapshot_storage = SnapshotStorage()
        return OperatorRunnerService(
            browser_config=browser_config,
            ai_client_type=ai_client_type,
            html_summarizer=HTMLSummarizer(),
            snapshot_storage=snapshot_storage
        )

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
        # ai_client_type is picked up from env variable
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
        # ai_client_type is picked up from env variable
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
        # ai_client_type is picked up from env variable
        return OperatorRunnerService(browser_config=browser_config)

def create_operator_runner(
    browser_config: Optional[BrowserConfig] = None,
    ai_client_type: Optional[str] = None
) -> OperatorRunnerInterface:
    ai_client_type = ai_client_type or os.getenv("AI_CLIENT_TYPE", "abacus")
    if browser_config is None:
        browser_config = BrowserConfig(headless=False)  # Default to headed mode
    return OperatorRunnerService(
        browser_config=browser_config,
        ai_client_type=ai_client_type
    )