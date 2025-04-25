# tests/e2e/test_api_endpoints.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

class TestAPIEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_execute_test_case(self, client):
        response = client.post(
            "/api/tests/execute",
            json={
                "url": "https://dev-psa.dev.ninjarmm.com/auth/",
                "test_steps": """
                    Given I am on the login page
                    When I enter "username@gmail.com" into Email field
                    And I enter "pass" into password field
                    Then I click Sign in button
                """
            },
            headers={"X-API-Key": "test_key", "X-Tenant-ID": "test_tenant"}
        )
        print("Response content:", response.json())  # Add this for debugging
        assert response.status_code == 200

    def test_execute_without_api_key(self, client):
        response = client.post(
            "/api/tests/execute",
            json={
                "url": "https://example.com",
                "test_steps": "Step 1: Go to homepage"
            }
        )

        assert response.status_code == 400

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]  # Accept either status

    @pytest.mark.asyncio
    async def test_test_suite_execution(self, client):
        response = client.post(
            "/api/tests/suite/execute",
            json={
                "suite_id": "test_suite_1",
                "test_cases": [
                    {
                        "url": "https://dev-psa.dev.ninjarmm.com/auth/",
                        "test_steps": """
                            Given I am on the login page
                            When I enter "username@gmail.com" into Email field
                            And I enter "pass" into password field
                            Then I click Sign in button
                        """
                    }
                ]
            },
            headers={"X-API-Key": "test_key", "X-Tenant-ID": "test_tenant"}
        )
        print("Response content:", response.json())  # Add this for debugging
        assert response.status_code == 200