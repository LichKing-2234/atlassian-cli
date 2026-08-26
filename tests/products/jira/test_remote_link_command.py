import re

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def test_jira_remote_link_create_maps_all_semantic_inputs(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import remote_link as remote_link_module

    calls = {}

    class FakeService:
        def create(self, issue_key: str, **kwargs) -> dict:
            calls["args"] = (issue_key, kwargs)
            return {"issue_key": issue_key, **kwargs}

    monkeypatch.setattr(
        remote_link_module,
        "build_remote_link_service",
        lambda *_args, **_kwargs: FakeService(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "remote-link",
            "create",
            "DEMO-1",
            "--url",
            "https://example.com/DEMO-1",
            "--title",
            "Example Page",
            "--summary",
            "example response",
            "--relationship",
            "example comment",
            "--icon-url",
            "https://example.com/DEMO-1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls["args"] == (
        "DEMO-1",
        {
            "url": "https://example.com/DEMO-1",
            "title": "Example Page",
            "summary": "example response",
            "relationship": "example comment",
            "icon_url": "https://example.com/DEMO-1234",
        },
    )


def test_jira_remote_link_create_routes_raw_output(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import remote_link as remote_link_module

    class FakeService:
        def create_raw(self, issue_key: str, **kwargs) -> dict:
            return {"create_response": {"id": "10001"}, "issue_key": issue_key, **kwargs}

    monkeypatch.setattr(
        remote_link_module,
        "build_remote_link_service",
        lambda *_args, **_kwargs: FakeService(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "remote-link",
            "create",
            "DEMO-1",
            "--url",
            "https://example.com/DEMO-1",
            "--title",
            "Example Page",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"create_response"' in result.stdout


def test_jira_remote_link_create_help_lists_semantic_inputs() -> None:
    result = runner.invoke(
        app,
        ["jira", "issue", "remote-link", "create", "--help"],
        terminal_width=160,
    )

    assert result.exit_code == 0
    output = ANSI_ESCAPE_RE.sub("", result.output)
    assert "Jira 7.11 remote issue link" in output
    for option in ("--url", "--title", "--summary", "--relationship", "--icon-url"):
        assert option in output
