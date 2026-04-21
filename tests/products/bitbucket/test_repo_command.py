from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_bitbucket_repo_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import repo as repo_module

    monkeypatch.setattr(
        repo_module,
        "build_repo_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get": lambda self, project_key, repo_slug: {
                    "project_key": project_key,
                    "slug": repo_slug,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "repo",
            "get",
            "OPS",
            "infra",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"slug": "infra"' in result.stdout
