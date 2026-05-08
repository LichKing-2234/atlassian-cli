from atlassian_cli.products.bitbucket.services.pr_comment import PullRequestCommentService


class FakeCommentProvider:
    def __init__(self) -> None:
        self.calls = []

    def list_pull_request_comments(self, project_key, repo_slug, pr_id, *, start, limit):
        self.calls.append(("list", project_key, repo_slug, pr_id, start, limit))
        return [
            {
                "id": 1001,
                "version": 3,
                "text": "example comment",
                "author": {"displayName": "Example Author", "name": "example-user-id"},
            }
        ]

    def get_pull_request_comment(self, project_key, repo_slug, pr_id, comment_id):
        self.calls.append(("get", project_key, repo_slug, pr_id, comment_id))
        return {"id": comment_id, "version": 3, "text": "example comment"}

    def add_pull_request_comment(self, project_key, repo_slug, pr_id, text, *, parent_id=None):
        self.calls.append(("add", project_key, repo_slug, pr_id, text, parent_id))
        return {"id": 1002, "version": 1, "text": text}

    def update_pull_request_comment(
        self, project_key, repo_slug, pr_id, comment_id, text, *, version
    ):
        self.calls.append(("edit", project_key, repo_slug, pr_id, comment_id, text, version))
        return {"id": comment_id, "version": version + 1, "text": text}

    def delete_pull_request_comment(self, project_key, repo_slug, pr_id, comment_id, *, version):
        self.calls.append(("delete", project_key, repo_slug, pr_id, comment_id, version))
        return None


def test_comment_service_lists_normalized_envelope() -> None:
    service = PullRequestCommentService(FakeCommentProvider())

    result = service.list("DEMO", "example-repo", 42, start=0, limit=25)

    assert result == {
        "results": [
            {
                "id": "1001",
                "version": 3,
                "text": "example comment",
                "author": {"display_name": "Example Author", "name": "example-user-id"},
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }


def test_comment_service_get_add_reply_edit_and_delete() -> None:
    provider = FakeCommentProvider()
    service = PullRequestCommentService(provider)

    assert service.get("DEMO", "example-repo", 42, "1001")["id"] == "1001"
    assert service.add("DEMO", "example-repo", 42, "example comment")["text"] == "example comment"
    assert (
        service.reply("DEMO", "example-repo", 42, "1001", "example response")["text"]
        == "example response"
    )
    assert (
        service.edit("DEMO", "example-repo", 42, "1001", "example comment", version=3)["version"]
        == 4
    )
    assert service.delete("DEMO", "example-repo", 42, "1001", version=4) == {
        "id": "1001",
        "deleted": True,
    }
    assert provider.calls[-2:] == [
        ("edit", "DEMO", "example-repo", 42, "1001", "example comment", 3),
        ("delete", "DEMO", "example-repo", 42, "1001", 4),
    ]


def test_comment_service_raw_methods_preserve_provider_payloads() -> None:
    service = PullRequestCommentService(FakeCommentProvider())

    assert service.list_raw("DEMO", "example-repo", 42, start=0, limit=25)[0]["id"] == 1001
    assert service.get_raw("DEMO", "example-repo", 42, "1001")["id"] == "1001"
    assert service.add_raw("DEMO", "example-repo", 42, "example comment")["id"] == 1002
    assert (
        service.reply_raw("DEMO", "example-repo", 42, "1001", "example response")["text"]
        == "example response"
    )
    assert (
        service.edit_raw("DEMO", "example-repo", 42, "1001", "example comment", version=3)[
            "version"
        ]
        == 4
    )
    assert service.delete_raw("DEMO", "example-repo", 42, "1001", version=4) == {}
