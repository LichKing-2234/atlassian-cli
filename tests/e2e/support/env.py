import os
from dataclasses import dataclass
from pathlib import Path

from atlassian_cli.cli import DEFAULT_CONFIG_FILE


@dataclass(frozen=True)
class LiveEnv:
    config_file: Path
    jira_project: str
    confluence_space: str
    bitbucket_project: str
    bitbucket_create_project: str
    bitbucket_repo: str
    jira_issue_type: str | None = None
    confluence_parent_page: str | None = None
    bitbucket_existing_repo: str | None = None


def load_live_env() -> LiveEnv:
    if os.getenv("ATLASSIAN_E2E") != "1":
        raise RuntimeError("ATLASSIAN_E2E=1 is required for live e2e tests")
    config_file = Path(os.getenv("ATLASSIAN_CONFIG_FILE", str(DEFAULT_CONFIG_FILE))).expanduser()
    return LiveEnv(
        config_file=config_file,
        jira_project=os.getenv("ATLASSIAN_E2E_JIRA_PROJECT", "DEMO"),
        confluence_space=os.getenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", "~example-user"),
        bitbucket_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", "DEMO"),
        bitbucket_create_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT", "DEMO"),
        bitbucket_repo=os.getenv("ATLASSIAN_E2E_BITBUCKET_REPO", "example-repo"),
        jira_issue_type=os.getenv("ATLASSIAN_E2E_JIRA_ISSUE_TYPE"),
        confluence_parent_page=os.getenv("ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE"),
        bitbucket_existing_repo=os.getenv("ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO"),
    )
