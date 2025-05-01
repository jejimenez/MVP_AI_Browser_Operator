# app/infrastructure/html_summarizer.py
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup, Comment, NavigableString
from app.utils.config import HTML_SUMMARIZER_CONFIG
from app.infrastructure.interfaces import HTMLSummarizerInterface
import logging

logger = logging.getLogger('app.infrastructure.html_summarizer')

class HTMLSummarizer(HTMLSummarizerInterface):
    """Converts HTML to a JSON DOM for visible elements, compatible with Playwright.

    Responsibilities:
    - Parse HTML using a configurable parser (default: lxml).
    - Filter visible elements based on style and attributes.
    - Map tags to accessibility roles and extract names.
    - Produce a JSON structure for AI-driven Playwright instructions.
    """
    def __init__(self, parser: str = 'lxml', config: Dict = HTML_SUMMARIZER_CONFIG):
        """Initialize with parser and configuration.

        Args:
            parser: BeautifulSoup parser ('lxml', 'html5lib', etc.).
            config: Configuration dict with role_map, input_type_map, and visible_attributes.
        """
        self.parser = parser
        self.role_map = config['role_map']
        self.input_type_map = config['input_type_map']
        self.visible_attributes = config['visible_attributes']

    def is_visible(self, element: BeautifulSoup) -> bool:
        """Check if an element is visible based on style, attributes, or content."""
        logger.debug(f"Checking visibility for element: {element.name}, attrs: {element.attrs}")
        if isinstance(element, (Comment, NavigableString)):
            logger.debug("Skipping comment or string")
            return False
        style = element.get('style', '')
        if 'display: none' in style or 'visibility: hidden' in style or 'opacity: 0' in style:
            logger.debug("Invisible due to style")
            return False
        if element.get('hidden') or element.get('aria-hidden') == 'true':
            logger.debug("Invisible due to hidden or aria-hidden")
            return False
        interactive = element.name in ['a', 'button', 'input', 'select', 'textarea'] or \
                      element.get('role') in ['button', 'link', 'textbox', 'combobox', 'menuitem', 'tab']
        if interactive:
            logger.debug("Visible as interactive element")
            return True
        if element.name in ['img', 'svg', 'canvas', 'iframe']:
            logger.debug("Visible as special element")
            return True
        text = element.get_text(strip=True)
        if not text and not element.find_all(recursive=False):
            logger.debug("Invisible: no text or children")
            return False
        if element.find_all(recursive=False):
            for child in element.find_all(recursive=False):
                if self.is_visible(child):
                    logger.debug("Visible due to visible child")
                    return True
        return bool(text)

    def tag_to_role(self, tag_name: str, element: BeautifulSoup) -> Optional[str]:
        """Map an HTML tag to an accessibility role."""
        if element.get('role'):
            logger.debug(f"Using explicit role: {element['role']}")
            return element['role']
        tag_name = tag_name.lower()
        if tag_name == 'input':
            input_type = element.get('type', 'text')
            role = self.input_type_map.get(input_type, 'textbox')
            logger.debug(f"Input type {input_type} mapped to role: {role}")
            return role
        role = self.role_map.get(tag_name, 'generic')
        logger.debug(f"Tag {tag_name} mapped to role: {role}")
        return role

    def get_name(self, element: BeautifulSoup, text: str) -> str:
        """Extract an accessible name for an element."""
        logger.debug(f"Getting name for element: {element.name}, text: {text}, attrs: {element.attrs}")
        if not hasattr(element, 'attrs'):
            logger.warning(f"Element {element} has no attributes")
            return ''

        # Robust aria-label check
        aria_label = element.get('aria-label', '').strip()
        if not aria_label:
            for attr in element.attrs:
                if attr.lower() == 'aria-label':
                    aria_label = element.attrs[attr].strip()
                    break
        if aria_label:
            logger.debug(f"Name from aria-label: {aria_label}")
            return aria_label

        # Direct text for non-generic roles
        role = self.tag_to_role(element.name, element)
        direct_text = element.string.strip() if element.string else ''
        if direct_text and role != 'generic':
            logger.debug(f"Name from direct text: {direct_text}")
            return direct_text

        # Child text for generic roles without child elements
        if role == 'generic':
            child_elements = element.find_all(recursive=False)
            if not child_elements and text:
                logger.debug(f"Name from child text for generic role: {text}")
                return text
            logger.debug(f"Skipping child text for generic role with {len(child_elements)} children")

        # Special cases
        if element.name == 'img':
            name = element.get('alt', '').strip()
            logger.debug(f"Name from alt: {name}")
            return name
        if element.name in ['input', 'textarea', 'select']:
            name = (element.get('aria-label', '').strip() or
                    element.get('value', '').strip() or
                    element.get('placeholder', '').strip() or  # Moved placeholder before name
                    element.get('name', '').strip())
            logger.debug(f"Name for input/textarea/select: {name}")
            return name
        if element.name == 'iframe':
            name = element.get('title', '').strip()
            logger.debug(f"Name from title: {name}")
            return name

        logger.debug("No name found")
        return ''

    def element_to_json(self, element: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Convert an element to JSON representation."""
        if not self.is_visible(element):
            logger.debug(f"Skipping invisible element: {element.name}")
            return None
        if not element.name:
            logger.warning(f"Skipping element with no tag name: {element}")
            return None

        text = element.get_text(strip=True)
        role = self.tag_to_role(element.name, element)
        if role is None:
            logger.debug(f"Filtering out element with no role: {element.name}")
            return None

        attributes = {
            key: value for key, value in element.attrs.items()
            if key in self.visible_attributes
        }
        if 'class' in attributes and isinstance(attributes['class'], list):
            attributes['class'] = ' '.join(attributes['class'])
        logger.debug(f"Attributes for {element.name}: {attributes}")

        name = self.get_name(element, text)
        node = {'role': role, 'name': name}
        if attributes:
            node['attributes'] = attributes

        # Heading level
        if role == 'heading':
            if 'aria-level' in attributes:
                try:
                    node['level'] = int(attributes['aria-level'])
                except ValueError:
                    node['level'] = 1
                    logger.debug(f"Invalid aria-level: {attributes['aria-level']}, defaulting to 1")
            else:
                node['level'] = int(element.name[1]) if element.name.startswith('h') and element.name[1].isdigit() else 1
            logger.debug(f"Assigned heading level: {node['level']}")

        # Focused state
        if element.get('focused') == 'true' or (
            element.name in ['input', 'textarea'] and
            element == element.find_parent().find(focus=True)
        ):
            node['focused'] = True

        # Popup
        if element.get('haspopup'):
            node['haspopup'] = element['haspopup']

        # Children
        children = [
            child_json for child in element.find_all(recursive=False)
            if (child_json := self.element_to_json(child))
        ]
        if children:
            node['children'] = children

        # Text role override
        if text and role == 'text' and text != name and 'aria-label' not in attributes:
            node = {'role': 'text', 'name': text}
            logger.debug(f"Overwriting name for role=text to: {text}")

        logger.debug(f"Processed element: {element.name}, role: {role}, name: {node['name']}, children: {len(children)}")
        return node

    def summarize_html(self, html_content: str) -> Dict[str, Any]:
        """Convert HTML to JSON DOM for visible elements.

        Args:
            html_content: HTML string to process.

        Returns:
            Dict: JSON representation of visible DOM elements.

        Raises:
            ValueError: If html_content is None.
        """
        if html_content is None:
            logger.error("html_content is None")
            raise ValueError("html_content cannot be None")

        try:
            soup = BeautifulSoup(html_content, self.parser)
            logger.debug(f"Parsed HTML with {self.parser}")
        except Exception as e:
            logger.warning(f"Parsing error with {self.parser}: {str(e)}. Falling back to html5lib.")
            try:
                soup = BeautifulSoup(html_content, 'html5lib')
                logger.debug("Parsed HTML with html5lib fallback")
            except Exception as fallback_e:
                logger.error(f"Fallback parser failed: {str(fallback_e)}")
                return {'role': 'WebArea', 'name': '', 'children': []}

        root = soup.find('body') or soup
        if not root:
            logger.warning("No body or root element found in HTML")
            return {'role': 'WebArea', 'name': '', 'children': []}

        json_result = self.element_to_json(root)
        title = soup.title.get_text(separator=' ', strip=True) if soup.title else ''
        logger.debug(f"Title extracted: {title}")

        if not json_result:
            return {'role': 'WebArea', 'name': title, 'children': []}

        json_result['role'] = 'WebArea'
        json_result['name'] = title
        return json_result

    def load_test_html(self, file_path: str) -> str:
        """Load HTML from a file for testing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError as e:
            logger.error(f"Test HTML file not found: {file_path}")
            raise