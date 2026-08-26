import pytest

pytestmark = pytest.mark.e2e


def test_jira_fixed_version_live(jira_fixed_version) -> None:
    """Require the Jira fixed-version fixture to complete successfully."""


def test_confluence_fixed_version_live(confluence_fixed_version) -> None:
    """Require the Confluence fixed-version fixture to complete successfully."""
