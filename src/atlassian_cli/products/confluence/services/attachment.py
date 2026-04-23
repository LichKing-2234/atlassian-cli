from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceAttachment


class AttachmentService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> dict:
        raw = self.provider.list_attachments(page_id)
        attachments = [
            ConfluenceAttachment.from_api_response(item).to_simplified_dict()
            for item in raw.get("results", [])
            if isinstance(item, dict)
        ]
        payload = {"results": attachments}
        if raw.get("start") is not None:
            payload["start_at"] = raw["start"]
        if raw.get("limit") is not None:
            payload["max_results"] = raw["limit"]
        return payload

    def list_raw(self, page_id: str) -> dict:
        return self.provider.list_attachments(page_id)

    def upload(self, page_id: str, file_path: str) -> dict:
        return ConfluenceAttachment.from_api_response(
            self.provider.upload_attachment(page_id, file_path)
        ).to_simplified_dict()

    def upload_raw(self, page_id: str, file_path: str) -> dict:
        return self.provider.upload_attachment(page_id, file_path)

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_raw(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)
