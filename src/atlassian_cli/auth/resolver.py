from atlassian_cli.auth.models import AuthMode, ResolvedAuth


def resolve_auth(
    *,
    auth: AuthMode | None,
    username: str | None,
    password: str | None,
    token: str | None,
    headers: dict[str, str] | None = None,
) -> ResolvedAuth:
    mode = auth or AuthMode.BASIC
    return ResolvedAuth(
        mode=mode,
        username=username,
        password=password,
        token=token,
        headers=headers or {},
    )
