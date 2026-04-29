from pathlib import Path


def test_readme_mentions_markdown_default_and_interactive_lists() -> None:
    readme = Path("README.md").read_text()

    assert "markdown" in readme
    assert "interactive" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
    assert "table" not in readme


def test_readme_mentions_interactive_preview_browser() -> None:
    readme = Path("README.md").read_text()

    assert "live preview" in readme.lower()
    assert "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit" in readme
    assert "bottom preview" in readme.lower()


def test_readme_mentions_full_local_e2e_suite() -> None:
    readme = Path("README.md").read_text()
    contributing = Path("CONTRIBUTING.md").read_text()

    assert "CONTRIBUTING.md" in readme
    assert "tests/e2e/test_jira_live.py" in contributing
    assert "tests/e2e/test_confluence_live.py" in contributing
    assert "tests/e2e/test_bitbucket_live.py" in contributing
    assert "ATLASSIAN_E2E=1" in contributing
    assert "ATLASSIAN_E2E_JIRA_PROJECT" in contributing
    assert "ATLASSIAN_E2E_CONFLUENCE_SPACE" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_PROJECT" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_REPO" in contributing
    assert "real writes" in contributing.lower()
