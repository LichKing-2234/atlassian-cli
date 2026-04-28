from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_comment_list_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"list": lambda self, page_id: {"results": [{"id": "c1", "body": "LGTM"}]}},
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
            {"add": lambda self, page_id, body: {"id": "c2", "body": body}},
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
            "ship it",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "c2"' in result.stdout


def test_confluence_comment_reply_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"reply": lambda self, comment_id, body: {"id": "c3", "body": body}},
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
            "ack",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "c3"' in result.stdout
