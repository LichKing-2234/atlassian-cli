from atlassian_cli.auth.models import AuthMode, ResolvedAuth
from atlassian_cli.core.errors import ConfigError


def resolve_auth(
    *,
    auth: AuthMode | None,
    username: str | None,
    password: str | None,
    token: str | None,
    headers: dict[str, str] | None = None,
) -> ResolvedAuth:
    mode = auth or AuthMode.BASIC
    if mode in {AuthMode.PAT, AuthMode.BEARER} and token is None:
        raise ConfigError(f"{mode.value} authentication requires a token")
    return ResolvedAuth(
        mode=mode,
        username=username,
        password=password,
        token=token,
        headers=headers or {},
    )
