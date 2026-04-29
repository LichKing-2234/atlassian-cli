import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    GitSandbox,
    build_live_provider,
    run_json,
    unique_name,
)

pytestmark = pytest.mark.e2e


def _delete_repo(live_env, repo_slug: str) -> None:
    provider = build_live_provider(Product.BITBUCKET, live_env)
    provider.client.delete_repo(live_env.bitbucket_create_project, repo_slug)


def test_bitbucket_project_and_repo_queries_live(live_env) -> None:
    projects = run_json(live_env, "bitbucket", "project", "list", "--output", "json")
    assert projects["results"]

    project = run_json(
        live_env,
        "bitbucket",
        "project",
        "get",
        live_env.bitbucket_project,
        "--output",
        "json",
    )
    assert project["key"].lower() == live_env.bitbucket_project.lower()

    repos = run_json(
        live_env,
        "bitbucket",
        "repo",
        "list",
        "--project",
        live_env.bitbucket_project,
        "--output",
        "json",
    )
    assert any(item["slug"] == live_env.bitbucket_repo for item in repos["results"])

    repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--output",
        "json",
    )
    assert repo["slug"] == live_env.bitbucket_repo


def test_bitbucket_repo_create_live(live_env) -> None:
    registry = CleanupRegistry()
    repo_name = unique_name("atlassian-cli-e2e-repo")
    repo_slug = None
    try:
        created = run_json(
            live_env,
            "bitbucket",
            "repo",
            "create",
            "--project",
            live_env.bitbucket_create_project,
            "--name",
            repo_name,
            "--output",
            "json",
        )
        repo_slug = created["slug"]
        registry.add(
            f"bitbucket repo delete {repo_slug}", lambda: _delete_repo(live_env, repo_slug)
        )
        assert created["name"] == repo_name
    finally:
        registry.run()


def test_bitbucket_branch_and_pr_round_trip_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    raw_repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--output",
        "raw-json",
    )
    clone_links = raw_repo.get("links", {}).get("clone", [])
    clone_url = next(
        (
            link["href"]
            for preferred in ("ssh", "http")
            for link in clone_links
            if link.get("name") == preferred
        ),
        None,
    )
    assert clone_url is not None

    branch_name = unique_name("e2e-branch")
    sandbox_path = tmp_path / "repo"
    sandbox = GitSandbox.clone(clone_url, sandbox_path)
    sandbox.configure_identity()
    if not sandbox.has_head():
        sandbox.create_initial_commit(
            "master",
            "README.md",
            "# atlassian-cli e2e\n",
            "test: seed e2e repo",
        )
    remote_heads = sandbox.run("ls-remote", "--heads", "origin").stdout
    if "refs/heads/master" not in remote_heads:
        sandbox.push_head_to_branch("master")
        remote_heads = sandbox.run("ls-remote", "--heads", "origin").stdout
    assert "refs/heads/master" in remote_heads

    sandbox.create_commit(
        branch_name,
        "e2e-note.txt",
        f"{branch_name}\n",
        f"test: add {branch_name}",
    )
    sandbox.push(branch_name)
    registry.add(
        f"bitbucket branch delete {branch_name}",
        lambda: sandbox.delete_remote_branch(branch_name),
    )

    branches = run_json(
        live_env,
        "bitbucket",
        "branch",
        "list",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--filter",
        branch_name,
        "--output",
        "json",
    )
    assert any(item["display_id"] == branch_name for item in branches["results"])

    created_pr = run_json(
        live_env,
        "bitbucket",
        "pr",
        "create",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--title",
        unique_name("e2e-pr"),
        "--description",
        "created by live e2e",
        "--from-ref",
        f"refs/heads/{branch_name}",
        "--to-ref",
        "refs/heads/master",
        "--output",
        "json",
    )
    pr_id = created_pr["id"]

    listed = run_json(
        live_env,
        "bitbucket",
        "pr",
        "list",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--state",
        "OPEN",
        "--output",
        "json",
    )
    assert any(item["id"] == pr_id for item in listed["results"])

    fetched = run_json(
        live_env,
        "bitbucket",
        "pr",
        "get",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        str(pr_id),
        "--output",
        "json",
    )
    assert fetched["id"] == pr_id

    merged = run_json(
        live_env,
        "bitbucket",
        "pr",
        "merge",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        str(pr_id),
        "--output",
        "json",
    )
    assert merged["id"] == pr_id
    assert merged["state"] == "MERGED"
