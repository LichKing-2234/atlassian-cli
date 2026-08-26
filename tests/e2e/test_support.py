import subprocess
import sys

import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support.cleanup import CleanupRegistry
from tests.e2e.support.context import build_live_context
from tests.e2e.support.discovery import (
    build_jira_create_payload,
    discover_jira_comment_visibilities,
    discover_jira_issue_type,
    resolve_bitbucket_repo_target,
    resolve_confluence_write_target,
)
from tests.e2e.support.env import LiveEnv, load_live_env
from tests.e2e.support.names import unique_name
from tests.e2e.support.runner import run_cli
from tests.e2e.support.versions import (
    assert_confluence_fixed_version,
    assert_jira_fixed_version,
)


def test_load_live_env_uses_defaults(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    monkeypatch.setattr("tests.e2e.support.env.DOTENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))
    monkeypatch.delenv("ATLASSIAN_E2E_JIRA_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_REPO", raising=False)

    env = load_live_env()

    assert env == LiveEnv(
        config_file=config_file,
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
        jira_issue_type=None,
        confluence_parent_page=None,
        bitbucket_existing_repo=None,
    )


def test_load_live_env_reads_repo_dotenv(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config.toml"
    reviewer_config = tmp_path / "reviewer-config.toml"
    config_file.write_text("")
    repo_dotenv = tmp_path / ".env"
    monkeypatch.setattr("tests.e2e.support.env.DOTENV_FILE", repo_dotenv)
    repo_dotenv.write_text(
        "\n".join(
            [
                "ATLASSIAN_E2E=1",
                f"ATLASSIAN_CONFIG_FILE={config_file}",
                "ATLASSIAN_E2E_JIRA_PROJECT=DEMO-1234",
                "ATLASSIAN_E2E_CONFLUENCE_SPACE=Example Page",
                "ATLASSIAN_E2E_BITBUCKET_PROJECT=DEMO",
                "ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT=DEMO",
                "ATLASSIAN_E2E_BITBUCKET_REPO=example-repo",
                "ATLASSIAN_E2E_JIRA_ISSUE_TYPE=Task",
                "ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE=123456",
                "ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO=example-repo",
                f"ATLASSIAN_E2E_BITBUCKET_REVIEWER_CONFIG={reviewer_config}",
            ]
        )
    )
    monkeypatch.delenv("ATLASSIAN_E2E", raising=False)
    monkeypatch.delenv("ATLASSIAN_CONFIG_FILE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_JIRA_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_REPO", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_JIRA_ISSUE_TYPE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_REVIEWER_CONFIG", raising=False)

    env = load_live_env()

    assert env == LiveEnv(
        config_file=config_file,
        jira_project="DEMO-1234",
        confluence_space="Example Page",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
        jira_issue_type="Task",
        confluence_parent_page="123456",
        bitbucket_existing_repo="example-repo",
        bitbucket_reviewer_config=reviewer_config,
    )


def test_load_live_env_prefers_process_env_over_repo_dotenv(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    repo_dotenv = tmp_path / ".env"
    monkeypatch.setattr("tests.e2e.support.env.DOTENV_FILE", repo_dotenv)
    repo_dotenv.write_text(
        "\n".join(
            [
                "ATLASSIAN_E2E=1",
                "ATLASSIAN_E2E_JIRA_PROJECT=DEMO-1234",
                "ATLASSIAN_E2E_CONFLUENCE_SPACE=Example Page",
            ]
        )
    )
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("ATLASSIAN_E2E_JIRA_PROJECT", "DEMO")
    monkeypatch.setenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", "~example-user")

    env = load_live_env()

    assert env.jira_project == "DEMO"
    assert env.confluence_space == "~example-user"


def test_cleanup_registry_runs_in_reverse_order() -> None:
    calls: list[str] = []
    registry = CleanupRegistry()

    registry.add("first", lambda: calls.append("first"))
    registry.add("second", lambda: calls.append("second"))
    registry.run()

    assert calls == ["second", "first"]


def test_cleanup_registry_runs_remaining_callbacks_before_reporting_failures() -> None:
    calls: list[str] = []
    registry = CleanupRegistry()

    def fail() -> None:
        raise RuntimeError("example response")

    registry.add("first", lambda: calls.append("first"))
    registry.add("broken", fail)
    registry.add("last", lambda: calls.append("last"))

    with pytest.raises(AssertionError, match="broken: example response"):
        registry.run()

    assert calls == ["last", "first"]


def test_assert_jira_fixed_version_accepts_target() -> None:
    class Provider:
        class Client:
            @staticmethod
            def get_server_info() -> dict:
                return {
                    "version": "7.11.0",
                    "buildNumber": 711000,
                    "deploymentType": "Server",
                }

        client = Client()

    assert_jira_fixed_version(Provider())


def test_assert_jira_fixed_version_rejects_other_version() -> None:
    class Provider:
        class Client:
            @staticmethod
            def get_server_info() -> dict:
                return {
                    "version": "8.0.0",
                    "buildNumber": 800000,
                    "deploymentType": "Server",
                }

        client = Client()

    with pytest.raises(AssertionError, match="expected Jira 7.11.0 build 711000 Server"):
        assert_jira_fixed_version(Provider())


def test_assert_confluence_fixed_version_accepts_target() -> None:
    class Provider:
        class Client:
            @staticmethod
            def get(path: str) -> dict:
                assert path == "rest/applinks/1.0/manifest"
                return {"typeId": "confluence", "version": "6.12.4", "buildNumber": 9667}

        client = Client()

    assert_confluence_fixed_version(Provider())


def test_assert_confluence_fixed_version_rejects_other_version() -> None:
    class Provider:
        class Client:
            @staticmethod
            def get(path: str) -> dict:
                assert path == "rest/applinks/1.0/manifest"
                return {"typeId": "confluence", "version": "7.0.0", "buildNumber": 10000}

        client = Client()

    with pytest.raises(AssertionError, match="expected Confluence 6.12.4"):
        assert_confluence_fixed_version(Provider())


def test_unique_name_includes_prefix() -> None:
    value = unique_name("issue")
    assert value.startswith("issue-")
    assert len(value) > len("issue-")


def test_run_cli_includes_config_file(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    live_env = LiveEnv(
        config_file=tmp_path / "config.toml",
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
    )

    run_cli(live_env, "jira", "project", "list", "--output", "json")

    assert calls["command"][:5] == [
        sys.executable,
        "-m",
        "atlassian_cli.main",
        "--config-file",
        str(live_env.config_file),
    ]
    assert "PYTHONPATH" in calls["env"]


def test_run_cli_reads_repo_dotenv_for_subprocess_env(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    repo_dotenv = tmp_path / ".env"
    repo_dotenv.write_text(
        "\n".join(
            [
                "ATLASSIAN_DEPLOYMENT=server",
                "ATLASSIAN_HOST=jira.example.com",
            ]
        )
    )

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr("tests.e2e.support.env.DOTENV_FILE", repo_dotenv)
    monkeypatch.delenv("ATLASSIAN_DEPLOYMENT", raising=False)
    monkeypatch.delenv("ATLASSIAN_HOST", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)
    live_env = LiveEnv(
        config_file=tmp_path / "config.toml",
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
    )

    run_cli(live_env, "jira", "project", "list", "--output", "json")

    assert calls["env"]["ATLASSIAN_DEPLOYMENT"] == "server"
    assert calls["env"]["ATLASSIAN_HOST"] == "jira.example.com"


def test_build_live_context_reads_product_config(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"
        """.strip()
    )
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))

    env = load_live_env()
    context = build_live_context(Product.JIRA, env)

    assert context.product is Product.JIRA
    assert context.url == "https://jira.example.com"
    assert context.auth.username == "example-user"


def test_build_live_context_reads_env_backed_product_config(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "${ATLASSIAN_DEPLOYMENT}"
        url = "https://${ATLASSIAN_HOST}"
        auth = "${ATLASSIAN_AUTH}"
        username = "${ATLASSIAN_USERNAME}"
        token = "${ATLASSIAN_TOKEN}"
        """.strip()
    )
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("ATLASSIAN_DEPLOYMENT", "server")
    monkeypatch.setenv("ATLASSIAN_HOST", "jira.example.com")
    monkeypatch.setenv("ATLASSIAN_AUTH", "basic")
    monkeypatch.setenv("ATLASSIAN_USERNAME", "example-user")
    monkeypatch.setenv("ATLASSIAN_TOKEN", "example-token")

    env = load_live_env()
    context = build_live_context(Product.JIRA, env)

    assert context.product is Product.JIRA
    assert context.url == "https://jira.example.com"
    assert context.auth.username == "example-user"
    assert context.auth.token == "example-token"


def test_build_live_context_reads_env_backed_product_config_from_repo_dotenv(
    tmp_path, monkeypatch
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "${ATLASSIAN_DEPLOYMENT}"
        url = "https://${ATLASSIAN_HOST}"
        auth = "${ATLASSIAN_AUTH}"
        username = "${ATLASSIAN_USERNAME}"
        token = "${ATLASSIAN_TOKEN}"
        """.strip()
    )
    repo_dotenv = tmp_path / ".env"
    repo_dotenv.write_text(
        "\n".join(
            [
                "ATLASSIAN_E2E=1",
                f"ATLASSIAN_CONFIG_FILE={config_file}",
                "ATLASSIAN_DEPLOYMENT=server",
                "ATLASSIAN_HOST=jira.example.com",
                "ATLASSIAN_AUTH=basic",
                "ATLASSIAN_USERNAME=example-user",
                "ATLASSIAN_TOKEN=example-token",
            ]
        )
    )
    monkeypatch.setattr("tests.e2e.support.env.DOTENV_FILE", repo_dotenv)
    monkeypatch.delenv("ATLASSIAN_E2E", raising=False)
    monkeypatch.delenv("ATLASSIAN_CONFIG_FILE", raising=False)
    monkeypatch.delenv("ATLASSIAN_DEPLOYMENT", raising=False)
    monkeypatch.delenv("ATLASSIAN_HOST", raising=False)
    monkeypatch.delenv("ATLASSIAN_AUTH", raising=False)
    monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
    monkeypatch.delenv("ATLASSIAN_TOKEN", raising=False)

    env = load_live_env()
    context = build_live_context(Product.JIRA, env)

    assert context.product is Product.JIRA
    assert context.url == "https://jira.example.com"
    assert context.auth.username == "example-user"
    assert context.auth.token == "example-token"


class FakeJiraProvider:
    class Client:
        def issue_createmeta(self, project_key, expand):
            assert project_key == "DEMO"
            assert expand == "projects.issuetypes.fields"
            return {
                "projects": [
                    {
                        "issuetypes": [
                            {
                                "name": "Task",
                                "fields": {
                                    "summary": {"required": True},
                                    "customfield_10001": {
                                        "required": True,
                                        "allowedValues": [{"id": "11", "value": "Linux"}],
                                    },
                                    "customfield_10002": {
                                        "required": True,
                                        "schema": {"type": "array"},
                                        "allowedValues": [
                                            {"id": "12", "value": "example response"}
                                        ],
                                    },
                                    "reporter": {"required": True},
                                },
                            }
                        ]
                    }
                ]
            }

    def __init__(self) -> None:
        self.client = self.Client()


def test_build_jira_create_payload_uses_allowed_value_defaults() -> None:
    payload = build_jira_create_payload(
        FakeJiraProvider(),
        project_key="DEMO",
        summary="Example issue summary",
        issue_type="Task",
        env_overrides={},
        reporter_name="example-user",
    )

    assert payload["project"]["key"] == "DEMO"
    assert payload["customfield_10001"] == {"id": "11"}
    assert payload["customfield_10002"] == [{"id": "12"}]
    assert payload["reporter"] == {"name": "example-user"}


def test_build_jira_create_payload_raises_clear_error_for_unknown_issue_type() -> None:
    try:
        build_jira_create_payload(
            FakeJiraProvider(),
            project_key="DEMO",
            summary="Example issue summary",
            issue_type="Bug",
            env_overrides={},
            reporter_name="example-user",
        )
    except RuntimeError as exc:
        assert "issue type" in str(exc)
        assert "ATLASSIAN_E2E_JIRA_ISSUE_TYPE" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_discover_jira_issue_type_selects_writable_non_subtask() -> None:
    assert (
        discover_jira_issue_type(
            FakeJiraProvider(),
            project_key="DEMO",
            reporter_name="example-user",
        )
        == "Task"
    )


def test_discover_jira_comment_visibilities_returns_project_roles() -> None:
    class FakeProvider:
        class Client:
            def get(self, path: str) -> dict:
                assert path == "rest/api/2/project/DEMO/role"
                return {"reviewer-one": "https://jira.example.com/rest/api/2/project/DEMO/role/1"}

        client = Client()

    assert discover_jira_comment_visibilities(FakeProvider(), "DEMO") == [
        {"type": "role", "value": "reviewer-one"}
    ]


def test_resolve_confluence_write_target_prefers_explicit_parent(tmp_path) -> None:
    env = LiveEnv(
        config_file=tmp_path / "config.toml",
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
        confluence_parent_page="1234",
    )

    target = resolve_confluence_write_target(env)

    assert target == {"space_key": "~example-user", "parent_page_id": "1234"}


def test_resolve_bitbucket_repo_target_uses_override_when_present(tmp_path) -> None:
    env = LiveEnv(
        config_file=tmp_path / "config.toml",
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
        bitbucket_existing_repo="sandbox-repo",
    )

    target = resolve_bitbucket_repo_target(env)

    assert target == {"project_key": "DEMO", "repo_slug": "sandbox-repo"}
