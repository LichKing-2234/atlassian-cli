from atlassian_cli.core.exit_codes import (
    EXIT_AUTH,
    EXIT_CONFLICT,
    EXIT_NETWORK,
    EXIT_NOT_FOUND,
    EXIT_UNKNOWN,
    EXIT_USAGE,
)


class AtlassianCliError(Exception):
    """Base CLI error."""


class ConfigError(AtlassianCliError):
    """Invalid config or missing settings."""


class AuthError(AtlassianCliError):
    """Authentication or authorization failure."""


class TransportError(AtlassianCliError):
    """Transport-level failure."""


class NotFoundError(AtlassianCliError):
    """Requested resource was not found."""


class ValidationError(AtlassianCliError):
    """User input is invalid."""


class ConflictError(AtlassianCliError):
    """Requested mutation conflicts with current state."""


class ServerError(AtlassianCliError):
    """Remote server returned an internal error."""


class UnsupportedError(AtlassianCliError):
    """Requested feature is not supported."""


def exit_code_for_error(error: Exception) -> int:
    if isinstance(error, NotFoundError):
        return EXIT_NOT_FOUND
    if isinstance(error, ConflictError):
        return EXIT_CONFLICT
    if isinstance(error, (ConfigError, ValidationError, UnsupportedError)):
        return EXIT_USAGE
    if isinstance(error, AuthError):
        return EXIT_AUTH
    if isinstance(error, TransportError):
        return EXIT_NETWORK
    return EXIT_UNKNOWN
