from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


class FakeCommentService:
    def list(self, project_key, repo_slug, pr_id, start=0, limit=25):
        return {
            "results": [{"id": "1001", "text": "example comment"}],
            "start_at": start,
            "max_results": limit,
        }

    def list_raw(self, project_key, repo_slug, pr_id, start=0, limit=25):
        return [{"id": 1001, "text": "example comment"}]

    def get(self, project_key, repo_slug, pr_id, comment_id):
        return {"id": comment_id, "text": "example comment"}

    def get_raw(self, project_key, repo_slug, pr_id, comment_id):
        return {"id": int(comment_id), "text": "example comment"}

    def add(self, project_key, repo_slug, pr_id, text):
        return {"id": "1002", "text": text}

    def add_raw(self, project_key, repo_slug, pr_id, text):
        return {"id": 1002, "text": text}

    def reply(self, project_key, repo_slug, pr_id, parent_id, text):
        return {"id": "1003", "text": text, "parent": {"id": parent_id}}

    def reply_raw(self, project_key, repo_slug, pr_id, parent_id, text):
        return {"id": 1003, "text": text, "parent": {"id": int(parent_id)}}

    def edit(self, project_key, repo_slug, pr_id, comment_id, text, version):
        return {"id": comment_id, "version": version + 1, "text": text}

    def edit_raw(self, project_key, repo_slug, pr_id, comment_id, text, version):
        return {"id": int(comment_id), "version": version + 1, "text": text}

    def delete(self, project_key, repo_slug, pr_id, comment_id, version):
        return {"id": comment_id, "deleted": True}

    def delete_raw(self, project_key, repo_slug, pr_id, comment_id, version):
        return {}


def test_bitbucket_pr_comment_commands_output_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(
        comment_module, "build_comment_service", lambda *_args: FakeCommentService()
    )

    commands = [
        ["list", "DEMO", "example-repo", "42"],
        ["get", "DEMO", "example-repo", "42", "1001"],
        ["add", "DEMO", "example-repo", "42", "example comment"],
        ["reply", "DEMO", "example-repo", "42", "1001", "example response"],
        ["edit", "DEMO", "example-repo", "42", "1001", "example comment", "--version", "3"],
        ["delete", "DEMO", "example-repo", "42", "1001", "--version", "4"],
    ]

    for command in commands:
        result = runner.invoke(
            app,
            [
                "--url",
                "https://bitbucket.example.com",
                "bitbucket",
                "pr",
                "comment",
                *command,
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0
        assert result.stdout.strip().startswith("{")


def test_bitbucket_pr_comment_raw_output_uses_raw_service(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(
        comment_module, "build_comment_service", lambda *_args: FakeCommentService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "get",
            "DEMO",
            "example-repo",
            "42",
            "1001",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": 1001' in result.stdout


def test_bitbucket_pr_comment_edit_requires_version(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(
        comment_module, "build_comment_service", lambda *_args: FakeCommentService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "edit",
            "DEMO",
            "example-repo",
            "42",
            "1001",
            "example comment",
        ],
    )

    assert result.exit_code != 0
    assert "--version" in result.output
