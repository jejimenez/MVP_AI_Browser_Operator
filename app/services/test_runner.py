# app/services/test_runner.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json
import uuid

from app.domain.step_parser import (
    StepParserFactory,
    SnapshotParserFactory,
    ParsedStep,
    StepType
)
from app.infrastructure.playwright_manager import (
    create_browser_manager,
    BrowserManagerInterface,
    BrowserConfig,
    ExecutionResult
)
from app.infrastructure.ai_client import (
    create_ai_client,
    AIResponse
)
from app.utils.logger import get_logger
from app.domain.exceptions import (
    TestExecutionException,
    StepExecutionException
)

logger = get_logger(__name__)

@dataclass
class StepExecutionResult:
    """Represents the result of a single step execution."""
    step: ParsedStep
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
    async def run_test_case(self, url: str, test_steps: str) -> TestCaseResult:
        """Execute a complete test case."""
        pass

    @abstractmethod
    async def validate_test_case(self, test_steps: str) -> bool:
        """Validate test case steps before execution."""
        pass

class TestRunnerService(TestRunnerInterface):
    """Service for executing test cases."""

    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        step_parser_type: str = "gherkin",
        snapshot_parser_type: str = "html",
        ai_client_type: str = "abacus"
    ):
        """Initialize TestRunnerService with necessary configurations."""
        self.browser_config = browser_config or BrowserConfig()
        self.step_parser = StepParserFactory.create_parser(step_parser_type)
        self.snapshot_parser = SnapshotParserFactory.create_parser(snapshot_parser_type)
        self.ai_client = create_ai_client(ai_client_type)
        self._browser_manager: Optional[BrowserManagerInterface] = None

    async def _initialize_browser(self) -> None:
        """Initialize browser manager if not already initialized."""
        if not self._browser_manager:
            self._browser_manager = create_browser_manager(config=self.browser_config)
            await self._browser_manager.start()

    async def _cleanup_browser(self) -> None:
        """Cleanup browser resources."""
        try:
            if self._browser_manager:
                await self._browser_manager.stop()
                self._browser_manager = None
        except Exception as e:
            logger.error(f"Browser cleanup failed: {str(e)}")

    async def run_test_case(self, url: str, test_steps: str) -> TestCaseResult:
        """
        Execute a complete test case.

        Args:
            url (str): Starting URL for the test
            test_steps (str): Test steps in natural language or Gherkin

        Returns:
            TestCaseResult: Complete test execution results

        Raises:
            TestExecutionException: If test execution fails
        """
        start_time = datetime.now()
        steps_results = []
        success = True
        error_message = None
        metadata = {"request_id": str(uuid.uuid4())}

        try:
            # Parse steps
            parsed_steps = self.step_parser.parse_steps(test_steps)
            if not parsed_steps:
                raise ValueError("No valid steps found in test case")

            # Initialize browser
            logger.info("Initializing browser for test execution")
            await self._initialize_browser()

            # Navigate to initial URL
            nav_result = await self._browser_manager.execute_step(
                f"goto('{url}', wait_until='networkidle')"
            )
            if not nav_result.success:
                raise Exception(f"Failed to navigate to URL: {nav_result.error_message}")

            # Execute each step
            for step in parsed_steps:
                step_result = await self._execute_single_step(self._browser_manager, step)
                steps_results.append(step_result)

                if not step_result.execution_result.success:
                    success = False
                    error_message = step_result.execution_result.error_message
                    break

        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Test case execution failed: {error_message}", exc_info=True)

        finally:
            # Cleanup
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
        browser: BrowserManagerInterface,
        step: ParsedStep
    ) -> StepExecutionResult:
        """Execute a single test step."""
        start_time = datetime.now()

        try:
            # Get current page snapshot
            snapshot_before = await browser.get_page_content()

            # Get Playwright instruction from AI or cache
            instruction = await self._get_playwright_instruction(
                snapshot_before,
                step
            )

            # Execute the instruction
            execution_result = await browser.execute_step(instruction)

            # Get snapshot after execution
            snapshot_after = await browser.get_page_content()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return StepExecutionResult(
                step=step,
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

    async def _get_playwright_instruction(
        self,
        snapshot: str,
        step: ParsedStep
    ) -> str:
        """
        Get Playwright instruction for step execution.
        This could be extended to include caching/DB lookup.
        """
        try:
            # Here you could add cache/DB lookup before calling AI
            ai_response = await self.ai_client.generate_playwright_instruction(
                snapshot,
                step.original_text
            )

            # Try high precision first, fall back to low precision
            instructions = (
                ai_response.high_precision or
                ai_response.low_precision
            )

            if not instructions:
                raise StepExecutionException(
                    "No valid Playwright instructions generated"
                )

            return instructions[0]  # Return first valid instruction

        except Exception as e:
            raise StepExecutionException(
                f"Failed to generate Playwright instruction: {str(e)}"
            )

    async def validate_test_case(self, test_steps: str) -> bool:
        """
        Validate test case steps before execution.

        Args:
            test_steps (str): Test steps to validate

        Returns:
            bool: True if valid, False otherwise
        """
        try:
            logger.info(f"Validating test steps: {test_steps}")
            parsed_steps = self.step_parser.parse_steps(test_steps)
            valid = len(parsed_steps) > 0
            logger.info(f"Validation result: {valid}. Found {len(parsed_steps)} valid steps.")
            return valid
        except Exception as e:
            logger.error(f"Test case validation failed: {str(e)}")
            return False

def create_test_runner(
    browser_config: Optional[BrowserConfig] = None,
    step_parser_type: str = "gherkin",
    snapshot_parser_type: str = "html",
    ai_client_type: str = "abacus"
) -> TestRunnerInterface:
    """Create test runner instance."""
    return TestRunnerService(
        browser_config=browser_config,
        step_parser_type=step_parser_type,
        snapshot_parser_type=snapshot_parser_type,
        ai_client_type=ai_client_type
    )