from atlassian import Confluence

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.auth.session_patch import patch_session_headers


class ConfluenceServerProvider:
    def __init__(
        self,
        *,
        auth_mode: AuthMode = AuthMode.BASIC,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if auth_mode in {AuthMode.PAT, AuthMode.BEARER} and token is not None:
            kwargs["token"] = token
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Confluence(**kwargs)
        session = getattr(self.client, "_session", None)
        if session is not None:
            patch_session_headers(session, headers or {})

    def get_page(self, page_id: str) -> dict:
        return self.client.get_page_by_id(page_id, expand="space,version")

    def create_page(self, *, space_key: str, title: str, body: str) -> dict:
        return self.client.create_page(space=space_key, title=title, body=body)

    def update_page(self, *, page_id: str, title: str, body: str) -> dict:
        return self.client.update_page(page_id=page_id, title=title, body=body)

    def delete_page(self, page_id: str) -> dict:
        self.client.remove_page(page_id)
        return {"id": page_id, "deleted": True}

    def list_spaces(self, *, start: int, limit: int) -> dict:
        return self.client.get_all_spaces(start=start, limit=limit)

    def get_space(self, space_key: str) -> dict:
        return self.client.get_space(space_key)

    def list_attachments(self, page_id: str) -> dict:
        return self.client.get_attachments_from_content(page_id)

    def upload_attachment(self, page_id: str, file_path: str) -> dict:
        return self.client.attach_file(file_path, page_id=page_id)

    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        return {"attachment_id": attachment_id, "destination": destination}
