# app/schemas/requests.py

from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime

class TestCaseRequest(BaseModel):
    """Request model for test case execution."""
    url: HttpUrl
    test_steps: str
    timeout: Optional[int] = Field(default=30, ge=1, le=300)
    capture_screenshots: bool = True
    retry_attempts: Optional[int] = Field(default=1, ge=1, le=3)

class TestCaseFileRequest(BaseModel):
    """Request model for file-based test case."""
    url: HttpUrl
    file: bytes
    file_type: str = "text/plain"

class TestSuiteRequest(BaseModel):
    """Request model for test suite execution."""
    suite_id: str
    test_cases: List[TestCaseRequest]
    parallel_execution: bool = False
    max_parallel_tests: Optional[int] = Field(default=5, ge=1, le=10)