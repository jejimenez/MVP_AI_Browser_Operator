# app/schemas/responses.py

from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class StepResult(BaseModel):
    """Response model for step execution result."""
    step: str
    success: bool
    screenshot_url: Optional[str]
    duration: float
    error: Optional[str]

class TestCaseResponse(BaseModel):
    """Response model for test case execution."""
    request_id: str
    tenant_id: str
    execution_time: datetime
    success: bool
    steps_results: List[StepResult]
    total_duration: float
    error_message: Optional[str]

class TestExecutionStatus(BaseModel):
    """Response model for test execution status."""
    execution_id: str
    status: str
    progress: float
    completed_steps: int
    total_steps: int
    current_step: Optional[str]
    start_time: datetime
    estimated_completion: Optional[datetime]

class TestSuiteResponse(BaseModel):
    """Response model for test suite execution."""
    suite_id: str
    tenant_id: str
    execution_time: datetime
    results: List[TestCaseResponse]
    total_cases: int
    successful_cases: int
    failed_cases: int

class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    components: Dict[str, bool]