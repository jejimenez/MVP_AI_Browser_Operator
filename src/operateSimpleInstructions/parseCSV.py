import csv
import re

def parse_csv(file_path):
    test_cases = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Split Action into individual steps
            steps = row['Action'].split('\n')
            parsed_steps = []
            for step in steps:
                step = step.strip()
                if step and not step.startswith('##'):  # Ignore empty or comment lines
                    action = re.sub(r'[#*]+|\s+', ' ', step).strip()  # Clean up markdown
                    parsed_steps.append({
                        "step": action,
                        "data": row['Data'] if step == steps[0] else "",  # Data only for first step in group
                        "expected": row['Expected Result'] if step == steps[-1] else ""  # Expected only for last
                    })
            test_cases.append({
                "steps": parsed_steps,
                "data": row['Data'],
                "expected": row['Expected Result']
            })
    return test_cases
"""
# Test parsing
csv_file = "test_cases.csv"
test_cases = parse_csv(csv_file)
for test in test_cases:
    for step in test["steps"]:
        print(step)
"""