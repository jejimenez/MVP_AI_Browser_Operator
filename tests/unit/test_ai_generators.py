# tests/unit/test_ai_generators.py

import pytest
from unittest.mock import Mock, AsyncMock
import json
from datetime import datetime

from app.infrastructure.ai_generators import (
    NLToGherkinGenerator,
    PlaywrightGenerator,
    GherkinStep,
    StepGenerationException
)
from app.infrastructure.ai_client import AIClientInterface, AIResponse

# Test Data
# Make sure VALID_NL_RESPONSE is properly formatted
VALID_NL_RESPONSE = json.dumps([
    {
        "gherkin": "Given I am on the login page",
        "action": "navigate",
        "target": "login page",
        "value": None
    },
    {
        "gherkin": "When I enter \"admin\" into the username field",
        "action": "input",
        "target": "username field",
        "value": "admin"
    },
    {
        "gherkin": "And I click the login button",
        "action": "click",
        "target": "login button",
        "value": None
    }
])

INVALID_NL_RESPONSE = json.dumps([
    {
        "gherkin": "Given I am on the login page"
        # intentionally missing "action" and "target"
    }
])

VALID_PLAYWRIGHT_RESPONSE = "await page.click('button#login');"
INVALID_PLAYWRIGHT_RESPONSE = "click('button#login');"  # Missing await page

# Fixtures
@pytest.fixture
def mock_ai_client():
    """Create a mock AI client."""
    client = Mock(spec=AIClientInterface)
    client.send_prompt = AsyncMock()
    return client

@pytest.fixture
def nl_to_gherkin_generator(mock_ai_client):
    """Create a NLToGherkinGenerator with mock client."""
    generator = NLToGherkinGenerator(mock_ai_client)
    # Mock the prompt template loading
    generator.prompt_template = "Test prompt: {natural_language_description}"
    return generator

@pytest.fixture
def playwright_generator(mock_ai_client):
    """Create a PlaywrightGenerator with mock client."""
    generator = PlaywrightGenerator(mock_ai_client)
    # Mock the prompt template loading
    generator.prompt_template = "Test prompt: {html_snapshot} {gherkin_step}"
    return generator

# Tests for GherkinStep
class TestGherkinStep:
    # Add a test to verify the test data
    def test_valid_nl_response(self):
        """Verify that our test data is valid."""
        print(f"\nTest data: {VALID_NL_RESPONSE}")
        data = json.loads(VALID_NL_RESPONSE)
        assert isinstance(data, list)
        for step in data:
            assert all(field in step for field in ["gherkin", "action", "target"])

    def test_valid_gherkin_step(self):
        """Test creating a valid GherkinStep."""
        step = GherkinStep(
            gherkin="When I click the login button",
            action="click",
            target="login button"
        )
        assert step.gherkin == "When I click the login button"
        assert step.action == "click"
        assert step.target == "login button"
        assert step.value is None

    def test_invalid_gherkin_step(self):
        """Test creating an invalid GherkinStep."""
        with pytest.raises(ValueError):
            GherkinStep(
                gherkin="",  # Empty gherkin
                action="click",
                target="login button"
            )

# Tests for NLToGherkinGenerator
class TestNLToGherkinGenerator:
    @pytest.mark.asyncio
    async def test_validate_response_directly(self, nl_to_gherkin_generator):
        """Test the validation method directly."""
        is_valid = await nl_to_gherkin_generator.validate_response(VALID_NL_RESPONSE)
        print(f"\nDirect validation result: {is_valid}")
        assert is_valid, "Validation should pass for valid test data"

    @pytest.mark.asyncio
    async def test_generate_steps_valid_response(self, nl_to_gherkin_generator, mock_ai_client):
        """Test generating steps with valid AI response."""
        # Print the prompt template
        print(f"\nPrompt template: {nl_to_gherkin_generator.prompt_template}")

        # Setup mock response with properly formatted JSON
        mock_ai_client.send_prompt.return_value = AIResponse(
            content=VALID_NL_RESPONSE,
            metadata={"foo": "bar"}
        )

        # Print the mock response content
        print(f"\nMock response content: {VALID_NL_RESPONSE}")

        # Execute
        steps = await nl_to_gherkin_generator.generate_steps(
            "Log in as admin"
        )

    @pytest.mark.asyncio
    async def test_validate_response_valid(self, nl_to_gherkin_generator):
        """Test response validation with valid response."""
        # Test the validation directly
        is_valid = await nl_to_gherkin_generator.validate_response(VALID_NL_RESPONSE)
        assert is_valid, "Response should be valid"

    @pytest.mark.asyncio
    async def test_generate_steps_invalid_json(self, nl_to_gherkin_generator, mock_ai_client):
        """Test generating steps with invalid JSON response."""
        # Setup mock response with invalid JSON
        mock_ai_client.send_prompt.return_value = AIResponse(
            content="Invalid JSON",
            metadata={"foo": "bar"}
        )

        with pytest.raises(StepGenerationException) as exc_info:
            await nl_to_gherkin_generator.generate_steps("Log in as admin")
        assert "Invalid AI response format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_steps_missing_fields(self, nl_to_gherkin_generator, mock_ai_client):
        """Test generating steps with missing required fields."""
        # Setup mock response with missing fields
        mock_ai_client.send_prompt.return_value = AIResponse(
            content=INVALID_NL_RESPONSE,
            metadata={"foo": "bar"}
        )

        # Assert raises exception
        with pytest.raises(StepGenerationException) as exc_info:
            await nl_to_gherkin_generator.generate_steps("Log in as admin")
        assert "Invalid AI response format" in str(exc_info.value)

        


    @pytest.mark.asyncio
    async def test_validate_response_invalid(self, nl_to_gherkin_generator):
        """Test response validation with invalid response."""
        assert not await nl_to_gherkin_generator.validate_response(INVALID_NL_RESPONSE)

# Tests for PlaywrightGenerator
class TestPlaywrightGenerator:
    @pytest.mark.asyncio
    async def test_generate_instruction_valid(self, playwright_generator, mock_ai_client):
        """Test generating valid Playwright instruction."""
        # Setup mock response
        mock_ai_client.send_prompt.return_value = AIResponse(
            content=VALID_PLAYWRIGHT_RESPONSE,
            metadata={"foo": "bar"}
        )

        # Execute
        instruction = await playwright_generator.generate_instruction(
            snapshot="<html>...</html>",
            gherkin_step="When I click the login button"
        )

        # Assert
        assert instruction == "await page.click('button#login');"
        assert instruction.startswith("await page.")

    @pytest.mark.asyncio
    async def test_generate_instruction_invalid(self, playwright_generator, mock_ai_client):
        """Test generating invalid Playwright instruction."""
        # Setup mock response
        mock_ai_client.send_prompt.return_value = AIResponse(
            content=INVALID_PLAYWRIGHT_RESPONSE,
            metadata={"foo": "bar"}
        )

        # Assert raises exception
        with pytest.raises(StepGenerationException) as exc_info:
            await playwright_generator.generate_instruction(
                snapshot="<html>...</html>",
                gherkin_step="When I click the login button"
            )
        assert "Invalid Playwright instruction format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_clean_instruction_markdown(self, playwright_generator):
        """Test cleaning instruction with markdown formatting."""
        instruction = "```javascript\nawait page.click('button');\n```"
        cleaned = playwright_generator._clean_instruction(instruction)
        assert cleaned == "await page.click('button');"

    @pytest.mark.asyncio
    async def test_validate_response_valid(self, playwright_generator):
        """Test response validation with valid instruction."""
        assert await playwright_generator.validate_response(VALID_PLAYWRIGHT_RESPONSE)

    @pytest.mark.asyncio
    async def test_validate_response_invalid(self, playwright_generator):
        """Test response validation with invalid instruction."""
        assert not await playwright_generator.validate_response(INVALID_PLAYWRIGHT_RESPONSE)

    @pytest.mark.asyncio
    async def test_generate_instruction_with_expect(self, playwright_generator, mock_ai_client):
        """Test generating instruction with expect assertion."""
        expect_response = "await expect(page.locator('h1')).toHaveText('Dashboard');"
        mock_ai_client.send_prompt.return_value = AIResponse(
            content=expect_response,
            metadata={"foo": "bar"}
        )

        instruction = await playwright_generator.generate_instruction(
            snapshot="<html><h1>Dashboard</h1></html>",
            gherkin_step="Then I should see the Dashboard heading"
        )

        assert instruction == expect_response
        assert instruction.startswith("await expect")

# Integration-style tests
class TestGeneratorIntegration:
    @pytest.mark.asyncio
    async def test_full_generation_flow(self, nl_to_gherkin_generator, playwright_generator, mock_ai_client):
        """Test the full flow from NL to Playwright instruction."""
        # Setup mock responses
        mock_ai_client.send_prompt.side_effect = [
            AIResponse(content=VALID_NL_RESPONSE, metadata={"foo": "bar"}),
            AIResponse(content=VALID_PLAYWRIGHT_RESPONSE, metadata={"foo": "bar"})
        ]

        # Generate Gherkin steps
        steps = await nl_to_gherkin_generator.generate_steps("Log in as admin")
        assert len(steps) > 0

        # Generate Playwright instruction for first step
        instruction = await playwright_generator.generate_instruction(
            snapshot="<html>...</html>",
            gherkin_step=steps[0].gherkin
        )
        assert instruction.startswith("await page.")