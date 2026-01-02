"""
Custom exceptions for AthleAgent backend.
"""


class AthleAgentException(Exception):
    """Base exception for all AthleAgent errors."""
    pass


class AuthenticationError(AthleAgentException):
    """Authentication failed."""
    pass


class AuthorizationError(AthleAgentException):
    """User not authorized for this action."""
    pass


class NotFoundError(AthleAgentException):
    """Resource not found."""
    pass


class ValidationError(AthleAgentException):
    """Data validation failed."""
    pass


class DatabaseError(AthleAgentException):
    """Database operation failed."""
    pass


class MLModelError(AthleAgentException):
    """ML model operation failed."""
    pass


class ExternalAPIError(AthleAgentException):
    """External API call failed."""
    pass

