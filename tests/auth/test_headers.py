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


def test_collect_env_headers_reads_single_complete_header_value() -> None:
    headers = collect_env_headers(
        {
            "ATLASSIAN_HEADER": "accessToken: env-token",
            "UNRELATED_ENV": "ignored",
        }
    )

    assert headers == {
        "accessToken": "env-token",
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
