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
                    "summary": "First issue",
                }
            ]
            return [{"key": "DEMO-1"}]

    service = IssueService(provider=FakeBatchProvider())

    result = service.batch_create(
        [
            {
                "project": {"key": "DEMO"},
                "issuetype": {"name": "Task"},
                "summary": "First issue",
            }
        ]
    )

    assert result == {"issues": [{"key": "DEMO-1"}]}


def test_issue_service_batch_create_preserves_unexpected_payload_shapes() -> None:
    class FakeBatchProvider:
        def create_issues(self, issues: list[dict]) -> list[object]:
            assert issues == [{"summary": "First issue"}]
            return [{"error": "validation failed"}, "unexpected"]

    service = IssueService(provider=FakeBatchProvider())

    result = service.batch_create([{"summary": "First issue"}])

    assert result == {"issues": [{"error": "validation failed"}, "unexpected"]}


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
