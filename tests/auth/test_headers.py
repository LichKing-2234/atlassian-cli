from atlassian_cli.auth.headers import collect_env_headers, parse_cli_headers
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


def test_collect_env_headers_maps_prefix_and_underscores() -> None:
    headers = collect_env_headers(
        {
            "ATLASSIAN_HEADER_AUTHORIZATION": "Bearer env-token",
            "ATLASSIAN_HEADER_X_REQUEST_SOURCE": "agora-oauth",
            "UNRELATED_ENV": "ignored",
        }
    )

    assert headers == {
        "Authorization": "Bearer env-token",
        "X-Request-Source": "agora-oauth",
    }


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
