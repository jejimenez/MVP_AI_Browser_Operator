# app/domain/step_parser.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
import re
from datetime import datetime

from app.domain.exceptions import InvalidStepFormatException

class StepType(Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    INPUT = "input"
    WAIT = "wait"
    VERIFY = "verify"

@dataclass
class ParsedStep:
    """Represents a parsed Gherkin step with structured information."""
    step_type: StepType
    target: str
    value: Optional[str]
    original_text: str
    metadata: Dict[str, Any]
    action: str

    def __post_init__(self):
        """Validate the step after initialization."""
        if not self.action:
            self.action = self.step_type.value
        if not isinstance(self.step_type, StepType):
            raise ValueError(f"Invalid step type: {self.step_type}")

class StepParser(ABC):
    """Abstract base class for step parsers."""

    @abstractmethod
    def parse_steps(self, steps_text: str) -> List[ParsedStep]:
        """Parse multiple steps from text."""
        pass

    @abstractmethod
    def parse_single_step(self, step: str) -> ParsedStep:
        """Parse a single step from text."""
        pass

class GherkinStepParser(StepParser):
    """Parser for Gherkin-style steps."""

    # Gherkin keywords
    KEYWORDS = ("given", "when", "then", "and", "but")

    # Regular expressions for different step types
    PATTERNS = {
        # Click pattern matches "click/press/tap the <target> button/link"
        "click": r"(?:click|press|tap)(?:\s+(?:the|on|at))?\s+(.+?(?:\s+(?:button|link|element))?)$",

        # Input pattern matches "enter/type/fill '<value>' into/in the <target> field/input"
        "input": r"(?:enter|type|fill|input)\s+['\"](.+?)['\"](?:\s+(?:into|in|to))?\s+(?:the\s+)?(.+?(?:\s+(?:field|input|box))?)$",

        # Navigate pattern matches "am on/go to/navigate to the <target> page"
        "navigate": r"(?:am\s+on|go\s+to|navigate\s+to)(?:\s+the)?\s+(.+?(?:\s+page)?)$",

        # Wait pattern matches "wait for <target> seconds/minutes"
        "wait": r"wait\s+(?:for\s+)?(\d+(?:\s+(?:second|seconds|minute|minutes)))$",

        # Verify pattern matches "see/verify/check the <target>"
        "verify": r"(?:see|verify|check|confirm)(?:\s+that)?(?:\s+the)?\s+(.+?)(?:\s+is\s+displayed|\s+appears)?$"
    }

    def parse_steps(self, steps_text: str) -> List[ParsedStep]:
        """Parse multiple steps from text."""
        if not steps_text or not steps_text.strip():
            return []

        # Split text into lines and filter out empty lines and comments
        lines = [
            line.strip()
            for line in steps_text.split('\n')
            if line.strip() and not line.strip().startswith('#')
        ]

        return [self.parse_single_step(step) for step in lines]

    def parse_single_step(self, step: str) -> ParsedStep:
        """Parse a single step from text."""
        if not step or not step.strip():
            raise InvalidStepFormatException("Empty step")

        # Extract keyword and main step text
        step = step.strip()
        keyword = self._extract_keyword(step)
        step_text = step[len(keyword):].strip()

        if not step_text or step_text.strip() == "":
            raise InvalidStepFormatException("Step is empty or whitespace only.")

        # Try each pattern to find matching step type
        for step_type in StepType:
            pattern = self.PATTERNS.get(step_type.value)
            if not pattern:
                continue

            match = re.search(pattern, step_text.lower())
            if match:
                return self._create_parsed_step(
                    step_type=step_type,
                    match=match,
                    original_text=step,
                    keyword=keyword
                )

        # If no pattern matches, default to verify
        return ParsedStep(
            step_type=StepType.VERIFY,
            target=step_text,
            value=None,
            original_text=step,
            metadata=self._create_metadata(keyword),
            action=StepType.VERIFY.value
        )

    def _extract_keyword(self, step: str) -> str:
        """Extract the Gherkin keyword from the step."""
        words = step.strip().lower().split()
        if not words:
            raise InvalidStepFormatException("Empty step")

        keyword = words[0]
        if keyword not in self.KEYWORDS:
            raise InvalidStepFormatException(f"Invalid step keyword: {keyword}")

        return step[:len(keyword)].strip()

    def _create_parsed_step(
        self,
        step_type: StepType,
        match: re.Match,
        original_text: str,
        keyword: str
    ) -> ParsedStep:
        """Create a ParsedStep instance based on the match."""
        if step_type == StepType.INPUT:
            value = match.group(1)
            target = match.group(2).strip()  # Added strip() to clean up any extra spaces
        else:
            value = None
            target = match.group(1).strip()  # Added strip() to clean up any extra spaces

        # Special handling for wait steps to ensure we capture the full duration
        if step_type == StepType.WAIT:
            if not "second" in target and not "minute" in target:
                target = f"{target} seconds"  # Default to seconds if not specified

        # Special handling for navigate steps
        if step_type == StepType.NAVIGATE:
            if not "page" in target.lower():
                target = f"{target} page"

        return ParsedStep(
            step_type=step_type,
            target=target,
            value=value,
            original_text=original_text,
            metadata=self._create_metadata(keyword),
            action=step_type.value
        )

    def _create_metadata(self, keyword: str) -> Dict[str, Any]:
        """Create metadata for the step."""
        return {
            "keyword": keyword,
            "timestamp": datetime.utcnow().isoformat(),
            "parser_version": "1.0"
        }

class StepParserFactory:
    """Factory for creating step parsers."""

    @staticmethod
    def create_parser(parser_type: str = "gherkin") -> StepParser:
        """Create a step parser of the specified type."""
        parsers = {
            "gherkin": GherkinStepParser
        }

        if parser_type not in parsers:
            raise ValueError(f"Unsupported parser type: {parser_type}")

        return parsers[parser_type]()