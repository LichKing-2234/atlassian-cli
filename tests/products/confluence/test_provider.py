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
