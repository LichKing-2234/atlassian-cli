class AttachmentService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> list[dict]:
        return self.provider.list_attachments(page_id)

    def upload(self, page_id: str, file_path: str) -> dict:
        return self.provider.upload_attachment(page_id, file_path)

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)
