from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_field_search_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import field as field_module

    calls = {}

    def search(_self, keyword, *, limit):
        calls["args"] = (keyword, limit)
        return {"results": [{"id": "customfield_10001", "name": "Story Points", "type": "number"}]}

    monkeypatch.setattr(
        field_module,
        "build_field_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"search": search},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "field",
            "search",
            "--keyword",
            "story",
            "--limit",
            "1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"name": "Story Points"' in result.stdout
    assert calls["args"] == ("story", 1)


def test_jira_field_options_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import field as field_module

    calls = {}

    def options(
        _self,
        field_id,
        *,
        project_key,
        issue_type,
        contains,
        return_limit,
    ):
        calls["args"] = (
            field_id,
            project_key,
            issue_type,
            contains,
            return_limit,
        )
        return {"results": [{"id": "1", "value": "One"}]}

    monkeypatch.setattr(
        field_module,
        "build_field_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"options": options},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "field",
            "options",
            "customfield_10001",
            "--project-key",
            "DEMO",
            "--issue-type",
            "Bug",
            "--contains",
            "one",
            "--return-limit",
            "1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"value": "One"' in result.stdout
    assert calls["args"] == ("customfield_10001", "DEMO", "Bug", "one", 1)
