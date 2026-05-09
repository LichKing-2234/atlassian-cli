from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from atlassian_cli.models.base import ApiModel
from atlassian_cli.models.common import coerce_str, first_present, nested_get


def _format_bitbucket_timestamp(value: str | None) -> str | None:
    if value in (None, ""):
        return None

    if isinstance(value, str) and value.isdigit():
        try:
            timestamp = int(value) / 1000
            return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, ValueError):
            return value

    return value


class BitbucketUserRef(ApiModel):
    display_name: str | None = None
    name: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketUserRef":
        data = data or {}
        return cls(
            display_name=coerce_str(first_present(data.get("displayName"), data.get("name"))),
            name=coerce_str(data.get("name")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"display_name": self.display_name, "name": self.name}
        return {key: value for key, value in payload.items() if value not in (None, "")}


class BitbucketRef(ApiModel):
    id: str | None = None
    display_id: str | None = None
    latest_commit: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketRef":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            display_id=coerce_str(first_present(data.get("displayId"), data.get("display_id"))),
            latest_commit=coerce_str(data.get("latestCommit")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "display_id": self.display_id,
            "latest_commit": self.latest_commit,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


class BitbucketReviewer(ApiModel):
    user: BitbucketUserRef | None = None
    approved: bool = False

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketReviewer":
        data = data or {}
        user_data = data.get("user") if isinstance(data.get("user"), dict) else {}
        return cls(
            user=BitbucketUserRef.from_api_response(user_data) if user_data else None,
            approved=bool(data.get("approved", False)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"approved": self.approved}
        if self.user:
            payload.update(self.user.to_simplified_dict())
        return payload


class BitbucketProject(ApiModel):
    id: str | None = None
    key: str = ""
    name: str = ""
    description: str | None = None
    public: bool | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketProject":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            description=coerce_str(data.get("description")),
            public=data.get("public"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "public": self.public,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


class BitbucketRepo(ApiModel):
    slug: str = ""
    name: str = ""
    state: str | None = None
    project: BitbucketProject | None = None
    public: bool | None = None
    archived: bool | None = None
    forkable: bool | None = None
    default_branch: BitbucketRef | None = None
    links: dict[str, Any] | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketRepo":
        data = data or {}
        return cls(
            slug=str(data.get("slug", "")),
            name=str(data.get("name", "")),
            state=coerce_str(data.get("state")),
            project=BitbucketProject.from_api_response(data.get("project"))
            if data.get("project")
            else None,
            public=data.get("public"),
            archived=data.get("archived"),
            forkable=data.get("forkable"),
            default_branch=BitbucketRef.from_api_response(data.get("defaultBranch"))
            if isinstance(data.get("defaultBranch"), dict)
            else None,
            links=data.get("links") if isinstance(data.get("links"), dict) else None,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "slug": self.slug,
            "name": self.name,
            "state": self.state,
            "public": self.public,
            "archived": self.archived,
            "forkable": self.forkable,
            "links": self.links,
        }
        if self.project:
            payload["project"] = self.project.to_simplified_dict()
        if self.default_branch:
            payload["default_branch"] = self.default_branch.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketPullRequest(ApiModel):
    id: int
    title: str
    description: str | None = None
    state: str | None = None
    open: bool | None = None
    closed: bool | None = None
    author: BitbucketUserRef | None = None
    reviewers: list[BitbucketReviewer] = Field(default_factory=list)
    participants: list[dict[str, Any]] = Field(default_factory=list)
    from_ref: BitbucketRef | None = None
    to_ref: BitbucketRef | None = None
    created_date: str | None = None
    updated_date: str | None = None
    links: dict[str, Any] | None = None
    version: int | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketPullRequest":
        data = data or {}
        author_user = nested_get(data, "author", "user")
        return cls(
            id=int(data.get("id", 0)),
            title=str(data.get("title", "")),
            description=coerce_str(data.get("description")),
            state=coerce_str(data.get("state")),
            open=data.get("open"),
            closed=data.get("closed"),
            author=BitbucketUserRef.from_api_response(author_user)
            if isinstance(author_user, dict)
            else None,
            reviewers=[
                BitbucketReviewer.from_api_response(item)
                for item in data.get("reviewers", [])
                if isinstance(item, dict)
            ],
            participants=[item for item in data.get("participants", []) if isinstance(item, dict)],
            from_ref=BitbucketRef.from_api_response(data.get("fromRef"))
            if isinstance(data.get("fromRef"), dict)
            else None,
            to_ref=BitbucketRef.from_api_response(data.get("toRef"))
            if isinstance(data.get("toRef"), dict)
            else None,
            created_date=coerce_str(
                first_present(data.get("createdDate"), data.get("created_date"))
            ),
            updated_date=coerce_str(
                first_present(data.get("updatedDate"), data.get("updated_date"))
            ),
            links=data.get("links") if isinstance(data.get("links"), dict) else None,
            version=data.get("version"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state,
            "open": self.open,
            "closed": self.closed,
            "participants": self.participants,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
            "links": self.links,
        }
        if self.author:
            payload["author"] = self.author.to_simplified_dict()
        if self.reviewers:
            payload["reviewers"] = [item.to_simplified_dict() for item in self.reviewers]
        if self.from_ref:
            payload["from_ref"] = self.from_ref.to_simplified_dict()
        if self.to_ref:
            payload["to_ref"] = self.to_ref.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}

    def to_list_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "updated_date": _format_bitbucket_timestamp(self.updated_date),
        }

        if self.author:
            payload["author"] = self.author.to_simplified_dict()
        if self.reviewers:
            payload["reviewers"] = [item.to_simplified_dict() for item in self.reviewers]
        if self.from_ref and self.from_ref.display_id:
            payload["from_ref"] = {"display_id": self.from_ref.display_id}
        if self.to_ref and self.to_ref.display_id:
            payload["to_ref"] = {"display_id": self.to_ref.display_id}

        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketCommentAnchor(ApiModel):
    path: str | None = None
    line: int | None = None
    line_type: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketCommentAnchor":
        data = data or {}
        return cls(
            path=coerce_str(data.get("path")),
            line=data.get("line"),
            line_type=coerce_str(first_present(data.get("lineType"), data.get("line_type"))),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"path": self.path, "line": self.line, "line_type": self.line_type}
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketCommentParent(ApiModel):
    id: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketCommentParent":
        data = data or {}
        return cls(id=coerce_str(data.get("id")))

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id}
        return {key: value for key, value in payload.items() if value not in (None, "")}


class BitbucketPullRequestComment(ApiModel):
    id: str
    version: int | None = None
    text: str | None = None
    author: BitbucketUserRef | None = None
    created_date: str | None = None
    updated_date: str | None = None
    parent: BitbucketCommentParent | None = None
    anchor: BitbucketCommentAnchor | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketPullRequestComment":
        data = data or {}
        author_data = data.get("author") if isinstance(data.get("author"), dict) else {}
        if isinstance(author_data.get("user"), dict):
            author_data = author_data["user"]
        parent_data = data.get("parent") if isinstance(data.get("parent"), dict) else None
        anchor_data = data.get("anchor") if isinstance(data.get("anchor"), dict) else None
        return cls(
            id=str(data.get("id", "")),
            version=data.get("version"),
            text=coerce_str(data.get("text")),
            author=BitbucketUserRef.from_api_response(author_data) if author_data else None,
            created_date=coerce_str(
                first_present(data.get("createdDate"), data.get("created_date"))
            ),
            updated_date=coerce_str(
                first_present(data.get("updatedDate"), data.get("updated_date"))
            ),
            parent=BitbucketCommentParent.from_api_response(parent_data) if parent_data else None,
            anchor=BitbucketCommentAnchor.from_api_response(anchor_data) if anchor_data else None,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "version": self.version,
            "text": self.text,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
        }
        if self.author:
            payload["author"] = self.author.to_simplified_dict()
        if self.parent:
            payload["parent"] = self.parent.to_simplified_dict()
        if self.anchor:
            payload["anchor"] = self.anchor.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketBuildStatus(ApiModel):
    key: str | None = None
    name: str | None = None
    state: str | None = None
    url: str | None = None
    description: str | None = None
    date_added: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketBuildStatus":
        data = data or {}
        return cls(
            key=coerce_str(data.get("key")),
            name=coerce_str(data.get("name")),
            state=coerce_str(data.get("state")),
            url=coerce_str(data.get("url")),
            description=coerce_str(data.get("description")),
            date_added=coerce_str(first_present(data.get("dateAdded"), data.get("date_added"))),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "key": self.key,
            "name": self.name,
            "state": self.state,
            "url": self.url,
            "description": self.description,
            "date_added": self.date_added,
        }
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketCommitBuildStatusSummary(ApiModel):
    commit: str
    overall_state: str
    results: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketCommitBuildStatusSummary":
        data = data or {}
        return cls(
            commit=str(data.get("commit", "")),
            overall_state=str(data.get("overall_state", "UNKNOWN")),
            results=[item for item in data.get("results", []) if isinstance(item, dict)],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "commit": self.commit,
            "overall_state": self.overall_state,
            "results": self.results,
        }


class BitbucketPullRequestBuildStatusSummary(ApiModel):
    pull_request: dict[str, Any]
    overall_state: str
    commits: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketPullRequestBuildStatusSummary":
        data = data or {}
        return cls(
            pull_request=data.get("pull_request", {}),
            overall_state=str(data.get("overall_state", "UNKNOWN")),
            commits=[item for item in data.get("commits", []) if isinstance(item, dict)],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "pull_request": self.pull_request,
            "overall_state": self.overall_state,
            "commits": self.commits,
        }
