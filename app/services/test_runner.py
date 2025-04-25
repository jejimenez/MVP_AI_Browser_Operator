from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json

from app.domain.step_parser import (
    StepParserFactory,
    SnapshotParserFactory,
    ParsedStep,
    StepType
)
from app.infrastructure.playwright_manager import (
    create_browser_manager,
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
        
        try:
            # Parse all steps first
            parsed_steps = self.step_parser.parse_steps(test_steps)
            
            # Create browser session
            async with create_browser_manager(
                browser_type="playwright",
                config=self.browser_config,
                start_url=url
            ) as browser:
                # Execute each step
                for step in parsed_steps:
                    step_result = await self._execute_single_step(browser, step)
                    steps_results.append(step_result)

                    if not step_result.execution_result.success:
                        raise StepExecutionException(
                            f"Step failed: {step_result.execution_result.error_message}"
                        )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return TestCaseResult(
                success=True,
                steps_results=steps_results,
                start_time=start_time,
                end_time=end_time,
                total_duration=duration,
                metadata={"url": url}
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Test execution failed: {str(e)}")
            return TestCaseResult(
                success=False,
                steps_results=steps_results,
                start_time=start_time,
                end_time=end_time,
                total_duration=duration,
                error_message=str(e),
                metadata={"url": url}
            )

    async def _execute_single_step(
        self,
        browser,
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

class TestRunnerFactory:
    """Factory for creating test runners."""

    @staticmethod
    def create_runner(
        runner_type: str = "default",
        **kwargs
    ) -> TestRunnerInterface:
        """Create test runner instance."""
        runners = {
            "default": TestRunnerService
        }

        if runner_type not in runners:
            raise ValueError(f"Unsupported runner type: {runner_type}")

        return runners[runner_type](**kwargs)