from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_user_search_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import user as user_module

    monkeypatch.setattr(
        user_module,
        "build_user_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "search": lambda self, query: {
                    "results": [{"display_name": "Cloud User", "name": "Cloud User"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "user",
            "search",
            "--query",
            "cloud",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout
