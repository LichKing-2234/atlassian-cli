import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    LiveEnv,
    assert_confluence_fixed_version,
    assert_jira_fixed_version,
    build_live_provider,
    load_live_env,
)


@pytest.fixture(scope="session")
def live_env() -> LiveEnv:
    try:
        return load_live_env()
    except RuntimeError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def jira_fixed_version(live_env: LiveEnv):
    provider = build_live_provider(Product.JIRA, live_env)
    assert_jira_fixed_version(provider)
    return provider


@pytest.fixture(scope="session")
def confluence_fixed_version(live_env: LiveEnv):
    provider = build_live_provider(Product.CONFLUENCE, live_env)
    assert_confluence_fixed_version(provider)
    return provider


@pytest.fixture
def cleanup_registry():
    registry = CleanupRegistry()
    yield registry
    registry.run()
