from typing import Any

from atlassian_cli.models.base import ApiModel, TimestampMixin
from atlassian_cli.models.common import coerce_str, first_present, nested_get


class ConfluenceUserRef(ApiModel):
    display_name: str = "Unknown"
    email: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceUserRef":
        data = data or {}
        return cls(
            display_name=str(first_present(data.get("displayName"), "Unknown")),
            email=coerce_str(first_present(data.get("email"), data.get("emailAddress"))),
        )


class ConfluenceVersion(ApiModel):
    number: int = 0
    by: ConfluenceUserRef | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceVersion":
        data = data or {}
        return cls(
            number=int(data.get("number", 0)),
            by=ConfluenceUserRef.from_api_response(data.get("by")) if data.get("by") else None,
        )


class ConfluenceSpace(ApiModel):
    id: str | None = None
    key: str = ""
    name: str = ""
    type: str | None = None
    status: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceSpace":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            type=coerce_str(data.get("type")),
            status=coerce_str(data.get("status")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "key": self.key, "name": self.name}
        if self.type:
            payload["type"] = self.type
        if self.status:
            payload["status"] = self.status
        return {key: value for key, value in payload.items() if value not in (None, "")}


class ConfluenceAttachment(ApiModel):
    id: str | None = None
    title: str = ""
    media_type: str | None = None
    file_size: int | None = None
    download_url: str | None = None
    version_number: int | None = None
    created: str | None = None
    author_display_name: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "ConfluenceAttachment":
        data = data or {}
        version = data.get("version") if isinstance(data.get("version"), dict) else {}
        author = version.get("by") if isinstance(version.get("by"), dict) else {}
        extensions = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
        links = data.get("_links") if isinstance(data.get("_links"), dict) else {}
        return cls(
            id=coerce_str(data.get("id")),
            title=str(first_present(data.get("title"), data.get("fileName"), "")),
            media_type=coerce_str(
                first_present(data.get("mediaType"), extensions.get("mediaType"))
            ),
            file_size=extensions.get("fileSize"),
            download_url=coerce_str(links.get("download")),
            version_number=int(version["number"]) if version.get("number") is not None else None,
            created=coerce_str(data.get("created")),
            author_display_name=coerce_str(author.get("displayName")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "media_type": self.media_type,
            "file_size": self.file_size,
            "download_url": self.download_url,
            "version_number": self.version_number,
            "created": self.created,
            "author_display_name": self.author_display_name,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


class ConfluencePage(ApiModel, TimestampMixin):
    id: str | None = None
    title: str = ""
    type: str | None = None
    status: str | None = None
    space: ConfluenceSpace | None = None
    version: ConfluenceVersion | None = None
    author: ConfluenceUserRef | None = None
    created: str | None = None
    updated: str | None = None
    url: str | None = None
    content: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluencePage":
        data = data or {}
        space_data = data.get("space")
        if not space_data and isinstance(data.get("_expandable"), dict):
            space_path = data["_expandable"].get("space")
            if isinstance(space_path, str) and space_path.startswith("/rest/api/space/"):
                key = space_path.split("/rest/api/space/")[1]
                space_data = {"key": key, "name": f"Space {key}"}
        space = ConfluenceSpace.from_api_response(space_data) if space_data is not None else None
        version = (
            ConfluenceVersion.from_api_response(data.get("version"))
            if data.get("version")
            else None
        )
        history = data.get("history") if isinstance(data.get("history"), dict) else {}
        base_url = kwargs.get("base_url")
        is_cloud = bool(kwargs.get("is_cloud", False))
        url = None
        if base_url and data.get("id") is not None:
            base_url = str(base_url).rstrip("/")
            if is_cloud:
                space_key = space.key if space and space.key else "unknown"
                url = f"{base_url}/spaces/{space_key}/pages/{data['id']}"
            else:
                url = f"{base_url}/pages/viewpage.action?pageId={data['id']}"
        return cls(
            id=coerce_str(data.get("id")),
            title=str(data.get("title", "")),
            type=coerce_str(data.get("type")),
            status=coerce_str(first_present(data.get("status"), "current")),
            space=space,
            version=version,
            author=ConfluenceUserRef.from_api_response(data.get("author"))
            if data.get("author")
            else None,
            created=coerce_str(history.get("createdDate")),
            updated=coerce_str(
                first_present(
                    nested_get(history, "lastUpdated", "when"),
                    nested_get(data, "version", "when"),
                )
            ),
            url=url,
            content=coerce_str(nested_get(data, "body", "storage", "value")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "url": self.url,
        }
        if self.space:
            payload["space"] = self.space.to_simplified_dict()
        if self.version:
            payload["version"] = self.version.number
        if self.author:
            payload["author"] = self.author.display_name
        return {key: value for key, value in payload.items() if value not in (None, "")}


class ConfluenceComment(ApiModel):
    id: str | None = None
    body: str | None = None
    created: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceComment":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            body=coerce_str(nested_get(data, "body", "storage", "value")),
            created=coerce_str(nested_get(data, "history", "createdDate")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "body": self.body, "created": self.created}
        return {key: value for key, value in payload.items() if value not in (None, "")}
