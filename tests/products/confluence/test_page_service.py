from atlassian_cli.products.confluence.services.page import PageService


class FakePageProvider:
    def __init__(self) -> None:
        self.client = type("Client", (), {"url": "https://confluence.example.com"})()
        self.search_calls: list[dict] = []

    def get_page(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict:
        del include_metadata, convert_to_markdown
        return {
            "id": page_id,
            "title": "Example Page",
            "type": "page",
            "status": "current",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": {"number": 7},
            "body": {"storage": {"value": "## Runbook\n\nUse the checklist."}},
        }

    def get_page_by_title(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict | None:
        assert space_key == "DEMO"
        assert title == "Example Page"
        return self.get_page(
            "1234",
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )

    def search_pages(
        self,
        query: str,
        *,
        limit: int,
        spaces_filter=None,
    ) -> list[dict]:
        self.search_calls.append(
            {"query": query, "limit": limit, "spaces_filter": spaces_filter}
        )
        return [self.get_page("1234")]

    def get_page_children(self, page_id: str) -> list[dict]:
        if page_id == "root":
            return [
                {
                    "id": "child-1",
                    "title": "Child One",
                    "type": "page",
                    "space": {"key": "DEMO", "name": "Demo Project"},
                    "version": {"number": 1},
                }
            ]
        return []

    def get_space_homepage(self, space_key: str) -> dict:
        assert space_key == "DEMO"
        return {
            "id": "root",
            "title": "Root Page",
            "type": "page",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": {"number": 1},
        }

    def move_page(
        self,
        page_id: str,
        target_parent_id: str | None = None,
        target_space_key: str | None = None,
        position: str = "append",
    ) -> dict:
        assert page_id == "1234"
        assert target_parent_id == "5678"
        assert target_space_key is None
        assert position == "append"
        return {
            "id": page_id,
            "title": "Example Page",
            "type": "page",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": {"number": 8},
        }

    def get_page_version(
        self,
        page_id: str,
        version: int,
        *,
        convert_to_markdown: bool = True,
    ) -> dict:
        del convert_to_markdown
        body = "Version 1 body" if version == 1 else "Version 2 body"
        return {
            "id": page_id,
            "title": "Example Page",
            "type": "page",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": {"number": version},
            "body": {"storage": {"value": body}},
        }

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
        assert space_key == "DEMO"
        assert title == "Example Page"
        assert body == "## Runbook"
        assert parent_id == "5678"
        assert content_format == "markdown"
        assert enable_heading_anchors is True
        assert emoji == "📝"
        return self.get_page("1235")

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
        assert page_id == "1234"
        assert title == "Example Page"
        assert body == "## Runbook"
        assert parent_id == "5678"
        assert content_format == "markdown"
        assert is_minor_edit is True
        assert version_comment == "Example update"
        assert enable_heading_anchors is False
        assert emoji is None
        return self.get_page(page_id)


def test_page_service_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get("1234")

    assert result == {
        "metadata": {
            "id": "1234",
            "title": "Example Page",
            "type": "page",
            "status": "current",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": 7,
            "url": "https://confluence.example.com/pages/viewpage.action?pageId=1234",
        },
        "content": {"value": "## Runbook\n\nUse the checklist."},
    }


def test_page_service_exposes_raw_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get_raw("1234")

    assert "body" in result


def test_page_service_get_by_title_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get_by_title("DEMO", "Example Page")

    assert result["metadata"]["id"] == "1234"
    assert result["metadata"]["title"] == "Example Page"


def test_page_service_get_by_title_returns_none_when_missing() -> None:
    class MissingPageProvider(FakePageProvider):
        def get_page_by_title(
            self,
            space_key: str,
            title: str,
            *,
            include_metadata: bool = True,
            convert_to_markdown: bool = True,
        ) -> dict | None:
            del space_key, title, include_metadata, convert_to_markdown
            return None

    service = PageService(provider=MissingPageProvider())

    result = service.get_by_title("DEMO", "Missing")

    assert result is None


def test_page_service_search_normalizes_results() -> None:
    provider = FakePageProvider()
    service = PageService(provider=provider)

    result = service.search("label=documentation", limit=5, spaces_filter=["DEMO", "~example-user"])

    assert result["results"][0]["title"] == "Example Page"
    assert provider.search_calls == [
        {
            "query": "label=documentation",
            "limit": 5,
            "spaces_filter": ["DEMO", "~example-user"],
        }
    ]


def test_page_service_children_normalizes_results() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.children("root")

    assert result["results"][0]["id"] == "child-1"


def test_page_service_tree_flattens_hierarchy() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.tree("DEMO")

    assert result["results"][0]["id"] == "root"
    assert result["results"][0]["depth"] == 0
    assert result["results"][1]["id"] == "child-1"
    assert result["results"][1]["depth"] == 1


def test_page_service_history_normalizes_version_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.history("1234", version=2, convert_to_markdown=False)

    assert result["metadata"]["id"] == "1234"
    assert result["metadata"]["version"] == 2
    assert result["content"]["value"] == "Version 2 body"


def test_page_service_diff_returns_unified_diff() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.diff("1234", from_version=1, to_version=2)

    assert "--- version-1" in result["diff"]
    assert "+++ version-2" in result["diff"]
    assert "+Version 2 body" in result["diff"]


def test_page_service_move_normalizes_result() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.move("1234", target_parent_id="5678")

    assert result["id"] == "1234"
    assert result["version"] == 8


def test_page_service_create_returns_message_and_page() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.create(
        space_key="DEMO",
        title="Example Page",
        content="## Runbook",
        parent_id="5678",
        content_format="markdown",
        enable_heading_anchors=True,
        include_content=False,
        emoji="📝",
    )

    assert result["message"] == "Page created successfully"
    assert result["page"]["id"] == "1235"


def test_page_service_update_returns_message_and_page() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.update(
        "1234",
        title="Example Page",
        content="## Runbook",
        parent_id="5678",
        content_format="markdown",
        is_minor_edit=True,
        version_comment="Example update",
        enable_heading_anchors=False,
        include_content=True,
        emoji=None,
    )

    assert result["message"] == "Page updated successfully"
    assert result["page"]["metadata"]["id"] == "1234"
