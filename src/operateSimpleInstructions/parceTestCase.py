import spacy
import re

nlp = spacy.load("en_core_web_sm")

def parse_test_case(test_case):
    # Split into sentences manually for better control
    sentences = re.split(r'\.\s*', test_case.strip())
    steps = []
    
    for sent in sentences:
        if not sent:
            continue
        doc = nlp(sent)
        action = None
        element = None
        text = None
        condition = None
        
        # Identify action
        sent_lower = sent.lower()
        if "click" in sent_lower:
            action = "click"
        elif "check" in sent_lower or "chek" in sent_lower:  # Handle typo
            action = "check"
        
        # Extract quoted text (e.g., 'Book this room')
        quoted_text = re.search(r"'([^']*)'", sent)
        if quoted_text:
            text = quoted_text.group(1)
        
        # Identify element
        for token in doc:
            if token.text.lower() in ["button", "message"]:
                element = token.text.lower()
        
        # Handle condition for 'check' action
        if action == "check" and "appears" in sent_lower:
            condition = {}
            if quoted_text:
                condition["text"] = quoted_text.group(1)
            # Check for hex color
            hex_match = re.search(r'#([0-9a-fA-F]{6})', sent)
            if hex_match:
                condition["color"] = hex_match.group(0).lower()  # e.g., '#721c24'
            else:
                for token in doc:
                    if token.text.lower() in ["red", "blue", "green"]:
                        condition["color"] = token.text.lower()
        
        # If no quoted text for 'click', use a fallback (e.g., 'Book')
        if action == "click" and not text:
            for token in doc:
                if token.pos_ in ["NOUN", "PROPN"] and token.text != "button":
                    text = token.text
                    break
        
        steps.append({"action": action, "element": element, "text": text, "condition": condition})
    
    return steps

# Test it
test_case = "Click in the button with the text 'Book this room'. Then click in Book. Chek if the message 'size must be between 3 and 18' appears in red"
parsed = parse_test_case(test_case)
for step in parsed:
    print(step)