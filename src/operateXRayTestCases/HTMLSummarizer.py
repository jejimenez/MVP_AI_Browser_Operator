from bs4 import BeautifulSoup
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

        # Special handling
        apps = section.find("div", attrs={"data-testid": os.getenv('SPECIAL_DIV')})
        if apps:
            app_index = 0
            for app_card in apps.find_all("button", attrs={"data-testid": "app-card"}):
                app_name_elem = app_card.find("h3", attrs={"data-testid": "styled-text-div"})
                app_name = app_name_elem.find("span").get_text(strip=True) if app_name_elem and app_name_elem.find("span") else "Unnamed App"
                app_status_elem = app_card.find("div", attrs={"data-testid": "app-status"})
                app_status = app_status_elem.find("span").get_text(strip=True) if app_status_elem and app_status_elem.find("span") else "Unknown Status"
                attrs = [f"status={app_status}"]
                attrs.append(f"index={app_index}")
                if app_card.get("class"): attrs.append(f"class={' '.join(app_card.get('class'))}")
                data_attrs = {k: v for k, v in app_card.attrs.items() if k.startswith("data-")}
                if data_attrs: attrs.append(f"data={data_attrs}")
                visible = is_element_visible(app_card)
                attrs.append(f"visible={str(visible).lower()}")
                wan_lines.append(f"    [Button: {app_name} | {', '.join(attrs)}]")
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