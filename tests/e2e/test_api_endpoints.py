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
                "url": "https://example.com",
                "test_steps": "Step 1: Go to homepage\nStep 2: Click login"
            },
            headers={"X-API-Key": "test_key", "X-Tenant-ID": "test_tenant"}
        )

        assert response.status_code == 200
        assert "success" in response.json()
        assert "steps_results" in response.json()

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
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_test_suite_execution(self, client):
        response = client.post(
            "/api/tests/suite/execute",
            json={
                "suite_id": "test_suite_1",
                "test_cases": [
                    {
                        "url": "https://example.com",
                        "test_steps": "Step 1: Go to homepage"
                    }
                ]
            },
            headers={"X-API-Key": "test_key", "X-Tenant-ID": "test_tenant"}
        )

        assert response.status_code == 200
        assert "results" in response.json()