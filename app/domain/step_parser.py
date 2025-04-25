# app/domain/step_parser.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import re
import json
from bs4 import BeautifulSoup

from app.utils.logger import get_logger
from app.domain.exceptions import (
    StepParsingException,
    InvalidStepFormatException,
    SnapshotParsingException
)

logger = get_logger(__name__)

class StepType(Enum):
    """Enumeration of possible step types."""
    CLICK = "click"
    INPUT = "input"
    NAVIGATE = "navigate"
    VERIFY = "verify"
    WAIT = "wait"
    CUSTOM = "custom"

@dataclass
class ParsedStep:
    """Represents a parsed test step."""
    original_text: str
    step_type: StepType
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    metadata: Dict[str, Any] = None

class StepParserInterface(ABC):
    """Abstract interface for step parsers."""

    @abstractmethod
    def parse_steps(self, content: str) -> List[ParsedStep]:
        """Parse multiple steps from content."""
        pass

    @abstractmethod
    def parse_single_step(self, step: str) -> ParsedStep:
        """Parse a single step."""
        pass

class GherkinStepParser(StepParserInterface):
    """Parser for Gherkin-style test steps."""

    _STEP_PATTERNS = {
        StepType.NAVIGATE: r"(?i)(?:Given|When|Then|And|But)?\s*(?:I am on|I navigate to|I go to|I visit|I open)\s+(?:the\s+)?(.+?)(?:\s+page)?$",
        StepType.INPUT: r"(?i)(?:Given|When|Then|And|But)?\s*(?:I )?(?:enter|type|fill|input)\s+[\"']([^\"']+)[\"']\s+(?:in(?:to)?|to)\s+(?:the\s+)?(.+?)(?:\s+field)?$",
        StepType.CLICK: r"(?i)(?:Given|When|Then|And|But)?\s*(?:I )?(?:click|press|select|choose)\s+(?:the\s+)?(.+?)(?:\s+button)?$",
        StepType.VERIFY: r"(?i)(?:Given|When|Then|And|But)?\s*(?:I )?(?:verify|check|assert|ensure|should see)\s+(?:that\s+)?(.+)$",
        StepType.WAIT: r"(?i)(?:Given|When|Then|And|But)?\s*(?:I )?wait\s+(?:for\s+)?(.+)$"
    }

    def parse_steps(self, content: str) -> List[ParsedStep]:
        """Parse multiple steps from Gherkin-style content."""
        try:
            # Split content into lines and remove empty ones
            lines = [
                line.strip()
                for line in content.split('\n')
                if line.strip()
            ]

            # Parse each line
            parsed_steps = []
            for line in lines:
                try:
                    parsed_step = self.parse_single_step(line)
                    if parsed_step:
                        parsed_steps.append(parsed_step)
                except InvalidStepFormatException as e:
                    logger.warning(f"Invalid step format: {line}. Error: {str(e)}")
                    continue

            if not parsed_steps:
                raise StepParsingException("No valid steps found in content")

            return parsed_steps

        except Exception as e:
            logger.error(f"Failed to parse steps: {str(e)}")
            raise StepParsingException(f"Failed to parse steps: {str(e)}")

    def parse_single_step(self, step: str) -> ParsedStep:
        """Parse a single Gherkin step."""
        try:
            step = step.strip()
            if not step:
                raise InvalidStepFormatException("Empty step")

            # Try to match step against known patterns
            for step_type, pattern in self._STEP_PATTERNS.items():
                match = re.match(pattern, step)
                if match:
                    return self._create_parsed_step(step, step_type, match)

            # If no pattern matches, log warning and treat as custom step
            logger.warning(f"No pattern match found for step: {step}")
            return ParsedStep(
                original_text=step,
                step_type=StepType.CUSTOM,
                action="custom",
                metadata={"raw_text": step}
            )

        except Exception as e:
            logger.error(f"Failed to parse step: {step}. Error: {str(e)}")
            raise InvalidStepFormatException(f"Invalid step format: {str(e)}")

    def _create_parsed_step(self, original: str, step_type: StepType, match: re.Match) -> ParsedStep:
        """Create ParsedStep object from regex match."""
        try:
            if step_type == StepType.INPUT:
                return ParsedStep(
                    original_text=original,
                    step_type=step_type,
                    action="input",
                    value=match.group(1),
                    target=match.group(2)
                )
            else:
                return ParsedStep(
                    original_text=original,
                    step_type=step_type,
                    action=step_type.value,
                    target=match.group(1)
                )
        except Exception as e:
            logger.error(f"Failed to create parsed step: {str(e)}")
            raise InvalidStepFormatException(f"Failed to create parsed step: {str(e)}")

class StepParserFactory:
    """Factory for creating step parsers."""

    @staticmethod
    def create_parser(parser_type: str = "gherkin") -> StepParserInterface:
        """
        Create step parser instance.

        Args:
            parser_type (str): Type of parser to create

        Returns:
            StepParserInterface: Parser instance

        Raises:
            ValueError: If parser_type is not supported
        """
        parsers = {
            "gherkin": GherkinStepParser
        }

        if parser_type not in parsers:
            raise ValueError(f"Unsupported parser type: {parser_type}")

        return parsers[parser_type]()

@dataclass
class ParsedElement:
    """Represents a parsed HTML element."""
    tag: str
    element_type: Optional[str]
    identifier: Optional[str]
    text_content: Optional[str]
    attributes: Dict[str, str]
    xpath: str
    css_selector: str
    is_clickable: bool = False
    is_visible: bool = True
    metadata: Dict[str, Any] = None

class SnapshotParserInterface(ABC):
    """Abstract interface for HTML snapshot parsers."""

    @abstractmethod
    def parse_snapshot(self, html_content: str) -> List[ParsedElement]:
        """Parse HTML snapshot and extract elements."""
        pass

    @abstractmethod
    def find_element(self, html_content: str, target: str) -> Optional[ParsedElement]:
        """Find specific element in HTML snapshot."""
        pass

class BeautifulSoupSnapshotParser(SnapshotParserInterface):
    """HTML snapshot parser using BeautifulSoup."""

    INTERACTIVE_ELEMENTS = {
        'a', 'button', 'input', 'select', 'textarea', 'label',
        'details', 'dialog', 'menu', 'menuitem', 'option'
    }

    def parse_snapshot(self, html_content: str) -> List[ParsedElement]:
        """
        Parse HTML content and extract relevant elements.

        Args:
            html_content (str): HTML content to parse

        Returns:
            List[ParsedElement]: List of parsed elements

        Raises:
            SnapshotParsingException: If parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            parsed_elements = []

            for element in soup.find_all(True):  # Find all tags
                try:
                    parsed_element = self._parse_element(element)
                    if parsed_element:
                        parsed_elements.append(parsed_element)
                except Exception as e:
                    logger.warning(f"Failed to parse element {element}: {str(e)}")
                    continue

            return parsed_elements

        except Exception as e:
            raise SnapshotParsingException(f"Failed to parse HTML snapshot: {str(e)}")

    def find_element(self, html_content: str, target: str) -> Optional[ParsedElement]:
        """
        Find specific element in HTML content.

        Args:
            html_content (str): HTML content to search in
            target (str): Target element description

        Returns:
            Optional[ParsedElement]: Found element or None

        Raises:
            SnapshotParsingException: If parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Try different search strategies
            element = (
                self._find_by_text(soup, target) or
                self._find_by_id(soup, target) or
                self._find_by_name(soup, target) or
                self._find_by_aria_label(soup, target)
            )

            if element:
                return self._parse_element(element)
            return None

        except Exception as e:
            raise SnapshotParsingException(f"Failed to find element '{target}': {str(e)}")

    def _parse_element(self, element) -> Optional[ParsedElement]:
        """Parse BeautifulSoup element into ParsedElement."""
        try:
            # Get element attributes
            attrs = dict(element.attrs) if hasattr(element, 'attrs') else {}

            # Generate selectors
            css_selector = self._generate_css_selector(element)
            xpath = self._generate_xpath(element)

            # Determine if element is interactive
            is_clickable = (
                element.name in self.INTERACTIVE_ELEMENTS or
                'onclick' in attrs or
                'role' in attrs and attrs['role'] in {'button', 'link', 'menuitem'}
            )

            return ParsedElement(
                tag=element.name,
                element_type=attrs.get('type'),
                identifier=attrs.get('id') or attrs.get('name'),
                text_content=element.get_text(strip=True),
                attributes=attrs,
                xpath=xpath,
                css_selector=css_selector,
                is_clickable=is_clickable,
                is_visible=self._is_visible(element)
            )

        except Exception as e:
            logger.warning(f"Failed to parse element: {str(e)}")
            return None

    def _find_by_text(self, soup: BeautifulSoup, text: str) -> Optional[Any]:
        """Find element by visible text content."""
        return soup.find(lambda tag: tag.get_text(strip=True) == text)

    def _find_by_id(self, soup: BeautifulSoup, id_: str) -> Optional[Any]:
        """Find element by ID."""
        return soup.find(id=id_)

    def _find_by_name(self, soup: BeautifulSoup, name: str) -> Optional[Any]:
        """Find element by name attribute."""
        return soup.find(attrs={"name": name})

    def _find_by_aria_label(self, soup: BeautifulSoup, label: str) -> Optional[Any]:
        """Find element by aria-label attribute."""
        return soup.find(attrs={"aria-label": label})

    def _generate_css_selector(self, element) -> str:
        """Generate CSS selector for element."""
        selectors = []
        current = element

        while current and current.name:
            # Add tag
            current_selector = current.name

            # Add ID if present
            if 'id' in current.attrs:
                current_selector += f"#{current['id']}"
                selectors.insert(0, current_selector)
                break

            # Add classes if present
            if 'class' in current.attrs:
                classes = '.'.join(current['class'])
                current_selector += f".{classes}"

            # Add position
            if current.parent:
                siblings = current.parent.find_all(current.name, recursive=False)
                if len(siblings) > 1:
                    position = siblings.index(current) + 1
                    current_selector += f":nth-of-type({position})"

            selectors.insert(0, current_selector)
            current = current.parent

        return ' > '.join(selectors)

    def _generate_xpath(self, element) -> str:
        """Generate XPath for element."""
        components = []
        current = element

        while current and current.name:
            # Add tag
            current_xpath = current.name

            # Add position if needed
            if current.parent:
                siblings = current.parent.find_all(current.name, recursive=False)
                if len(siblings) > 1:
                    position = siblings.index(current) + 1
                    current_xpath += f"[{position}]"

            components.insert(0, current_xpath)
            current = current.parent

        return '//' + '/'.join(components)

    def _is_visible(self, element) -> bool:
        """Determine if element is likely visible."""
        style = element.get('style', '').lower()
        return not (
            'display: none' in style or
            'visibility: hidden' in style or
            element.get('hidden') is not None or
            element.get('aria-hidden') == 'true'
        )

class SnapshotParserFactory:
    """Factory for creating snapshot parsers."""

    @staticmethod
    def create_parser(parser_type: str = "beautifulsoup") -> SnapshotParserInterface:
        """
        Create snapshot parser instance.

        Args:
            parser_type (str): Type of parser to create.
                             Supported types: ["beautifulsoup", "html", "bs4"]

        Returns:
            SnapshotParserInterface: Parser instance

        Raises:
            ValueError: If parser_type is not supported
        """
        # Define parser mappings (including aliases)
        parsers = {
            "beautifulsoup": BeautifulSoupSnapshotParser,
            "html": BeautifulSoupSnapshotParser,  # alias
            "bs4": BeautifulSoupSnapshotParser,   # alias
        }

        # Normalize parser type
        parser_type = parser_type.lower()

        if parser_type not in parsers:
            raise ValueError(
                f"Unsupported parser type: {parser_type}. "
                f"Supported types are: {list(parsers.keys())}"
            )

        return parsers[parser_type]()