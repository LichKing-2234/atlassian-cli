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
