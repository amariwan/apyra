"""Authentication and authorization exceptions."""


class AuthenticationError(Exception):
    """Raised when a token cannot be authenticated."""


class AuthorizationError(Exception):
    """Raised when an authenticated principal lacks permission."""
