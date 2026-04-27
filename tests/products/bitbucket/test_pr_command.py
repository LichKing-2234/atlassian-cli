from typer.testing import CliRunner

from atlassian_cli.cli import app

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
                "list": lambda self, project_key, repo_slug, state: {
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
                "list": lambda self, project_key, repo_slug, state: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Ship output cleanup",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
                "list_table": lambda self, project_key, repo_slug, state: {
                    "results": [{"id": 42, "title": "Ship output cleanup", "state": "OPEN"}]
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


def test_bitbucket_pr_list_table_uses_summary_payload(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Ship output cleanup",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
                "list_table": lambda self, project_key, repo_slug, state: {
                    "results": [{"id": 42, "title": "Ship output cleanup", "state": "OPEN"}]
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
            "table",
        ],
    )

    assert result.exit_code == 0
    assert "Ship output cleanup" in result.stdout
    assert "Long body" not in result.stdout
