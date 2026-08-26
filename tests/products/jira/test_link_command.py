from __future__ import annotations

import click
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


class FakeLinkService:
    def create(self, **kwargs) -> dict:
        return {"status": "created", "created": True, "link": kwargs}

    def create_raw(self, **kwargs) -> dict:
        return {"raw": kwargs}

    def list(self, issue_key: str) -> dict:
        return {"issue_key": issue_key, "results": [{"id": "10001"}]}

    def list_raw(self, issue_key: str) -> list[dict]:
        return [{"id": "10001", "issue": issue_key}]

    def delete(self, link_id: str) -> dict:
        return {"id": link_id, "deleted": True}

    def delete_raw(self, link_id: str) -> dict:
        return {"id": link_id, "deleted": True, "raw": True}

    def types(self, name_filter: str | None = None) -> dict:
        return {
            "results": [{"id": "10000", "name": "Cloners"}],
            "name_filter": name_filter,
        }

    def types_raw(self, name_filter: str | None = None) -> list[dict]:
        return [
            {
                "id": "10000",
                "name": "Cloners",
                "name_filter": name_filter,
                "raw": True,
            }
        ]


def install_fake_service(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import link as link_module

    monkeypatch.setattr(link_module, "build_issue_link_service", lambda *_args: FakeLinkService())


def invoke(*args: str):
    return runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "link", *args],
        terminal_width=160,
    )


def test_jira_issue_link_create_passes_explicit_direction(monkeypatch) -> None:
    install_fake_service(monkeypatch)

    result = invoke(
        "create",
        "--inward",
        "DEMO-1",
        "--outward",
        "DEMO-1234",
        "--type",
        "Cloners",
        "--comment",
        "example comment",
        "--comment-visibility",
        '{"type":"group","value":"reviewer-one"}',
        "--output",
        "json",
    )

    assert result.exit_code == 0
    assert '"inward_issue": "DEMO-1"' in result.stdout
    assert '"outward_issue": "DEMO-1234"' in result.stdout
    assert '"comment": "example comment"' in result.stdout
    assert '"comment_visibility"' in result.stdout
    assert '"value": "reviewer-one"' in result.stdout


def test_jira_issue_link_commands_route_standard_and_raw_output(monkeypatch) -> None:
    install_fake_service(monkeypatch)

    listed = invoke("list", "DEMO-1", "--output", "json")
    raw_types = invoke("types", "--output", "raw-json")
    raw_create = invoke(
        "create",
        "--inward",
        "DEMO-1",
        "--outward",
        "DEMO-1234",
        "--type",
        "Cloners",
        "--output",
        "raw-json",
    )

    assert listed.exit_code == raw_types.exit_code == raw_create.exit_code == 0
    assert '"issue_key": "DEMO-1"' in listed.stdout
    assert '"raw": true' in raw_types.stdout
    assert '"raw"' in raw_create.stdout


def test_jira_issue_link_delete_requires_yes(monkeypatch) -> None:
    install_fake_service(monkeypatch)

    rejected = invoke("delete", "10001", "--output", "json")
    deleted = invoke("delete", "10001", "--yes", "--output", "json")

    assert rejected.exit_code != 0
    assert "pass --yes to confirm delete" in click.unstyle(rejected.output)
    assert deleted.exit_code == 0
    assert '"deleted": true' in deleted.stdout


def test_jira_issue_link_types_passes_name_filter(monkeypatch) -> None:
    install_fake_service(monkeypatch)

    result = invoke("types", "--name-filter", "clone", "--output", "json")

    assert result.exit_code == 0
    assert '"name_filter": "clone"' in result.stdout


def test_jira_issue_link_create_rejects_incomplete_comment_visibility(monkeypatch) -> None:
    install_fake_service(monkeypatch)

    result = invoke(
        "create",
        "--inward",
        "DEMO-1",
        "--outward",
        "DEMO-1234",
        "--type",
        "Cloners",
        "--comment-visibility",
        '{"type":"group"}',
    )

    assert result.exit_code != 0
    plain_output = " ".join(click.unstyle(result.output).replace("│", " ").split())
    assert "must contain string type and value" in plain_output
