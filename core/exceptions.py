"""
Exceptions for the Universal UiPath-to-PAD Conversion Engine.
"""

class ConversionEngineError(Exception):
    """Base exception for all conversion engine errors."""
    pass

class ProjectScanError(ConversionEngineError):
    """Raised when scanning a project folder, zip, or nupkg fails."""
    pass

class XamlParseError(ConversionEngineError):
    """Raised when XAML parsing fails."""
    pass

class CircularWorkflowError(ConversionEngineError):
    """Raised when circular workflow dependencies are detected."""
    pass

class UnsupportedActivityError(ConversionEngineError):
    """Raised in strict mode when an unmappable activity is encountered."""
    def __init__(self, activity_type: str, workflow_name: str, message: str = ""):
        self.activity_type = activity_type
        self.workflow_name = workflow_name
        msg = f"Unsupported activity '{activity_type}' in workflow '{workflow_name}'. {message}".strip()
        super().__init__(msg)

class StrictValidationError(ConversionEngineError):
    """Raised when strict validation fails."""
    def __init__(self, message: str, errors: list = None):
        super().__init__(message)
        self.errors = errors or []

