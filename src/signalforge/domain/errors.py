from __future__ import annotations


class SignalForgeError(Exception):
    """Base class for errors that can be safely translated at the API boundary."""


class AuthenticationError(SignalForgeError):
    pass


class AuthorizationError(SignalForgeError):
    pass


class ValidationError(SignalForgeError):
    pass


class NotFoundError(SignalForgeError):
    pass


class ConflictError(SignalForgeError):
    pass


class PayloadTooLargeError(SignalForgeError):
    pass

