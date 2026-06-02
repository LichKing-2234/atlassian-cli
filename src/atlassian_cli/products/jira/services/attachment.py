from __future__ import annotations

from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraAttachment


class AttachmentService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def list(self, issue_key: str) -> dict:
        attachments = [
            JiraAttachment.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_issue_attachments(issue_key)
            if isinstance(item, dict)
        ]
        return {"results": attachments}

    def list_raw(self, issue_key: str) -> list[dict]:
        return self.provider.list_issue_attachments(issue_key)

    def upload(self, issue_key: str, file_path: str) -> dict:
        return JiraAttachment.from_api_response(
            self.provider.upload_issue_attachment(issue_key, file_path)
        ).to_simplified_dict()

    def upload_raw(self, issue_key: str, file_path: str) -> dict:
        return self.provider.upload_issue_attachment(issue_key, file_path)

    def download(self, issue_key: str, *, name: str, destination: str) -> dict:
        return self.provider.download_issue_attachment(
            self._resolve_attachment(issue_key, name),
            destination,
            issue_key=issue_key,
        )

    def download_raw(self, issue_key: str, *, name: str, destination: str) -> dict:
        return self.download(issue_key, name=name, destination=destination)

    def _resolve_attachment(self, issue_key: str, name: str) -> dict:
        matches = [
            item
            for item in self.provider.list_issue_attachments(issue_key)
            if isinstance(item, dict) and item.get("filename") == name
        ]
        if not matches:
            raise ValueError(f"No attachment named {name} found on issue {issue_key}")
        if len(matches) > 1:
            raise ValueError(f"Multiple attachments named {name} found on issue {issue_key}")
        return matches[0]
