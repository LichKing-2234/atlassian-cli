import pytest

from atlassian_cli.auth.models import AuthMode, ResolvedAuth
from atlassian_cli.config.models import Deployment, Product
from atlassian_cli.core.context import ExecutionContext
from atlassian_cli.core.errors import UnsupportedError
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def test_build_provider_returns_jira_server_provider() -> None:
    context = ExecutionContext(
        profile="prod-jira",
        product=Product.JIRA,
        deployment=Deployment.SERVER,
        url="https://jira.example.com",
        output="table",
        auth=ResolvedAuth(mode=AuthMode.BASIC, username="alice", token="secret"),
    )

    provider = build_provider(context)

    assert isinstance(provider, JiraServerProvider)


def test_build_provider_rejects_cloud() -> None:
    context = ExecutionContext(
        profile="cloud-jira",
        product=Product.JIRA,
        deployment=Deployment.CLOUD,
        url="https://example.atlassian.net",
        output="table",
        auth=ResolvedAuth(mode=AuthMode.BASIC, username="alice", token="secret"),
    )

    with pytest.raises(UnsupportedError):
        build_provider(context)
