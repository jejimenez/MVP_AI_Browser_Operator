# app/api/dependencies.py

from fastapi import Depends, HTTPException, Header
from typing import Optional

from app.services.test_runner import TestRunnerInterface, TestRunnerFactory
from app.services.health import HealthChecker
from app.utils.config import get_settings

async def get_test_runner() -> TestRunnerInterface:
    """Dependency for test runner service."""
    settings = get_settings()
    return TestRunnerFactory.create_runner(
        runner_type=settings.runner_type,
        browser_config=settings.browser_config
    )

async def get_current_tenant(
    x_tenant_id: Optional[str] = Header(None)
) -> str:
    """Dependency for tenant identification."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-ID header is required"
        )
    return x_tenant_id

async def validate_api_key(
    x_api_key: Optional[str] = Header(None)
) -> str:
    """Dependency for API key validation."""
    if not x_api_key:
        raise HTTPException(
            status_code=400,
            detail="X-API-Key header is required"
        )

    settings = get_settings()
    if x_api_key not in settings.valid_api_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key

async def get_health_checker() -> HealthChecker:
    """Dependency for health checker service."""
    return HealthChecker()