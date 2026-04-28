from typing import Any

from pydantic import Field

from atlassian_cli.models.base import ApiModel
from atlassian_cli.models.common import adf_to_text, coerce_str, first_present, nested_get


class JiraUser(ApiModel):
    account_id: str | None = None
    name: str | None = None
    key: str | None = None
    display_name: str = "Unassigned"
    email: str | None = None
    avatar_url: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraUser":
        data = data or {}
        avatars = data.get("avatarUrls") if isinstance(data.get("avatarUrls"), dict) else {}
        return cls(
            account_id=coerce_str(data.get("accountId")),
            name=coerce_str(first_present(data.get("name"), data.get("username"))),
            key=coerce_str(data.get("key")),
            display_name=str(first_present(data.get("displayName"), "Unassigned")),
            email=coerce_str(first_present(data.get("emailAddress"), data.get("email"))),
            avatar_url=coerce_str(avatars.get("48x48")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "display_name": self.display_name,
            "name": self.name or self.display_name,
            "key": self.key,
            "account_id": self.account_id,
            "email": self.email,
            "avatar_url": self.avatar_url,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


class JiraNamedField(ApiModel):
    name: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraNamedField":
        data = data or {}
        return cls(name=str(data.get("name", "")))

    def to_simplified_dict(self) -> dict[str, Any]:
        return {"name": self.name}


class JiraField(ApiModel):
    id: str = ""
    name: str = ""
    type: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraField":
        data = data or {}
        schema = data.get("schema") if isinstance(data.get("schema"), dict) else {}
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            type=coerce_str(schema.get("type")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "name": self.name, "type": self.type}
        return {key: value for key, value in payload.items() if value not in (None, "")}


class JiraProject(ApiModel):
    id: str | None = None
    key: str = ""
    name: str = ""
    description: str | None = None
    lead: JiraUser | None = None
    category: str | None = None
    avatar_url: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraProject":
        data = data or {}
        avatars = data.get("avatarUrls") if isinstance(data.get("avatarUrls"), dict) else {}
        category = (
            data.get("projectCategory") if isinstance(data.get("projectCategory"), dict) else {}
        )
        lead = JiraUser.from_api_response(data.get("lead")) if data.get("lead") else None
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            description=coerce_str(data.get("description")),
            lead=lead,
            category=coerce_str(category.get("name")),
            avatar_url=coerce_str(avatars.get("48x48")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "key": self.key, "name": self.name}
        if self.description:
            payload["description"] = self.description
        if self.lead:
            payload["lead"] = self.lead.to_simplified_dict()
        if self.category:
            payload["category"] = self.category
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class JiraIssue(ApiModel):
    id: str | None = None
    key: str = ""
    summary: str = ""
    description: str | None = None
    status: JiraNamedField | None = None
    issue_type: JiraNamedField | None = None
    priority: JiraNamedField | None = None
    assignee: JiraUser | None = None
    reporter: JiraUser | None = None
    labels: list[str] = Field(default_factory=list)
    project: JiraProject | None = None
    created: str | None = None
    updated: str | None = None
    url: str | None = None
    comments: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    parent: dict[str, Any] | None = None
    subtasks: list[dict[str, Any]] = Field(default_factory=list)
    resolution: JiraNamedField | None = None
    duedate: str | None = None
    resolutiondate: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraIssue":
        data = data or {}
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        raw_description = fields.get("description")
        description = (
            adf_to_text(raw_description)
            if isinstance(raw_description, dict)
            else coerce_str(raw_description)
        )

        comments = []
        comment_items = nested_get(fields, "comment", "comments")
        if isinstance(comment_items, list):
            comments = [
                {
                    "id": coerce_str(item.get("id")),
                    "body": (
                        adf_to_text(item.get("body"))
                        if isinstance(item.get("body"), dict)
                        else coerce_str(item.get("body"))
                    ),
                    "author": JiraUser.from_api_response(item.get("author")).to_simplified_dict()
                    if item.get("author")
                    else None,
                }
                for item in comment_items
                if isinstance(item, dict)
            ]

        attachments = [
            {
                "id": coerce_str(item.get("id")),
                "filename": coerce_str(item.get("filename")),
                "mime_type": coerce_str(item.get("mimeType")),
            }
            for item in fields.get("attachment", [])
            if isinstance(item, dict)
        ]

        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            summary=str(fields.get("summary", "")),
            description=description,
            status=(
                JiraNamedField.from_api_response(fields.get("status"))
                if fields.get("status")
                else None
            ),
            issue_type=(
                JiraNamedField.from_api_response(fields.get("issuetype"))
                if fields.get("issuetype")
                else None
            ),
            priority=(
                JiraNamedField.from_api_response(fields.get("priority"))
                if fields.get("priority")
                else None
            ),
            assignee=JiraUser.from_api_response(fields.get("assignee"))
            if fields.get("assignee")
            else None,
            reporter=JiraUser.from_api_response(fields.get("reporter"))
            if fields.get("reporter")
            else None,
            labels=[str(label) for label in fields.get("labels", []) if label],
            project=JiraProject.from_api_response(fields.get("project"))
            if fields.get("project")
            else None,
            created=coerce_str(fields.get("created")),
            updated=coerce_str(fields.get("updated")),
            url=coerce_str(data.get("self")),
            comments=comments,
            attachments=attachments,
            parent=fields.get("parent") if isinstance(fields.get("parent"), dict) else None,
            subtasks=[item for item in fields.get("subtasks", []) if isinstance(item, dict)],
            resolution=(
                JiraNamedField.from_api_response(fields.get("resolution"))
                if fields.get("resolution")
                else None
            ),
            duedate=coerce_str(fields.get("duedate")),
            resolutiondate=coerce_str(fields.get("resolutiondate")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "key": self.key,
            "summary": self.summary,
            "description": self.description,
            "created": self.created,
            "updated": self.updated,
            "url": self.url,
            "labels": self.labels,
            "comments": self.comments,
            "attachments": self.attachments,
            "parent": self.parent,
            "subtasks": self.subtasks,
            "duedate": self.duedate,
            "resolutiondate": self.resolutiondate,
        }
        if self.status:
            payload["status"] = self.status.to_simplified_dict()
        if self.issue_type:
            payload["issue_type"] = self.issue_type.to_simplified_dict()
        if self.priority:
            payload["priority"] = self.priority.to_simplified_dict()
        if self.assignee:
            payload["assignee"] = self.assignee.to_simplified_dict()
        else:
            payload["assignee"] = {"display_name": "Unassigned", "name": "Unassigned"}
        if self.reporter:
            payload["reporter"] = self.reporter.to_simplified_dict()
        if self.project:
            payload["project"] = self.project.to_simplified_dict()
        if self.resolution:
            payload["resolution"] = self.resolution.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, [], {})}


class JiraSearchResult(ApiModel):
    total: int = -1
    start_at: int = 0
    max_results: int = 0
    issues: list[JiraIssue] = Field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraSearchResult":
        data = data or {}
        return cls(
            total=int(data.get("total", -1)),
            start_at=int(data.get("startAt", 0)),
            max_results=int(data.get("maxResults", 0)),
            issues=[
                JiraIssue.from_api_response(item)
                for item in data.get("issues", [])
                if isinstance(item, dict)
            ],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "start_at": self.start_at,
            "max_results": self.max_results,
            "issues": [issue.to_simplified_dict() for issue in self.issues],
        }
