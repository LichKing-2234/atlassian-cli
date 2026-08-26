from click import unstyle
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_page_label_help_describes_page_and_name_inputs() -> None:
    for command in ("list", "add"):
        result = runner.invoke(app, ["confluence", "page", "label", command, "--help"])

        assert result.exit_code == 0
        compact = " ".join(unstyle(result.output).replace("│", " ").split())
        assert "Confluence page ID." in compact
        if command == "add":
            assert "Label name to add." in compact


def test_confluence_page_label_list_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page_label as label_module

    monkeypatch.setattr(
        label_module,
        "build_label_service",
        lambda *_args: type(
            "FakeService",
            (),
            {"list": lambda self, page_id: {"results": [{"id": "55", "name": "example-repo"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "label",
            "list",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"name": "example-repo"' in result.stdout


def test_confluence_page_label_add_maps_name_and_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page_label as label_module

    captured = {}

    class FakeService:
        def add(self, page_id: str, name: str) -> dict:
            captured.update(page_id=page_id, name=name)
            return {"results": [{"id": "55", "name": name}]}

    monkeypatch.setattr(label_module, "build_label_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "label",
            "add",
            "1234",
            "--name",
            "example-repo",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {"page_id": "1234", "name": "example-repo"}
    assert '"name": "example-repo"' in result.stdout
