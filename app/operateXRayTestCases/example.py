from abacus_client import AbacusAIClient


def test_abacus_api():
    try:
        # Initialize client
        client = AbacusAIClient()

        # Test code generation

        code_prompt = """ Prompt test """
        code_response = client.send_prompt(
            prompt=code_prompt,
        )

        if code_response and code_response.get('success') and code_response.get('result'):
            # Extract the content from the response
            gherkin_text = code_response['result']['content']
            print(gherkin_text)

    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    test_abacus_api()