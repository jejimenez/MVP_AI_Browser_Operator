# app/domain/exceptions.py

class AIClientException(Exception):
    """Base exception for AI client errors."""
    pass

class InvalidPromptException(AIClientException):
    """Exception for invalid prompt inputs."""
    pass

class ValidationException(Exception):
    """Base exception for validation errors."""
    pass

class BrowserException(Exception):
    """Base exception for browser-related errors."""
    pass

class NavigationException(BrowserException):
    """Exception for navigation failures."""
    pass

class ElementNotFoundException(BrowserException):
    """Exception for element not found errors."""
    pass

class ScreenshotException(BrowserException):
    """Exception for screenshot-related errors."""
    pass

class StepParsingException(Exception):
    """Base exception for step parsing errors."""
    pass

class InvalidStepFormatException(StepParsingException):
    """Exception for invalid step format."""
    pass

class SnapshotParsingException(Exception):
    """Exception for page snapshot parsing errors."""
    pass

class TestExecutionException(Exception):
    """Base exception for test execution errors."""
    pass

class StepExecutionException(TestExecutionException):
    """Exception for step execution failures."""
    pass

class StepGenerationException(AIClientException):
    """Exception for AI step generation failures."""
    pass

class SecurityException(Exception):
    """Raised when an instruction violates security constraints."""
    pass