**WebOperatorFromTC**

**WebOperatorFromTC** is an AI-driven web automation framework designed
to simplify web application testing by converting natural language test
cases into executable browser automation scripts. Powered by Playwright
for browser interactions and the Gemini-2.0-flash AI model for natural
language processing, it enables non-technical users to create and run
tests with minimal coding. The framework supports modern web
applications, including JavaScript-heavy React single-page applications
(SPAs), and provides robust execution with detailed logging and error
handling.

**Features**

-   **Natural Language Processing**: Converts user-defined test cases
    > (e.g., \"Navigate to login page, enter email, click submit\") into
    > structured Gherkin steps.

-   **AI-Driven Automation**: Translates Gherkin steps into Playwright
    > instructions using web page snapshots, ensuring context-aware
    > automation.

-   **Browser Automation**: Executes tests in a Chromium browser,
    > supporting navigation, form filling, and clicking.

-   **RESTful API**: Provides endpoints for triggering test execution
    > and health checks.

-   **Snapshot Generation**: Summarizes web page HTML for AI analysis,
    > capturing visible and interactive elements.

-   **Debugging Support**: Includes detailed logging, retries, and
    > storage for screenshots and Playwright traces.

-   **XRay Integration**: Supports integration with XRay for test case
    > management (under development).

**Project Goals**

-   Enable non-technical users to write test cases in natural language.

-   Generate dynamic, context-aware Playwright instructions for diverse
    > web applications.

-   Ensure reliable test execution with robust error handling.

-   Provide programmatic access via a RESTful API.

-   Integrate with test management systems like XRay.

**Prerequisites**

-   **Python**: 3.9 or higher

-   **Node.js**: Required for Playwright dependencies

-   **Dependencies**: Listed in requirements.txt

-   **Environment Variables**:

    -   GEMINI_API_KEY: API key for Gemini-2.0-flash

    -   TARGET_URL: Default URL for testing (e.g.,
        > https://dev-psa.dev.ninjarmm.com)

**Installation**

-   **Clone the Repository**:

-   bash

git clone https://github.com/\<your-username\>/WebOperatorFromTC.git

-   cd WebOperatorFromTC

-   **Set Up a Virtual Environment**:

-   bash

python -m venv venv

-   source venv/bin/activate \# On Windows: venv\\Scripts\\activate

-   **Install Python Dependencies**:

-   bash

-   pip install -r requirements.txt

-   **Install Playwright Browsers**:

-   bash

-   playwright install chromium

-   **Configure Environment Variables**: Create a .env file in the
    > project root:

-   plaintext

GEMINI_API_KEY=\<your-gemini-api-key\>

TARGET_URL=https://dev-psa.dev.ninjarmm.com

-   LOG_LEVEL=DEBUG

**Usage**

**Running the API**

Start the FastAPI application using Uvicorn:

bash

uvicorn app.main:app \--reload

The API will be available at http://localhost:8000. Key endpoints:

-   GET /health: Check API status.

-   POST /operator/execute: Trigger test execution with a JSON payload
    > (see below).

**Executing a Test Case**

Send a test case to the /operator/execute endpoint using curl or a tool
like Postman:

bash

curl -X POST http://localhost:8000/operator/execute \\

-H \"Content-Type: application/json\" \\

-d \'{\"test_case\": \"Navigate to login page, enter email
test@example.com, click submit\"}\'

Response:

json

{

\"status\": \"success\",

\"result\": {

\"gherkin_steps\": \[\"Given I navigate to the login page\", \"When I
enter email \'test@example.com\'\", \"Then I click submit\"\],

\"execution_status\": \"completed\",

\"logs\": \[\"Navigated to https://dev-psa.dev.ninjarmm.com\", \"Filled
email field\", \"Clicked submit button\"\]

}

}

**Running Tests**

Run the test suite to verify functionality:

bash

PYTHONPATH=. pytest tests/ -v \--log-cli-level=DEBUG

For detailed debugging, run specific test suites:

-   **Unit Tests**:

-   bash

-   PYTHONPATH=. pytest tests/unit/ -vv \--log-cli-level=DEBUG

-   **Integration Tests**:

-   bash

-   PYTHONPATH=. pytest tests/integration/ -vv \--log-cli-level=DEBUG

-   **End-to-End Tests**:

-   bash

-   PYTHONPATH=. pytest tests/e2e/ -vv \--log-cli-level=DEBUG

-   **Specific Integration Test** (e.g., successful operator execution):

-   bash

-   PYTHONPATH=. pytest tests/integration/test_operator_runner.py -vv -k
    > \"test_successful_operator_execution\" \--log-cli-level=DEBUG

**Call the API**

To call the API remember to have the FastAPI application started using Uvicorn. This command will run the operator with the browser controls. Change the headless flag to true if you want to running in background

curl -X POST http://localhost:8000/api/operator/execute \
-H "Content-Type: application/json" \
-H "X-API-Key: test_key" \
-H "X-Tenant-ID: test_tenant" \
-d '{
    "url": "https://dev-psa.dev.ninjarmm.com/auth/",
    "test_steps": "Given I am on the login page\nWhen I enter \"username@gmail.com\" into Email field\nAnd I enter \"pass\" into password field\nThen I click Sign in button",
    "headless": false
}'

**Directory Structure**

WebOperatorFromTC/

├── app/

│ ├── api/ \# FastAPI endpoints (health, test execution)

│ │ ├── dependencies.py

│ │ └── routes/

│ │ ├── health.py

│ │ └── operator_execution.py

│ ├── domain/ \# Business logic (step parsing, exceptions)

│ │ ├── exceptions.py

│ │ └── step_parser.py

│ ├── infrastructure/ \# AI client, Playwright manager, snapshot storage

│ │ ├── ai_client.py

│ │ ├── ai_generators.py

│ │ ├── db.py

│ │ ├── html_summarizer.py

│ │ ├── interfaces.py

│ │ ├── playwright_manager.py

│ │ └── snapshot_storage.py

│ ├── main.py \# FastAPI application entry point

│ ├── operateXRayTestCases/ \# XRay test case implementations

│ │ ├── HTMLSummarizer.py

│ │ ├── abacus_client.py

│ │ ├── example.py

│ │ ├── login.py

│ │ ├── operateXRay.py

│ │ └── otp.py

│ ├── prompts/ \# AI prompt templates

│ │ └── custom_agents/

│ ├── schemas/ \# Pydantic models for API

│ │ ├── requests.py

│ │ └── responses.py

│ ├── services/ \# Orchestration logic (operator runner)

│ │ ├── health.py

│ │ └── operator_runner.py

│ └── utils/ \# Shared utilities (logging, config)

│ ├── config.py

│ ├── html_summarizer.py

│ ├── logger.py

│ └── otp.py

├── debug_screenshots/ \# Debugging artifacts (screenshots)

├── debug_traces/ \# Debugging artifacts (Playwright traces)

├── screenshots/ \# Additional screenshot storage

├── src/operateXRayTestCases/ \# Legacy or source test case scripts

├── tests/ \# Unit, integration, and end-to-end tests

│ ├── conftest.py \# Pytest fixtures

│ ├── e2e/ \# End-to-end tests

│ │ └── test_api_endpoints.py

│ ├── integration/ \# Integration tests

│ │ └── test_operator_runner.py

│ ├── test_data/ \# Mock data (snapshots, test cases)

│ │ ├── snapshots/

│ │ └── test_cases/

│ └── unit/ \# Unit tests

│ ├── test_ai_generators.py

│ ├── test_html_parser.py

│ ├── test_operator_runner.py

│ ├── test_playwright_manager.py

│ └── test_step_parser.py

├── traces/ \# Playwright trace storage

└── requirements.txt \# Python dependencies

**Debugging**

-   **Logs**: Check console output or log files for detailed execution
    > logs.

-   **Screenshots and Traces**: Inspect debug_screenshots/,
    > screenshots/, and debug_traces/ for visual debugging.

-   **Headless Mode**: Set headless=False in
    > app/infrastructure/playwright_manager.py to watch browser
    > interactions.

-   **Snapshot Issues**: If snapshots are incomplete (e.g., \<noscript\>
    > content), verify the waiting mechanism in playwright_manager.py.

**Current Challenges**

-   **Incomplete Snapshots**: React SPAs may render after Playwright's
    > wait_until=\'load\', leading to empty snapshots. Workaround: Use
    > wait_for_selector for specific elements (e.g., input#email).

-   **Navigation Timeouts**: Adjust BrowserConfig.timeout or use
    > wait_until=\'load\' for SPAs with continuous network activity.

-   **AI Accuracy**: Incomplete snapshots may cause incorrect Playwright
    > instructions. Ensure prompts in prompts/custom_agents/ enforce the
    > current URL.

**Contributing**

-   Fork the repository.

-   Create a feature branch (git checkout -b feature/\<feature-name\>).

-   Commit changes (git commit -m \"Add feature X\").

-   Push to the branch (git push origin feature/\<feature-name\>).

-   Open a pull request with a detailed description.

Please follow the coding style in .editorconfig and run tests before
submitting.

**License**

This project is licensed under the MIT License. See the LICENSE file for
details.

**Contact**

For questions or support, contact the project maintainer at
\<jimenez.ing.sis@gmail.com\> or open an issue on GitHub.
