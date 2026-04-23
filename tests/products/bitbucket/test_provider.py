from atlassian_cli.products.bitbucket.providers.server import BitbucketServerProvider


def build_provider_with_client(client) -> BitbucketServerProvider:
    provider = BitbucketServerProvider.__new__(BitbucketServerProvider)
    provider.client = client
    return provider


def test_list_projects_materializes_paged_generator() -> None:
    class FakeClient:
        def project_list(self, *, limit: int, start: int):
            yield {"key": "OPS", "name": "Operations"}
            yield {"key": "CLOUD", "name": "Cloud"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_projects(start=0, limit=5)

    assert result == [
        {"key": "OPS", "name": "Operations"},
        {"key": "CLOUD", "name": "Cloud"},
    ]


def test_list_repos_materializes_paged_generator() -> None:
    class FakeClient:
        def repo_list(self, *, project_key: str, limit: int, start: int):
            yield {"slug": "infra", "project": {"key": project_key}}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_repos(project_key="OPS", start=0, limit=5)

    assert result == [{"slug": "infra", "project": {"key": "OPS"}}]


def test_list_branches_materializes_paged_generator() -> None:
    class FakeClient:
        def get_branches(self, project_key: str, repo_slug: str, filter=None):
            yield {"displayId": "main", "latestCommit": "abc123"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_branches("OPS", "infra", None)

    assert result == [{"displayId": "main", "latestCommit": "abc123"}]


def test_list_pull_requests_materializes_paged_generator() -> None:
    class FakeClient:
        def get_pull_requests(self, project_key: str, repo_slug: str, state: str):
            yield {"id": 1, "title": "Add release automation"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_pull_requests("OPS", "infra", "OPEN")

    assert result == [{"id": 1, "title": "Add release automation"}]


def test_bitbucket_provider_merge_pull_request_forwards_message_and_version() -> None:
    calls = {}

    class FakeClient:
        def merge_pull_request(self, project_key, repo_slug, pr_id, merge_message, pr_version=None):
            calls["args"] = (project_key, repo_slug, pr_id, merge_message, pr_version)
            return {"id": pr_id, "state": "MERGED"}

    provider = build_provider_with_client(FakeClient())

    result = provider.merge_pull_request(
        "OPS",
        "infra",
        42,
        merge_message="Merge pull request #42: Ship output cleanup",
        pr_version=7,
    )

    assert result["state"] == "MERGED"
    assert calls["args"] == (
        "OPS",
        "infra",
        42,
        "Merge pull request #42: Ship output cleanup",
        7,
    )
