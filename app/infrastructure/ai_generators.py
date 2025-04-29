# app/infrastructure/ai_generators.py

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
import os
from app.domain.exceptions import AIClientException
from abc import ABC, abstractmethod

from app.infrastructure.ai_client import AIClientInterface
from app.domain.exceptions import StepGenerationException
from app.utils.logger import get_logger

logger = get_logger(__name__)

def load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = os.path.join("app", "prompts", filename)
    try:
        with open(prompt_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(f"Prompt file not found: {filename}")

@dataclass
class GherkinStep:
    """Represents a structured Gherkin step with its parsed components."""
    gherkin: str  # The full Gherkin step text
    action: str   # The action type (click, input, etc.)
    target: str   # The target element or page
    value: Optional[str] = None  # The value to input (if applicable)

    def __post_init__(self):
        """Validate the step after initialization."""
        if not self.gherkin or not self.action or not self.target:
            raise ValueError("Gherkin step must have gherkin text, action, and target")

class GeneratorInterface(ABC):
    """Base interface for all generators."""

    @abstractmethod
    async def validate_response(self, response: str) -> bool:
        """Validate the AI response format."""
        pass

class NLToGherkinGenerator(GeneratorInterface):
    """Generates structured Gherkin steps from natural language."""

    def __init__(self, ai_client: AIClientInterface):
        self.ai_client = ai_client
        self.prompt_template = load_prompt("nl_to_gherkin.txt")

    async def generate_steps(self, natural_language: str) -> List[GherkinStep]:
        """Generate structured Gherkin steps from natural language description."""
        try:
            # Prepare the prompt
            prompt = self.prompt_template.replace(
                "{natural_language_description}",
                natural_language.strip()
            )

            logger.debug(f"NLToGherkinGenerator Prompt: {prompt}")

            # Get response from AI
            response = await self.ai_client.send_prompt(prompt)

            # Add debug logging
            logger.debug(f"NLToGherkinGenerator Response: {response.content}")

            clean_content = self._clean_steps(response.content)
            logger.debug(f"NLToGherkinGenerator clean_content: {clean_content}")

            # Validate response format
            if not await self.validate_response(clean_content):
                raise StepGenerationException("Invalid AI response format")

            # Parse JSON response
            steps_data = json.loads(clean_content)

            # Convert to GherkinStep objects
            return [
                GherkinStep(
                    gherkin=step["gherkin"],
                    action=step["action"],
                    target=step["target"],
                    value=step.get("value")
                )
                for step in steps_data
            ]

        except AIClientException as e:
            # Handle AI client specific errors (e.g., rate limits)
            logger.error(f"AI client error during instruction generation: {e}")
            raise StepGenerationException(f"AI client error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise StepGenerationException(f"Failed to parse AI response as JSON: {e}")
        except KeyError as e:
            raise StepGenerationException(f"Missing required field in AI response: {e}")
        except Exception as e:
            raise StepGenerationException(f"Step generation failed: {str(e)}")

    def _clean_steps(self, instruction: str) -> str:
        instruction = instruction.strip()
        # Remove code block with language
        if instruction.startswith("```json"):
            instruction = instruction[len("```json"):].strip()
            if instruction.endswith("```"):
                instruction = instruction[:-3].strip()
        # Remove generic code block
        elif instruction.startswith("```") and instruction.endswith("```"):
            instruction = instruction[3:-3].strip()
        return instruction
    
    async def validate_response(self, response: str) -> bool:
        """Validate that the response is a properly formatted JSON array."""
        print(f"\nValidating response: {response}")
        print(f"Response type: {type(response)}")

        try:
            data = json.loads(response)
            print(f"Parsed JSON: {data}")
            print(f"JSON type: {type(data)}")

            if not isinstance(data, list):
                print(f"Expected list, got {type(data)}")
                return False

            for step in data:
                print(f"Validating step: {step}")
                required_fields = {"gherkin", "action", "target"}
                current_fields = set(step.keys())
                print(f"Current fields: {current_fields}")
                print(f"Required fields: {required_fields}")

                if not required_fields.issubset(current_fields):
                    print(f"Missing fields: {required_fields - current_fields}")
                    return False

            return True
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return False
        except Exception as e:
            print(f"Validation error: {str(e)}")
            return False

class PlaywrightGenerator(GeneratorInterface):
    """Generates Playwright instructions from Gherkin steps and HTML snapshots."""

    def __init__(self, ai_client: AIClientInterface):
        self.ai_client = ai_client
        self.prompt_template = load_prompt("gherkin_to_playwright.txt")

    async def generate_instruction(self, snapshot: str, gherkin_step: str) -> str:
        """Generate a Playwright instruction from a snapshot and Gherkin step."""
        try:
            # Prepare the prompt
            prompt = self.prompt_template.replace("{web_page_snapshot}", snapshot)
            prompt = prompt.replace("{gherkin_step}", gherkin_step)
            #logger.debug(f"Prompt PlaywrightGenerator: {prompt}")

            # Get response from AI
            response = await self.ai_client.send_prompt(prompt)
            logger.debug(f"Response PlaywrightGenerator: {response}")

            response_content = self._clean_instruction(response.content)

            # Validate response
            if not await self.validate_response(response_content):
                raise StepGenerationException("Invalid Playwright instruction format")

            # Return the cleaned instruction
            return response_content
        
        except AIClientException as e:
            # Handle AI client specific errors (e.g., rate limits)
            logger.error(f"AI client error during instruction generation: {e}")
            raise StepGenerationException(f"AI client error: {str(e)}") from e
        
        except Exception as e:
            raise StepGenerationException(f"Playwright instruction generation failed: {str(e)}")

    async def validate_response(self, response: str) -> bool:
        """Validate that the response is a valid Playwright selector JSON."""
        try:
            # Parse the response as JSON
            selectors = json.loads(response)

            # Validate structure
            if not isinstance(selectors, dict):
                return False

            # Check for required keys
            if 'high_precision' not in selectors or 'low_precision' not in selectors:
                return False

            # Validate that both are lists
            if not (isinstance(selectors['high_precision'], list) and
                    isinstance(selectors['low_precision'], list)):
                return False

            # Validate that lists are not empty
            if not (selectors['high_precision'] or selectors['low_precision']):
                return False

            return True

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response: {response}")
            return False
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False
        
    def _clean_instruction(self, instruction: str) -> str:
        instruction = instruction.strip()
        # Remove code block with language
        if instruction.startswith("```javascript"):
            instruction = instruction[len("```javascript"):].strip()
            if instruction.endswith("```"):
                instruction = instruction[:-3].strip()
        # Remove code block with language
        if instruction.startswith("```json"):
            instruction = instruction[len("```json"):].strip()
            if instruction.endswith("```"):
                instruction = instruction[:-3].strip()
        # Remove generic code block
        elif instruction.startswith("```") and instruction.endswith("```"):
            instruction = instruction[3:-3].strip()
        return instruction

def create_nl_to_gherkin_generator(
    ai_client_type: str = "abacus"
) -> NLToGherkinGenerator:
    """Factory function to create NL to Gherkin generator."""
    from app.infrastructure.ai_client import create_ai_client
    ai_client = create_ai_client(ai_client_type)
    return NLToGherkinGenerator(ai_client)

def create_playwright_generator(
    ai_client_type: str = "abacus"
) -> PlaywrightGenerator:
    """Factory function to create Playwright generator."""
    from app.infrastructure.ai_client import create_ai_client
    ai_client = create_ai_client(ai_client_type)
    return PlaywrightGenerator(ai_client)