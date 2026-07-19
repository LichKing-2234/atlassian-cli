from copy import deepcopy

import pytest

from atlassian_cli.core.errors import TransportError
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryRef,
    ServerIdentity,
)
from atlassian_cli.products.bitbucket.services.pr_edit import (
    PullRequestEdits,
    PullRequestEditService,
)

SERVER = ServerIdentity.from_url("https://bitbucket.example.com")
REPOSITORY = RepositoryRef(SERVER, "DEMO", "example-repo")
REF = PullRequestRef(REPOSITORY, 1234)

RAW_PR = {
    "id": 1234,
    "version": 7,
    "title": "Example pull request",
    "description": "example response",
    "fromRef": {
        "id": "refs/heads/feature/DEMO-1234/example-change",
        "displayId": "feature/DEMO-1234/example-change",
        "repository": {"slug": "example-repo", "project": {"key": "DEMO"}},
    },
    "toRef": {
        "id": "refs/heads/main",
        "displayId": "main",
        "repository": {"slug": "example-repo", "project": {"key": "DEMO"}},
    },
    "reviewers": [
        {"user": {"name": "reviewer-one", "displayName": "reviewer-one"}, "approved": True}
    ],
    "links": {
        "self": [
            {
                "href": (
                    "https://bitbucket.example.com/projects/DEMO/repos/"
                    "example-repo/pull-requests/1234"
                )
            }
        ]
    },
}


class FakeProvider:
    def __init__(self, current=RAW_PR) -> None:
        self.current = current
        self.get_calls = []
        self.update_calls = []

    def get_pull_request(self, project_key, repo_slug, pr_id):
        self.get_calls.append((project_key, repo_slug, pr_id))
        return deepcopy(self.current)

    def update_pull_request(self, project_key, repo_slug, pr_id, payload):
        self.update_calls.append((project_key, repo_slug, pr_id, deepcopy(payload)))
        return {"id": pr_id, **deepcopy(payload), "links": deepcopy(RAW_PR["links"])}


def test_edit_preserves_explicit_empty_values_and_uses_supplied_current() -> None:
    provider = FakeProvider()
    service = PullRequestEditService(provider)

    result = service.edit(
        REF,
        PullRequestEdits(title="", body="", base="develop"),
        current=deepcopy(RAW_PR),
    )

    assert provider.get_calls == []
    assert len(provider.update_calls) == 1
    payload = provider.update_calls[0][3]
    assert payload == {
        "version": 7,
        "title": "",
        "description": "",
        "fromRef": RAW_PR["fromRef"],
        "toRef": {
            **RAW_PR["toRef"],
            "id": "refs/heads/develop",
            "displayId": "develop",
        },
        "reviewers": RAW_PR["reviewers"],
    }
    assert result["title"] == ""


def test_edit_fetches_once_and_updates_once_with_fetched_version() -> None:
    provider = FakeProvider()
    service = PullRequestEditService(provider)

    service.edit(REF, PullRequestEdits(title="Example pull request"))

    assert provider.get_calls == [("DEMO", "example-repo", 1234)]
    assert len(provider.update_calls) == 1
    payload = provider.update_calls[0][3]
    assert payload["version"] == 7
    assert payload["description"] == "example response"
    assert payload["fromRef"] == RAW_PR["fromRef"]
    assert payload["toRef"] == RAW_PR["toRef"]


def test_edit_merges_reviewer_desired_state_without_losing_retained_objects() -> None:
    current = deepcopy(RAW_PR)
    current["reviewers"].append(
        {"user": {"slug": "reviewer-two", "displayName": "reviewer-two"}, "approved": False}
    )
    provider = FakeProvider(current)

    PullRequestEditService(provider).edit(
        REF,
        PullRequestEdits(
            add_reviewers=("reviewer-two", "reviewer-three", "reviewer-three"),
            remove_reviewers=("reviewer-one",),
        ),
    )

    reviewers = provider.update_calls[0][3]["reviewers"]
    assert reviewers == [
        current["reviewers"][1],
        {"user": {"name": "reviewer-three"}},
    ]


def test_reviewer_removal_wins_and_no_op_changes_do_not_duplicate_users() -> None:
    provider = FakeProvider()

    PullRequestEditService(provider).edit(
        REF,
        PullRequestEdits(
            add_reviewers=("reviewer-one", "reviewer-two"),
            remove_reviewers=("reviewer-two", "reviewer-four"),
        ),
    )

    assert provider.update_calls[0][3]["reviewers"] == RAW_PR["reviewers"]


def test_load_rejects_non_mapping_response() -> None:
    provider = FakeProvider("<html>example response</html>")

    with pytest.raises(TransportError, match="invalid Bitbucket pull request response"):
        PullRequestEditService(provider).load(REF)


def test_edit_rejects_non_mapping_update_response() -> None:
    class TextUpdateProvider(FakeProvider):
        def update_pull_request(self, project_key, repo_slug, pr_id, payload):
            del project_key, repo_slug, pr_id, payload
            return "<html>example response</html>"

    with pytest.raises(TransportError, match="invalid Bitbucket pull request update response"):
        PullRequestEditService(TextUpdateProvider()).edit(
            REF,
            PullRequestEdits(title="Example pull request"),
        )


def test_dirty_distinguishes_omitted_values_from_explicit_empty_values() -> None:
    assert PullRequestEdits().dirty() is False
    assert PullRequestEdits(title="").dirty() is True
    assert PullRequestEdits(body="").dirty() is True
    assert PullRequestEdits(base="").dirty() is True
    assert PullRequestEdits(add_reviewers=("reviewer-one",)).dirty() is True
