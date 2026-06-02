from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_attachment_download_outputs_json(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.confluence.commands import attachment as attachment_module

    target = tmp_path / "deploy.log"
    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "download": lambda self, attachment_id, destination: {
                    "attachment_id": attachment_id,
                    "path": destination,
                    "bytes_written": 21,
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
            "attachment",
            "download",
            "55",
            "--destination",
            str(target),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"attachment_id": "55"' in result.stdout
    assert str(target) in result.stdout


def test_confluence_attachment_list_accepts_filters(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import attachment as attachment_module

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, page_id, **kwargs: {
                    "page_id": page_id,
                    "filters": kwargs,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "confluence",
            "attachment",
            "list",
            "1234",
            "--start",
            "5",
            "--limit",
            "10",
            "--filename",
            "diagram.png",
            "--media-type",
            "image/png",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"filename": "diagram.png"' in result.stdout
    assert '"media_type": "image/png"' in result.stdout
