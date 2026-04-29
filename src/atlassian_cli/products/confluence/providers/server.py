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

    def get_page(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict:
        del convert_to_markdown
        expand = "space,version,body.storage" if include_metadata else "body.storage"
        return self.client.get_page_by_id(page_id, expand=expand)

    def get_page_by_title(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict | None:
        del convert_to_markdown
        expand = "space,version,body.storage" if include_metadata else "body.storage"
        return self.client.get_page_by_title(space_key, title, expand=expand)

    @staticmethod
    def _quote_cql_string(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def search_pages(
        self,
        query: str,
        *,
        limit: int,
        spaces_filter: list[str] | None = None,
    ) -> list[dict]:
        cql = query
        if query and not any(token in query for token in ("=", "~", " AND ", " OR ", ">", "<")):
            cql = f"siteSearch ~ {self._quote_cql_string(query)}"
        if spaces_filter:
            quoted_spaces = ", ".join(self._quote_cql_string(item) for item in spaces_filter)
            cql = f"space in ({quoted_spaces}) AND ({cql})"
        raw = self.client.cql(cql, limit=limit, expand="space,version,body.storage")
        results = raw.get("results", [])
        return [item.get("content", item) for item in results if isinstance(item, dict)]

    def get_page_children(self, page_id: str) -> list[dict]:
        return self.client.get_child_pages(page_id)

    def get_space_homepage(self, space_key: str) -> dict:
        return self.client.get_home_page_of_space(space_key)

    def move_page(
        self,
        page_id: str,
        target_parent_id: str | None = None,
        target_space_key: str | None = None,
        position: str = "append",
    ) -> dict:
        current_page = self.get_page(page_id)
        current_space_key = current_page.get("space", {}).get("key")
        space_key = target_space_key or current_space_key
        target_id = target_parent_id
        if target_id is None and target_space_key:
            target_id = self.get_space_homepage(target_space_key).get("id")
        self.client.move_page(space_key, page_id, target_id=target_id, position=position)
        return self.get_page(page_id)

    def get_page_version(
        self,
        page_id: str,
        version: int,
        *,
        convert_to_markdown: bool = True,
    ) -> dict:
        del convert_to_markdown
        return self.client.get_page_by_id(
            page_id, expand="space,version,body.storage", version=version
        )

    def create_page(
        self,
        *,
        space_key: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "markdown",
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict:
        del enable_heading_anchors, emoji
        representation = "storage" if content_format == "markdown" else content_format
        return self.client.create_page(
            space=space_key,
            title=title,
            body=body,
            parent_id=parent_id,
            representation=representation,
        )

    def update_page(
        self,
        *,
        page_id: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "markdown",
        is_minor_edit: bool = False,
        version_comment: str | None = None,
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict:
        del enable_heading_anchors, emoji
        representation = "storage" if content_format == "markdown" else content_format
        return self.client.update_page(
            page_id=page_id,
            title=title,
            body=body,
            parent_id=parent_id,
            representation=representation,
            minor_edit=is_minor_edit,
            version_comment=version_comment,
        )

    def delete_page(self, page_id: str) -> dict:
        self.client.remove_page(page_id)
        return {"id": page_id, "deleted": True}

    def list_spaces(self, *, start: int, limit: int) -> dict:
        return self.client.get_all_spaces(start=start, limit=limit)

    def get_space(self, space_key: str) -> dict:
        return self.client.get_space(space_key)

    def list_comments(self, page_id: str) -> list[dict]:
        response = self.client.get_page_comments(page_id)
        if isinstance(response, dict):
            results = response.get("results")
            if isinstance(results, list):
                return [item for item in results if isinstance(item, dict)]
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        return []

    def add_comment(self, page_id: str, body: str) -> dict:
        return self.client.add_comment(page_id, body)

    def reply_to_comment(self, comment_id: str, body: str) -> dict:
        session = getattr(self.client, "_session", None)
        base_url = str(getattr(self.client, "url", "")).rstrip("/")
        if session is None or not base_url:
            raise RuntimeError("replying to comments is unavailable without an HTTP session")
        response = session.post(
            f"{base_url}/rest/api/content/",
            json={
                "type": "comment",
                "container": {"id": comment_id, "type": "comment", "status": "current"},
                "body": {"storage": {"value": body, "representation": "storage"}},
            },
        )
        response.raise_for_status()
        return response.json()

    def list_attachments(self, page_id: str) -> dict:
        return self.client.get_attachments_from_content(page_id)

    def upload_attachment(self, page_id: str, file_path: str) -> dict:
        response = self.client.attach_file(file_path, page_id=page_id)
        if isinstance(response, dict):
            results = response.get("results")
            if isinstance(results, list) and results and isinstance(results[0], dict):
                return results[0]
        return response

    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        from pathlib import Path

        attachment = self.client.get(
            f"rest/api/content/{attachment_id}",
            params={"expand": "version"},
        )
        title = str(attachment.get("title") or attachment_id)
        links = attachment.get("_links") if isinstance(attachment.get("_links"), dict) else {}
        download_link = links.get("download")
        if not isinstance(download_link, str) or not download_link:
            raise RuntimeError(f"attachment download url missing for {attachment_id}")

        target = Path(destination)
        if target.exists() and target.is_dir():
            target = target / title
        elif destination.endswith("/") or destination.endswith("\\"):
            target.mkdir(parents=True, exist_ok=True)
            target = target / title
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        session = getattr(self.client, "_session", None)
        base_url = getattr(self.client, "url", None)
        bytes_written = 0
        if session is not None and isinstance(base_url, str) and base_url:
            download_url = self.client.url_joiner(base_url, download_link)
            response = session.get(download_url, stream=True)
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    bytes_written += len(chunk)
        else:
            payload = self.client.get(download_link, not_json_response=True)
            content = bytes(payload)
            target.write_bytes(content)
            bytes_written = len(content)
        return {
            "attachment_id": str(attachment_id),
            "title": title,
            "path": str(target),
            "bytes_written": bytes_written,
        }
