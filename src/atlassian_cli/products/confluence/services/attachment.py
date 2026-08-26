import base64
import binascii

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

    def upload(
        self,
        page_id: str,
        file_path: str | None,
        *,
        content_base64: str | None = None,
        filename: str | None = None,
        comment: str | None = None,
        minor_edit: bool = False,
    ) -> dict:
        return ConfluenceAttachment.from_api_response(
            self.upload_raw(
                page_id,
                file_path,
                content_base64=content_base64,
                filename=filename,
                comment=comment,
                minor_edit=minor_edit,
            )
        ).to_simplified_dict()

    def upload_raw(
        self,
        page_id: str,
        file_path: str | None,
        *,
        content_base64: str | None = None,
        filename: str | None = None,
        comment: str | None = None,
        minor_edit: bool = False,
    ) -> dict:
        has_file_path = bool(file_path)
        has_content = content_base64 is not None
        if has_file_path == has_content:
            raise ValueError("provide exactly one of --file or --content-base64")
        if has_content and not filename:
            raise ValueError("--filename is required with --content-base64")

        content = None
        if content_base64 is not None:
            try:
                content = base64.b64decode(content_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"invalid --content-base64: {exc}") from exc

        return self.provider.upload_attachment(
            page_id,
            file_path,
            content=content,
            filename=filename if has_content else None,
            comment=comment,
            minor_edit=minor_edit,
        )

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_raw(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_from_content(self, page_id: str, *, name: str, destination: str) -> dict:
        return self.provider.download_attachment_from_content(page_id, name, destination)

    def download_from_content_raw(self, page_id: str, *, name: str, destination: str) -> dict:
        return self.download_from_content(page_id, name=name, destination=destination)
