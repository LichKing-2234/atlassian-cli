from atlassian_cli.auth.models import AuthMode, ResolvedAuth
from atlassian_cli.config.models import Deployment, Product
from atlassian_cli.core.context import ExecutionContext
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.bitbucket.providers.server import BitbucketServerProvider
from atlassian_cli.products.confluence.providers.server import ConfluenceServerProvider
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def make_context(product: Product) -> ExecutionContext:
    return ExecutionContext(
        profile="oauth-profile",
        product=product,
        deployment=Deployment.SERVER,
        url="https://example.com",
        output="json",
        auth=ResolvedAuth(
            mode=AuthMode.PAT,
            username="alice",
            password="legacy-password",
            token="legacy-token",
            headers={"Authorization": "Bearer oauth-token"},
        ),
    )


def test_build_provider_passes_headers_to_bitbucket_provider(monkeypatch) -> None:
    captured = {}

    class FakeProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("atlassian_cli.products.factory.BitbucketServerProvider", FakeProvider)

    build_provider(make_context(Product.BITBUCKET))

    assert captured["headers"] == {"Authorization": "Bearer oauth-token"}


def test_jira_provider_prefers_injected_headers(monkeypatch) -> None:
    captured = {"patched": None}

    class FakeJira:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self._session = object()

    monkeypatch.setattr("atlassian_cli.products.jira.providers.server.Jira", FakeJira)
    monkeypatch.setattr(
        "atlassian_cli.products.jira.providers.server.patch_session_headers",
        lambda session, headers: captured.__setitem__("patched", headers),
    )

    JiraServerProvider(
        url="https://jira.example.com",
        username="alice",
        password="legacy-password",
        token="legacy-token",
        headers={"Authorization": "Bearer oauth-token"},
    )

    assert captured["username"] == "alice"
    assert captured["password"] == "legacy-password"
    assert captured["patched"] == {"Authorization": "Bearer oauth-token"}


def test_confluence_provider_prefers_injected_headers(monkeypatch) -> None:
    captured = {"patched": None}

    class FakeConfluence:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self._session = object()

    monkeypatch.setattr("atlassian_cli.products.confluence.providers.server.Confluence", FakeConfluence)
    monkeypatch.setattr(
        "atlassian_cli.products.confluence.providers.server.patch_session_headers",
        lambda session, headers: captured.__setitem__("patched", headers),
    )

    ConfluenceServerProvider(
        url="https://confluence.example.com",
        username="alice",
        password="legacy-password",
        token="legacy-token",
        headers={"Authorization": "Bearer oauth-token"},
    )

    assert captured["username"] == "alice"
    assert captured["password"] == "legacy-password"
    assert captured["patched"] == {"Authorization": "Bearer oauth-token"}


def test_bitbucket_provider_prefers_injected_headers(monkeypatch) -> None:
    captured = {"patched": None}

    class FakeBitbucket:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self._session = object()

    monkeypatch.setattr("atlassian_cli.products.bitbucket.providers.server.Bitbucket", FakeBitbucket)
    monkeypatch.setattr(
        "atlassian_cli.products.bitbucket.providers.server.patch_session_headers",
        lambda session, headers: captured.__setitem__("patched", headers),
    )

    BitbucketServerProvider(
        url="https://bitbucket.example.com",
        username="alice",
        password="legacy-password",
        token="legacy-token",
        headers={"Authorization": "Bearer oauth-token"},
    )

    assert captured["username"] == "alice"
    assert captured["password"] == "legacy-password"
    assert captured["patched"] == {"Authorization": "Bearer oauth-token"}
