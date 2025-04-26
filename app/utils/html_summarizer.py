from bs4 import BeautifulSoup, Comment, NavigableString

def html_to_json_visible(html_content):
    """
    Convert HTML content to a JSON representation, including only visible elements.
    Produces a structure similar to Playwright's accessibility snapshot with roles, names, and attributes.
    
    Args:
        html_content (str): HTML string (e.g., from get_html).
    
    Returns:
        dict: JSON representation of visible DOM elements.
    """
    def is_visible(element):
        """Check if an element is visible (not hidden by CSS or attributes)."""
        if isinstance(element, (Comment, NavigableString)):
            return False
        style = element.get('style', '')
        if 'display: none' in style or 'visibility: hidden' in style:
            return False
        if element.get('hidden') or element.get('aria-hidden') == 'true':
            return False
        # Check if element has meaningful content (text or interactive)
        text = element.get_text(strip=True)
        interactive = element.name in ['a', 'button', 'input', 'select', 'textarea'] or element.get('role') in ['button', 'link', 'textbox', 'combobox']
        return bool(text or interactive or element.find_all(recursive=False))

    def tag_to_role(tag_name, element):
        """Map HTML tag to ARIA role, similar to Playwright's accessibility snapshot."""
        role_map = {
            'a': 'link',
            'button': 'button',
            'input': 'textbox' if element.get('type') in ['text', 'search', 'email', 'password'] else 'checkbox' if element.get('type') == 'checkbox' else 'radio' if element.get('type') == 'radio' else None,
            'select': 'combobox',
            'textarea': 'textbox',
            'h1': 'heading',
            'h2': 'heading',
            'h3': 'heading',
            'h4': 'heading',
            'h5': 'heading',
            'h6': 'heading',
            'div': 'generic',
            'span': 'generic',
            'p': 'text',
            'nav': 'navigation',
            'form': 'form',
            'search': 'searchbox'
        }
        # Use explicit role attribute if present
        if element.get('role'):
            return element['role']
        return role_map.get(tag_name.lower(), 'generic')

    def element_to_json(element):
        """Recursively convert a BeautifulSoup element to JSON."""
        if not is_visible(element):
            return None
        
        # Extract text content (visible text only)
        text = element.get_text(strip=True)
        # Map tag to ARIA role
        role = tag_to_role(element.name, element)
        # Extract relevant attributes
        attributes = {
            key: value for key, value in element.attrs.items()
            if key in ['id', 'class', 'href', 'aria-label', 'data-testid', 'role', 'type', 'value']
        }
        if 'class' in attributes:
            attributes['class'] = ' '.join(attributes['class']) if isinstance(attributes['class'], list) else attributes['class']
        
        # Determine name (text, aria-label, or value)
        name = element.get('aria-label', text or element.get('value', ''))
        
        # Build JSON node
        node = {
            'role': role,
            'name': name,
        }
        if attributes:
            node['attributes'] = attributes
        if role == 'heading':
            node['level'] = int(element.name[1]) if element.name.startswith('h') and element.name[1].isdigit() else 1
        if element.get('focused') == 'true' or element.name in ['input', 'textarea'] and element == element.find_parent().find(focus=True):
            node['focused'] = True
        if element.get('haspopup'):
            node['haspopup'] = element['haspopup']
        
        # Process children
        children = []
        for child in element.find_all(recursive=False):
            child_json = element_to_json(child)
            if child_json:
                children.append(child_json)
        if children:
            node['children'] = children
        
        # Add text nodes for non-empty text content
        if text and role == 'text':
            node = {'role': 'text', 'name': text}
        
        return node if node.get('children') or node.get('name') or node.get('role') != 'generic' else None

    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        # Find the root element (e.g., body or specific div)
        root = soup.find('body') or soup
        if not root:
            return {'role': 'WebArea', 'name': '', 'children': []}
        
        # Convert to JSON
        json_result = element_to_json(root)
        if not json_result:
            json_result = {'role': 'WebArea', 'name': soup.title.string if soup.title else '', 'children': []}
        else:
            json_result['role'] = 'WebArea'
            json_result['name'] = soup.title.string if soup.title else ''
        
        return json_result
    except Exception as e:
        print(f"Error in html_to_json_visible: {e}")
        return {'role': 'WebArea', 'name': '', 'children': []}