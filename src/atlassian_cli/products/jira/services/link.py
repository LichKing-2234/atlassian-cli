from __future__ import annotations

from typing import Any

from atlassian_cli.core.errors import ConflictError, TransportError, ValidationError
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraIssueLink, JiraIssueLinkType


class IssueLinkService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def list(self, issue_key: str) -> dict:
        return {
            "issue_key": issue_key,
            "results": [
                self._parse_link(link, issue_key).to_simplified_dict()
                for link in self.provider.list_issue_links(issue_key)
            ],
        }

    def list_raw(self, issue_key: str) -> list[dict]:
        return self.provider.list_issue_links(issue_key)

    def types(self, name_filter: str | None = None) -> dict:
        return {
            "results": [
                JiraIssueLinkType.from_api_response(link_type).to_simplified_dict()
                for link_type in self.types_raw(name_filter=name_filter)
            ]
        }

    def types_raw(self, name_filter: str | None = None) -> list[dict]:
        link_types = self.provider.get_issue_link_types()
        if not name_filter:
            return link_types
        query = name_filter.casefold()
        return [
            link_type
            for link_type in link_types
            if query in str(link_type.get("name", "")).casefold()
        ]

    def create(
        self,
        *,
        inward_issue: str,
        outward_issue: str,
        link_type: str,
        comment: str | None = None,
        comment_visibility: dict[str, str] | None = None,
    ) -> dict:
        result = self._create(
            inward_issue=inward_issue,
            outward_issue=outward_issue,
            link_type=link_type,
            comment=comment,
            comment_visibility=comment_visibility,
        )
        return {
            "status": result["status"],
            "created": result["created"],
            "link": result["link"],
        }

    def create_raw(
        self,
        *,
        inward_issue: str,
        outward_issue: str,
        link_type: str,
        comment: str | None = None,
        comment_visibility: dict[str, str] | None = None,
    ) -> dict:
        result = self._create(
            inward_issue=inward_issue,
            outward_issue=outward_issue,
            link_type=link_type,
            comment=comment,
            comment_visibility=comment_visibility,
        )
        return {
            "link_type_response": result["link_type_response"],
            "create_response": result["create_response"],
            "issue_link_response": result["issue_link_response"],
        }

    def delete(self, link_id: str) -> dict:
        self.provider.delete_issue_link(link_id)
        return {"id": link_id, "deleted": True}

    def delete_raw(self, link_id: str) -> dict | None:
        return self.provider.delete_issue_link(link_id)

    def _create(
        self,
        *,
        inward_issue: str,
        outward_issue: str,
        link_type: str,
        comment: str | None,
        comment_visibility: dict[str, str] | None,
    ) -> dict[str, Any]:
        if inward_issue == outward_issue:
            raise ValidationError("inward and outward issues must be different")

        link_types = self.provider.get_issue_link_types()
        if not any(item.get("name") == link_type for item in link_types):
            available = ", ".join(
                sorted(str(item["name"]) for item in link_types if item.get("name"))
            )
            suffix = f" Available types: {available}." if available else ""
            raise ValidationError(f"Unknown Jira issue link type: {link_type}.{suffix}")

        before_raw = self.provider.list_issue_links(inward_issue)
        before = self._matching_links(
            before_raw,
            requested_issue=inward_issue,
            inward_issue=inward_issue,
            outward_issue=outward_issue,
            link_type=link_type,
        )
        if len(before) > 1:
            raise ConflictError(
                "Multiple identical Jira issue links already exist; delete duplicates before retrying"
            )
        if before:
            normalized, _ = before[0]
            return {
                "status": "existing",
                "created": False,
                "link_type_response": link_types,
                "create_response": None,
                "issue_link_response": before_raw,
                "link": normalized,
            }

        payload: dict[str, Any] = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_issue},
            "outwardIssue": {"key": outward_issue},
        }
        if comment:
            payload["comment"] = {"body": comment}
            if comment_visibility:
                payload["comment"]["visibility"] = comment_visibility
        create_response = self.provider.create_issue_link(payload)
        after_raw = self.provider.list_issue_links(inward_issue)
        after = self._matching_links(
            after_raw,
            requested_issue=inward_issue,
            inward_issue=inward_issue,
            outward_issue=outward_issue,
            link_type=link_type,
        )
        if len(after) != 1:
            raise ConflictError(
                "Jira accepted the create request, but link read-back was "
                f"{'missing' if not after else 'ambiguous'}"
            )
        normalized, _ = after[0]
        return {
            "status": "created",
            "created": True,
            "link_type_response": link_types,
            "create_response": create_response,
            "issue_link_response": after_raw,
            "link": normalized,
        }

    def _matching_links(
        self,
        links: list[dict],
        *,
        requested_issue: str,
        inward_issue: str,
        outward_issue: str,
        link_type: str,
    ) -> list[tuple[dict, dict]]:
        matches = []
        for raw in links:
            normalized = self._parse_link(raw, requested_issue).to_simplified_dict()
            if (
                normalized.get("type") == link_type
                and normalized.get("inward_issue") == inward_issue
                and normalized.get("outward_issue") == outward_issue
            ):
                matches.append((normalized, raw))
        return matches

    @staticmethod
    def _parse_link(link: dict, requested_issue: str) -> JiraIssueLink:
        if not isinstance(link.get("outwardIssue"), dict) and not isinstance(
            link.get("inwardIssue"), dict
        ):
            raise TransportError(
                f"Jira issue link {link.get('id', '<unknown>')} has no linked issue"
            )
        return JiraIssueLink.from_api_response(link, requested_issue=requested_issue)
