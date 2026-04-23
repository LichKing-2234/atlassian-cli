from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_space_list_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import space as space_module

    monkeypatch.setattr(
        space_module,
        "build_space_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, start, limit: {
                    "results": [{"id": "1", "key": "OPS", "name": "Operations"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "space",
            "list",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout
