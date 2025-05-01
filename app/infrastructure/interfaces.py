# app/infrastructure/interfaces.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AIResponse:
    """Data class to represent a structured AI response."""
    content: str
    metadata: Optional[Dict[str, Any]] = None

class AIClientInterface(ABC):
    """Abstract interface for AI clients."""
    
    @abstractmethod
    async def send_prompt(self, prompt: str) -> AIResponse:
        """Send prompt to AI and get response."""
        pass

class StepGeneratorInterface(ABC):
    """Abstract interface for step generators."""
    
    @abstractmethod
    async def generate_steps(self, natural_language: str) -> List[str]:
        """Generate steps from natural language."""
        pass

class PlaywrightGeneratorInterface(ABC):
    """Abstract interface for Playwright code generators."""
    
    @abstractmethod
    async def generate_instruction(self, snapshot: str, step: str) -> str:
        """Generate Playwright instruction from snapshot and step."""
        pass

class BrowserManagerInterface(ABC):
    """Interface for browser management."""
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def execute_step(self, instruction: str) -> Any:
        pass

    @abstractmethod
    async def get_page_content(self) -> str:
        pass

class HTMLSummarizerInterface(ABC):
    """Interface for HTML summarization."""
    @abstractmethod
    def summarize_html(self, html_content: str) -> Dict[str, Any]:
        """Convert HTML to JSON DOM for visible elements."""
        pass