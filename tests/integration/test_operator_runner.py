# tests/integration/test_operator_runner.py

import pytest
from unittest.mock import patch
from app.services.operator_runner import OperatorRunnerFactory
from app.domain.exceptions import OperatorExecutionException, AIClientException, StepGenerationException
from app.infrastructure.ai_client import AIResponse
from app.infrastructure.ai_generators import GherkinStep
from datetime import datetime, UTC

class TestOperatorRunnerIntegration:
    @pytest.fixture
    async def runner(self):
        # You can pass custom config here if needed
        return OperatorRunnerFactory.create_debug_runner()

    @pytest.fixture
    def mock_gherkin_response(self):
        return AIResponse(
            content="""
            [
            {
                "gherkin": "Given I am on the homepage",
                "action": "navigate",
                "target": "homepage",
                "value": null
            },
            {
                "gherkin": "When I click the login button",
                "action": "click",
                "target": "login button",
                "value": null
            },
            {
                "gherkin": "And I enter \"test@example.com\" into the email field",
                "action": "input",
                "target": "email field",
                "value": "test@example.com"
            },
            {
                "gherkin": "And I click Submit",
                "action": "click",
                "target": "Submit",
                "value": null
            }
            ]
            """,
            metadata={
                "model": "claude-3-sonnet",
                "raw_response": {}
            }
        )

    @pytest.mark.asyncio
    async def test_successful_operator_execution(self, runner, sample_test_case):
        result = await runner.run_operator_case(
            url="https://dev-psa.dev.ninjarmm.com",
            natural_language_steps=sample_test_case
        )

        assert result.success
        assert len(result.steps_results) > 0
        assert result.total_duration > 0

    @pytest.mark.asyncio
    async def test_playwright_instruction_generation_and_execution(self, runner):
        """
        Test the complete workflow starting from predefined Gherkin steps,
        letting the AI generate the Playwright instructions and executing them.
        """
        # Prepare predefined Gherkin steps (bypassing first AI call)
        predefined_steps = [
            GherkinStep(
                gherkin="Given I am on the login page",
                action="navigate",
                target="login page"
            ),
            GherkinStep(
                gherkin="When I enter my email into the email field",
                action="input",
                target="email field",
                value="test@example.com"
            ),
            GherkinStep(
                gherkin="And I enter my password into the password field",
                action="input",
                target="password field",
                value="password123"
            ),
            GherkinStep(
                gherkin="Then I click the sign in button",
                action="click",
                target="sign in button"
            )
        ]

        # Mock only the Gherkin generation part
        with patch('app.infrastructure.ai_generators.NLToGherkinGenerator.generate_steps') as mock_gherkin:
            # Configure mock to return our predefined steps
            mock_gherkin.return_value = predefined_steps

            # Run the test case
            result = await runner.run_operator_case(
                url="https://dev-psa.dev.ninjarmm.com",
                natural_language_steps="""
                Navigate to login page
                Enter email
                Enter password
                Click sign in
                """
            )

            # Verify the mock was called
            mock_gherkin.assert_called_once()

            # Verify overall result
            assert result.success, f"Operator run failed: {result.error_message}"
            #assert len(result.steps_results) == len(predefined_steps)
            assert result.total_duration > 0

            # Verify each step's execution
            for idx, step_result in enumerate(result.steps_results):
                print(f"\nStep {idx + 1}:")
                print(f"Gherkin: {step_result.gherkin_step.gherkin}")
                print(f"Action: {step_result.gherkin_step.action}")
                print(f"Target: {step_result.gherkin_step.target}")
                print(f"Value: {step_result.gherkin_step.value}")
                print(f"Generated Playwright instruction: {step_result.playwright_instruction}")
                print(f"Success: {step_result.execution_result.success}")
                print(f"URL after execution: {step_result.execution_result.page_url}")

                assert step_result.execution_result.success, (
                    f"Step {idx + 1} failed: {step_result.execution_result.error_message}"
                )
                assert step_result.playwright_instruction, "No Playwright instruction generated"
                assert step_result.execution_result.screenshot_path, "No screenshot captured"

                # Action-specific validations
                if step_result.gherkin_step.action == "navigate":
                    assert "goto" in step_result.playwright_instruction.lower()
                elif step_result.gherkin_step.action == "input":
                    assert any(action in step_result.playwright_instruction.lower()
                             for action in ['type', 'fill'])
                    assert step_result.gherkin_step.value in step_result.playwright_instruction
                elif step_result.gherkin_step.action == "click":
                    assert "click" in step_result.playwright_instruction.lower()

            # Verify final state
            final_step = result.steps_results[-1]
            assert "dev-psa.dev.ninjarmm.com" in final_step.execution_result.page_url

    @pytest.mark.asyncio
    async def test_failed_operator_execution(self, runner):
        with pytest.raises(OperatorExecutionException):
            await runner.run_operator_case(
                url="https://invalid-url.com",
                natural_language_steps="invalid step"
            )

    @pytest.mark.asyncio
    async def test_operator_validation(self, runner, sample_test_case):
        # If you have a validation method, use it here
        is_valid = await runner.validate_operator_case(sample_test_case)
        assert is_valid

    @pytest.mark.asyncio
    async def test_google_search_flow(self, runner):
        # Natural language steps describing the test scenario
        nl_steps = (
            "Navigate to google\n"
            "Search for python\n"
            "Click on the first result"
        )

        # Run the operator case starting at Google's homepage
        result = await runner.run_operator_case(
            url="https://www.google.com",
            natural_language_steps=nl_steps
        )

        # Assert overall success
        assert result.success, f"Operator run failed: {result.error_message}"

        # Assert the expected number of steps were executed
        assert len(result.steps_results) == 3

        # Assert each step executed successfully
        assert all(step.execution_result.success for step in result.steps_results)

        # Assert total duration is reasonable (e.g., > 0)
        assert result.total_duration > 0

        # Optional: Validate the Playwright instructions roughly match expected actions
        expected_actions = ["goto", "type", "click"]
        for step_result, expected_action in zip(result.steps_results, expected_actions):
            instruction = step_result.playwright_instruction.lower()
            assert expected_action in instruction, f"Expected '{expected_action}' in instruction but got: {instruction}"

        # Optional: Print step info for debugging
        for idx, step in enumerate(result.steps_results, 1):
            print(f"Step {idx}: {step.natural_language_step} - Success: {step.execution_result.success}")
            print(f"  Gherkin: {step.gherkin_step.gherkin}")
            print(f"  Instruction: {step.playwright_instruction}")
            print(f"  URL after step: {step.execution_result.page_url}")
    
    @pytest.mark.asyncio
    async def test_handle_rate_limit_error(self, runner):
        """Test handling of AI rate limit errors during Gherkin generation."""
        with patch('app.infrastructure.ai_generators.NLToGherkinGenerator.generate_steps') as mock_generate:
            # Configure mock to raise rate limit error
            mock_generate.side_effect = AIClientException(
                "InvalidRequest(400): You have exceeded our usage limits. "
                "Please wait for few hours before retrying"
            )

            # Run the test case and expect a failed result
            result = await runner.run_operator_case(
                url="https://example.com",
                natural_language_steps="Navigate to login page"
            )

            # Verify the result indicates failure
            assert not result.success
            assert "Step generation error" in result.error_message
            assert "exceeded our usage limits" in result.error_message

            # Verify the mock was called
            mock_generate.assert_called_once()

            # Verify no steps were executed
            assert len(result.steps_results) == 0

            # Verify execution metadata
            assert result.total_duration > 0
            assert isinstance(result.start_time, datetime)
            assert isinstance(result.end_time, datetime)


    @pytest.mark.asyncio
    async def test_handle_empty_steps_error(self, runner):
        """Test handling when AI returns empty steps."""
        with patch('app.infrastructure.ai_generators.NLToGherkinGenerator.generate_steps') as mock_generate:
            # Configure mock to return empty list
            mock_generate.return_value = []

            result = await runner.run_operator_case(
                url="https://example.com",
                natural_language_steps="Navigate to login page"
            )

            assert not result.success
            assert "Step generation error" in result.error_message
            assert "No steps were generated" in result.error_message
            assert len(result.steps_results) == 0

    @pytest.mark.asyncio
    async def test_handle_other_ai_errors(self, runner):
        """Test handling of other AI client errors."""
        with patch('app.infrastructure.ai_generators.NLToGherkinGenerator.generate_steps') as mock_generate:
            # Configure mock to raise a different error
            mock_generate.side_effect = AIClientException("Some other AI error")

            result = await runner.run_operator_case(
                url="https://example.com",
                natural_language_steps="Navigate to login page"
            )

            assert not result.success
            assert "Step generation error" in result.error_message
            assert "Some other AI error" in result.error_message
            assert len(result.steps_results) == 0

    @pytest.mark.asyncio
    async def test_handle_unexpected_error(self, runner):
        """Test handling of unexpected errors."""
        with patch('app.infrastructure.ai_generators.NLToGherkinGenerator.generate_steps') as mock_generate:
            # Configure mock to raise an unexpected error
            mock_generate.side_effect = ValueError("Unexpected error")

            result = await runner.run_operator_case(
                url="https://example.com",
                natural_language_steps="Navigate to login page"
            )

            assert not result.success
            assert "Unexpected error" in result.error_message
            assert len(result.steps_results) == 0