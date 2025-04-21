# tests/unit/test_step_parser.py

import pytest
from app.domain.step_parser import (
    StepParserFactory,
    ParsedStep,
    StepType
)

class TestStepParser:
    @pytest.fixture
    def parser(self):
        return StepParserFactory.create_parser("gherkin")

    def test_parse_click_step(self, parser):
        step = "click login button"
        result = parser.parse_single_step(step)

        assert isinstance(result, ParsedStep)
        assert result.step_type == StepType.CLICK
        assert result.target == "login button"

    def test_parse_input_step(self, parser):
        step = 'enter "test@example.com" into email field'
        result = parser.parse_single_step(step)

        assert result.step_type == StepType.INPUT
        assert result.value == "test@example.com"
        assert result.target == "email field"

    def test_parse_invalid_step(self, parser):
        with pytest.raises(Exception):
            parser.parse_single_step("")

    @pytest.mark.parametrize("step_text,expected_type", [
        ("click login button", StepType.CLICK),
        ("enter 'test' in username", StepType.INPUT),
        ("wait for 5 seconds", StepType.WAIT),
        ("verify page title", StepType.VERIFY),
    ])
    def test_step_types(self, parser, step_text, expected_type):
        result = parser.parse_single_step(step_text)
        assert result.step_type == expected_type