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


def load_live_env() -> LiveEnv:
    if os.getenv("ATLASSIAN_E2E") != "1":
        raise RuntimeError("ATLASSIAN_E2E=1 is required for live e2e tests")
    config_file = Path(os.getenv("ATLASSIAN_CONFIG_FILE", str(DEFAULT_CONFIG_FILE))).expanduser()
    return LiveEnv(
        config_file=config_file,
        jira_project=os.getenv("ATLASSIAN_E2E_JIRA_PROJECT", "EEP"),
        confluence_space=os.getenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", "ADC"),
        bitbucket_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", "~luxuhui_agora.io"),
        bitbucket_create_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT", "ADUC"),
        bitbucket_repo=os.getenv("ATLASSIAN_E2E_BITBUCKET_REPO", "atlassian-cli-e2e-test"),
    )
