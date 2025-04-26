# app/services/test_runner.py

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
    TestExecutionException,
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
    snapshot_after: str
    start_time: datetime
    end_time: datetime
    duration: float

@dataclass
class TestCaseResult:
    """Represents the result of a test case execution."""
    success: bool
    steps_results: List[StepExecutionResult]
    start_time: datetime
    end_time: datetime
    total_duration: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

class TestRunnerInterface(ABC):
    """Abstract interface for test runners."""

    @abstractmethod
    async def run_test_case(self, url: str, natural_language_steps: str) -> TestCaseResult:
        """Execute a complete test case from natural language description."""
        pass

class TestRunnerService(TestRunnerInterface):
    """Service for executing test cases from natural language."""

    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        ai_client_type: str = "abacus"
    ):
        self.browser_config = browser_config or BrowserConfig()
        # Remove step_parser dependency
        self.nl_to_gherkin = create_nl_to_gherkin_generator(ai_client_type)
        self.playwright_generator = create_playwright_generator(ai_client_type)
        self._browser_manager: Optional[BrowserManagerInterface] = None

    async def _initialize_browser(self) -> None:
        if not self._browser_manager:
            self._browser_manager = create_browser_manager(config=self.browser_config)
            await self._browser_manager.start()

    async def _cleanup_browser(self) -> None:
        try:
            if self._browser_manager:
                await self._browser_manager.stop()
                self._browser_manager = None
        except Exception as e:
            logger.error(f"Browser cleanup failed: {str(e)}")

    async def run_test_case(self, url: str, natural_language_steps: str) -> TestCaseResult:
        start_time = datetime.now()
        steps_results = []
        success = True
        error_message = None
        metadata = {"request_id": str(uuid.uuid4())}

        try:
            # 1. Generate structured Gherkin steps from NL
            logger.info("Generating structured Gherkin steps from natural language")
            gherkin_steps = await self.nl_to_gherkin.generate_steps(natural_language_steps)

            # 2. Initialize browser
            logger.info("Initializing browser for test execution")
            await self._initialize_browser()

            # 3. Navigate to initial URL
            logger.info(f"Navigating to URL: {url}")
            nav_result = await self._browser_manager.execute_step(
                f"goto('{url}', wait_until='networkidle')"
            )
            if not nav_result.success:
                raise TestExecutionException(f"Failed to navigate to URL: {nav_result.error_message}")

            # 4. Execute each step
            nl_steps_list = [s for s in natural_language_steps.split('\n') if s.strip()]
            for idx, step in enumerate(gherkin_steps):
                logger.info(f"Executing step {idx + 1}/{len(gherkin_steps)}: {step.gherkin}")
                step_result = await self._execute_single_step(
                    natural_language_step=nl_steps_list[idx] if idx < len(nl_steps_list) else "",
                    gherkin_step=step
                )
                steps_results.append(step_result)

                if not step_result.execution_result.success:
                    success = False
                    error_message = step_result.execution_result.error_message
                    break

        except StepGenerationException as e:
            success = False
            error_message = f"Step generation error: {str(e)}"
            logger.error(error_message)
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Test case execution failed: {error_message}", exc_info=True)
        finally:
            await self._cleanup_browser()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return TestCaseResult(
            success=success,
            steps_results=steps_results,
            start_time=start_time,
            end_time=end_time,
            total_duration=duration,
            error_message=error_message,
            metadata=metadata
        )

    async def _execute_single_step(
        self,
        natural_language_step: str,
        gherkin_step: GherkinStep
    ) -> StepExecutionResult:
        start_time = datetime.now()
        try:
            # Get current page snapshot
            snapshot_before = await self._browser_manager.get_page_content()

            # Convert snapshot to structured format for AI
            snapshot_json = html_to_json_visible(snapshot_before)

            # Generate Playwright instruction
            instruction = await self.playwright_generator.generate_instruction(
                json.dumps(snapshot_json, indent=2),
                gherkin_step.gherkin  # Use the Gherkin text from structured step
            )

            # Execute the instruction
            execution_result = await self._browser_manager.execute_step(instruction)

            # Get snapshot after execution
            snapshot_after = await self._browser_manager.get_page_content()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return StepExecutionResult(
                natural_language_step=natural_language_step,
                gherkin_step=gherkin_step,
                execution_result=execution_result,
                playwright_instruction=instruction,
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )
        except Exception as e:
            raise StepExecutionException(f"Step execution failed: {str(e)}")

def create_test_runner(
    browser_config: Optional[BrowserConfig] = None,
    ai_client_type: str = "abacus"
) -> TestRunnerInterface:
    return TestRunnerService(
        browser_config=browser_config,
        ai_client_type=ai_client_type
    )