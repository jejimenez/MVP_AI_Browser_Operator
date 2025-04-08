from parceTestCase import parse_test_case
from browserAutomation import execute_test  # Assume saved in a separate file

def process_test_case(test_case, url="https://automationintesting.online/"):
    parsed = parse_test_case(test_case)
    results = execute_test(parsed, url)
    return results

# Example usage
test_case = "Click in the button with the text 'Book this room'. Then click in Book. Chek if a message that contains 'Firstname should not be blank' appears in color #721c24"
results = process_test_case(test_case)
for result in results:
    print(result)