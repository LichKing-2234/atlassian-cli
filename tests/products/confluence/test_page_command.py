from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_page_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, page_id: {"id": page_id, "title": "Runbook"}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "1234"' in result.stdout
