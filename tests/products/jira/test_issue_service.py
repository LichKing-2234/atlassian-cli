import pytest

from atlassian_cli.core.errors import ConflictError, TransportError, ValidationError
from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.jira.services.issue import IssueService


class FakeIssueProvider:
    def __init__(self) -> None:
        self.get_issue_calls = 0

    def get_issue(
        self,
        issue_key: str,
        *,
        fields=None,
        expand=None,
        comment_limit: int = 10,
        properties=None,
        update_history: bool = True,
    ) -> dict:
        del fields, expand, comment_limit, properties, update_history
        self.get_issue_calls += 1
        return {
            "key": issue_key,
            "fields": {
                "summary": "Example issue summary",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Example Author"},
                "reporter": {"displayName": "reviewer-one"},
                "priority": {"name": "High"},
                "updated": "2026-04-19T09:00:00.000+0000",
            },
        }

    def search_issues(
        self,
        jql: str,
        *,
        fields=None,
        expand=None,
        start_at: int = 0,
        limit: int = 25,
        projects_filter=None,
    ) -> dict:
        del fields, expand, projects_filter
        assert jql == "project = DEMO"
        assert start_at == 0
        assert limit == 2
        return {
            "total": 2,
            "startAt": start_at,
            "maxResults": limit,
            "issues": [
                {
                    "key": "DEMO-1",
                    "fields": {
                        "summary": "Example issue summary",
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Example Author"},
                        "reporter": {"displayName": "reviewer-one"},
                        "priority": {"name": "High"},
                        "updated": "2026-04-19T09:00:00.000+0000",
                    },
                },
                {
                    "key": "DEMO-2",
                    "fields": {
                        "summary": "Example follow-up",
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "reviewer-two"},
                        "reporter": {"displayName": "reviewer-one"},
                        "priority": {"name": "Medium"},
                        "updated": "2026-04-20T09:00:00.000+0000",
                    },
                },
            ],
        }


def test_issue_service_normalizes_issue_payload() -> None:
    service = IssueService(provider=FakeIssueProvider())

    result = service.get("DEMO-1")

    assert result["key"] == "DEMO-1"
    assert result["status"] == {"name": "Open"}
    assert result["assignee"] == {"display_name": "Example Author", "name": "Example Author"}
    assert result["reporter"] == {"display_name": "reviewer-one", "name": "reviewer-one"}


def test_issue_service_exposes_raw_issue_payload() -> None:
    provider = FakeIssueProvider()
    service = IssueService(provider=provider)

    result = service.get_raw("DEMO-1")

    assert result["fields"]["summary"] == "Example issue summary"
    assert result["fields"]["status"]["name"] == "Open"


def test_issue_service_search_normalizes_without_refetching_each_issue() -> None:
    provider = FakeIssueProvider()
    service = IssueService(provider=provider)

    result = service.search("project = DEMO", start=0, limit=2)

    assert result["total"] == 2
    assert result["start_at"] == 0
    assert result["max_results"] == 2
    assert [item["key"] for item in result["issues"]] == ["DEMO-1", "DEMO-2"]
    assert [item["status"]["name"] for item in result["issues"]] == ["Open", "In Progress"]
    assert provider.get_issue_calls == 0


def test_issue_service_search_page_returns_collection_page() -> None:
    service = IssueService(provider=FakeIssueProvider())

    page = service.search_page("project = DEMO", start=0, limit=2)

    assert isinstance(page, CollectionPage)
    assert page.start == 0
    assert page.limit == 2
    assert page.total == 2
    assert [item["key"] for item in page.items] == ["DEMO-1", "DEMO-2"]


def test_issue_service_delete_returns_success_payload() -> None:
    class FakeDeleteProvider:
        def delete_issue(self, issue_key: str) -> None:
            assert issue_key == "DEMO-1"

    service = IssueService(provider=FakeDeleteProvider())

    assert service.delete("DEMO-1") == {"key": "DEMO-1", "deleted": True}


def test_issue_service_get_watchers_normalizes_server_users() -> None:
    class FakeWatcherProvider:
        def get_issue_watchers(self, issue_key: str) -> dict:
            assert issue_key == "DEMO-1"
            return {
                "watchCount": 1,
                "isWatching": False,
                "watchers": [
                    {
                        "name": "example-user-id",
                        "displayName": "Example Author",
                    }
                ],
            }

    result = IssueService(provider=FakeWatcherProvider()).get_watchers("DEMO-1")

    assert result == {
        "issue_key": "DEMO-1",
        "watcher_count": 1,
        "is_watching": False,
        "watchers": [
            {
                "display_name": "Example Author",
                "name": "example-user-id",
            }
        ],
    }


@pytest.mark.parametrize(
    ("method_name", "provider_method", "message"),
    [
        ("get_watchers", "get_issue_watchers", "watcher list response"),
        ("get_worklogs", "get_worklogs", "worklog list response"),
    ],
)
def test_issue_service_rejects_non_object_watcher_or_worklog_response(
    method_name: str, provider_method: str, message: str
) -> None:
    provider = type(
        "InvalidProvider",
        (),
        {provider_method: lambda self, issue_key: "<html>example response</html>"},
    )()

    with pytest.raises(TransportError, match=message):
        getattr(IssueService(provider=provider), method_name)("DEMO-1")


def test_issue_service_add_watcher_returns_server_confirmation() -> None:
    calls: list[tuple[str, str]] = []

    class FakeWatcherProvider:
        def add_watcher(self, issue_key: str, user_identifier: str) -> None:
            calls.append((issue_key, user_identifier))

    result = IssueService(provider=FakeWatcherProvider()).add_watcher("DEMO-1", "example-user-id")

    assert calls == [("DEMO-1", "example-user-id")]
    assert result == {
        "success": True,
        "message": "User 'example-user-id' added as watcher to DEMO-1",
        "issue_key": "DEMO-1",
        "user": "example-user-id",
    }


def test_issue_service_remove_watcher_returns_server_confirmation() -> None:
    calls: list[tuple[str, str]] = []

    class FakeWatcherProvider:
        def remove_watcher(self, issue_key: str, username: str) -> None:
            calls.append((issue_key, username))

    result = IssueService(provider=FakeWatcherProvider()).remove_watcher(
        "DEMO-1", "example-user-id"
    )

    assert calls == [("DEMO-1", "example-user-id")]
    assert result == {
        "success": True,
        "message": "User 'example-user-id' removed from watching DEMO-1",
        "issue_key": "DEMO-1",
        "user": "example-user-id",
    }


def test_issue_service_get_worklogs_normalizes_entries() -> None:
    class FakeWorklogProvider:
        def get_worklogs(self, issue_key: str) -> dict:
            assert issue_key == "DEMO-1"
            return {
                "startAt": 0,
                "maxResults": 20,
                "total": 1,
                "worklogs": [
                    {
                        "id": "10001",
                        "comment": "*example comment*",
                        "created": "2026-08-26T10:00:00.000+0000",
                        "updated": "2026-08-26T10:01:00.000+0000",
                        "started": "2026-08-26T09:00:00.000+0000",
                        "timeSpent": "1m",
                        "timeSpentSeconds": 60,
                        "author": {
                            "name": "example-user-id",
                            "displayName": "Example Author",
                        },
                    }
                ],
            }

    result = IssueService(provider=FakeWorklogProvider()).get_worklogs("DEMO-1")

    assert result == {
        "worklogs": [
            {
                "id": "10001",
                "comment": "*example comment*",
                "created": "2026-08-26T10:00:00.000+0000",
                "updated": "2026-08-26T10:01:00.000+0000",
                "started": "2026-08-26T09:00:00.000+0000",
                "time_spent": "1m",
                "time_spent_seconds": 60,
                "author": {
                    "display_name": "Example Author",
                    "name": "example-user-id",
                },
            }
        ]
    }


def test_issue_service_add_worklog_converts_comment_and_normalizes_result() -> None:
    calls: list[dict] = []

    class FakeWorklogProvider:
        def add_worklog(self, issue_key: str, time_spent: str, **kwargs) -> dict:
            calls.append({"issue_key": issue_key, "time_spent": time_spent, **kwargs})
            return {
                "id": "10001",
                "comment": kwargs["comment"],
                "started": kwargs["started"],
                "timeSpent": time_spent,
                "timeSpentSeconds": 60,
                "author": {
                    "name": "example-user-id",
                    "displayName": "Example Author",
                },
            }

    result = IssueService(provider=FakeWorklogProvider()).add_worklog(
        "DEMO-1",
        "1m",
        comment="**example comment**",
        started="2026-08-26T10:00:00.000+0000",
        original_estimate="1h",
        remaining_estimate="30m",
    )

    assert calls == [
        {
            "issue_key": "DEMO-1",
            "time_spent": "1m",
            "comment": "*example comment*",
            "started": "2026-08-26T10:00:00.000+0000",
            "original_estimate": "1h",
            "remaining_estimate": "30m",
        }
    ]
    assert result == {
        "message": "Worklog added successfully",
        "worklog": {
            "id": "10001",
            "comment": "*example comment*",
            "started": "2026-08-26T10:00:00.000+0000",
            "time_spent": "1m",
            "time_spent_seconds": 60,
            "author": {
                "display_name": "Example Author",
                "name": "example-user-id",
            },
        },
    }


def test_issue_service_add_worklog_preserves_explicit_jira_comment() -> None:
    captured: dict[str, object] = {}

    class FakeWorklogProvider:
        def add_worklog(self, issue_key: str, time_spent: str, **kwargs) -> dict:
            captured.update(issue_key=issue_key, time_spent=time_spent, **kwargs)
            return {"id": "10001", "comment": kwargs["comment"]}

    IssueService(provider=FakeWorklogProvider()).add_worklog(
        "DEMO-1",
        "1m",
        comment="*example comment*",
        comment_format="jira",
    )

    assert captured["comment"] == "*example comment*"


class FakeReparentProvider:
    def __init__(
        self,
        *,
        source_is_subtask: bool = True,
        destination_is_subtask: bool = False,
        destination_project: str = "DEMO",
        readback_parent: str = "DEMO-1",
    ) -> None:
        self.source_is_subtask = source_is_subtask
        self.destination_is_subtask = destination_is_subtask
        self.destination_project = destination_project
        self.readback_parent = readback_parent
        self.reparent_calls = []

    def get_issue(self, issue_key: str, *, fields: str, **kwargs) -> dict:
        del kwargs
        if fields == "parent":
            return {"key": issue_key, "fields": {"parent": {"key": self.readback_parent}}}
        if issue_key == "DEMO-1234":
            return {
                "id": "10003",
                "key": issue_key,
                "fields": {
                    "issuetype": {"name": "Sub-task", "subtask": self.source_is_subtask},
                    "parent": {"key": "DEMO-2"},
                    "project": {"key": "DEMO"},
                },
            }
        return {
            "key": issue_key,
            "fields": {
                "issuetype": {"name": "Task", "subtask": self.destination_is_subtask},
                "project": {"key": self.destination_project},
            },
        }

    def reparent_subtask(self, issue_id: str, parent_key: str) -> None:
        self.reparent_calls.append((issue_id, parent_key))


def test_issue_service_reparents_subtask_and_verifies_readback() -> None:
    provider = FakeReparentProvider()

    result = IssueService(provider=provider).reparent_subtask("DEMO-1234", "DEMO-1")

    assert result == {
        "issue_key": "DEMO-1234",
        "previous_parent": "DEMO-2",
        "new_parent": "DEMO-1",
    }
    assert provider.reparent_calls == [("10003", "DEMO-1")]


@pytest.mark.parametrize(
    ("provider", "message"),
    [
        (FakeReparentProvider(source_is_subtask=False), "DEMO-1234 is not a sub-task"),
        (
            FakeReparentProvider(destination_is_subtask=True),
            "destination parent DEMO-1 is a sub-task",
        ),
        (
            FakeReparentProvider(destination_project="OTHER"),
            "source sub-task and destination parent must be in the same project",
        ),
    ],
)
def test_issue_service_reparent_rejects_invalid_source_or_destination(
    provider, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        IssueService(provider=provider).reparent_subtask("DEMO-1234", "DEMO-1")

    assert provider.reparent_calls == []


def test_issue_service_reparent_fails_when_readback_does_not_change() -> None:
    provider = FakeReparentProvider(readback_parent="DEMO-2")

    with pytest.raises(ConflictError, match="without changing the parent"):
        IssueService(provider=provider).reparent_subtask("DEMO-1234", "DEMO-1")


def test_issue_service_batch_create_normalizes_created_issues() -> None:
    class FakeBatchProvider:
        def create_issues(self, issues: list[dict]) -> list[dict]:
            assert issues == [
                {
                    "project": {"key": "DEMO"},
                    "issuetype": {"name": "Task"},
                    "summary": "Example issue summary",
                    "assignee": {"name": "example-user-id"},
                    "description": "h2. Details\n\n* example response",
                    "components": [{"name": "DEMO"}],
                    "priority": {"name": "High"},
                }
            ]
            return [{"key": "DEMO-1"}]

    service = IssueService(provider=FakeBatchProvider())
    issues = [
        {
            "project_key": "DEMO",
            "issue_type": "Task",
            "summary": "Example issue summary",
            "assignee": "example-user-id",
            "description": "## Details\n\n- example response",
            "components": ["DEMO"],
            "priority": {"name": "High"},
        }
    ]

    result = service.batch_create(issues)

    assert result == {
        "message": "Issues created successfully",
        "issues": [{"key": "DEMO-1"}],
    }
    assert issues[0]["project_key"] == "DEMO"


def test_issue_service_batch_create_validate_only_prepares_without_mutation() -> None:
    class NonMutatingProvider:
        def create_issues(self, issues: list[dict]) -> list[dict]:
            raise AssertionError(f"provider must not be called: {issues}")

    issues = [
        {
            "project_key": "DEMO",
            "issue_type": "Task",
            "summary": "Example issue summary",
            "description": "## Details",
        }
    ]

    result = IssueService(provider=NonMutatingProvider()).batch_create(issues, validate_only=True)

    assert result == {"message": "Issues validated successfully", "issues": []}
    assert issues[0]["description"] == "## Details"


def test_issue_service_batch_create_preserves_unexpected_payload_shapes() -> None:
    class FakeBatchProvider:
        def create_issues(self, issues: list[dict]) -> list[object]:
            assert issues == [
                {
                    "project": {"key": "DEMO"},
                    "issuetype": {"name": "Task"},
                    "summary": "Example issue summary",
                }
            ]
            return [{"error": "validation failed"}, "unexpected"]

    service = IssueService(provider=FakeBatchProvider())

    result = service.batch_create(
        [
            {
                "project_key": "DEMO",
                "issue_type": "Task",
                "summary": "Example issue summary",
            }
        ]
    )

    assert result == {
        "message": "Issues created successfully",
        "issues": [{"error": "validation failed"}, "unexpected"],
    }


def test_issue_service_batch_create_preserves_legacy_rest_fields() -> None:
    class FakeBatchProvider:
        def create_issues(self, issues: list[dict]) -> list[dict]:
            assert issues == [
                {
                    "project": {"key": "DEMO"},
                    "issuetype": {"name": "Task"},
                    "summary": "Example issue summary",
                    "description": "h2. Example Page",
                }
            ]
            return [{"key": "DEMO-1"}]

    result = IssueService(provider=FakeBatchProvider()).batch_create(
        [
            {
                "project": {"key": "DEMO"},
                "issuetype": {"name": "Task"},
                "summary": "Example issue summary",
                "description": "h2. Example Page",
            }
        ]
    )

    assert result["issues"] == [{"key": "DEMO-1"}]


class FakeSemanticIssueProvider:
    def __init__(self) -> None:
        self.get_calls: list[dict] = []
        self.search_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.attachment_calls: list[tuple[str, str]] = []

    def get_issue(
        self,
        issue_key: str,
        *,
        fields=None,
        expand=None,
        comment_limit: int = 10,
        properties=None,
        update_history: bool = True,
    ) -> dict:
        self.get_calls.append(
            {
                "issue_key": issue_key,
                "fields": fields,
                "expand": expand,
                "comment_limit": comment_limit,
                "properties": properties,
                "update_history": update_history,
            }
        )
        return {
            "id": "10000",
            "key": issue_key,
            "fields": {
                "summary": "Example issue summary",
                "description": "Investigate rollout health",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Example Author"},
                "updated": "2026-04-29T09:00:00.000+0000",
            },
        }

    def search_issues(
        self,
        jql: str,
        *,
        fields=None,
        expand=None,
        start_at: int = 0,
        limit: int = 10,
        projects_filter=None,
    ) -> dict:
        self.search_calls.append(
            {
                "jql": jql,
                "fields": fields,
                "expand": expand,
                "start_at": start_at,
                "limit": limit,
                "projects_filter": projects_filter,
            }
        )
        return {
            "startAt": start_at,
            "maxResults": limit,
            "total": 1,
            "issues": [
                {
                    "id": "10000",
                    "key": "DEMO-1",
                    "fields": {
                        "summary": "Example issue summary",
                        "status": {"name": "Open"},
                    },
                }
            ],
        }

    def get_create_meta(self, project_key: str, issue_type: str) -> dict:
        assert project_key == "DEMO"
        assert issue_type == "Task"
        return {
            "required": ["customfield_10001"],
            "allowed_values": {
                "customfield_10001": [{"id": "11", "value": "Linux"}],
            },
        }

    def create_issue(self, fields: dict) -> dict:
        self.create_calls.append(fields)
        return {
            "id": "10001",
            "key": "DEMO-2",
            "fields": {
                "summary": fields["summary"],
                "description": fields.get("description"),
                "status": {"name": "Open"},
            },
        }

    def update_issue(
        self, issue_key: str, fields: dict, *, attachments: list[str] | None = None
    ) -> dict:
        self.update_calls.append(
            {"issue_key": issue_key, "fields": fields, "attachments": attachments}
        )
        result = {
            "id": "10000",
            "key": issue_key,
            "fields": {
                "summary": "Updated summary",
                "description": "Updated description",
                "status": {"name": "In Progress"},
            },
        }
        if attachments:
            result["attachment_results"] = [
                self.upload_issue_attachment(issue_key, path) for path in attachments
            ]
        return result

    def upload_issue_attachment(self, issue_key: str, file_path: str) -> dict:
        self.attachment_calls.append((issue_key, file_path))
        return {"id": "10001", "filename": file_path, "size": 42}


def test_issue_service_get_passes_mcp_style_read_options() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.get(
        "DEMO-1",
        fields=["summary", "status"],
        expand="renderedFields",
        comment_limit=5,
        properties=["triage", "ops"],
        update_history=False,
    )

    assert result["key"] == "DEMO-1"
    assert provider.get_calls == [
        {
            "issue_key": "DEMO-1",
            "fields": ["summary", "status"],
            "expand": "renderedFields",
            "comment_limit": 5,
            "properties": ["triage", "ops"],
            "update_history": False,
        }
    ]


def test_issue_service_get_raises_clear_error_for_text_response() -> None:
    class TextIssueProvider(FakeIssueProvider):
        def get_issue(self, issue_key: str, **kwargs) -> str:
            del issue_key, kwargs
            return "<html>example response</html>"

    service = IssueService(provider=TextIssueProvider())

    with pytest.raises(TransportError, match="JiraIssue response"):
        service.get("DEMO-1")


def test_issue_service_search_returns_mcp_style_envelope() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.search(
        "project = DEMO",
        fields=["summary"],
        expand="changelog",
        start_at=3,
        limit=7,
        projects_filter=["DEMO", "OPS"],
    )

    assert result["start_at"] == 3
    assert result["max_results"] == 7
    assert result["issues"][0]["key"] == "DEMO-1"
    assert provider.search_calls[0]["projects_filter"] == ["DEMO", "OPS"]


def test_issue_service_create_returns_message_and_issue_resource() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.create(
        project_key="DEMO",
        summary="Example issue summary",
        issue_type="Task",
        assignee="example-user",
        description="Investigate rollout health",
        components=["API"],
        additional_fields={"customfield_10001": {"id": "11"}},
    )

    assert result["message"] == "Issue created successfully"
    assert result["issue"]["key"] == "DEMO-2"
    assert provider.create_calls[0]["customfield_10001"] == {"id": "11"}


def test_issue_service_create_converts_markdown_description_to_jira_markup() -> None:
    provider = FakeSemanticIssueProvider()

    IssueService(provider=provider).create(
        project_key="DEMO",
        summary="Example issue summary",
        issue_type="Task",
        description=("# Example Page\n\n- **example response**\n- [Example Page](DEMO)"),
        additional_fields={"customfield_10001": {"id": "11"}},
    )

    assert provider.create_calls[0]["description"] == (
        "h1. Example Page\n\n* *example response*\n* [Example Page|DEMO]"
    )


def test_issue_service_create_preserves_explicit_jira_markup_description() -> None:
    provider = FakeSemanticIssueProvider()

    IssueService(provider=provider).create(
        project_key="DEMO",
        summary="Example issue summary",
        issue_type="Task",
        description="h2. Requirements\n\n* example response",
        description_format="jira",
        additional_fields={"customfield_10001": {"id": "11"}},
    )

    assert provider.create_calls[0]["description"] == ("h2. Requirements\n\n* example response")


def test_issue_service_create_raises_for_missing_required_metadata_field() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    try:
        service.create(
            project_key="DEMO",
            summary="Example issue summary",
            issue_type="Task",
            assignee=None,
            description=None,
            components=None,
            additional_fields={},
        )
    except ValueError as exc:
        assert "customfield_10001" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_issue_service_create_rejects_empty_required_input_before_provider() -> None:
    class NonMutatingProvider:
        def get_create_meta(self, project_key: str, issue_type: str) -> dict:
            raise AssertionError(f"provider must not be called: {project_key}, {issue_type}")

        def create_issue(self, fields: dict) -> dict:
            raise AssertionError(f"provider must not be called: {fields}")

    with pytest.raises(ValueError, match="non-empty project_key, summary, and issue_type"):
        IssueService(provider=NonMutatingProvider()).create(
            project_key="DEMO",
            summary="",
            issue_type="Task",
        )


def test_issue_service_update_returns_message_issue_and_attachment_results() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.update(
        "DEMO-1",
        fields={"summary": "Updated summary", "description": "Updated description"},
        additional_fields={"labels": ["ops"]},
        components=["API"],
        attachments=["release.txt"],
    )

    assert result["message"] == "Issue updated successfully"
    assert result["issue"]["key"] == "DEMO-1"
    assert provider.update_calls == [
        {
            "issue_key": "DEMO-1",
            "fields": {
                "summary": "Updated summary",
                "description": "Updated description",
                "labels": ["ops"],
                "components": [{"name": "API"}],
            },
            "attachments": ["release.txt"],
        }
    ]
    assert provider.attachment_calls == [("DEMO-1", "release.txt")]
    assert result["issue"]["attachment_results"] == [
        {"id": "10001", "filename": "release.txt", "size": 42}
    ]


def test_issue_service_update_runs_aligned_operations_and_converts_markdown() -> None:
    calls = []

    class FakeProvider:
        def update_issue(self, issue_key, fields, *, attachments=None):
            calls.append(("update", issue_key, fields, attachments))
            return {"key": issue_key, "attachment_results": [{"id": "10001"}]}

        def transition_issue(self, issue_key, transition, *, fields=None, comment=None):
            calls.append(("transition", issue_key, transition, fields, comment))
            return {"key": issue_key, "transition": transition}

        @staticmethod
        def get_issue_transitions(issue_key):
            assert issue_key == "DEMO-1"
            return [{"id": 31, "name": "Done"}]

        def add_comment(self, issue_key, body, visibility=None):
            calls.append(("comment", issue_key, body, visibility))
            return {"id": "10002", "body": body, "visibility": visibility}

        def add_worklog(self, issue_key, time_spent, *, started=None):
            calls.append(("worklog", issue_key, time_spent, started))
            return {"id": "10003", "timeSpent": time_spent, "started": started}

        def get_issue(self, issue_key, **kwargs):
            calls.append(("get", issue_key))
            return {
                "key": issue_key,
                "fields": {"summary": "Updated summary", "status": {"name": "Done"}},
            }

    result = IssueService(provider=FakeProvider()).update(
        "DEMO-1",
        fields={"description": "## Example Page"},
        additional_fields={"labels": ["ops"]},
        components=["API"],
        attachments=["release.txt"],
        transition="Done",
        comment="**example comment**",
        comment_visibility={"type": "role", "value": "reviewer-one"},
        worklog="1m",
        worklog_started="2026-08-26T10:00:00.000+0000",
    )

    assert calls == [
        (
            "update",
            "DEMO-1",
            {
                "description": "h2. Example Page",
                "labels": ["ops"],
                "components": [{"name": "API"}],
            },
            ["release.txt"],
        ),
        ("transition", "DEMO-1", "31", None, None),
        (
            "comment",
            "DEMO-1",
            "*example comment*",
            {"type": "role", "value": "reviewer-one"},
        ),
        ("worklog", "DEMO-1", "1m", "2026-08-26T10:00:00.000+0000"),
        ("get", "DEMO-1"),
    ]
    assert result["message"] == "Issue updated successfully"
    assert result["issue"]["key"] == "DEMO-1"
    assert result["issue"]["attachment_results"] == [{"id": "10001"}]
    assert result["operations_performed"] == [
        "fields_updated",
        "attachments_uploaded",
        "transitioned:Done",
        "comment_added",
        "worklog_added",
    ]


def test_issue_service_assign_resolves_user_json_and_unassigns() -> None:
    calls = []

    class FakeProvider:
        def assign_issue(self, issue_key, assignee):
            calls.append(("assign", issue_key, assignee))
            return {"assigned": True}

        def get_issue(self, issue_key, **kwargs):
            calls.append(("get", issue_key))
            return {"key": issue_key, "fields": {"assignee": None}}

    service = IssueService(provider=FakeProvider())

    assigned = service.assign("DEMO-1", '{"name":"example-user"}')
    unassigned = service.assign("DEMO-1", None)

    assert calls == [
        ("assign", "DEMO-1", "example-user"),
        ("get", "DEMO-1"),
        ("assign", "DEMO-1", None),
        ("get", "DEMO-1"),
    ]
    assert assigned["issue"]["key"] == "DEMO-1"
    assert unassigned["issue"]["assignee"]["name"] == "Unassigned"


def test_issue_service_transition_resolves_name_and_converts_comment() -> None:
    calls = []

    class FakeProvider:
        @staticmethod
        def get_issue_transitions(issue_key):
            assert issue_key == "DEMO-1"
            return [{"id": 31, "name": "Done"}]

        def transition_issue(self, issue_key, transition, *, fields=None, comment=None):
            calls.append((issue_key, transition, fields, comment))
            return {"key": issue_key, "transition": transition}

        @staticmethod
        def get_issue(issue_key, **kwargs):
            return {"key": issue_key, "fields": {"status": {"name": "Done"}}}

    result = IssueService(provider=FakeProvider()).transition(
        "DEMO-1",
        "done",
        fields={"resolution": {"name": "Fixed"}},
        comment="**example comment**",
    )

    assert calls == [
        (
            "DEMO-1",
            "31",
            {"resolution": {"name": "Fixed"}},
            "*example comment*",
        )
    ]
    assert result["message"] == "Issue transitioned successfully"
    assert result["issue"]["status"]["name"] == "Done"
