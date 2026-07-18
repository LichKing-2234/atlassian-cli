from dataclasses import replace

import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    GitSandbox,
    build_live_provider,
    resolve_bitbucket_repo_target,
    run_cli,
    run_json,
    unique_name,
)

pytestmark = pytest.mark.e2e


def _delete_repo(live_env, repo_slug: str) -> None:
    provider = build_live_provider(Product.BITBUCKET, live_env)
    provider.client.delete_repo(live_env.bitbucket_create_project, repo_slug)


def test_bitbucket_project_and_repo_queries_live(live_env) -> None:
    target = resolve_bitbucket_repo_target(live_env)
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
        target["project_key"],
        "--output",
        "json",
    )
    assert any(item["slug"] == target["repo_slug"] for item in repos["results"])

    repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        target["project_key"],
        target["repo_slug"],
        "--output",
        "json",
    )
    assert repo["slug"] == target["repo_slug"]


def test_bitbucket_repo_create_live(live_env) -> None:
    registry = CleanupRegistry()
    repo_name = unique_name("example-repo")
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


def test_bitbucket_pr_checks_live(live_env, tmp_path, request) -> None:
    registry = CleanupRegistry()
    request.addfinalizer(registry.run)
    created_repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "create",
        "--project",
        live_env.bitbucket_create_project,
        "--name",
        unique_name("example-repo"),
        "--output",
        "json",
    )
    repo_slug = created_repo["slug"]
    registry.add(
        f"bitbucket repo delete {repo_slug}",
        lambda: _delete_repo(live_env, repo_slug),
    )
    target = {
        "project_key": live_env.bitbucket_create_project,
        "repo_slug": repo_slug,
    }
    raw_repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        target["project_key"],
        target["repo_slug"],
        "--output",
        "raw-json",
    )
    ssh_clone_url = next(
        (
            link["href"]
            for link in raw_repo.get("links", {}).get("clone", [])
            if link.get("name") == "ssh"
        ),
        None,
    )
    assert ssh_clone_url is not None

    branch_name = unique_name("feature/DEMO-1234/example-change")
    sandbox = GitSandbox.clone(ssh_clone_url, tmp_path / "repo")
    sandbox.configure_identity()
    if not sandbox.has_head():
        sandbox.create_initial_commit(
            "master",
            "README.md",
            "example response\n",
            "test: seed example-repo",
        )
    remote_heads = sandbox.run("ls-remote", "--heads", "origin").stdout
    if "refs/heads/master" not in remote_heads:
        sandbox.push_head_to_branch("master")

    sandbox.create_commit(
        branch_name,
        "example.py",
        f"{branch_name}\n",
        f"test: add {branch_name}",
    )
    sandbox.push(branch_name)
    head_commit = sandbox.run("rev-parse", "HEAD").stdout.strip()

    created_pr = run_json(
        live_env,
        "bitbucket",
        "pr",
        "create",
        target["project_key"],
        target["repo_slug"],
        "--title",
        "Example issue summary",
        "--description",
        "example comment",
        "--from-ref",
        f"refs/heads/{branch_name}",
        "--to-ref",
        "refs/heads/master",
        "--output",
        "json",
    )
    pr_id = created_pr["id"]
    repo_selector = f"{target['project_key']}/{target['repo_slug']}"

    provider = build_live_provider(Product.BITBUCKET, live_env)
    build_response = provider.request_api(
        "POST",
        f"rest/build-status/1.0/commits/{head_commit}",
        headers=None,
        params=None,
        json_body={
            "description": "example response",
            "key": "DEMO-1234",
            "name": "Example pull request",
            "state": "SUCCESSFUL",
            "url": "https://bitbucket.example.com/example-response",
        },
        data=None,
    )
    assert build_response.status_code < 300, build_response.text

    checked = run_json(
        live_env,
        "bitbucket",
        "pr",
        "checks",
        str(pr_id),
        "-R",
        repo_selector,
        "--json",
        "name,state,bucket,link",
    )
    assert checked == [
        {
            "bucket": "pass",
            "link": "https://bitbucket.example.com/example-response",
            "name": "Example pull request",
            "state": "SUCCESS",
        }
    ]

    for extra in ((), ("--watch",)):
        result = run_cli(
            live_env,
            "bitbucket",
            "pr",
            "checks",
            str(pr_id),
            "-R",
            repo_selector,
            *extra,
        )
        assert result.returncode == 0, result.stderr
        assert "Example pull request\tpass\t0\t" in result.stdout


def test_bitbucket_branch_and_pr_round_trip_live(live_env, tmp_path, request) -> None:
    registry = CleanupRegistry()
    request.addfinalizer(registry.run)
    target = resolve_bitbucket_repo_target(live_env)
    raw_repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        target["project_key"],
        target["repo_slug"],
        "--output",
        "raw-json",
    )
    clone_links = raw_repo.get("links", {}).get("clone", [])
    ssh_clone_url = next(
        (link["href"] for link in clone_links if link.get("name") == "ssh"),
        None,
    )
    http_clone_url = next(
        (link["href"] for link in clone_links if link.get("name") == "http"),
        None,
    )
    assert ssh_clone_url is not None
    assert http_clone_url is not None

    branch_name = unique_name("feature/DEMO-1234/example-change")
    sandbox_path = tmp_path / "repo"
    sandbox = GitSandbox.clone(ssh_clone_url, sandbox_path)
    sandbox.configure_identity()
    if not sandbox.has_head():
        sandbox.create_initial_commit(
            "master",
            "README.md",
            "# example response\n",
            "test: seed example-repo",
        )
    remote_heads = sandbox.run("ls-remote", "--heads", "origin").stdout
    if "refs/heads/master" not in remote_heads:
        sandbox.push_head_to_branch("master")
        remote_heads = sandbox.run("ls-remote", "--heads", "origin").stdout
    assert "refs/heads/master" in remote_heads

    sandbox.create_commit(
        branch_name,
        "example.py",
        f"{branch_name}\n",
        f"test: add {branch_name}",
    )
    sandbox.push(branch_name)
    registry.add(
        f"bitbucket branch delete {branch_name}",
        lambda: sandbox.delete_remote_branch(branch_name),
    )

    compare_endpoint = f"projects/{target['project_key']}/repos/{target['repo_slug']}/compare"
    compare_head_commit = sandbox.run("rev-parse", "HEAD").stdout.strip()
    compare_fields = [
        "-f",
        f"from=refs/heads/{branch_name}",
        "-f",
        "to=refs/heads/master",
    ]

    compared_diff = run_json(
        live_env,
        "bitbucket",
        "api",
        "-X",
        "GET",
        f"{compare_endpoint}/diff",
        *compare_fields,
    )
    assert compared_diff["diffs"]

    compared_changes = run_cli(
        live_env,
        "bitbucket",
        "api",
        "-X",
        "GET",
        "--paginate",
        "--jq",
        ".values[].path.toString",
        f"{compare_endpoint}/changes",
        *compare_fields,
    )
    assert compared_changes.returncode == 0, compared_changes.stderr
    assert "example.py" in compared_changes.stdout.splitlines()

    compared_commits = run_cli(
        live_env,
        "bitbucket",
        "api",
        "-X",
        "GET",
        "--paginate",
        "--jq",
        ".values[].id",
        f"{compare_endpoint}/commits",
        *compare_fields,
    )
    assert compared_commits.returncode == 0, compared_commits.stderr
    assert compare_head_commit in compared_commits.stdout.splitlines()

    branches = run_json(
        live_env,
        "bitbucket",
        "branch",
        "list",
        target["project_key"],
        target["repo_slug"],
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
        target["project_key"],
        target["repo_slug"],
        "--title",
        "Example pull request",
        "--description",
        "example response",
        "--from-ref",
        f"refs/heads/{branch_name}",
        "--to-ref",
        "refs/heads/master",
        "--output",
        "json",
    )
    pr_id = created_pr["id"]
    repo_selector = f"{target['project_key']}/{target['repo_slug']}"

    listed = run_json(
        live_env,
        "bitbucket",
        "pr",
        "list",
        "-R",
        repo_selector,
        "--head",
        branch_name,
        "--json",
        "number,title,state,url",
    )
    assert any(item["number"] == pr_id for item in listed)

    listed_via_positionals = run_json(
        live_env,
        "bitbucket",
        "pr",
        "list",
        target["project_key"],
        target["repo_slug"],
        "--state",
        "open",
        "--json",
        "number,state",
    )
    assert any(item == {"number": pr_id, "state": "OPEN"} for item in listed_via_positionals)

    listed_via_alias = run_json(
        live_env,
        "bitbucket",
        "pr",
        "ls",
        "-R",
        repo_selector,
        "--json",
        "number",
    )
    assert any(item["number"] == pr_id for item in listed_via_alias)

    viewed = run_json(
        live_env,
        "bitbucket",
        "pr",
        "view",
        str(pr_id),
        "-R",
        repo_selector,
        "--json",
        "number,title,state,url,headRefName",
    )
    assert viewed["number"] == pr_id
    assert viewed["headRefName"] == branch_name

    sandbox.run("remote", "add", "upstream", http_clone_url)
    viewed_from_branch = run_json(
        live_env,
        "bitbucket",
        "pr",
        "view",
        "--json",
        "number",
        cwd=sandbox_path,
    )
    assert viewed_from_branch["number"] == pr_id

    pr_url = viewed["url"]
    edited = run_cli(
        live_env,
        "bitbucket",
        "pr",
        "edit",
        str(pr_id),
        "-R",
        repo_selector,
        "--title",
        "Example pull request",
        "--body",
        "example response",
    )
    assert edited.returncode == 0, edited.stderr
    assert edited.stdout.strip() == pr_url

    viewed_after_edit = run_json(
        live_env,
        "bitbucket",
        "pr",
        "view",
        str(pr_id),
        "-R",
        repo_selector,
        "--json",
        "number,title,body,url",
    )
    assert viewed_after_edit == {
        "number": pr_id,
        "title": "Example pull request",
        "body": "example response",
        "url": pr_url,
    }

    viewed_from_url = run_json(
        live_env,
        "bitbucket",
        "pr",
        "view",
        pr_url,
        "-R",
        "~example-user/example-repo",
        "--json",
        "number,url",
    )
    assert viewed_from_url == {"number": pr_id, "url": pr_url}

    browsed = run_cli(
        live_env,
        "bitbucket",
        "pr",
        "browse",
        target["project_key"],
        target["repo_slug"],
        "--state",
        "OPEN",
        "--limit",
        "1",
    )
    assert browsed.returncode == 0
    assert "Example pull request" in browsed.stdout

    fetched = run_json(
        live_env,
        "bitbucket",
        "pr",
        "get",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert fetched["id"] == pr_id

    diff_payload = run_json(
        live_env,
        "bitbucket",
        "pr",
        "diff",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert diff_payload["id"] == pr_id
    assert "diff" in diff_payload
    assert branch_name in diff_payload["diff"] or "example.py" in diff_payload["diff"]

    diff_with_lines = run_json(
        live_env,
        "bitbucket",
        "pr",
        "diff",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--with-lines",
        "--output",
        "json",
    )
    assert diff_with_lines["id"] == pr_id

    inline_anchor = None
    for file_diff in diff_with_lines["files"]:
        if file_diff.get("path") != "example.py":
            continue
        for hunk in file_diff.get("hunks", []):
            for line in hunk.get("lines", []):
                anchor = line.get("anchor")
                if anchor and anchor.get("line_type") == "ADDED":
                    inline_anchor = anchor
                    break
            if inline_anchor:
                break
        if inline_anchor:
            break
    assert inline_anchor is not None

    added_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "add",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "example comment",
        "--output",
        "json",
    )
    comment_id = added_comment["id"]
    comment_version = added_comment["version"]

    inline_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "add",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "example comment",
        "--path",
        inline_anchor["path"],
        "--line",
        str(inline_anchor["line"]),
        "--line-type",
        inline_anchor["line_type"],
        "--output",
        "json",
    )
    inline_comment_id = inline_comment["id"]
    inline_comment_version = inline_comment["version"]
    if "anchor" in inline_comment:
        assert inline_comment["anchor"]["path"] == inline_anchor["path"]
        assert inline_comment["anchor"]["line"] == inline_anchor["line"]
        assert inline_comment["anchor"]["line_type"] == inline_anchor["line_type"]

    raw_diff_after_inline = run_json(
        live_env,
        "bitbucket",
        "pr",
        "diff",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--with-lines",
        "--output",
        "raw-json",
    )
    raw_inline_comment_ids = [
        str(comment_id)
        for file_diff in raw_diff_after_inline.get("diffs", [])
        if file_diff.get("destination", {}).get("toString") == inline_anchor["path"]
        for hunk in file_diff.get("hunks", [])
        for segment in hunk.get("segments", [])
        for line in segment.get("lines", [])
        if line.get("destination") == inline_anchor["line"]
        for comment_id in line.get("commentIds", [])
    ]
    assert inline_comment_id in raw_inline_comment_ids

    comments = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "list",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert any(item["id"] == comment_id for item in comments["results"])

    raw_comments = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "list",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "raw-json",
    )
    assert any(str(item["id"]) == str(comment_id) for item in raw_comments)

    fetched_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "get",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        comment_id,
        "--output",
        "json",
    )
    assert fetched_comment["id"] == comment_id

    reply = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "reply",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        comment_id,
        "example response",
        "--output",
        "json",
    )
    assert reply["parent"]["id"] == comment_id

    edited_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "edit",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        comment_id,
        "example comment",
        "--version",
        str(comment_version),
        "--output",
        "json",
    )
    assert edited_comment["id"] == comment_id

    deleted_reply = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "delete",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        reply["id"],
        "--version",
        str(reply["version"]),
        "--output",
        "json",
    )
    assert deleted_reply["deleted"] is True

    deleted_inline_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "delete",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        inline_comment_id,
        "--version",
        str(inline_comment_version),
        "--output",
        "json",
    )
    assert deleted_inline_comment["deleted"] is True

    head_commit = fetched.get("from_ref", {}).get("latest_commit")
    if not head_commit:
        head_commit = sandbox.run("rev-parse", branch_name).stdout.strip()

    pr_build_status = run_json(
        live_env,
        "bitbucket",
        "pr",
        "build-status",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert pr_build_status["pull_request"]["id"] == pr_id
    assert "overall_state" in pr_build_status
    assert "commits" in pr_build_status

    raw_pr_build_status = run_json(
        live_env,
        "bitbucket",
        "pr",
        "build-status",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--latest-only",
        "--output",
        "raw-json",
    )
    assert raw_pr_build_status["pull_request"]["id"] == pr_id
    assert raw_pr_build_status["commits"][0]["commit"] == head_commit
    assert "build_statuses" in raw_pr_build_status["commits"][0]
    assert "overall_state" not in raw_pr_build_status

    commit_build_status = run_json(
        live_env,
        "bitbucket",
        "commit",
        "build-status",
        head_commit,
        "--output",
        "json",
    )
    assert commit_build_status["commit"] == head_commit
    assert "overall_state" in commit_build_status
    assert "results" in commit_build_status

    reviewer_live_env = (
        replace(live_env, config_file=live_env.bitbucket_reviewer_config)
        if live_env.bitbucket_reviewer_config
        else live_env
    )
    approved = run_json(
        reviewer_live_env,
        "bitbucket",
        "pr",
        "approve",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert approved["approved"] is True

    unapproved = run_json(
        reviewer_live_env,
        "bitbucket",
        "pr",
        "unapprove",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert unapproved["approved"] is False

    merged = run_json(
        live_env,
        "bitbucket",
        "pr",
        "merge",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert merged["id"] == pr_id
    assert merged["state"] == "MERGED"
