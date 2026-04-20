import pytest

from atlassian_cli.auth.headers import parse_cli_headers
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.auth.resolver import resolve_auth


def test_parse_cli_headers_accepts_repeated_name_value_pairs() -> None:
    headers = parse_cli_headers(
        [
            "Authorization: Bearer flag-token",
            "X-Request-Source: agora-oauth",
        ]
    )

    assert headers == {
        "Authorization": "Bearer flag-token",
        "X-Request-Source": "agora-oauth",
    }


def test_parse_cli_headers_rejects_missing_colon() -> None:
    with pytest.raises(ValueError, match="Invalid header format"):
        parse_cli_headers(["Authorization"])


def test_resolve_auth_preserves_injected_headers() -> None:
    auth = resolve_auth(
        auth=AuthMode.BASIC,
        username="alice",
        password=None,
        token="legacy-token",
        headers={"Authorization": "Bearer oauth-token"},
    )

    assert auth.mode is AuthMode.BASIC
    assert auth.headers == {"Authorization": "Bearer oauth-token"}
