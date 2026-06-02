from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceAttachment


class AttachmentService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(
        self,
        page_id: str,
        *,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict:
        raw = self.provider.list_attachments(
            page_id,
            start=start,
            limit=limit,
            filename=filename,
            media_type=media_type,
        )
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

    def list_raw(
        self,
        page_id: str,
        *,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict:
        return self.provider.list_attachments(
            page_id,
            start=start,
            limit=limit,
            filename=filename,
            media_type=media_type,
        )

    def upload(self, page_id: str, file_path: str, *, comment: str | None = None) -> dict:
        return ConfluenceAttachment.from_api_response(
            self.provider.upload_attachment(page_id, file_path, comment=comment)
        ).to_simplified_dict()

    def upload_raw(
        self, page_id: str, file_path: str, *, comment: str | None = None
    ) -> dict:
        return self.provider.upload_attachment(page_id, file_path, comment=comment)

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_raw(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_from_content(self, page_id: str, *, name: str, destination: str) -> dict:
        return self.provider.download_attachment_from_content(page_id, name, destination)

    def download_from_content_raw(
        self, page_id: str, *, name: str, destination: str
    ) -> dict:
        return self.download_from_content(page_id, name=name, destination=destination)
