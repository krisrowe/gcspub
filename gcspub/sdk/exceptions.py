class GcsPubError(Exception):
    """Base exception for gcspub."""
    pass

class MissingDependencyError(GcsPubError):
    """Raised when a required system dependency (e.g., gcloud, gsutil) is missing."""
    def __init__(self, dependency_name: str, install_instructions: str):
        self.dependency_name = dependency_name
        self.install_instructions = install_instructions
        super().__init__(f"Missing required dependency: {dependency_name}. {install_instructions}")

class ConfigurationError(GcsPubError):
    """Raised when gcspub is not properly configured (e.g., missing email)."""
    pass

class AuthMismatchError(GcsPubError):
    """Raised when the active gcloud identity does not match the configured gcspub email."""
    pass

class AuthError(GcsPubError):
    """Raised when the user is not authenticated or the account is missing from auth list."""
    pass
