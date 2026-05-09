import pytest

from atlassian_cli.core.errors import TransportError
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService


class FakeBuildStatusProvider:
    def __init__(self) -> None:
        self.calls = []

    def get_pull_request(self, project_key, repo_slug, pr_id):
        self.calls.append(("pr", project_key, repo_slug, pr_id))
        return {"id": pr_id, "fromRef": {"latestCommit": "head123"}}

    def list_pull_request_commits(self, project_key, repo_slug, pr_id, *, start, limit):
        self.calls.append(("commits", project_key, repo_slug, pr_id, start, limit))
        return [{"id": "abc123"}, {"id": "def456"}]

    def get_associated_build_statuses(self, commit):
        self.calls.append(("status", commit))
        if commit == "abc123":
            return {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]}
        if commit == "def456":
            return {"values": [{"key": "DEMO", "state": "FAILED"}]}
        if commit == "head123":
            return {"values": [{"key": "DEMO", "state": "INPROGRESS"}]}
        return {"values": []}


def test_commit_build_status_normalizes_results() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_commit("abc123")

    assert result == {
        "commit": "abc123",
        "overall_state": "SUCCESSFUL",
        "results": [{"key": "DEMO", "state": "SUCCESSFUL"}],
    }


def test_commit_build_status_empty_results_are_unknown() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_commit("empty123")

    assert result == {"commit": "empty123", "overall_state": "UNKNOWN", "results": []}


def test_pull_request_build_status_aggregates_all_commits() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_pull_request("DEMO", "example-repo", 42)

    assert result["pull_request"] == {
        "id": 42,
        "project_key": "DEMO",
        "repo_slug": "example-repo",
    }
    assert result["overall_state"] == "FAILED"
    assert [item["commit"] for item in result["commits"]] == ["abc123", "def456"]


def test_pull_request_build_status_latest_only_uses_head_commit() -> None:
    provider = FakeBuildStatusProvider()
    service = BuildStatusService(provider)

    result = service.for_pull_request("DEMO", "example-repo", 42, latest_only=True)

    assert result["overall_state"] == "INPROGRESS"
    assert [item["commit"] for item in result["commits"]] == ["head123"]
    assert ("commits", "DEMO", "example-repo", 42, 0, None) not in provider.calls


def test_pull_request_build_status_raw_preserves_status_payloads() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_pull_request_raw("DEMO", "example-repo", 42)

    assert result == {
        "pull_request": {
            "id": 42,
            "project_key": "DEMO",
            "repo_slug": "example-repo",
        },
        "commits": [
            {
                "commit": "abc123",
                "build_statuses": {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]},
            },
            {
                "commit": "def456",
                "build_statuses": {"values": [{"key": "DEMO", "state": "FAILED"}]},
            },
        ],
    }


def test_pull_request_build_status_raw_latest_only_uses_head_commit() -> None:
    provider = FakeBuildStatusProvider()
    service = BuildStatusService(provider)

    result = service.for_pull_request_raw("DEMO", "example-repo", 42, latest_only=True)

    assert result["commits"] == [
        {
            "commit": "head123",
            "build_statuses": {"values": [{"key": "DEMO", "state": "INPROGRESS"}]},
        }
    ]
    assert ("commits", "DEMO", "example-repo", 42, 0, None) not in provider.calls


def test_build_status_rejects_non_json_status_payload() -> None:
    class TextStatusProvider(FakeBuildStatusProvider):
        def get_associated_build_statuses(self, commit):
            return "<html>example response</html>"

    service = BuildStatusService(TextStatusProvider())

    with pytest.raises(TransportError, match="Bitbucket build status response"):
        service.for_commit("abc123")
