# tests/integration/test_test_runner.py

import pytest
from app.services.test_runner import TestRunnerFactory
from app.domain.exceptions import TestExecutionException

class TestTestRunner:
    @pytest.fixture
    async def runner(self):
        return TestRunnerFactory.create_runner()

    @pytest.mark.asyncio
    async def test_successful_test_execution(self, runner, sample_test_case):
        result = await runner.run_test_case(
            url="https://example.com",
            test_steps=sample_test_case
        )

        assert result.success
        assert len(result.steps_results) > 0
        assert result.total_duration > 0

    @pytest.mark.asyncio
    async def test_failed_test_execution(self, runner):
        with pytest.raises(TestExecutionException):
            await runner.run_test_case(
                url="https://invalid-url.com",
                test_steps="invalid step"
            )

    @pytest.mark.asyncio
    async def test_test_validation(self, runner, sample_test_case):
        is_valid = await runner.validate_test_case(sample_test_case)
        assert is_valid