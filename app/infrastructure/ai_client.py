"""
Modified ai_client.py to include Gemini API integration.
"""
import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from abacusai import ApiClient
import requests

from app.infrastructure.interfaces import AIClientInterface, AIResponse
from app.utils.logger import get_logger
from app.domain.exceptions import AIClientException

# Use a type alias for better readability
JSONType = Dict[str, Any]

logger = get_logger(__name__)
load_dotenv()



class AbacusAIClient(AIClientInterface):
    """Implementation of AIClientInterface using Abacus.AI SDK."""

    DEFAULT_MODEL_NAME = "claude-3-sonnet"  # Class-level default

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "claude-3-sonnet",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,  # Add kwargs for compatibility
    ):
        self._api_key = api_key or os.getenv("ABACUS_API_KEY")
        if not self._api_key:
            raise ValueError("API key must be provided or set in ABACUS_API_KEY environment variable")

        self._model_name = model_name if model_name is not None else self.DEFAULT_MODEL_NAME  # Use default if None
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
            content = response.get("content", "").strip()

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
        logger.info(f"Temperature updated to: {value}")



class GeminiAIClient(AIClientInterface):
    """Implementation of AIClientInterface for Google Gemini API."""

    DEFAULT_MODEL_NAME = "gemini-2.0-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",  # Use gemini-2.0-flash
        max_tokens: int = 2048,  #  set a default value
        temperature: float = 0.7,
        **kwargs: Any,
    ):
        """
        Initializes the Gemini AI client.

        Args:
            api_key: The API key for the Gemini API.
            model_name: The name of the Gemini model to use.
            max_tokens: Maximum number of tokens in the generated text.
            temperature: Sampling temperature for the model.
        """
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "API key must be provided or set in GEMINI_API_KEY environment variable"
            )
        self._model_name = model_name if model_name is not None else self.DEFAULT_MODEL_NAME  # Use default if None
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._base_url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(self._model_name) # Use dynamic url

        logger.info(f"Successfully initialized Gemini API client with model: {self._model_name}")


    async def send_prompt(self, prompt: str) -> AIResponse:
        """
        Sends a prompt to the Gemini API and retrieves the response.

        Args:
            prompt: The prompt to send to the API.

        Returns:
            An AIResponse object containing the generated text.

        Raises:
            AIClientException: If there is an error communicating with the API.
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
             "safetySettings": [  # Added safety settings as recommended by Google.
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ],
            "generationConfig": {  # Add a generationConfig object
                "maxOutputTokens": self._max_tokens,
                "temperature": self._temperature
            },
        }

        logger.debug(f"Sending prompt to Gemini API: {self._base_url}")
        try:
            response = requests.post(self._base_url, headers=headers, json=payload)
            response.raise_for_status()  # Raise for bad status codes
            data = response.json()
            logger.debug(f"Received response from Gemini API: {data}")
            return self._process_response(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API error: {e}")
            raise AIClientException(f"Gemini API request failed: {e}.  Check your API endpoint and parameters.  Error Details: {e}.  Response Content: {response.text if hasattr(response, 'text') else 'No response text available.  Status Code: {response.status_code}'}. URL: {response.request.url}")
        except json.JSONDecodeError as e:
            logger.error(f"Gemini API error: {e}")
            raise AIClientException(f"Gemini API response was not valid JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise AIClientException(f"An unexpected error occurred: {e}")

    def _process_response(self, response: Dict) -> AIResponse:
        """
        Processes the response from the Gemini API into the AIResponse format.

        Args:
            response: The JSON response from the Gemini API.

        Returns:
            An AIResponse object.

        Raises:
            AIClientException: If the response is not in the expected format.
        """
        try:
            # Extract content from the response.  Adjust the path as necessary
            if (
                response
                and response.get("candidates")
                and len(response.get("candidates", [])) > 0
                and response["candidates"][0].get("content")
                and response["candidates"][0]["content"].get("parts")
                and len(response["candidates"][0]["content"]["parts"]) > 0
            ):
                content = response["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                content = "No response from the API."  # Or handle this as an exception

            if not content:
                raise AIClientException("Empty response from Gemini API")
            return AIResponse(
                content=content,
                metadata={"model": self._model_name, "raw_response": response},
            )
        except KeyError as e:
            logger.error(f"Missing key in Gemini response: {e}")
            raise AIClientException(f"Missing key in Gemini API response: {e}")
        except Exception as e:
            logger.error(f"Error processing Gemini response: {e}")
            raise AIClientException(f"Failed to process Gemini API response: {e}")

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
        logger.info(f"Temperature updated to: {value}")

class GrokAIClient(AIClientInterface):
    """Implementation of AIClientInterface for xAI Grok API."""

    DEFAULT_MODEL_NAME = "grok-3-mini-beta"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "grok-3-mini-beta",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ):
        """
        Initializes the Grok AI client.

        Args:
            api_key: The API key for the xAI API.
            model_name: The name of the Grok model to use.
            max_tokens: Maximum number of tokens in the generated text.
            temperature: Sampling temperature for the model.
        """
        self._api_key = api_key or os.getenv("GROK_API_KEY")
        if not self._api_key:
            raise ValueError(
                "API key must be provided or set in GROK_API_KEY environment variable"
            )
        self._model_name = model_name if model_name is not None else self.DEFAULT_MODEL_NAME
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._base_url = "https://api.x.ai/v1/chat/completions"

        logger.info(f"Successfully initialized Grok API client with model: {self._model_name}")

    async def send_prompt(self, prompt: str) -> AIResponse:
        """
        Sends a prompt to the xAI Grok API and retrieves the response.

        Args:
            prompt: The prompt to send to the API.

        Returns:
            An AIResponse object containing the generated text.

        Raises:
            AIClientException: If there is an error communicating with the API.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a test assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": self._model_name,
            "stream": False,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

        logger.debug(f"Sending prompt to Grok API: {self._base_url}")
        try:
            response = requests.post(self._base_url, headers=headers, json=payload)
            response.raise_for_status()  # Raise for bad status codes
            data = response.json()
            logger.debug(f"Received response from Grok API: {data}")
            return self._process_response(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Grok API error: {e}")
            raise AIClientException(f"Grok API request failed: {str(e)}. Response: {response.text if 'response' in locals() else 'No response'}")
        except json.JSONDecodeError as e:
            logger.error(f"Grok API response not valid JSON: {e}")
            raise AIClientException(f"Grok API response was not valid JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise AIClientException(f"An unexpected error occurred: {str(e)}")

    def _process_response(self, response: Dict) -> AIResponse:
        """
        Processes the response from the Grok API into the AIResponse format.

        Args:
            response: The JSON response from the Grok API.

        Returns:
            An AIResponse object.

        Raises:
            AIClientException: If the response is not in the expected format.
        """
        try:
            # Extract content from the response
            if (
                response
                and response.get("choices")
                and len(response.get("choices", [])) > 0
                and response["choices"][0].get("message")
                and response["choices"][0]["message"].get("content")
            ):
                content = response["choices"][0]["message"]["content"].strip()
            else:
                content = "No response from the API."

            if not content:
                raise AIClientException("Empty response from Grok API")

            return AIResponse(
                content=content,
                metadata={"model": self._model_name, "raw_response": response},
            )
        except KeyError as e:
            logger.error(f"Missing key in Grok response: {e}")
            raise AIClientException(f"Missing key in Grok API response: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing Grok response: {e}")
            raise AIClientException(f"Failed to process Grok API response: {str(e)}")

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
    model_name: Optional[str] = None,  # Changed to Optional, no default
    max_tokens: int = 10000,
    temperature: float = 0.7,
    **kwargs: Any
) -> AIClientInterface:
    """Factory function to create AI clients."""
    clients = {
        "abacus": AbacusAIClient,
        "gemini": GeminiAIClient,
        "grok": GrokAIClient, 
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
