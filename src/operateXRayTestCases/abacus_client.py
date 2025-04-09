import os
import requests
import json
from dotenv import load_dotenv
from abacusai import ApiClient

# Load environment variables
load_dotenv()

class AbacusAIClient:
    def __init__(self):
        self.api_key = os.getenv('ABACUS_API_KEY')
        if not self.api_key:
            raise ValueError("ABACUS_API_KEY not found in environment variables")

        # Base URL
        self.base_url = os.getenv('ABACUS_BASE_URL')
        self.deployment_id = os.getenv('ABACUS_DEPLOYMENT_ID')
        self.deployment_token = os.getenv('ABACUS_DEPLOYMENT_TOKEN')

        # Headers matching the working curl command
        self.headers = {
            'apiKey': self.api_key,
            'Content-Type': 'application/json'
        }

        # Initialize the Abacus.AI SDK client
        self.sdk_client = ApiClient(api_key=self.api_key)

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
        url = f"{self.base_url}/api/v0/evaluatePrompt"

        payload = {
            "prompt": prompt,
            "modelName": model_name,
            "maxTokens": 1000,
            "temperature": 0.7
        }

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            return None

    def execute_agent(self, wan_output: str, gherkin_step: str):
        """Execute the deployed WAN to Playwright agent using the SDK"""

        try:
            response = self.sdk_client.execute_agent(
                deployment_token=self.deployment_token,
                deployment_id=self.deployment_id,
                arguments=None,
                keyword_arguments={
                    "wan_output": wan_output,
                    "gherkin_step": gherkin_step
                }
            )
            
            return response
        except Exception as e:
            print(f"Agent execution failed: {e}")
            return None
        
    def wan_to_playwright_agent(self, wan: str, gherkin:str):
        instruction = self.execute_agent(wan, gherkin)
        instructions = [instr.strip() for instr in instruction['segments'][0]['segment'].split('; ') if instr.strip()]
        return instructions
    

# Example usage
if __name__ == "__main__":
    client = AbacusAIClient()
    """
    # Example 1: List projects
    print("Listing projects...")
    projects = client.list_projects()
    if projects:
        print("Projects list successful!")
        print(json.dumps(projects, indent=2))
    else:
        print("Failed to list projects")

    # Example 2: Send a prompt to the general LLM
    print("\nSending a prompt to the general LLM...")
    response = client.send_prompt("What is machine learning?")
    if response:
        print("Prompt successful!")
        print(json.dumps(response, indent=2))
    else:
        print("Failed to send prompt")
    """
    # Example 3: Execute the trained agent
    print("\nExecuting the trained agent...")
    deployment_id = "59f9bd0bc"  # Replace with your deployment ID
    deployment_token = "05afc22b3d3a4c329bcb804e316c374e"  # Replace with your deployment token
    wan_output = """
    Main navigation:
      - button "Home" with icon
      - link "Products" with dropdown
      - button "PSA" with blue background
      - link "Contact Us" aligned right
    """
    gherkin_step = "And I navigate to PSA"

    agent_response = client.wan_to_playwright_agent(wan_output, gherkin_step)
    if agent_response:
        print("Agent execution successful!")
        print(json.dumps(agent_response, indent=2))
    else:
        print("Failed to execute agent")
    