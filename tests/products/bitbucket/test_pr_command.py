from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.output.interactive import CollectionPage

runner = CliRunner()


def test_bitbucket_pr_list_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [{"id": 42, "title": "Ship output cleanup", "state": "OPEN"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "OPS",
            "infra",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout


def test_bitbucket_pr_list_json_keeps_full_payload(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Ship output cleanup",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "OPS",
            "infra",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"description": "Long body"' in result.stdout


def test_bitbucket_pr_list_markdown_non_tty_uses_summary_payload(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Ship output cleanup",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "OPS",
            "infra",
            "--output",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert "Ship output cleanup" in result.stdout
    assert "Long body" not in result.stdout


def test_bitbucket_pr_list_uses_interactive_browser_for_markdown_tty(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(pr_module, "browse_collection", lambda source: calls.setdefault("source", source))
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [{"id": 42, "title": "Ship output cleanup"}],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: CollectionPage(
                    items=[{"id": 42, "title": "Ship output cleanup"}],
                    start=start,
                    limit=limit,
                    total=1,
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Ship output cleanup",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "list", "OPS", "infra"],
    )

    assert result.exit_code == 0
    assert calls["source"].title == "Bitbucket pull requests"
