import pytest

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryHostMismatchError,
    RepositoryRef,
    ServerIdentity,
    parse_pull_request_url,
    parse_repository_selector,
)

SERVER = ServerIdentity.from_url("https://bitbucket.example.com/bitbucket")


@pytest.mark.parametrize(
    ("value", "project", "repo"),
    [
        ("DEMO/example-repo", "DEMO", "example-repo"),
        ("bitbucket.example.com/DEMO/example-repo", "DEMO", "example-repo"),
        (
            "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/example-repo",
            "DEMO",
            "example-repo",
        ),
        (
            "https://bitbucket.example.com/bitbucket/scm/DEMO/example-repo.git",
            "DEMO",
            "example-repo",
        ),
        (
            "ssh://git@bitbucket.example.com:7999/DEMO/example-repo.git",
            "DEMO",
            "example-repo",
        ),
        ("git@bitbucket.example.com:DEMO/example-repo.git", "DEMO", "example-repo"),
        ("bitbucket.example.com:DEMO/example-repo.git", "DEMO", "example-repo"),
        (
            "https://bitbucket.example.com/bitbucket/users/example-user/repos/example-repo",
            "~example-user",
            "example-repo",
        ),
    ],
)
def test_parse_repository_selector(value: str, project: str, repo: str) -> None:
    assert parse_repository_selector(value, SERVER) == RepositoryRef(SERVER, project, repo)


def test_repository_selector_rejects_another_host() -> None:
    with pytest.raises(RepositoryHostMismatchError):
        parse_repository_selector(
            "https://other.example.com/scm/DEMO/example-repo.git",
            SERVER,
        )


def test_repository_selector_rejects_bare_repo_name() -> None:
    with pytest.raises(ValidationError, match="PROJECT/REPOSITORY"):
        parse_repository_selector("example-repo", SERVER)


def test_parse_pull_request_url_is_authoritative() -> None:
    value = (
        "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/"
        "example-repo/pull-requests/1234"
    )
    assert parse_pull_request_url(value, SERVER) == PullRequestRef(
        RepositoryRef(SERVER, "DEMO", "example-repo"),
        1234,
    )


@pytest.mark.parametrize(
    "value",
    [
        (
            "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/"
            "example-repo?at=feature%2FDEMO-1234%2Fexample-change#readme"
        ),
        (
            "https://bitbucket.example.com/bitbucket/scm/DEMO/"
            "example-repo.git?at=feature%2FDEMO-1234%2Fexample-change#readme"
        ),
    ],
)
def test_repository_url_tolerates_query_and_fragment(value: str) -> None:
    assert parse_repository_selector(value, SERVER) == RepositoryRef(SERVER, "DEMO", "example-repo")


def test_pull_request_url_tolerates_query_and_fragment() -> None:
    value = (
        "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/"
        "example-repo/pull-requests/1234?commentId=1#example-comment"
    )
    assert parse_pull_request_url(value, SERVER) == PullRequestRef(
        RepositoryRef(SERVER, "DEMO", "example-repo"),
        1234,
    )


def test_repository_url_requires_configured_context_path() -> None:
    with pytest.raises(ValidationError, match="context path"):
        parse_repository_selector(
            "https://bitbucket.example.com/projects/DEMO/repos/example-repo",
            SERVER,
        )


def test_repository_url_supports_server_without_context_path() -> None:
    server = ServerIdentity.from_url("https://bitbucket.example.com")
    value = "https://bitbucket.example.com/projects/DEMO/repos/example-repo"

    assert parse_repository_selector(value, server) == RepositoryRef(server, "DEMO", "example-repo")


def test_repository_url_percent_decodes_slugs() -> None:
    value = "https://bitbucket.example.com/bitbucket/projects/%44EMO/repos/example%2Drepo"

    assert parse_repository_selector(value, SERVER) == RepositoryRef(SERVER, "DEMO", "example-repo")


@pytest.mark.parametrize(
    "value",
    [
        "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/example-repo",
        (
            "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/"
            "example-repo/pull-requests/not-a-number"
        ),
        ("https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"),
    ],
)
def test_parse_pull_request_url_rejects_invalid_urls(value: str) -> None:
    with pytest.raises(ValidationError):
        parse_pull_request_url(value, SERVER)


def test_pull_request_url_rejects_another_host() -> None:
    value = (
        "https://other.example.com/bitbucket/projects/DEMO/repos/example-repo/pull-requests/1234"
    )

    with pytest.raises(RepositoryHostMismatchError):
        parse_pull_request_url(value, SERVER)


def test_host_prefixed_selector_includes_configured_port() -> None:
    server = ServerIdentity.from_url("https://bitbucket.example.com:8443/bitbucket")

    assert parse_repository_selector(
        "bitbucket.example.com:8443/DEMO/example-repo", server
    ) == RepositoryRef(server, "DEMO", "example-repo")


def test_host_prefixed_selector_rejects_wrong_port() -> None:
    server = ServerIdentity.from_url("https://bitbucket.example.com:8443/bitbucket")

    with pytest.raises(RepositoryHostMismatchError):
        parse_repository_selector("bitbucket.example.com/DEMO/example-repo", server)


def test_host_prefixed_selector_rejects_explicit_wrong_port() -> None:
    server = ServerIdentity.from_url("https://bitbucket.example.com:8443/bitbucket")

    with pytest.raises(RepositoryHostMismatchError):
        parse_repository_selector("bitbucket.example.com:7999/DEMO/example-repo", server)


def test_http_repository_url_rejects_wrong_port() -> None:
    value = "https://bitbucket.example.com:8443/bitbucket/projects/DEMO/repos/example-repo"

    with pytest.raises(RepositoryHostMismatchError):
        parse_repository_selector(value, SERVER)


@pytest.mark.parametrize(
    ("server_url", "value"),
    [
        (
            "https://bitbucket.example.com/bitbucket",
            "http://bitbucket.example.com:443/bitbucket/projects/DEMO/repos/example-repo",
        ),
        (
            "http://bitbucket.example.com/bitbucket",
            "https://bitbucket.example.com:80/bitbucket/projects/DEMO/repos/example-repo",
        ),
    ],
)
def test_http_repository_url_rejects_cross_scheme(server_url: str, value: str) -> None:
    with pytest.raises(RepositoryHostMismatchError):
        parse_repository_selector(value, ServerIdentity.from_url(server_url))


def test_pull_request_url_rejects_cross_scheme() -> None:
    value = (
        "http://bitbucket.example.com:443/bitbucket/projects/DEMO/repos/"
        "example-repo/pull-requests/1234"
    )

    with pytest.raises(RepositoryHostMismatchError):
        parse_pull_request_url(value, SERVER)


@pytest.mark.parametrize(
    "value",
    [
        ("//bitbucket.example.com/bitbucket/projects/DEMO/repos/example-repo/pull-requests/1234"),
        (
            "ssh://bitbucket.example.com:443/bitbucket/projects/DEMO/repos/"
            "example-repo/pull-requests/1234"
        ),
        (
            "ftp://bitbucket.example.com:443/bitbucket/projects/DEMO/repos/"
            "example-repo/pull-requests/1234"
        ),
    ],
)
def test_pull_request_url_rejects_non_http_urls(value: str) -> None:
    with pytest.raises(ValidationError):
        parse_pull_request_url(value, SERVER)


def test_ssh_clone_accepts_distinct_clone_port() -> None:
    value = "ssh://git@bitbucket.example.com:7999/DEMO/example-repo.git"

    assert parse_repository_selector(value, SERVER) == RepositoryRef(SERVER, "DEMO", "example-repo")
