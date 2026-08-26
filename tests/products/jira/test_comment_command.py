import pytest
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_comment_add_forwards_visibility_and_jira_markup(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    captured = {}

    class FakeService:
        def add(self, issue_key, body, *, visibility, body_format):
            captured.update(
                issue_key=issue_key,
                body=body,
                visibility=visibility,
                body_format=body_format,
            )
            return {"id": "10001", "body": body, "visibility": visibility}

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "add",
            "DEMO-1",
            "--body",
            "h2. Example response",
            "--body-format",
            "jira",
            "--visibility",
            '{"type":"role","value":"reviewer-one"}',
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "issue_key": "DEMO-1",
        "body": "h2. Example response",
        "visibility": {"type": "role", "value": "reviewer-one"},
        "body_format": "jira",
    }


def test_jira_comment_add_rejects_unknown_body_format() -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "add",
            "DEMO-1",
            "--body",
            "example comment",
            "--body-format",
            "html",
        ],
    )

    assert result.exit_code == 2
    assert "markdown" in result.output
    assert "jira" in result.output


@pytest.mark.parametrize(
    "visibility",
    [
        "not-json",
        "[]",
        '{"type":"user","value":"example-user-id"}',
        '{"type":"role"}',
        '{"type":"group","value":""}',
    ],
)
def test_jira_comment_add_rejects_invalid_core_visibility(monkeypatch, visibility) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args: pytest.fail("invalid visibility reached the service"),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "add",
            "DEMO-1",
            "--body",
            "example comment",
            "--visibility",
            visibility,
        ],
    )

    assert result.exit_code == 2
    assert "visibility" in result.output


def test_jira_comment_add_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "add": lambda self, issue_key, body, **_kwargs: {
                    "id": "10001",
                    "body": body,
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
            "comment",
            "add",
            "DEMO-1",
            "--body",
            "example approval comment",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "10001"' in result.stdout


def test_jira_comment_edit_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "edit": lambda self, issue_key, comment_id, body, **_kwargs: {
                    "id": comment_id,
                    "body": body,
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
            "comment",
            "edit",
            "DEMO-1",
            "10001",
            "--body",
            "updated",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "10001"' in result.stdout


def test_jira_comment_edit_forwards_visibility_and_jira_markup(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    captured = {}

    class FakeService:
        def edit(self, issue_key, comment_id, body, *, visibility, body_format):
            captured.update(
                issue_key=issue_key,
                comment_id=comment_id,
                body=body,
                visibility=visibility,
                body_format=body_format,
            )
            return {"id": comment_id, "body": body, "visibility": visibility}

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "edit",
            "DEMO-1",
            "10001",
            "--body",
            "{code}example response{code}",
            "--body-format",
            "jira",
            "--visibility",
            '{"type":"group","value":"reviewer-one"}',
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "issue_key": "DEMO-1",
        "comment_id": "10001",
        "body": "{code}example response{code}",
        "visibility": {"type": "group", "value": "reviewer-one"},
        "body_format": "jira",
    }


def test_jira_comment_raw_output_routes_new_inputs(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    captured = []

    class FakeService:
        def add_raw(self, issue_key, body, *, visibility, body_format):
            captured.append(("add", issue_key, None, body, visibility, body_format))
            return {"id": "10001", "body": body, "visibility": visibility}

        def edit_raw(self, issue_key, comment_id, body, *, visibility, body_format):
            captured.append(("edit", issue_key, comment_id, body, visibility, body_format))
            return {"id": comment_id, "body": body, "visibility": visibility}

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeService())

    added = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "add",
            "DEMO-1",
            "--body",
            "h2. Example response",
            "--body-format",
            "jira",
            "--visibility",
            '{"type":"role","value":"reviewer-one"}',
            "--output",
            "raw-json",
        ],
    )
    edited = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "edit",
            "DEMO-1",
            "10001",
            "--body",
            "{code}example response{code}",
            "--body-format",
            "jira",
            "--visibility",
            '{"type":"group","value":"reviewer-one"}',
            "--output",
            "raw-json",
        ],
    )

    assert added.exit_code == edited.exit_code == 0
    assert captured == [
        (
            "add",
            "DEMO-1",
            None,
            "h2. Example response",
            {"type": "role", "value": "reviewer-one"},
            "jira",
        ),
        (
            "edit",
            "DEMO-1",
            "10001",
            "{code}example response{code}",
            {"type": "group", "value": "reviewer-one"},
            "jira",
        ),
    ]
