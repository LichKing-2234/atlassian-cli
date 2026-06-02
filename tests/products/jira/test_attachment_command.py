from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_issue_attachment_list_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import attachment as attachment_module

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"list": lambda self, issue_key: {"results": [{"filename": "report.pdf"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "attachment",
            "list",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"filename": "report.pdf"' in result.stdout


def test_jira_issue_attachment_upload_uses_positional_file(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import attachment as attachment_module

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "upload": lambda self, issue_key, file_path: {
                    "issue_key": issue_key,
                    "filename": file_path,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "attachment",
            "upload",
            "DEMO-1",
            "./report.pdf",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"issue_key": "DEMO-1"' in result.stdout
    assert '"filename": "./report.pdf"' in result.stdout


def test_jira_issue_attachment_download_outputs_json(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.jira.commands import attachment as attachment_module

    target = tmp_path / "report.pdf"
    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "download": lambda self, issue_key, *, name, destination: {
                    "issue_key": issue_key,
                    "filename": name,
                    "path": destination,
                    "bytes_written": 15,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "attachment",
            "download",
            "DEMO-1",
            "--name",
            "report.pdf",
            "--destination",
            str(target),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"filename": "report.pdf"' in result.stdout
    assert str(target) in result.stdout
