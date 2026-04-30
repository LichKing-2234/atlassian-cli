import os
from dataclasses import dataclass
from pathlib import Path

from atlassian_cli.cli import DEFAULT_CONFIG_FILE

REPO_ROOT = Path(__file__).resolve().parents[3]
DOTENV_FILE = REPO_ROOT / ".env"


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


def _load_dotenv_values() -> dict[str, str]:
    if not DOTENV_FILE.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in DOTENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _env_value(
    name: str, default: str | None = None, *, dotenv_values: dict[str, str]
) -> str | None:
    if name in os.environ:
        return os.environ[name]
    return dotenv_values.get(name, default)


def load_live_env() -> LiveEnv:
    dotenv_values = _load_dotenv_values()
    if _env_value("ATLASSIAN_E2E", dotenv_values=dotenv_values) != "1":
        raise RuntimeError("ATLASSIAN_E2E=1 is required for live e2e tests")
    config_file = Path(
        _env_value("ATLASSIAN_CONFIG_FILE", str(DEFAULT_CONFIG_FILE), dotenv_values=dotenv_values)
    ).expanduser()
    return LiveEnv(
        config_file=config_file,
        jira_project=_env_value("ATLASSIAN_E2E_JIRA_PROJECT", "DEMO", dotenv_values=dotenv_values),
        confluence_space=_env_value(
            "ATLASSIAN_E2E_CONFLUENCE_SPACE", "~example-user", dotenv_values=dotenv_values
        ),
        bitbucket_project=_env_value(
            "ATLASSIAN_E2E_BITBUCKET_PROJECT", "DEMO", dotenv_values=dotenv_values
        ),
        bitbucket_create_project=_env_value(
            "ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT", "DEMO", dotenv_values=dotenv_values
        ),
        bitbucket_repo=_env_value(
            "ATLASSIAN_E2E_BITBUCKET_REPO", "example-repo", dotenv_values=dotenv_values
        ),
        jira_issue_type=_env_value("ATLASSIAN_E2E_JIRA_ISSUE_TYPE", dotenv_values=dotenv_values),
        confluence_parent_page=_env_value(
            "ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE", dotenv_values=dotenv_values
        ),
        bitbucket_existing_repo=_env_value(
            "ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO", dotenv_values=dotenv_values
        ),
    )
