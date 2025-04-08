import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AbacusAIClient:
    def __init__(self):
        self.api_key = os.getenv('ABACUS_API_KEY')
        if not self.api_key:
            raise ValueError("ABACUS_API_KEY not found in environment variables")

        # Base URL
        self.base_url = os.getenv('ABACUS_BASE_URL')

        # Headers matching the working curl command
        self.headers = {
            'apiKey': self.api_key,
            'Content-Type': 'application/json'
        }

    def list_projects(self):
        """List all projects"""
        url = f"{self.base_url}/api/v0/listProjects"

        try:
            response = requests.get(
                url,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            return None
    def send_prompt(self, prompt: str, model_name: str = "claude-3-sonnet"):
        """Send a prompt to the API"""
        url = f"{self.base_url}/api/v0/evaluatePrompt"  # Correct endpoint

        payload = {
            "prompt": prompt,
            "modelName": model_name,
            "maxTokens": 1000,
            "temperature": 0.7
        }

        try:
            #print(f"Making request to: {url}")
            #print(f"Headers: {self.headers}")
            #print(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )

            #print(f"Response Status: {response.status_code}")
            #print(f"Response Content: {response.text}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            return None

# Example usage
if __name__ == "__main__":
    client = AbacusAIClient()

    # First test the working endpoint (list projects)
    print("Testing list projects...")
    projects = client.list_projects()
    if projects:
        print("Projects list successful!")
        print(json.dumps(projects, indent=2))
    else:
        print("Failed to list projects")

    # Then try the prompt
    print("\nTesting prompt...")
    response = client.send_prompt("What is machine learning?")
    if response:
        print("Prompt successful!")
        print(json.dumps(response, indent=2))
    else:
        print("Failed to send prompt")