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