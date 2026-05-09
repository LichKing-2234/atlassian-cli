from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


class FakeBuildStatusService:
    def for_pull_request(self, project_key, repo_slug, pr_id, latest_only=False):
        return {
            "pull_request": {"id": pr_id, "project_key": project_key, "repo_slug": repo_slug},
            "overall_state": "SUCCESSFUL" if latest_only else "FAILED",
            "commits": [{"commit": "abc123", "overall_state": "SUCCESSFUL", "results": []}],
        }

    def for_pull_request_raw(self, project_key, repo_slug, pr_id, latest_only=False):
        return {
            "raw": True,
            "latest_only": latest_only,
            "pull_request": {"id": pr_id, "project_key": project_key, "repo_slug": repo_slug},
            "commits": [{"commit": "abc123", "build_statuses": {"values": []}}],
        }

    def for_commit(self, commit):
        return {"commit": commit, "overall_state": "SUCCESSFUL", "results": []}

    def for_commit_raw(self, commit):
        return {"values": []}


def test_bitbucket_pr_build_status_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module, "build_build_status_service", lambda *_args: FakeBuildStatusService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "build-status",
            "DEMO",
            "example-repo",
            "42",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"overall_state": "FAILED"' in result.stdout


def test_bitbucket_pr_build_status_latest_only_forwards_flag(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module, "build_build_status_service", lambda *_args: FakeBuildStatusService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "build-status",
            "DEMO",
            "example-repo",
            "42",
            "--latest-only",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"overall_state": "SUCCESSFUL"' in result.stdout


def test_bitbucket_pr_build_status_raw_output_uses_raw_service(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module, "build_build_status_service", lambda *_args: FakeBuildStatusService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "build-status",
            "DEMO",
            "example-repo",
            "42",
            "--latest-only",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert '"raw": true' in result.stdout
    assert '"latest_only": true' in result.stdout
    assert '"build_statuses": {' in result.stdout
    assert '"overall_state"' not in result.stdout


def test_bitbucket_commit_build_status_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import commit as commit_module

    monkeypatch.setattr(
        commit_module, "build_build_status_service", lambda *_args: FakeBuildStatusService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "commit",
            "build-status",
            "abc123",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"commit": "abc123"' in result.stdout
