import re

from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.products.confluence.services.attachment import AttachmentService

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


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


def test_confluence_attachment_upload_accepts_base64_content(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import attachment as attachment_module

    calls = {}

    class FakeService:
        def upload(self, page_id: str, file_path: str | None, **kwargs) -> dict:
            calls["args"] = (page_id, file_path, kwargs)
            return {"id": "55", "title": kwargs["filename"]}

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: FakeService(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "attachment",
            "upload",
            "1234",
            "--content-base64",
            "ZXhhbXBsZSByZXNwb25zZQ==",
            "--filename",
            "diagram.png",
            "--comment",
            "example comment",
            "--minor-edit",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls["args"] == (
        "1234",
        None,
        {
            "content_base64": "ZXhhbXBsZSByZXNwb25zZQ==",
            "filename": "diagram.png",
            "comment": "example comment",
            "minor_edit": True,
        },
    )
    assert '"title": "diagram.png"' in result.stdout


def test_confluence_attachment_upload_rejects_invalid_sources_before_http(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import attachment as attachment_module

    class FailProvider:
        def upload_attachment(self, *_args, **_kwargs):
            raise AssertionError("HTTP upload must not run for invalid input")

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: AttachmentService(provider=FailProvider()),
    )

    cases = [
        ([], "provide exactly one of --file or --content-base64"),
        (
            ["--file", "diagram.png", "--content-base64", "ZXhhbXBsZQ=="],
            "provide exactly one of --file or --content-base64",
        ),
        (["--content-base64", "ZXhhbXBsZQ=="], "--filename is required"),
        (
            ["--content-base64", "not-base64!", "--filename", "diagram.png"],
            "invalid --content-base64",
        ),
    ]

    for args, expected in cases:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://confluence.example.com",
                "confluence",
                "attachment",
                "upload",
                "1234",
                *args,
            ],
        )

        assert result.exit_code != 0
        assert expected in ANSI_ESCAPE_RE.sub("", result.output)


def test_confluence_attachment_upload_help_documents_aligned_inputs() -> None:
    commands = [
        ["confluence", "attachment", "upload", "--help"],
        ["confluence", "page", "attachment", "upload", "--help"],
    ]

    for command in commands:
        result = runner.invoke(app, command)

        assert result.exit_code == 0
        output = " ".join(ANSI_ESCAPE_RE.sub("", result.output).split())
        for value in (
            "--content-base64",
            "--filename",
            "--comment",
            "--minor-edit",
            "--no-minor-edit",
            "Defaults to false.",
        ):
            assert value in output
