from atlassian_cli.products.confluence.services.page import PageService


class FakePageProvider:
    def __init__(self) -> None:
        self.client = type("Client", (), {"url": "https://confluence.example.com"})()

    def get_page(self, page_id: str) -> dict:
        return {
            "id": page_id,
            "title": "Runbook",
            "type": "page",
            "status": "current",
            "space": {"key": "PROJ", "name": "Operations"},
            "version": {"number": 7},
            "body": {"view": {"value": "<p>huge html</p>"}},
        }

    def get_page_by_title(self, space_key: str, title: str) -> dict | None:
        assert space_key == "PROJ"
        assert title == "Runbook"
        return self.get_page("1234")

    def search_pages(self, query: str, limit: int) -> list[dict]:
        assert query == "runbook"
        assert limit == 10
        return [self.get_page("1234")]

    def get_page_children(self, page_id: str) -> list[dict]:
        if page_id == "root":
            return [
                {
                    "id": "child-1",
                    "title": "Child One",
                    "type": "page",
                    "space": {"key": "PROJ", "name": "Operations"},
                    "version": {"number": 1},
                }
            ]
        return []

    def get_space_homepage(self, space_key: str) -> dict:
        assert space_key == "PROJ"
        return {
            "id": "root",
            "title": "Root Page",
            "type": "page",
            "space": {"key": "PROJ", "name": "Operations"},
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
            "title": "Runbook",
            "type": "page",
            "space": {"key": "PROJ", "name": "Operations"},
            "version": {"number": 8},
        }

    def get_page_version(self, page_id: str, version: int) -> dict:
        body = "hello\nworld\n" if version == 1 else "hello\nops\n"
        return {
            "id": page_id,
            "title": "Runbook",
            "type": "page",
            "space": {"key": "PROJ", "name": "Operations"},
            "version": {"number": version},
            "body": {"storage": {"value": body}},
        }


def test_page_service_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get("1234")

    assert result == {
        "id": "1234",
        "title": "Runbook",
        "type": "page",
        "status": "current",
        "space": {"key": "PROJ", "name": "Operations"},
        "version": 7,
        "url": "https://confluence.example.com/pages/viewpage.action?pageId=1234",
    }


def test_page_service_exposes_raw_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get_raw("1234")

    assert "body" in result


def test_page_service_get_by_title_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get_by_title("PROJ", "Runbook")

    assert result["id"] == "1234"
    assert result["title"] == "Runbook"


def test_page_service_get_by_title_returns_none_when_missing() -> None:
    class MissingPageProvider(FakePageProvider):
        def get_page_by_title(self, space_key: str, title: str) -> dict | None:
            return None

    service = PageService(provider=MissingPageProvider())

    result = service.get_by_title("PROJ", "Missing")

    assert result is None


def test_page_service_search_normalizes_results() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.search("runbook", limit=10)

    assert result["results"][0]["title"] == "Runbook"


def test_page_service_children_normalizes_results() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.children("root")

    assert result["results"][0]["id"] == "child-1"


def test_page_service_tree_flattens_hierarchy() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.tree("PROJ")

    assert result["results"][0]["id"] == "root"
    assert result["results"][0]["depth"] == 0
    assert result["results"][1]["id"] == "child-1"
    assert result["results"][1]["depth"] == 1


def test_page_service_history_normalizes_version_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.history("1234", version=2)

    assert result["id"] == "1234"
    assert result["version"] == 2


def test_page_service_diff_returns_unified_diff() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.diff("1234", from_version=1, to_version=2)

    assert "--- version-1" in result["diff"]
    assert "+++ version-2" in result["diff"]
    assert "+ops" in result["diff"]


def test_page_service_move_normalizes_result() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.move("1234", target_parent_id="5678")

    assert result["id"] == "1234"
    assert result["version"] == 8
