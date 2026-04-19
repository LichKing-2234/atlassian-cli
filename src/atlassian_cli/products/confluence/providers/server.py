from atlassian import Confluence


class ConfluenceServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Confluence(url=url, username=username, password=password or token)

    def get_page(self, page_id: str) -> dict:
        return self.client.get_page_by_id(page_id, expand="space,version")

    def create_page(self, *, space_key: str, title: str, body: str) -> dict:
        return self.client.create_page(space=space_key, title=title, body=body)

    def update_page(self, *, page_id: str, title: str, body: str) -> dict:
        return self.client.update_page(page_id=page_id, title=title, body=body)

    def delete_page(self, page_id: str) -> dict:
        self.client.remove_page(page_id)
        return {"id": page_id, "deleted": True}

    def list_spaces(self, *, start: int, limit: int) -> list[dict]:
        return self.client.get_all_spaces(start=start, limit=limit)["results"]

    def get_space(self, space_key: str) -> dict:
        return self.client.get_space(space_key)

    def list_attachments(self, page_id: str) -> list[dict]:
        return self.client.get_attachments_from_content(page_id)["results"]

    def upload_attachment(self, page_id: str, file_path: str) -> dict:
        return self.client.attach_file(file_path, page_id=page_id)

    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        return {"attachment_id": attachment_id, "destination": destination}
