import pytest

from atlassian_cli.products.confluence.providers.server import ConfluenceServerProvider


def build_provider_with_client(client) -> ConfluenceServerProvider:
    provider = ConfluenceServerProvider.__new__(ConfluenceServerProvider)
    provider.client = client
    return provider


def test_search_pages_escapes_query_before_building_cql() -> None:
    calls: dict[str, object] = {}

    class FakeClient:
        def cql(self, query: str, *, limit: int, expand: str):
            calls["query"] = query
            calls["limit"] = limit
            calls["expand"] = expand
            return {"results": []}

    provider = build_provider_with_client(FakeClient())

    provider.search_pages('say "hello" \\ world', 10)

    assert calls["query"] == 'text ~ "say \\"hello\\" \\\\ world"'
    assert calls["limit"] == 10
    assert calls["expand"] == "space,version"


def test_get_page_children_forwards_fixed_version_pagination_and_expand() -> None:
    calls = {}

    class FakeClient:
        @staticmethod
        def get(path: str, *, params: dict) -> dict:
            calls["request"] = (path, params)
            return {"results": [{"id": "child-1"}], "start": 2, "limit": 1}

    result = build_provider_with_client(FakeClient()).get_page_children(
        "1234", expand="body.storage,version", limit=1, start=2
    )

    assert result == [{"id": "child-1"}]
    assert calls["request"] == (
        "rest/api/content/1234/child/page",
        {"expand": "body.storage,version", "limit": 1, "start": 2},
    )


def test_download_attachment_writes_file_to_destination(tmp_path) -> None:
    calls: list[tuple[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 64 * 1024
            yield b"release=42\n"
            yield b"status=ok\n"

    class FakeSession:
        def get(self, url: str, *, stream: bool):
            calls.append((url, stream))
            return FakeResponse()

    class FakeClient:
        url = "https://confluence.example.com/wiki"
        _session = FakeSession()

        @staticmethod
        def url_joiner(url: str, path: str) -> str:
            return "/".join(str(part).strip("/") for part in [url, path] if part is not None)

        def get(self, path: str, params=None, not_json_response: bool = False):
            calls.append((path, params if params is not None else not_json_response))
            if path == "rest/api/content/55":
                return {
                    "id": "55",
                    "title": "deploy.log",
                    "_links": {"download": "/download/attachments/55/deploy.log"},
                }
            raise AssertionError("download should stream from the HTTP session")

    provider = build_provider_with_client(FakeClient())

    result = provider.download_attachment("55", str(tmp_path))

    output_path = tmp_path / "deploy.log"
    assert output_path.read_bytes() == b"release=42\nstatus=ok\n"
    assert result == {
        "attachment_id": "55",
        "title": "deploy.log",
        "path": str(output_path),
        "bytes_written": 21,
    }
    assert calls[0] == ("rest/api/content/55", {"expand": "version"})
    assert calls[1] == (
        "https://confluence.example.com/wiki/download/attachments/55/deploy.log",
        True,
    )


def test_upload_attachment_returns_first_result_item(tmp_path) -> None:
    calls = {}

    class FakeClient:
        def get_attachments_from_content(self, page_id: str, *, filename: str):
            calls["lookup"] = (page_id, filename)
            return {"results": []}

        def post(self, path: str, **kwargs):
            calls["path"] = path
            return {
                "results": [
                    {
                        "id": "55",
                        "title": "deploy.log",
                        "_links": {"download": "/download/attachments/55/deploy.log"},
                    }
                ]
            }

    upload_file = tmp_path / "deploy.log"
    upload_file.write_text("release=42\nstatus=ok\n")
    provider = build_provider_with_client(FakeClient())

    result = provider.upload_attachment("1234", str(upload_file))

    assert result == {
        "id": "55",
        "title": "deploy.log",
        "_links": {"download": "/download/attachments/55/deploy.log"},
    }
    assert calls == {
        "lookup": ("1234", "deploy.log"),
        "path": "rest/api/content/1234/child/attachment",
    }


def test_list_attachments_forwards_pagination_and_filters() -> None:
    calls = {}

    class FakeClient:
        def get_attachments_from_content(
            self,
            page_id: str,
            *,
            start: int,
            limit: int,
            filename: str | None,
            media_type: str | None,
        ):
            calls["args"] = (page_id, start, limit, filename, media_type)
            return {"results": []}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_attachments(
        "1234",
        start=5,
        limit=10,
        filename="diagram.png",
        media_type="image/png",
    )

    assert result == {"results": []}
    assert calls["args"] == ("1234", 5, 10, "diagram.png", "image/png")


def test_upload_attachment_from_content_updates_existing_attachment() -> None:
    calls = {}

    class FakeClient:
        def get_attachments_from_content(self, page_id: str, *, filename: str):
            calls["lookup"] = (page_id, filename)
            return {"results": [{"id": "55", "title": filename}]}

        def post(self, path: str, *, headers: dict, files: dict, data: dict):
            calls["request"] = {
                "path": path,
                "headers": headers,
                "file": files["file"],
                "comment": files["comment"],
                "data": data,
            }
            return {"results": [{"id": "55", "title": "diagram.png"}]}

    provider = build_provider_with_client(FakeClient())

    result = provider.upload_attachment(
        "1234",
        None,
        content=b"example response",
        filename="diagram.png",
        comment="example comment",
        minor_edit=True,
    )

    assert result == {"id": "55", "title": "diagram.png"}
    assert calls == {
        "lookup": ("1234", "diagram.png"),
        "request": {
            "path": "rest/api/content/1234/child/attachment/55/data",
            "headers": {"X-Atlassian-Token": "no-check"},
            "file": ("diagram.png", b"example response"),
            "comment": (None, "example comment", "text/plain; charset=utf-8"),
            "data": {"minorEdit": "true"},
        },
    }


def test_upload_attachment_posts_fixed_version_multipart_contract(tmp_path) -> None:
    calls = {}

    class FakeClient:
        def get_attachments_from_content(self, page_id: str, *, filename: str):
            calls["lookup"] = (page_id, filename)
            return {"results": []}

        def post(self, path: str, *, headers: dict, files: dict, data: dict):
            calls["request"] = {
                "path": path,
                "headers": headers,
                "filename": files["file"][0],
                "content": files["file"][1].read(),
                "comment": files["comment"],
                "data": data,
            }
            return {"results": [{"id": "55", "title": "diagram.png"}]}

    upload_file = tmp_path / "diagram.png"
    upload_file.write_bytes(b"example response")
    provider = build_provider_with_client(FakeClient())

    result = provider.upload_attachment(
        "1234",
        str(upload_file),
        comment="example comment",
        minor_edit=False,
    )

    assert result == {"id": "55", "title": "diagram.png"}
    assert calls == {
        "lookup": ("1234", "diagram.png"),
        "request": {
            "path": "rest/api/content/1234/child/attachment",
            "headers": {"X-Atlassian-Token": "no-check"},
            "filename": "diagram.png",
            "content": b"example response",
            "comment": (None, "example comment", "text/plain; charset=utf-8"),
            "data": {"minorEdit": "false"},
        },
    }


def test_reply_to_comment_posts_comment_container_payload() -> None:
    calls = {}

    class FakeResponse:
        def __init__(self) -> None:
            self.payload = {"id": "c2", "body": {"storage": {"value": "example response"}}}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    class FakeSession:
        def post(self, url: str, json: dict):
            calls["url"] = url
            calls["json"] = json
            return FakeResponse()

    class FakeClient:
        url = "https://confluence.example.com"
        _session = FakeSession()

    provider = build_provider_with_client(FakeClient())

    result = provider.reply_to_comment("c1", "example response", content_format="storage")

    assert result["id"] == "c2"
    assert calls["url"] == "https://confluence.example.com/rest/api/content/"
    assert calls["json"] == {
        "type": "comment",
        "container": {"id": "c1", "type": "comment", "status": "current"},
        "body": {"storage": {"value": "example response", "representation": "storage"}},
    }


def test_list_comments_returns_results_items() -> None:
    class FakeClient:
        def get_page_comments(self, page_id: str):
            assert page_id == "1234"
            return {
                "results": [
                    {
                        "id": "c1",
                        "body": {"storage": {"value": "example approval"}},
                    }
                ]
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.list_comments("1234")

    assert result == [{"id": "c1", "body": {"storage": {"value": "example approval"}}}]


def test_get_page_labels_uses_official_content_label_api() -> None:
    class FakeClient:
        def get_page_labels(self, page_id: str):
            assert page_id == "1234"
            return {
                "results": [
                    {
                        "id": "55",
                        "name": "example-repo",
                        "prefix": "global",
                        "label": "example-repo",
                    }
                ]
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.get_page_labels("1234")

    assert result["results"][0]["name"] == "example-repo"


def test_add_page_label_reads_back_updated_labels() -> None:
    calls = []

    class FakeClient:
        def set_page_label(self, page_id: str, label: str):
            calls.append(("add", page_id, label))
            return {"name": label}

        def get_page_labels(self, page_id: str):
            calls.append(("read", page_id))
            return {
                "results": [
                    {
                        "id": "55",
                        "name": "example-repo",
                        "prefix": "global",
                        "label": "example-repo",
                    }
                ]
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.add_page_label("1234", "example-repo")

    assert result["results"][0]["name"] == "example-repo"
    assert calls == [
        ("add", "1234", "example-repo"),
        ("read", "1234"),
    ]


def test_get_page_restrictions_uses_official_by_operation_api() -> None:
    expected = {
        "read": {
            "operation": "read",
            "restrictions": {
                "user": {"results": [{"username": "~example-user"}]},
                "group": {"results": [{"name": "reviewer-one"}]},
            },
        },
        "update": {
            "operation": "update",
            "restrictions": {
                "user": {"results": [{"username": "~example-user"}]},
                "group": {"results": [{"name": "reviewer-two"}]},
            },
        },
    }

    class FakeClient:
        def get_all_restrictions_for_content(self, content_id: str):
            assert content_id == "1234"
            return expected

    provider = build_provider_with_client(FakeClient())

    assert provider.get_page_restrictions("1234") == expected


def test_add_comment_converts_markdown_to_storage() -> None:
    calls = {}

    class FakeClient:
        url = "https://confluence.example.com"

        def add_comment(self, page_id: str, body: str):
            calls["page_id"] = page_id
            calls["body"] = body
            return {"id": "c1", "body": {"storage": {"value": body}}}

    provider = build_provider_with_client(FakeClient())

    result = provider.add_comment("1234", "**example comment**")

    assert result["id"] == "c1"
    assert calls["page_id"] == "1234"
    assert calls["body"] == "<p><strong>example comment</strong></p>"


def test_reply_to_comment_converts_markdown_to_storage() -> None:
    calls = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"id": "c2"}

    class FakeSession:
        def post(self, url: str, json: dict):
            calls["json"] = json
            return FakeResponse()

    class FakeClient:
        url = "https://confluence.example.com"
        _session = FakeSession()

    provider = build_provider_with_client(FakeClient())

    result = provider.reply_to_comment("c1", "*example response*")

    assert result["id"] == "c2"
    assert calls["json"]["body"]["storage"]["value"] == "<p><em>example response</em></p>"


def test_get_page_rejects_markdown_conversion_until_supported() -> None:
    class FakeClient:
        pass

    provider = build_provider_with_client(FakeClient())

    try:
        provider.get_page("1234", convert_to_markdown=True)
    except NotImplementedError as exc:
        assert "convert_to_markdown" in str(exc)
    else:
        raise AssertionError("expected NotImplementedError")


def test_create_page_converts_markdown_with_heading_anchors_to_storage() -> None:
    calls = {}

    class FakeClient:
        def create_page(self, **kwargs):
            calls.update(kwargs)
            return {"id": "1234"}

    provider = build_provider_with_client(FakeClient())

    result = provider.create_page(
        space_key="DEMO",
        title="Example Page",
        body="# Example Page",
        content_format="markdown",
        enable_heading_anchors=True,
    )

    assert result == {"id": "1234"}
    assert calls["representation"] == "storage"
    assert "<h1" in calls["body"]
    assert 'ac:name="anchor"' in calls["body"]


def test_update_page_converts_markdown_and_forwards_version_inputs() -> None:
    calls = {}

    class FakeClient:
        def update_page(self, **kwargs):
            calls.update(kwargs)
            return {"id": "1234", "version": {"number": 2}}

    provider = build_provider_with_client(FakeClient())

    result = provider.update_page(
        page_id="1234",
        title="Example Page",
        body="## Example Page",
        parent_id="5678",
        content_format="markdown",
        is_minor_edit=True,
        version_comment="example comment",
        enable_heading_anchors=True,
    )

    assert result["version"]["number"] == 2
    assert calls["representation"] == "storage"
    assert 'ac:name="anchor"' in calls["body"]
    assert calls["parent_id"] == "5678"
    assert calls["minor_edit"] is True
    assert calls["version_comment"] == "example comment"
    assert calls["always_update"] is True


@pytest.mark.parametrize(
    ("operation", "unsupported", "message"),
    [
        ("create", {"enable_heading_anchors": True}, "heading anchors require Markdown"),
        ("create", {"emoji": "example response"}, "emoji is not supported"),
        ("create", {"content_format": "wiki"}, "content_format"),
        ("update", {"enable_heading_anchors": True}, "heading anchors require Markdown"),
        ("update", {"emoji": "example response"}, "emoji is not supported"),
        ("update", {"content_format": "xhtml"}, "content_format"),
    ],
)
def test_page_write_rejects_unsupported_inputs_before_client_mutation(
    operation: str, unsupported: dict, message: str
) -> None:
    class FakeClient:
        def create_page(self, **kwargs):
            raise AssertionError(f"create must not run: {kwargs}")

        def update_page(self, **kwargs):
            raise AssertionError(f"update must not run: {kwargs}")

    provider = build_provider_with_client(FakeClient())

    with pytest.raises(NotImplementedError, match=message):
        if operation == "create":
            provider.create_page(
                space_key="DEMO",
                title="Example Page",
                body="<h1>Example Page</h1>",
                **unsupported,
            )
        else:
            provider.update_page(
                page_id="1234",
                title="Example Page",
                body="<h1>Example Page</h1>",
                **unsupported,
            )
