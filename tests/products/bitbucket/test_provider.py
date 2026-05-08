from atlassian_cli.products.bitbucket.providers.server import BitbucketServerProvider


def build_provider_with_client(client) -> BitbucketServerProvider:
    provider = BitbucketServerProvider.__new__(BitbucketServerProvider)
    provider.client = client
    return provider


def test_list_projects_materializes_paged_generator() -> None:
    class FakeClient:
        def project_list(self, *, limit: int, start: int):
            yield {"key": "DEMO", "name": "Demo Project"}
            yield {"key": "CLOUD", "name": "Cloud"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_projects(start=0, limit=5)

    assert result == [
        {"key": "DEMO", "name": "Demo Project"},
        {"key": "CLOUD", "name": "Cloud"},
    ]


def test_list_repos_materializes_paged_generator() -> None:
    class FakeClient:
        def repo_list(self, *, project_key: str, limit: int, start: int):
            yield {"slug": "example-repo", "project": {"key": project_key}}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_repos(project_key="DEMO", start=0, limit=5)

    assert result == [{"slug": "example-repo", "project": {"key": "DEMO"}}]


def test_list_branches_materializes_paged_generator() -> None:
    class FakeClient:
        def get_branches(self, project_key: str, repo_slug: str, filter=None):
            yield {"displayId": "main", "latestCommit": "abc123"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_branches("DEMO", "example-repo", None)

    assert result == [{"displayId": "main", "latestCommit": "abc123"}]


def test_list_pull_requests_materializes_paged_generator() -> None:
    calls = {}

    class FakeClient:
        def get_pull_requests(
            self,
            project_key: str,
            repo_slug: str,
            state: str,
            limit: int,
            start: int,
        ):
            calls["args"] = (project_key, repo_slug, state, limit, start)
            yield {"id": 1, "title": "Add release automation"}
            yield {"id": 2, "title": "Refine release notes"}
            yield {"id": 3, "title": "Fix packaging"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_pull_requests("DEMO", "example-repo", "OPEN", start=25, limit=2)

    assert result == [
        {"id": 1, "title": "Add release automation"},
        {"id": 2, "title": "Refine release notes"},
    ]
    assert calls["args"] == ("DEMO", "example-repo", "OPEN", 2, 25)


def test_bitbucket_provider_merge_pull_request_forwards_message_and_version() -> None:
    calls = {}

    class FakeClient:
        def merge_pull_request(self, project_key, repo_slug, pr_id, merge_message, pr_version=None):
            calls["args"] = (project_key, repo_slug, pr_id, merge_message, pr_version)
            return {"id": pr_id, "state": "MERGED"}

    provider = build_provider_with_client(FakeClient())

    result = provider.merge_pull_request(
        "DEMO",
        "example-repo",
        42,
        merge_message="Merge pull request #42: Example pull request",
        pr_version=7,
    )

    assert result["state"] == "MERGED"
    assert calls["args"] == (
        "DEMO",
        "example-repo",
        42,
        "Merge pull request #42: Example pull request",
        7,
    )


def test_bitbucket_provider_get_pull_request_diff_uses_text_endpoint() -> None:
    calls = {}

    class FakeResponse:
        text = "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n"

    class FakeClient:
        def _url_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> str:
            return f"rest/api/latest/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}"

        def get(self, url: str, headers=None, advanced_mode: bool = False):
            calls["args"] = (url, headers, advanced_mode)
            return FakeResponse()

    provider = build_provider_with_client(FakeClient())

    result = provider.get_pull_request_diff("DEMO", "example-repo", 42)

    assert result.startswith("--- a/e2e-note.txt")
    assert calls["args"] == (
        "rest/api/latest/projects/DEMO/repos/example-repo/pull-requests/42.diff",
        {"Accept": "text/plain"},
        True,
    )


def test_create_repo_forwards_project_key_and_name_to_sdk() -> None:
    calls = {}

    class FakeClient:
        def create_repo(
            self,
            project_key: str,
            repository_slug: str,
            forkable: bool = False,
            is_private: bool = True,
        ):
            calls["args"] = (project_key, repository_slug, forkable, is_private)
            return {
                "slug": "atlassian-cli-e2e-temp",
                "name": repository_slug,
                "project": {"key": project_key},
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.create_repo(
        project_key="~example_user",
        name="atlassian-cli-e2e-temp",
        scm_id="git",
    )

    assert result["slug"] == "atlassian-cli-e2e-temp"
    assert calls["args"] == (
        "~example_user",
        "atlassian-cli-e2e-temp",
        False,
        True,
    )


def test_create_repo_rejects_non_git_scm_id() -> None:
    provider = build_provider_with_client(object())

    try:
        provider.create_repo(project_key="DEMO", name="example-repo", scm_id="hg")
    except ValueError as exc:
        assert "Only 'git' is supported" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported scm_id")


def test_bitbucket_provider_list_pull_request_comments_uses_comments_endpoint() -> None:
    calls = {}

    class FakeClient:
        def _url_pull_request_comments(self, project_key, repo_slug, pr_id):
            return (
                f"rest/api/latest/projects/{project_key}/repos/{repo_slug}"
                f"/pull-requests/{pr_id}/comments"
            )

        def get(self, url, params=None):
            calls["args"] = (url, params)
            return {"values": [{"id": 1001, "text": "example comment"}]}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_pull_request_comments("DEMO", "example-repo", 42, start=0, limit=25)

    assert result == [{"id": 1001, "text": "example comment"}]
    assert calls["args"] == (
        "rest/api/latest/projects/DEMO/repos/example-repo/pull-requests/42/comments",
        {"start": 0, "limit": 25},
    )


def test_bitbucket_provider_comment_methods_forward_to_sdk() -> None:
    calls = {}

    class FakeClient:
        def get_pull_request_comment(self, project_key, repo_slug, pr_id, comment_id):
            calls["get"] = (project_key, repo_slug, pr_id, comment_id)
            return {"id": comment_id, "text": "example comment"}

        def add_pull_request_comment(self, project_key, repo_slug, pr_id, text, parent_id=None):
            calls["add"] = (project_key, repo_slug, pr_id, text, parent_id)
            return {"id": 1001, "text": text}

        def update_pull_request_comment(
            self, project_key, repo_slug, pr_id, comment_id, comment, comment_version
        ):
            calls["update"] = (project_key, repo_slug, pr_id, comment_id, comment, comment_version)
            return {"id": comment_id, "version": comment_version + 1, "text": comment}

        def delete_pull_request_comment(
            self, project_key, repo_slug, pr_id, comment_id, comment_version
        ):
            calls["delete"] = (project_key, repo_slug, pr_id, comment_id, comment_version)
            return None

    provider = build_provider_with_client(FakeClient())

    assert provider.get_pull_request_comment("DEMO", "example-repo", 42, "1001")["id"] == "1001"
    assert (
        provider.add_pull_request_comment("DEMO", "example-repo", 42, "example comment")["text"]
        == "example comment"
    )
    assert (
        provider.add_pull_request_comment(
            "DEMO", "example-repo", 42, "example response", parent_id="1001"
        )["text"]
        == "example response"
    )
    assert (
        provider.update_pull_request_comment(
            "DEMO", "example-repo", 42, "1001", "example comment", version=3
        )["version"]
        == 4
    )
    assert provider.delete_pull_request_comment(
        "DEMO", "example-repo", 42, "1001", version=4
    ) is None
    assert calls["get"] == ("DEMO", "example-repo", 42, "1001")
    assert calls["add"] == ("DEMO", "example-repo", 42, "example response", "1001")
    assert calls["update"] == ("DEMO", "example-repo", 42, "1001", "example comment", 3)
    assert calls["delete"] == ("DEMO", "example-repo", 42, "1001", 4)


def test_bitbucket_provider_build_status_methods_forward_to_sdk() -> None:
    calls = {}

    class FakeClient:
        def get_pull_requests_commits(self, project_key, repo_slug, pr_id, start=0, limit=None):
            calls["commits"] = (project_key, repo_slug, pr_id, start, limit)
            return {"values": [{"id": "abc123"}, {"id": "def456"}]}

        def get_associated_build_statuses(self, commit):
            calls["build"] = commit
            return {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]}

    provider = build_provider_with_client(FakeClient())

    commits = provider.list_pull_request_commits("DEMO", "example-repo", 42, start=0, limit=25)
    statuses = provider.get_associated_build_statuses("abc123")

    assert commits == [{"id": "abc123"}, {"id": "def456"}]
    assert statuses == {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]}
    assert calls["commits"] == ("DEMO", "example-repo", 42, 0, 25)
    assert calls["build"] == "abc123"
