from atlassian_cli.core.errors import ConflictError, ValidationError
from atlassian_cli.products.jira.providers.base import JiraProvider


class RemoteIssueLinkService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def create(
        self,
        issue_key: str,
        *,
        url: str,
        title: str,
        summary: str | None = None,
        relationship: str | None = None,
        icon_url: str | None = None,
    ) -> dict:
        raw = self.create_raw(
            issue_key,
            url=url,
            title=title,
            summary=summary,
            relationship=relationship,
            icon_url=icon_url,
        )
        remote_link = raw["remote_link_response"]
        remote_object = remote_link.get("object", {})
        icon = remote_object.get("icon", {})
        result = {
            "issue_key": issue_key,
            "id": str(remote_link["id"]),
            "url": remote_object.get("url"),
            "title": remote_object.get("title"),
            "summary": remote_object.get("summary"),
            "relationship": remote_link.get("relationship"),
            "icon_url": icon.get("url16x16") if isinstance(icon, dict) else None,
        }
        return {key: value for key, value in result.items() if value not in (None, "")}

    def create_raw(
        self,
        issue_key: str,
        *,
        url: str,
        title: str,
        summary: str | None = None,
        relationship: str | None = None,
        icon_url: str | None = None,
    ) -> dict:
        if not issue_key.strip():
            raise ValidationError("issue key is required")
        if not url.strip():
            raise ValidationError("URL is required")
        if not title.strip():
            raise ValidationError("title is required")

        link_object = {"url": url, "title": title}
        if summary:
            link_object["summary"] = summary
        if icon_url:
            link_object["icon"] = {"url16x16": icon_url, "title": title}
        data = {"object": link_object}
        if relationship:
            data["relationship"] = relationship

        created = self.provider.create_remote_issue_link(issue_key, data)
        link_id = str(created["id"])
        remote_link = self.provider.get_remote_issue_link(issue_key, link_id)
        remote_object = remote_link.get("object", {})
        remote_icon = remote_object.get("icon", {}) if isinstance(remote_object, dict) else {}
        matches = (
            isinstance(remote_object, dict)
            and str(remote_link.get("id")) == link_id
            and remote_object.get("url") == url
            and remote_object.get("title") == title
            and (not summary or remote_object.get("summary") == summary)
            and (not relationship or remote_link.get("relationship") == relationship)
            and (
                not icon_url
                or (isinstance(remote_icon, dict) and remote_icon.get("url16x16") == icon_url)
            )
        )
        if not matches:
            raise ConflictError("Jira remote-link read-back did not match the create request")
        return {
            "create_response": created,
            "remote_link_response": remote_link,
        }
