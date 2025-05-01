# src/operateXRayTestCases/tests/test_html_parser.py
import pytest
from bs4 import BeautifulSoup, Comment, NavigableString
from app.infrastructure.html_summarizer import HTMLSummarizer
from pathlib import Path

def create_soup(html):
    return BeautifulSoup(html, 'lxml')  # Updated to lxml for consistency

@pytest.fixture
def summarizer():
    """Fixture for HTMLSummarizer instance."""
    return HTMLSummarizer(parser='lxml')

@pytest.fixture
def simple_html():
    return """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Heading</h1>
            <p>Paragraph text</p>
            <a href="/link">Click me</a>
            <div style="display: none;">Hidden div</div>
            <input type="text" value="Input value" aria-label="Search input">
            <img src="image.jpg" alt="Test image">
        </body>
    </html>
    """

def test_summarize_html_basic(simple_html, summarizer):
    """Test basic HTML conversion with visible elements."""
    result = summarizer.summarize_html(simple_html)
    assert result["role"] == "WebArea"
    assert result["name"] == "Test Page"
    children = result["children"]
    assert len(children) == 5  # h1, p, a, input, img
    assert children[0] == {"role": "heading", "name": "Main Heading", "level": 1}
    assert children[1] == {"role": "text", "name": "Paragraph text"}
    assert children[2] == {
        "role": "link",
        "name": "Click me",
        "attributes": {"href": "/link"}
    }
    assert children[3] == {
        "role": "textbox",
        "name": "Search input",
        "attributes": {"type": "text", "value": "Input value", "aria-label": "Search input"}
    }
    assert children[4] == {
        "role": "img",
        "name": "Test image",
        "attributes": {"src": "image.jpg", "alt": "Test image"}
    }

def test_input_element(summarizer):
    """Test processing of input element with aria-label."""
    html = """
    <body>
        <input type="text" value="Input value" aria-label="Search input">
    </body>
    """
    result = summarizer.summarize_html(html)
    assert len(result["children"]) == 1
    assert result["children"][0] == {
        "role": "textbox",
        "name": "Search input",
        "attributes": {"type": "text", "value": "Input value", "aria-label": "Search input"}
    }

def test_title_edge_cases(summarizer):
    html = "<html><head><title></title></head><body><p>Text</p></body>"
    result = summarizer.summarize_html(html)
    assert result["name"] == ""
    
    html = "<html><head></head><body><p>Text</p></body>"
    result = summarizer.summarize_html(html)
    assert result["name"] == ""
    
    html = "<html><head><title>Test <!-- comment --> Page</title></head><body><p>Text</p></body>"
    result = summarizer.summarize_html(html)
    assert result["name"] == "Test Page"

def test_invisible_elements(summarizer):
    html = "<body><div style='display: none;'>Hidden</div><p>Visible</p></body>"
    result = summarizer.summarize_html(html)
    assert len(result["children"]) == 1
    assert result["children"][0] == {"role": "text", "name": "Visible"}

def test_role_mapping(summarizer):
    """Test ARIA role mapping for various elements."""
    html = """
    <body>
        <a href="#">Link</a>
        <button>Button</button>
        <input type="checkbox">
        <select><option>Option</option></select>
        <h2>Heading</h2>
        <nav>Navigation</nav>
        <img src="img.jpg" alt="Image">
        <div role="custom">Custom</div>
    </body>
    """
    result = summarizer.summarize_html(html)
    children = result["children"]
    assert children[0]["role"] == "link"
    assert children[1]["role"] == "button"
    assert children[2]["role"] == "checkbox"
    assert children[3]["role"] == "combobox"
    assert children[4]["role"] == "heading"
    assert children[5]["role"] == "navigation"
    assert children[6]["role"] == "img"
    assert children[7]["role"] == "custom"  # Explicit role overrides

def test_name_extraction(summarizer):
    """Test accessible name extraction (aria-label, text, alt, value)."""
    html = """
    <body>
        <p aria-label="Custom label">Text</p>
        <img src="img.jpg" alt="Image alt">
        <input type="text" value="Input value">
        <iframe title="Frame title"></iframe>
        <p>Plain text</p>
    </body>
    """
    result = summarizer.summarize_html(html)
    children = result["children"]
    assert children[0]["name"] == "Custom label"  # aria-label
    assert children[1]["name"] == "Image alt"  # alt
    assert children[2]["name"] == "Input value"  # value
    assert children[3]["name"] == "Frame title"  # title
    assert children[4]["name"] == "Plain text"  # text

def test_nested_elements(summarizer):
    """Test nested visible elements with children."""
    html = """
    <body>
        <div>
            <h3>Subheading</h3>
            <p>Nested text</p>
            <span style="display: none;">Hidden</span>
        </div>
    </body>
    """
    result = summarizer.summarize_html(html)
    assert result["role"] == "WebArea"
    assert len(result["children"]) == 1
    div = result["children"][0]
    assert div["role"] == "generic"
    assert len(div["children"]) == 2  # h3, p
    assert div["children"][0] == {"role": "heading", "name": "Subheading", "level": 3}
    assert div["children"][1] == {"role": "text", "name": "Nested text"}

def test_empty_or_malformed_html(summarizer):
    """Test handling of empty or malformed HTML."""
    # Empty HTML
    result = summarizer.summarize_html("")
    assert result == {"role": "WebArea", "name": "", "children": []}

    # Malformed HTML
    result = summarizer.summarize_html("<div>Unclosed tag")
    assert result["role"] == "WebArea"
    assert result["children"][0]["role"] == "generic"
    assert result["children"][0]["name"] == "Unclosed tag"

def test_comments_and_strings(summarizer):
    """Test that comments and navigable strings are ignored."""
    html = """
    <body>
        <!-- This is a comment -->
        Text outside tags
        <p>Visible text</p>
    </body>
    """
    result = summarizer.summarize_html(html)
    assert len(result["children"]) == 1  # Only <p>
    assert result["children"][0] == {"role": "text", "name": "Visible text"}

def test_interactive_elements(summarizer):
    """Test visibility of interactive elements without text."""
    html = """
    <body>
        <button></button>
        <input type="submit">
        <a href="#"></a>
    </body>
    """
    result = summarizer.summarize_html(html)
    assert len(result["children"]) == 3
    assert result["children"][0]["role"] == "button"
    assert result["children"][1]["role"] == "button"  # submit input
    assert result["children"][2]["role"] == "link"

def test_attributes_filtering(summarizer):
    """Test that only relevant attributes are included."""
    html = """
    <body>
        <div id="main" class="container primary" data-custom="value" aria-label="Main div">Text</div>
    </body>
    """
    result = summarizer.summarize_html(html)
    div = result["children"][0]
    assert div["attributes"] == {
        "id": "main",
        "class": "container primary",
        "aria-label": "Main div"
    }

def test_heading_levels(summarizer):
    """Test heading levels for h1-h6."""
    html = """
    <body>
        <h1>One</h1>
        <h3>Three</h3>
        <div role="heading" aria-level="2">Custom</div>
    </body>
    """
    result = summarizer.summarize_html(html)
    assert result["children"][0]["level"] == 1
    assert result["children"][1]["level"] == 3
    assert result["children"][2]["level"] == 2

def test_error_handling(summarizer):
    """Test error handling for invalid input."""
    # Simulate parsing error by passing None
    with pytest.raises(ValueError):
        summarizer.summarize_html(None)

def test_example_page(summarizer):
    """Test processing of example_page.html with login form."""
    # Use load_test_html to read HTML file
    html_file = Path(__file__).parent.parent / "test_data" / "snapshots" / "example_page.html"
    html_content = summarizer.load_test_html(str(html_file))
    
    result = summarizer.summarize_html(html_content)
    assert result["role"] == "WebArea"
    assert result["name"] == ""  # No <title> tag
    assert len(result["children"]) == 1  # <div>
    
    div = result["children"][0]
    assert div["role"] == "generic"
    assert div["name"] == ""
    assert div["attributes"] == {"id": "login-form"}
    assert len(div["children"]) == 2  # <input>, <button>
    
    input_elem = div["children"][0]
    assert input_elem["role"] == "textbox"
    assert input_elem["name"] == "Email"  # From placeholder
    assert input_elem["attributes"] == {
        "type": "email",
        "name": "email",
        "placeholder": "Email"
    }
    
    button = div["children"][1]
    assert button["role"] == "button"
    assert button["name"] == "Login"
    assert button["attributes"] == {"id": "login-button"}