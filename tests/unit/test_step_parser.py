# tests/unit/test_step_parser.py

import pytest
from app.domain.step_parser import (
    StepParserFactory,
    ParsedStep,
    StepType,
    GherkinStepParser
)
from app.domain.exceptions import InvalidStepFormatException

class TestStepParser:
    @pytest.fixture
    def parser(self):
        return StepParserFactory.create_parser("gherkin")

    def test_parse_click_step(self, parser):
        step = "When I click the login button"
        result = parser.parse_single_step(step)

        assert isinstance(result, ParsedStep)
        assert result.step_type == StepType.CLICK
        assert result.target == "login button"
        assert result.original_text == step

    def test_parse_input_step(self, parser):
        step = 'When I enter "test@example.com" into the email field'
        result = parser.parse_single_step(step)

        assert result.step_type == StepType.INPUT
        assert result.value == "test@example.com"
        assert result.target == "email field"
        assert result.original_text == step

    def test_parse_invalid_step(self, parser):
        with pytest.raises(InvalidStepFormatException):
            parser.parse_single_step("")

    @pytest.mark.parametrize("step_text,expected_type,expected_target", [
        ("Given I click the login button", StepType.CLICK, "login button"),
        ("When I enter 'test' in the username field", StepType.INPUT, "username field"),
        ("Then I wait for 5 seconds", StepType.WAIT, "5 seconds"),
        ("And I verify the page title", StepType.VERIFY, "page title"),
        ("When I navigate to the dashboard", StepType.NAVIGATE, "dashboard page"),
    ])
    def test_step_types(self, parser, step_text, expected_type, expected_target):
        result = parser.parse_single_step(step_text)
        assert result.step_type == expected_type
        assert result.target == expected_target
        assert result.original_text == step_text

    def test_parse_multiple_steps(self, parser):
        steps_text = """
        Given I am on the login page
        When I enter "admin" into the username field
        And I enter "password123" into the password field
        And I click the login button
        Then I should see the dashboard
        """
        results = parser.parse_steps(steps_text)

        assert len(results) == 5
        assert all(isinstance(step, ParsedStep) for step in results)

        # Verify first step
        assert results[0].step_type == StepType.NAVIGATE
        assert results[0].target == "login page"

        # Verify input steps
        assert results[1].step_type == StepType.INPUT
        assert results[1].value == "admin"
        assert results[1].target == "username field"

        # Verify click step
        assert results[3].step_type == StepType.CLICK
        assert results[3].target == "login button"

    def test_parse_step_with_quotes(self, parser):
        steps = [
            'When I enter "test@example.com" into the email field',
            "When I enter 'test@example.com' into the email field",
        ]

        for step in steps:
            result = parser.parse_single_step(step)
            assert result.step_type == StepType.INPUT
            assert result.value == "test@example.com"
            assert result.target == "email field"

    def test_parse_step_with_special_characters(self, parser):
        step = 'When I enter "user.name+123@domain.com" into the email field'
        result = parser.parse_single_step(step)

        assert result.step_type == StepType.INPUT
        assert result.value == "user.name+123@domain.com"
        assert result.target == "email field"

    def test_parse_step_with_numbers(self, parser):
        step = "When I wait for 10 seconds"
        result = parser.parse_single_step(step)

        assert result.step_type == StepType.WAIT
        assert result.target == "10 seconds"

    def test_parse_verify_steps(self, parser):
        steps = [
            "Then I should see the welcome message",
            "Then I verify the error message is displayed",
            "And I should see the dashboard",
        ]

        for step in steps:
            result = parser.parse_single_step(step)
            assert result.step_type == StepType.VERIFY

    def test_step_keywords(self, parser):
        steps = [
            "Given I am on the homepage",
            "When I click the button",
            "Then I should see the result",
            "And I verify the message",
            "But I cannot see the error",
        ]

        results = parser.parse_steps("\n".join(steps))
        assert len(results) == 5
        assert all(isinstance(step, ParsedStep) for step in results)

    def test_parse_steps_with_empty_lines(self, parser):
        steps_text = """
        Given I am on the login page

        When I enter "admin" into the username field

        And I click the login button
        """

        results = parser.parse_steps(steps_text)
        assert len(results) == 3

    def test_parse_steps_with_comments(self, parser):
        steps_text = """
        # Login scenario
        Given I am on the login page
        # Enter credentials
        When I enter "admin" into the username field
        """

        results = parser.parse_steps(steps_text)
        assert len(results) == 2

    @pytest.mark.parametrize("invalid_step", [
        "",  # Empty step
        "   ",  # Whitespace only
        "Invalid step format",  # No Gherkin keyword
        "Given",  # Keyword only
    ])
    def test_invalid_steps(self, parser, invalid_step):
        with pytest.raises(InvalidStepFormatException):
            parser.parse_single_step(invalid_step)

    def test_step_metadata(self, parser):
        step = "When I click the login button"
        result = parser.parse_single_step(step)

        assert result.metadata is not None
        assert "timestamp" in result.metadata
        assert "keyword" in result.metadata
        assert result.metadata["keyword"] == "When"