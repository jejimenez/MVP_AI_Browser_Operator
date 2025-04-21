# app/infrastructure/ai_client.py

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import os
import json
import logging
from dataclasses import dataclass
import httpx
from dotenv import load_dotenv

from app.utils.logger import get_logger
from app.domain.exceptions import AIClientException, InvalidPromptException

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

@dataclass
class AIResponse:
    """Data class to represent a structured AI response."""
    high_precision: List[str]
    low_precision: List[str]
    raw_response: Dict[str, Any]

class AIClientInterface(ABC):
    """Abstract base class defining the interface for AI clients."""

    @abstractmethod
    async def generate_playwright_instruction(self, dom: str, step: str) -> AIResponse:
        """
        Generate Playwright instructions from DOM and step description.

        Args:
            dom (str): The DOM snapshot of the page
            step (str): The test step description

        Returns:
            AIResponse: Structured response containing high and low precision instructions

        Raises:
            AIClientException: If there's an error in AI processing
            InvalidPromptException: If the input is invalid
        """
        pass

class AbacusAIClient(AIClientInterface):
    """Implementation of AIClientInterface for Abacus.AI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.cloud.abacus.ai",
        timeout: int = 30
    ):
        """
        Initialize the Abacus AI client.

        Args:
            api_key (Optional[str]): API key for authentication. If None, reads from environment
            base_url (str): Base URL for the API
            timeout (int): Timeout in seconds for API calls

        Raises:
            ValueError: If API key is not provided and not found in environment
        """
        self._api_key = api_key or os.getenv("ABACUS_API_KEY")
        if not self._api_key:
            raise ValueError("API key must be provided or set in ABACUS_API_KEY environment variable")

        self._base_url = base_url
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

    async def generate_playwright_instruction(self, dom: str, step: str) -> AIResponse:
        """
        Generate Playwright instructions using Abacus.AI API.

        Args:
            dom (str): DOM snapshot
            step (str): Test step description

        Returns:
            AIResponse: Structured response with instructions

        Raises:
            AIClientException: On API errors
            InvalidPromptException: On invalid input
        """
        if not dom or not step:
            raise InvalidPromptException("Both DOM and step must be provided")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await self._make_api_call(client, dom, step)
                return self._process_response(response)
        except httpx.TimeoutException:
            raise AIClientException("API request timed out")
        except httpx.HTTPError as e:
            raise AIClientException(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in AI client: {str(e)}")
            raise AIClientException(f"Unexpected error: {str(e)}")

    async def _make_api_call(
        self,
        client: httpx.AsyncClient,
        dom: str,
        step: str
    ) -> Dict[str, Any]:
        """
        Make the actual API call to Abacus.AI.

        Args:
            client (httpx.AsyncClient): HTTP client
            dom (str): DOM snapshot
            step (str): Test step

        Returns:
            Dict[str, Any]: Raw API response

        Raises:
            AIClientException: On API errors
        """
        endpoint = f"{self._base_url}/api/v0/evaluatePrompt"

        prompt = self._construct_prompt(dom, step)

        try:
            response = await client.post(
                endpoint,
                headers=self._headers,
                json={"prompt": prompt}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"API error: {e.response.status_code}"
            if e.response.text:
                error_msg += f" - {e.response.text}"
            raise AIClientException(error_msg)

    def _construct_prompt(self, dom: str, step: str) -> str:
        """
        Construct the prompt for the AI model.

        Args:
            dom (str): DOM snapshot
            step (str): Test step

        Returns:
            str: Formatted prompt
        """
        return f"""
        Given this DOM snapshot and test step, generate Playwright instructions.
        Use both high-precision (unique selectors) and low-precision (fallback) approaches.

        DOM:
        {dom}

        Step:
        {step}

        Return JSON with two arrays:
        {{
            "high_precision": ["instruction1", "instruction2"],
            "low_precision": ["instruction1", "instruction2"]
        }}
        """

    def _process_response(self, response: Dict[str, Any]) -> AIResponse:
        """
        Process and validate the API response.

        Args:
            response (Dict[str, Any]): Raw API response

        Returns:
            AIResponse: Structured response object

        Raises:
            AIClientException: If response format is invalid
        """
        try:
            # Extract the actual response content (adjust based on actual API response structure)
            content = response.get("response", {})
            if isinstance(content, str):
                content = json.loads(content)

            return AIResponse(
                high_precision=content.get("high_precision", []),
                low_precision=content.get("low_precision", []),
                raw_response=response
            )
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            raise AIClientException(f"Invalid response format: {str(e)}")

# Factory function for creating AI clients
def create_ai_client(
    client_type: str = "abacus",
    api_key: Optional[str] = None,
    **kwargs
) -> AIClientInterface:
    """
    Factory function to create AI clients.

    Args:
        client_type (str): Type of AI client to create
        api_key (Optional[str]): API key for authentication
        **kwargs: Additional arguments for client initialization

    Returns:
        AIClientInterface: Initialized AI client

    Raises:
        ValueError: If client_type is not supported
    """
    clients = {
        "abacus": AbacusAIClient
    }

    if client_type not in clients:
        raise ValueError(f"Unsupported AI client type: {client_type}")

    return clients[client_type](api_key=api_key, **kwargs)