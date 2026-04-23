from typing import Any

from pydantic import Field

from atlassian_cli.models.base import ApiModel
from atlassian_cli.models.common import coerce_str, first_present, nested_get


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
            project=BitbucketProject.from_api_response(data.get("project")) if data.get("project") else None,
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
            created_date=coerce_str(first_present(data.get("createdDate"), data.get("created_date"))),
            updated_date=coerce_str(first_present(data.get("updatedDate"), data.get("updated_date"))),
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
