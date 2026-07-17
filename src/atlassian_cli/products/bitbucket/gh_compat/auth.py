from atlassian_cli.auth.models import ResolvedAuth
from atlassian_cli.core.errors import MissingCredentialError


def require_primary_auth(auth: ResolvedAuth) -> None:
    has_authorization_header = any(
        name.lower() == "authorization" and bool(value) for name, value in auth.headers.items()
    )
    has_basic = bool(auth.username and (auth.password or auth.token))
    if not (auth.token or has_basic or has_authorization_header):
        raise MissingCredentialError("authentication required")
