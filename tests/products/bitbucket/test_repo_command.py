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
            "PROJ",
            "infra",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"slug": "infra"' in result.stdout


def test_bitbucket_repo_create_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import repo as repo_module

    monkeypatch.setattr(
        repo_module,
        "build_repo_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "create": lambda self, project_key, name, scm_id: {
                    "slug": "atlassian-cli-e2e-temp",
                    "name": name,
                    "project": {"key": project_key},
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
            "create",
            "--project",
            "~example_user",
            "--name",
            "atlassian-cli-e2e-temp",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"slug": "atlassian-cli-e2e-temp"' in result.stdout
