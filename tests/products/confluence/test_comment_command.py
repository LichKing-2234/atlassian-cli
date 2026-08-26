from click import unstyle
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_comment_write_help_names_markdown_and_storage_contract() -> None:
    for command in ("add", "reply"):
        result = runner.invoke(app, ["confluence", "comment", command, "--help"])

        assert result.exit_code == 0
        compact_output = " ".join(unstyle(result.output).replace("│", " ").split())
        assert "Comment body. Interpreted as Markdown by default." in compact_output
        assert "Input format: markdown (default) or storage (raw escape hatch)." in compact_output


def test_confluence_comment_list_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"list": lambda self, page_id: {"results": [{"id": "c1", "body": "example approval"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "comment",
            "list",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "c1"' in result.stdout


def test_confluence_comment_add_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "add": lambda self, page_id, body, *, content_format: {
                    "id": "c2",
                    "body": body,
                    "content_format": content_format,
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
            "comment",
            "add",
            "1234",
            "--body",
            "example approval comment",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "c2"' in result.stdout


def test_confluence_comment_add_accepts_storage_escape_hatch(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    captured = {}

    class FakeService:
        def add(self, page_id, body, *, content_format):
            captured.update(
                page_id=page_id,
                body=body,
                content_format=content_format,
            )
            return {"id": "c2", "body": body}

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "comment",
            "add",
            "1234",
            "--body",
            "<p>example comment</p>",
            "--content-format",
            "storage",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "page_id": "1234",
        "body": "<p>example comment</p>",
        "content_format": "storage",
    }


def test_confluence_comment_reply_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "reply": lambda self, comment_id, body, *, content_format: {
                    "id": "c3",
                    "body": body,
                    "content_format": content_format,
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
            "comment",
            "reply",
            "c1",
            "--body",
            "example response",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "c3"' in result.stdout


def test_confluence_comment_reply_accepts_storage_escape_hatch(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    captured = {}

    class FakeService:
        def reply(self, comment_id, body, *, content_format):
            captured.update(
                comment_id=comment_id,
                body=body,
                content_format=content_format,
            )
            return {"id": "c3", "body": body}

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "comment",
            "reply",
            "c1",
            "--body",
            "<p>example response</p>",
            "--content-format",
            "storage",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "comment_id": "c1",
        "body": "<p>example response</p>",
        "content_format": "storage",
    }
