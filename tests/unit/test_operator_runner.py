# tests/unit/test_operator_runner.py
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import uuid
import json

from app.services.operator_runner import (
    OperatorRunnerService,
    StepExecutionResult,
    OperatorCaseResult
)
from app.infrastructure.ai_generators import GherkinStep
from app.infrastructure.playwright_manager import ExecutionResult
from app.domain.exceptions import (
    OperatorExecutionException,
    StepGenerationException,
    ValidationException
)
from app.infrastructure.interfaces import HTMLSummarizerInterface
from app.infrastructure.snapshot_storage import SnapshotStorage

# Test Data
SAMPLE_HTML = "<html><body><h1>Test Page</h1></body></html>"
SAMPLE_JSON = {"role": 'WebArea', 'name': '', 'children': [{'role': 'heading', 'name': 'Test Page', 'level': 1}]}
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
        screenshot_path=MOCK_SCREENSHOT_PATH,
        error_message=None
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
    generator.generate_instruction = AsyncMock(return_value=json.dumps({
        "high_precision": ["await page.click('#login-button');"],
        "low_precision": []
    }))
    return generator

@pytest.fixture
def mock_html_summarizer():
    summarizer = Mock(spec=HTMLSummarizerInterface)
    summarizer.summarize_html = Mock(return_value=SAMPLE_JSON)
    return summarizer

@pytest.fixture
def mock_snapshot_storage():
    storage = Mock(spec=SnapshotStorage)
    storage.save_snapshot = Mock()
    return storage

@pytest.fixture
async def test_runner(
    mock_browser_manager,
    mock_step_generator,
    mock_playwright_generator,
    mock_html_summarizer,
    mock_snapshot_storage
):
    """Fixture for test runner with mocked dependencies."""
    runner = None
    try:
        with patch('app.services.operator_runner.create_browser_manager', return_value=mock_browser_manager):
            runner = OperatorRunnerService(
                html_summarizer=mock_html_summarizer,
                snapshot_storage=mock_snapshot_storage
            )
            # Explicitly set mocked dependencies
            runner.nl_to_gherkin = mock_step_generator
            runner.playwright_generator = mock_playwright_generator
            runner._browser_manager = mock_browser_manager
            yield runner
    finally:
        if runner and hasattr(runner, '_browser_manager') and runner._browser_manager is not None:
            await runner._browser_manager.stop()

class TestOperatorRunner:
    @pytest.mark.asyncio
    async def test_successful_operator_execution(self, test_runner, mock_browser_manager, mock_html_summarizer, mock_snapshot_storage):
        """Test successful execution of a test case."""
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # goto
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=TEST_URL),  # url
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # wait_for_load_state
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # wait_for_load_state
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 1
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 2
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None)   # step 3
        ]

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )
        assert result.success
        assert len(result.steps_results) == 2  # Excludes skipped navigation step
        assert result.error_message is None
        assert isinstance(result.start_time, datetime)
        assert isinstance(result.end_time, datetime)
        assert result.total_duration > 0
        assert isinstance(result.metadata["request_id"], str)
        for step_result in result.steps_results:
            assert step_result.execution_result.screenshot_path == MOCK_SCREENSHOT_PATH
        mock_html_summarizer.summarize_html.assert_called()
        mock_snapshot_storage.save_snapshot.assert_called_with(SAMPLE_JSON)

    @pytest.mark.asyncio
    async def test_failed_operator_execution(self, test_runner, mock_browser_manager, mock_html_summarizer, mock_snapshot_storage):
        """Test handling of a failed step execution."""
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # goto
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=TEST_URL),  # url
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content (step 2)
            ExecutionResult(
                success=False,
                screenshot_path=MOCK_SCREENSHOT_PATH,
                error_message="Element not found"
            )  # step 2 action fails
        ]

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert result.success is False
        assert result.error_message == "Element not found"
        assert len(result.steps_results) == 2  # Stops after step 2 fails
        for step_result in result.steps_results:
            assert step_result.execution_result.screenshot_path == MOCK_SCREENSHOT_PATH
        assert mock_html_summarizer.summarize_html.call_count == 2
        assert mock_snapshot_storage.save_snapshot.call_count == 2

    @pytest.mark.asyncio
    async def test_step_generation_failure(self, test_runner, mock_step_generator, mock_browser_manager):
        """Test handling of step generation failure."""
        mock_step_generator.generate_steps.side_effect = StepGenerationException("AI error")
        test_runner._browser_manager = mock_browser_manager

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "Step generation error: Step generation failed: AI error" in result.error_message
        assert len(result.steps_results) == 0
        mock_step_generator.generate_steps.assert_called_once_with(TEST_NL_STEPS)
        mock_browser_manager.start.assert_not_called()
        mock_browser_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_initialization_failure(self, test_runner, mock_browser_manager):
        """Test handling of browser initialization failure."""
        mock_browser_manager.start.side_effect = Exception("Browser failed to start")

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "Browser failed to start" in result.error_message
        assert len(result.steps_results) == 0
        assert mock_browser_manager.stop.called

    @pytest.mark.asyncio
    async def test_step_execution_tracking(self, test_runner, mock_browser_manager, mock_html_summarizer, mock_snapshot_storage):
        """Test proper tracking of step execution results."""
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # goto
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=TEST_URL),  # url
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 1
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 2
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None)   # step 3
        ]

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert len(result.steps_results) == 2  # Excludes skipped navigation step
        for step_result in result.steps_results:
            assert isinstance(step_result, StepExecutionResult)
            assert step_result.playwright_instruction
            assert isinstance(step_result.start_time, datetime)
            assert isinstance(step_result.end_time, datetime)
            assert step_result.duration > 0
            assert step_result.execution_result.screenshot_path == MOCK_SCREENSHOT_PATH
        assert mock_html_summarizer.summarize_html.call_count == 2
        assert mock_snapshot_storage.save_snapshot.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_on_failure(self, test_runner, mock_browser_manager):
        """Test browser cleanup on test failure."""
        mock_browser_manager.execute_step.side_effect = Exception("Test error")

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "Failed to navigate" in result.error_message
        assert len(result.steps_results) == 0
        mock_browser_manager.stop.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_metadata_tracking(self, test_runner):
        """Test proper tracking of test metadata."""
        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert result.metadata
        assert "request_id" in result.metadata
        assert uuid.UUID(result.metadata["request_id"])

    @pytest.mark.asyncio
    async def test_playwright_instruction_generation(self, test_runner, mock_browser_manager, mock_playwright_generator):
        """Test generation of Playwright instructions."""
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # goto
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=TEST_URL),  # url
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content (step 1)
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 1 action
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content (step 2)
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 2 action
        ]
        mock_playwright_generator.generate_instruction.side_effect = [
            json.dumps({
                "high_precision": ["await page.fill('#username', 'admin');"],
                "low_precision": []
            }),  # input step
            json.dumps({
                "high_precision": ["await page.click('#login-button');"],
                "low_precision": []
            })   # click step
        ]

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert len(result.steps_results) == 2
        for idx, step_result in enumerate(result.steps_results):
            assert step_result.playwright_instruction
            if idx == 0:  # input step
                assert "await page.fill(" in step_result.playwright_instruction
            else:  # click step
                assert "await page.click(" in step_result.playwright_instruction
                
    @pytest.mark.asyncio
    async def test_browser_navigation(self, test_runner, mock_browser_manager):
        """Test initial browser navigation."""
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # goto
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=TEST_URL),  # url
        ]

        await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        mock_browser_manager.execute_step.assert_any_call(
            f"goto('{TEST_URL}', {{ wait_until: 'load', timeout: 30000 }})"
        )

    @pytest.mark.asyncio
    async def test_empty_steps_handling(self, test_runner, mock_step_generator):
        """Test handling of empty steps from generator."""
        mock_step_generator.generate_steps.return_value = []

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert not result.success
        assert "No steps were generated from the natural language input" in result.error_message
        assert len(result.steps_results) == 0
        mock_step_generator.generate_steps.assert_called_once_with(TEST_NL_STEPS)

    @pytest.mark.asyncio
    async def test_screenshot_path_tracking(self, test_runner, mock_browser_manager):
        """Test proper tracking of screenshot paths."""
        mock_browser_manager.execute_step.side_effect = [
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # goto
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=TEST_URL),  # url
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content (step 1)
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 1 action
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=SAMPLE_HTML),  # get_page_content (step 2)
            ExecutionResult(success=True, screenshot_path=MOCK_SCREENSHOT_PATH, result=None),  # step 2 action
        ]

        result = await test_runner.run_operator_case(
            url=TEST_URL,
            natural_language_steps=TEST_NL_STEPS
        )

        assert len(result.steps_results) == 2
        for step_result in result.steps_results:
            assert step_result.execution_result.screenshot_path == MOCK_SCREENSHOT_PATH
            assert step_result.execution_result.screenshot_path.startswith("screenshots/")
            assert step_result.execution_result.screenshot_path.endswith(".png")