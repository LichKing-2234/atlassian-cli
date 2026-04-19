class AtlassianCliError(Exception):
    """Base CLI error."""


class ConfigError(AtlassianCliError):
    """Invalid config or missing settings."""


class AuthError(AtlassianCliError):
    """Authentication or authorization failure."""


class ConnectionError(AtlassianCliError):
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
        return 4
    if isinstance(error, ConflictError):
        return 5
    if isinstance(error, (ConfigError, ValidationError, UnsupportedError)):
        return 2
    if isinstance(error, AuthError):
        return 3
    if isinstance(error, ConnectionError):
        return 6
    return 10
