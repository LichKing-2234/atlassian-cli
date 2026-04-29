import subprocess
import sys

from atlassian_cli.config.models import Product
from tests.e2e.support.cleanup import CleanupRegistry
from tests.e2e.support.context import build_live_context
from tests.e2e.support.env import LiveEnv, load_live_env
from tests.e2e.support.names import unique_name
from tests.e2e.support.runner import run_cli


def test_load_live_env_uses_defaults(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))
    monkeypatch.delenv("ATLASSIAN_E2E_JIRA_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_REPO", raising=False)

    env = load_live_env()

    assert env == LiveEnv(
        config_file=config_file,
        jira_project="TEST",
        confluence_space="~user@example.com",
        bitbucket_project="~example_user",
        bitbucket_create_project="EXAMPLE",
        bitbucket_repo="example-e2e-repo",
    )


def test_cleanup_registry_runs_in_reverse_order() -> None:
    calls: list[str] = []
    registry = CleanupRegistry()

    registry.add("first", lambda: calls.append("first"))
    registry.add("second", lambda: calls.append("second"))
    registry.run()

    assert calls == ["second", "first"]


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
        jira_project="TEST",
        confluence_space="~user@example.com",
        bitbucket_project="~example_user",
        bitbucket_create_project="EXAMPLE",
        bitbucket_repo="example-e2e-repo",
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


def test_build_live_context_reads_product_config(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "alice"
        token = "secret"
        """.strip()
    )
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))

    env = load_live_env()
    context = build_live_context(Product.JIRA, env)

    assert context.product is Product.JIRA
    assert context.url == "https://jira.example.com"
    assert context.auth.username == "alice"
