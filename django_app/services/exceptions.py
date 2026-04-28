class ServiceError(Exception):
    """Base exception for service-layer failures."""


class ExtractionError(ServiceError):
    """Raised when text extraction fails."""


class ValidationError(ServiceError):
    """Raised when validation pipeline fails."""
