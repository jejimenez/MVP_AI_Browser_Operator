from bs4 import BeautifulSoup, Comment, NavigableString
import re
from collections import Counter
import os
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

def HTMLSummarizer(html_content, max_lines=500):
    soup = BeautifulSoup(html_content, "html.parser")
    wan_lines = []

    # Page title
    title = soup.title.string if soup.title else "Untitled"
    wan_lines.append(f"[Page: {title}]")

    # Sections with IDs
    for section in soup.find_all(["div", "aside", "nav", "main", "section"], id=True):
        attrs = [f"id={section.get('id')}"]
        if section.get("class"):
            attrs.append(f"class={' '.join(section.get('class'))}")
        wan_lines.append(f"  [Section: {section.name.capitalize()} | {', '.join(attrs)}]")

        # Links within section
        for link in section.find_all("a", recursive=True)[:5]:
            attrs = [f"href={link.get('href', '')}"]
            if link.get("id"): attrs.append(f"id={link.get('id')}")
            if link.get("class"): attrs.append(f"class={' '.join(link.get('class'))}")
            data_attrs = {k: v for k, v in link.attrs.items() if k.startswith("data-")}
            if data_attrs: attrs.append(f"data={data_attrs}")
            text = link.get_text(strip=True) or "Unnamed Link"
            wan_lines.append(f"    [Link: {text} | {', '.join(attrs)}]")

        # Buttons within section
        for button in section.find_all("button", recursive=True)[:5]:
            attrs = []
            if button.get("id"): attrs.append(f"id={button.get('id')}")
            if button.get("class"): attrs.append(f"class={' '.join(button.get('class'))}")
            data_attrs = {k: v for k, v in button.attrs.items() if k.startswith("data-")}
            if data_attrs: attrs.append(f"data={data_attrs}")
            text = button.get_text(strip=True) or ""
            wan_lines.append(f"    [Button: {text} | {', '.join(attrs)}]")

    # Standalone inputs
    for input_elem in soup.find_all("input"):
        attrs = []
        if input_elem.get("class"): attrs.append(f"class={' '.join(input_elem.get('class'))}")
        if input_elem.get("aria-label"): attrs.append(f"aria-label={input_elem.get('aria-label')}")
        if input_elem.get("placeholder"): attrs.append(f"placeholder={input_elem.get('placeholder')}")
        data_attrs = {k: v for k, v in input_elem.attrs.items() if k.startswith("data-")}
        if data_attrs: attrs.append(f"data={data_attrs}")
        wan_lines.append(f"  [Input: Input | {', '.join(attrs)}]")

    # Limit output
    return "\n".join(wan_lines[:max_lines])

def html_to_wan(html_content, max_lines=10000):

    soup = BeautifulSoup(html_content, "html.parser")
    wan_lines = []

    # Page title
    title = soup.title.string if soup.title else "Untitled"
    wan_lines.append(f"[Page: {title}]")

    # Sections with IDs
    for section in soup.find_all(["div", "aside", "nav", "main", "section"], id=True):
        attrs = [f"id={section.get('id')}"]
        if section.get("class"):
            attrs.append(f"class={' '.join(section.get('class'))}")
        wan_lines.append(f"  [Section: {section.name.capitalize()} | {', '.join(attrs)}]")

        # Links within section
        for link in section.find_all("a", recursive=True)[:5]:
            attrs = [f"href={link.get('href', '')}"]
            if link.get("id"): attrs.append(f"id={link.get('id')}")
            if link.get("class"): attrs.append(f"class={' '.join(link.get('class'))}")
            data_attrs = {k: v for k, v in link.attrs.items() if k.startswith("data-")}
            if data_attrs: attrs.append(f"data={data_attrs}")
            text = link.get_text(strip=True) or "Unnamed Link"
            wan_lines.append(f"    [Link: {text} | {', '.join(attrs)}]")

        # Buttons within section
        for button in section.find_all("button", recursive=True)[:5]:
            attrs = []
            if button.get("id"): attrs.append(f"id={button.get('id')}")
            if button.get("class"): attrs.append(f"class={' '.join(button.get('class'))}")
            data_attrs = {k: v for k, v in button.attrs.items() if k.startswith("data-")}
            if data_attrs: attrs.append(f"data={data_attrs}")
            text = button.get_text(strip=True) or ""
            wan_lines.append(f"    [Button: {text} | {', '.join(attrs)}]")

    # Standalone inputs
    for input_elem in soup.find_all("input"):
        attrs = []
        if input_elem.get("class"): attrs.append(f"class={' '.join(input_elem.get('class'))}")
        if input_elem.get("aria-label"): attrs.append(f"aria-label={input_elem.get('aria-label')}")
        if input_elem.get("placeholder"): attrs.append(f"placeholder={input_elem.get('placeholder')}")
        data_attrs = {k: v for k, v in input_elem.attrs.items() if k.startswith("data-")}
        if data_attrs: attrs.append(f"data={data_attrs}")
        wan_lines.append(f"  [Input: Input | {', '.join(attrs)}]")

    return "\n".join(wan_lines[:max_lines])

def html_to_wan_visible(html_content, max_lines=1000):
    soup = BeautifulSoup(html_content, "html.parser")
    wan_lines = []

    # Page title
    title = soup.title.string if soup.title else "Untitled"
    wan_lines.append(f"[Page: {title}]")

    # Define visible sections
    visible_sections = [
        "application-sidebar", "top-navigation", "main-content", "system-tab-header",
        "system-dashboard-orgs-widget-table", "system-dashboard-router"
    ]

    def is_element_visible(elem):
        """Check if an element is likely visible based on DOM attributes."""
        # Check for display: none or visibility: hidden in the element or its parents
        current = elem
        while current and current.name != '[document]':
            style = current.get("style", "")
            # Only mark as invisible if explicitly hidden
            if "display: none" in style or "visibility: hidden" in style:
                return False
            # Skip opacity check for now, as it might be too strict for clickable elements
            current = current.parent
        return True

    # Process sections
    for section in soup.find_all(["div", "aside", "nav", "main", "section"], id=True):
        section_id = section.get("id")
        if any(keyword in section_id for keyword in ["modal", "editor", "tab-pane", "tab-container"]) and section_id not in visible_sections:
            continue
        if section.get("style") and "display: none" in section.get("style"):
            continue

        attrs = [f"id={section_id}"] if section_id else []
        if section.get("class"):
            attrs.append(f"class={' '.join(section.get('class'))}")
        if section.get("aria-label"):
            attrs.append(f"aria-label={section.get('aria-label')}")
        data_attrs = {k: v for k, v in section.attrs.items() if k.startswith("data-")}
        if data_attrs:
            attrs.append(f"data={data_attrs}")
        wan_lines.append(f"  [Section: {section.name.capitalize()} | {', '.join(attrs)}]")

        # Special handling for sidebar menu
        sidebar_menu = section.find("ul", class_="css-qdbqrm e1e4nj5n2")
        if sidebar_menu:
            for item in sidebar_menu.find_all(["a", "button"], recursive=True):
                link_text = item.get("aria-label", item.get_text(strip=True)) or "Unnamed Link"
                attrs = []
                if item.name == "a":
                    attrs.append(f"href={item.get('href', '')}")
                if item.get("id"): attrs.append(f"id={item.get('id')}")
                if item.get("class"): attrs.append(f"class={' '.join(item.get('class'))}")
                data_attrs = {k: v for k, v in item.attrs.items() if k.startswith("data-")}
                if data_attrs: attrs.append(f"data={data_attrs}")
                visible = is_element_visible(item)
                attrs.append(f"visible={str(visible).lower()}")
                wan_lines.append(f"    [Link: {link_text} | {', '.join(attrs)}]")

        # Special handling for Administration navigation menu
        admin_nav = section.find("nav", attrs={"aria-label": "Administration navigation"})
        if admin_nav:
            for top_level in admin_nav.find_all("div", class_="css-1owdrxr eu2udwo9", recursive=True):
                top_link = top_level.find("a", attrs={"data-test-subtab": "subtab-title"})
                if top_link:
                    link_text = top_link.find("span").get_text(strip=True) if top_link.find("span") else "Unnamed Link"
                    attrs = [f"href={top_link.get('href', '')}"]
                    if top_link.get("class"): attrs.append(f"class={' '.join(top_link.get('class'))}")
                    data_attrs = {k: v for k, v in top_link.attrs.items() if k.startswith("data-")}
                    if data_attrs: attrs.append(f"data={data_attrs}")
                    visible = is_element_visible(top_link)
                    attrs.append(f"visible={str(visible).lower()}")
                    wan_lines.append(f"    [Link: {link_text} | {', '.join(attrs)}]")

                expand_button = top_level.find("button", attrs={"data-test-icons": "open-arrow"})
                if expand_button:
                    button_text = expand_button.get("aria-label", "Unnamed Button")
                    attrs = []
                    if expand_button.get("class"): attrs.append(f"class={' '.join(expand_button.get('class'))}")
                    data_attrs = {k: v for k, v in expand_button.attrs.items() if k.startswith("data-")}
                    if data_attrs: attrs.append(f"data={data_attrs}")
                    visibility = "true" if "Collapse" in button_text else "false"
                    visible = is_element_visible(expand_button) and visibility == "true"
                    attrs.append(f"visible={str(visible).lower()}")
                    wan_lines.append(f"      [Button: {button_text} | {', '.join(attrs)}]")

                sub_links_container = top_level.find_next_sibling("div", class_="css-dgg5yp eu2udwo10")
                if sub_links_container:
                    container_attrs = [f"class={' '.join(sub_links_container.get('class', []))}"]
                    wan_lines.append(f"      [Sub-Container: Sub-Links | {', '.join(container_attrs)}]")
                    sub_link_index = 0
                    for sub_link in sub_links_container.find_all("a", attrs={"data-test-subtab": "subtab-links"}):
                        sub_link_text = sub_link.find("span").get_text(strip=True) if sub_link.find("span") else "Unnamed Sub-Link"
                        attrs = [f"href={sub_link.get('href', '')}"]
                        attrs.append(f"text={sub_link_text}")
                        attrs.append(f"index={sub_link_index}")
                        if sub_link.get("class"): attrs.append(f"class={' '.join(sub_link.get('class'))}")
                        data_attrs = {k: v for k, v in sub_link.attrs.items() if k.startswith("data-")}
                        if data_attrs: attrs.append(f"data={data_attrs}")
                        parent_ref = f"parent={link_text}"
                        attrs.append(parent_ref)
                        visibility = "true" if expand_button and "Collapse" in expand_button.get("aria-label", "") else "false"
                        visible = is_element_visible(sub_link) and visibility == "true"
                        attrs.append(f"visible={str(visible).lower()}")
                        wan_lines.append(f"        [Sub-Link: {sub_link_text} | {', '.join(attrs)}]")
                        sub_link_index += 1

        # Special handling for app cards
        apps = section.find("div", attrs={"data-testid": os.getenv('SPECIAL_DIV')})
        if apps:
            app_index = 0
            for app_card in apps.find_all("button", attrs={"data-testid": "app-card"}):
                # Extract the app name from the h3 and use it as the button's text
                app_name_elem = app_card.find("h3", attrs={"data-testid": "styled-text-div"})
                app_name = app_name_elem.find("span").get_text(strip=True) if app_name_elem and app_name_elem.find("span") else "Unnamed App"
                attrs = [f"index={app_index}"]
                if app_card.get("class"): attrs.append(f"class={' '.join(app_card.get('class'))}")
                data_attrs = {k: v for k, v in app_card.attrs.items() if k.startswith("data-")}
                if data_attrs: attrs.append(f"data={data_attrs}")
                attrs.append(f"text={app_name}")
                visible = is_element_visible(app_card)
                attrs.append(f"visible={str(visible).lower()}")
                wan_lines.append(f"    [Button: | {', '.join(attrs)}]")

                # Child: App status div
                app_status_div = app_card.find("div", attrs={"data-testid": lambda x: x and isinstance(x, str) and ("-enabled" in x or "-disabled" in x)})
                if app_status_div:
                    status_attrs = []
                    data_attrs = {k: v for k, v in app_status_div.attrs.items() if k.startswith("data-")}
                    if data_attrs: status_attrs.append(f"data={data_attrs}")
                    visible = is_element_visible(app_status_div)
                    status_attrs.append(f"visible={str(visible).lower()}")
                    wan_lines.append(f"      [Child: Div | {', '.join(status_attrs)}]")

                    # Child: Status (span)
                    app_status_elem = app_status_div.find("div", attrs={"data-testid": "app-status"})
                    if app_status_elem:
                        app_status = app_status_elem.find("span").get_text(strip=True) if app_status_elem.find("span") else "Unknown Status"
                        status_attrs = []
                        visible = is_element_visible(app_status_elem)
                        status_attrs.append(f"visible={str(visible).lower()}")
                        wan_lines.append(f"        [Child: Span | text={app_status}, {', '.join(status_attrs)}]")

                    # Child: Early access (span)
                    early_access_elem = app_status_div.find("span", class_="css-urb1ba e1ia73k00")
                    if early_access_elem:
                        early_access_text = early_access_elem.get_text(strip=True)
                        early_access_attrs = []
                        if early_access_elem.get("class"): early_access_attrs.append(f"class={' '.join(early_access_elem.get('class'))}")
                        visible = is_element_visible(early_access_elem)
                        early_access_attrs.append(f"visible={str(visible).lower()}")
                        wan_lines.append(f"        [Child: Span | text={early_access_text}, {', '.join(early_access_attrs)}]")

                # Child: App description
                app_desc_div = app_card.find("div", attrs={"data-testid": "app-description"})
                if app_desc_div:
                    desc_attrs = []
                    data_attrs = {k: v for k, v in app_desc_div.attrs.items() if k.startswith("data-")}
                    if data_attrs: desc_attrs.append(f"data={data_attrs}")
                    visible = is_element_visible(app_desc_div)
                    desc_attrs.append(f"visible={str(visible).lower()}")
                    wan_lines.append(f"      [Child: Div | {', '.join(desc_attrs)}]")

                    # Child: Description text (p)
                    app_desc_elem = app_desc_div.find("p", attrs={"data-testid": "styled-text-div"})
                    if app_desc_elem:
                        app_desc = app_desc_elem.find("span").get_text(strip=True) if app_desc_elem.find("span") else "No Description"
                        desc_text_attrs = []
                        data_attrs = {k: v for k, v in app_desc_elem.attrs.items() if k.startswith("data-")}
                        if data_attrs: desc_text_attrs.append(f"data={data_attrs}")
                        visible = is_element_visible(app_desc_elem)
                        desc_text_attrs.append(f"visible={str(visible).lower()}")
                        wan_lines.append(f"        [Child: P | text={app_desc}, {', '.join(desc_text_attrs)}]")

                app_index += 1

        # General links within section (excluding those already handled)
        for link in section.find_all("a", recursive=True)[:5]:
            if (sidebar_menu and link in sidebar_menu.find_all("a", recursive=True)) or (admin_nav and link in admin_nav.find_all("a", recursive=True)):
                continue
            if link.find_parent(attrs={"style": lambda x: x and "display: none" in x}):
                continue
            link_text = link.get("aria-label", link.get_text(strip=True)) or "Unnamed Link"
            attrs = [f"href={link.get('href', '')}"]
            if link.get("id"): attrs.append(f"id={link.get('id')}")
            if link.get("class"): attrs.append(f"class={' '.join(link.get('class'))}")
            data_attrs = {k: v for k, v in link.attrs.items() if k.startswith("data-")}
            if data_attrs: attrs.append(f"data={data_attrs}")
            visible = is_element_visible(link)
            attrs.append(f"visible={str(visible).lower()}")
            wan_lines.append(f"    [Link: {link_text} | {', '.join(attrs)}]")

        # Buttons within section (excluding those already handled)
        for button in section.find_all("button", recursive=True)[:5]:
            if (admin_nav and button in admin_nav.find_all("button", recursive=True)) or (apps and button in apps.find_all("button", recursive=True)):
                continue
            if button.find_parent(attrs={"style": lambda x: x and "display: none" in x}):
                continue
            attrs = []
            if button.get("id"): attrs.append(f"id={button.get('id')}")
            if button.get("class"): attrs.append(f"class={' '.join(button.get('class'))}")
            data_attrs = {k: v for k, v in button.attrs.items() if k.startswith("data-")}
            if data_attrs: attrs.append(f"data={data_attrs}")
            text = button.get_text(strip=True) or ""
            visible = is_element_visible(button)
            attrs.append(f"visible={str(visible).lower()}")
            wan_lines.append(f"    [Button: {text} | {', '.join(attrs)}]")

        # Text elements (for data points like "3,013 Open")
        for text_elem in section.find_all(["span", "div"], text=True, recursive=True)[:5]:
            text = text_elem.get_text(strip=True)
            if text in ["3,013", "5", "3,285", "84% Healthy", "No unhealthy devices", "No devices requiring attention", "No running actions"]:
                attrs = []
                if text_elem.get("id"): attrs.append(f"id={text_elem.get('id')}")
                if text_elem.get("class"): attrs.append(f"class={' '.join(text_elem.get('class'))}")
                visible = is_element_visible(text_elem)
                attrs.append(f"visible={str(visible).lower()}")
                wan_lines.append(f"    [Text: {text} | {', '.join(attrs)}]")

    # Standalone inputs (only visible ones)
    for input_elem in soup.find_all("input"):
        if input_elem.find_parent(attrs={"style": lambda x: x and "display: none" in x}):
            continue
        attrs = []
        if input_elem.get("class"): attrs.append(f"class={' '.join(input_elem.get('class'))}")
        if input_elem.get("aria-label"): attrs.append(f"aria-label={input_elem.get('aria-label')}")
        if input_elem.get("placeholder"): attrs.append(f"placeholder={input_elem.get('placeholder')}")
        data_attrs = {k: v for k, v in input_elem.attrs.items() if k.startswith("data-")}
        if data_attrs: attrs.append(f"data={data_attrs}")
        visible = is_element_visible(input_elem)
        attrs.append(f"visible={str(visible).lower()}")
        wan_lines.append(f"  [Input: Input | {', '.join(attrs)}]")

    return "\n".join(wan_lines[:max_lines])


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