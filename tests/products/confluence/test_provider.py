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


def test_download_attachment_writes_file_to_destination(tmp_path) -> None:
    calls: list[tuple[str, object]] = []

    class FakeClient:
        def get(self, path: str, params=None, not_json_response: bool = False):
            calls.append((path, params if params is not None else not_json_response))
            if path == "rest/api/content/55":
                return {
                    "id": "55",
                    "title": "deploy.log",
                    "_links": {"download": "/download/attachments/55/deploy.log"},
                }
            assert path == "/download/attachments/55/deploy.log"
            assert not_json_response is True
            return b"release=42\nstatus=ok\n"

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


def test_upload_attachment_returns_first_result_item(tmp_path) -> None:
    calls = {}

    class FakeClient:
        def attach_file(self, file_path: str, *, page_id: str):
            calls["args"] = (file_path, page_id)
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
    assert calls["args"] == (str(upload_file), "1234")


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

    result = provider.reply_to_comment("c1", "example response")

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
