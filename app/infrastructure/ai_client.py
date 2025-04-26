# app/infrastructure/ai_client.py

import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv
from abacusai import ApiClient

from app.infrastructure.interfaces import AIClientInterface, AIResponse
from app.utils.logger import get_logger
from app.domain.exceptions import AIClientException

logger = get_logger(__name__)
load_dotenv()

class AbacusAIClient(AIClientInterface):
    """Implementation of AIClientInterface using Abacus.AI SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "claude-3-sonnet",
        max_tokens: int = 1000,
        temperature: float = 0.7
    ):
        self._api_key = api_key or os.getenv("ABACUS_API_KEY")
        if not self._api_key:
            raise ValueError("API key must be provided or set in ABACUS_API_KEY environment variable")

        self._model_name = model_name
        self._max_tokens = max_tokens
        self._temperature = temperature

        try:
            self._sdk_client = ApiClient(api_key=self._api_key)
            logger.info("Successfully initialized Abacus.AI SDK client")
        except Exception as e:
            logger.error(f"Failed to initialize Abacus.AI SDK client: {str(e)}")
            raise AIClientException(f"SDK initialization failed: {str(e)}")

    async def send_prompt(self, prompt: str) -> AIResponse:
        """Send a prompt using the Abacus.AI SDK."""
        try:
            logger.debug(f"Sending prompt to Abacus.AI (model: {self._model_name})")

            # Call evaluatePrompt using the SDK
            response = self._sdk_client.evaluate_prompt(
                prompt=prompt,
                llm_name=self._model_name,
                max_tokens=self._max_tokens,
                temperature=self._temperature
            )

            # Convert response to dictionary and process
            response_dict = response.to_dict()
            return self._process_response(response_dict)

        except Exception as e:
            logger.error(f"AI client error: {str(e)}")
            raise AIClientException(f"Failed to send prompt: {str(e)}")

    def _process_response(self, response: Dict) -> AIResponse:
        """Process the SDK response into our AIResponse format."""
        try:
            # Extract content from the response
            # Note: Adjust the key based on actual SDK response structure
            content = response.get("response", "").strip()

            if not content:
                raise AIClientException("Empty response from AI service")

            return AIResponse(
                content=content,
                metadata={
                    "model": self._model_name,
                    "raw_response": response
                }
            )
        except Exception as e:
            raise AIClientException(f"Failed to process response: {str(e)}")

    @property
    def model_name(self) -> str:
        """Get the current model name."""
        return self._model_name

    @model_name.setter
    def model_name(self, value: str):
        """Set the model name."""
        self._model_name = value
        logger.info(f"Model name updated to: {value}")

    @property
    def max_tokens(self) -> int:
        """Get the current max tokens."""
        return self._max_tokens

    @max_tokens.setter
    def max_tokens(self, value: int):
        """Set max tokens."""
        self._max_tokens = value
        logger.info(f"Max tokens updated to: {value}")

    @property
    def temperature(self) -> float:
        """Get the current temperature."""
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        """Set temperature."""
        self._temperature = value
        logger.info(f"Temperature updated to: {value}")

def create_ai_client(
    client_type: str = "abacus",
    api_key: Optional[str] = None,
    model_name: str = "claude-3-sonnet",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    **kwargs
) -> AIClientInterface:
    """Factory function to create AI clients."""
    clients = {
        "abacus": AbacusAIClient
    }

    if client_type not in clients:
        raise ValueError(f"Unsupported AI client type: {client_type}")

    return clients[client_type](
        api_key=api_key,
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs
    )