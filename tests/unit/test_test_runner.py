# tests/unit/test_test_runner.py

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import uuid

from app.services.test_runner import (
    TestRunnerService,
    StepExecutionResult,
    TestCaseResult
)
from app.infrastructure.ai_generators import GherkinStep
from app.infrastructure.playwright_manager import ExecutionResult
from app.domain.exceptions import (
    TestExecutionException,
    StepGenerationException,
    ValidationException
)

# Test Data# Test Data
SAMPLE_HTML = "<html><body><h1>Test Page</h1></body></html>"
TEST_URL = "https://example.com"
TEST_NL_STEPS = "Log in as admin"
MOCK_SCREENSHOT_PATH = "screenshots/test.png"

@pytest.fixture
def mock_browser_manager():
    manager = Mock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.execute_step = AsyncMock(return_value=ExecutionResult(
        success=True,
        error_message=None,
        screenshot_path=MOCK_SCREENSHOT_PATH
    ))
    manager.get_page_content = AsyncMock(return_value=SAMPLE_HTML)
    return manager

@pytest.fixture
def mock_step_generator():
    generator = Mock()
    generator.generate_steps = AsyncMock(return_value=[
        GherkinStep(
            gherkin="Given I am on the login page",
            action="navigate",
            target="login page"
        ),
        GherkinStep(
            gherkin="When I enter 'admin' into the username field",
            action="input",
            target="username field",
            value="admin"
        ),
        GherkinStep(
            gherkin="And I click the login button",
            action="click",
            target="login button"
        )
    ])
    return generator

@pytest.fixture
def mock_playwright_generator():
    generator = Mock()
    generator.generate_instruction = AsyncMock(return_value="await page.click('#login-button');")
    return generator

@pytest.fixture
async def test_runner(
    mock_browser_manager,
    mock_step_generator,
    mock_playwright_generator
):
    with patch('app.services.test_runner.create_browser_manager', return_value=mock_browser_manager):
        runner = TestRunnerService()
        runner.step_generator = mock_step_generator
        runner.playwright_generator = mock_playwright_generator
        runner._browser_manager = mock_browser_manager
        yield runner

class TestTestRunner:
    @pytest.mark.asyncio
    async def test_successful_test_execution(self, test_runner, mock_browser_manager):
        """Test successful execution of a test case."""
        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert result.success
        assert len(result.steps_results) == 5
        assert result.error_message is None
        assert isinstance(result.start_time, datetime)
        assert isinstance(result.end_time, datetime)
        assert result.total_duration > 0
        assert isinstance(result.metadata["request_id"], str)
        # Add screenshot path assertion
        for step_result in result.steps_results:
            assert step_result.screenshot_path == MOCK_SCREENSHOT_PATH

    @pytest.mark.asyncio
    async def test_failed_test_execution(self, test_runner, mock_browser_manager):
        """Test handling of a failed step execution."""
        # Setup mock to fail on second step
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, error_message=None, screenshot_path=MOCK_SCREENSHOT_PATH),
            ExecutionResult(success=True, error_message=None, screenshot_path=MOCK_SCREENSHOT_PATH),
            ExecutionResult(
                success=False,
                error_message="Element not found",
                screenshot_path=MOCK_SCREENSHOT_PATH
            )
        ]

        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "Element not found" in result.error_message
        assert len(result.steps_results) == 2  # Should stop after failed step
        for step_result in result.steps_results:
            assert step_result.screenshot_path == MOCK_SCREENSHOT_PATH
    

    @pytest.mark.asyncio
    async def test_step_generation_failure(self, test_runner, mock_step_generator):
        """Test handling of step generation failure."""
        mock_step_generator.generate_steps.side_effect = StepGenerationException("AI error")

        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "AI error" in result.error_message
        assert len(result.steps_results) == 0

    @pytest.mark.asyncio
    async def test_browser_initialization_failure(self, test_runner, mock_browser_manager):
        """Test handling of browser initialization failure."""
        mock_browser_manager.start.side_effect = Exception("Browser failed to start")

        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "Browser failed to start" in result.error_message
        assert len(result.steps_results) == 0

    @pytest.mark.asyncio
    async def test_step_execution_tracking(self, test_runner, mock_browser_manager):
        """Test proper tracking of step execution results."""
        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert len(result.steps_results) == 3
        for step_result in result.steps_results:
            assert isinstance(step_result, StepExecutionResult)
            assert step_result.snapshot_before == SAMPLE_HTML
            assert step_result.playwright_instruction
            assert isinstance(step_result.start_time, datetime)
            assert isinstance(step_result.end_time, datetime)
            assert step_result.duration > 0
            assert step_result.screenshot_path == MOCK_SCREENSHOT_PATH

    @pytest.mark.asyncio
    async def test_cleanup_on_failure(self, test_runner, mock_browser_manager):
        """Test browser cleanup on test failure."""
        # Update the error case to include screenshot path
        mock_browser_manager.execute_step.side_effect = Exception("Test error")

        await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        mock_browser_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_metadata_tracking(self, test_runner):
        """Test proper tracking of test metadata."""
        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert result.metadata
        assert "request_id" in result.metadata
        assert uuid.UUID(result.metadata["request_id"])  # Verify it's a valid UUID

    @pytest.mark.asyncio
    async def test_playwright_instruction_generation(self, test_runner, mock_playwright_generator):
        """Test generation of Playwright instructions."""
        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert len(result.steps_results) == 3
        for step_result in result.steps_results:
            assert step_result.playwright_instruction.startswith("await ")
            assert step_result.playwright_instruction.endswith(";")

    @pytest.mark.asyncio
    async def test_browser_navigation(self, test_runner, mock_browser_manager):
        """Test initial browser navigation."""
        # Update execute_step mock to include screenshot path
        mock_browser_manager.execute_step.return_value = ExecutionResult(
            success=True,
            error_message=None,
            screenshot_path=MOCK_SCREENSHOT_PATH
        )

        await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        # Verify initial navigation
        mock_browser_manager.execute_step.assert_any_call(
            f"goto('{TEST_URL}', wait_until='networkidle')"
        )

    @pytest.mark.asyncio
    async def test_empty_steps_handling(self, test_runner, mock_step_generator):
        """Test handling of empty steps from generator."""
        mock_step_generator.generate_steps.return_value = []

        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "No steps generated" in result.error_message
        assert len(result.steps_results) == 0

    @pytest.mark.asyncio
    async def test_screenshot_path_tracking(self, test_runner, mock_browser_manager):
        """Test proper tracking of screenshot paths."""
        result = await test_runner.run_test_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert len(result.steps_results) == 3
        for step_result in result.steps_results:
            assert step_result.screenshot_path == MOCK_SCREENSHOT_PATH
            assert step_result.screenshot_path.startswith("screenshots/")
            assert step_result.screenshot_path.endswith(".png")