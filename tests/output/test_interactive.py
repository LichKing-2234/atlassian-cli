from atlassian_cli.output.interactive import (
    CollectionBrowserState,
    CollectionPage,
    InteractiveCollectionSource,
)


def test_collection_browser_state_loads_next_page_when_advancing_past_loaded_items() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_page(start: int, limit: int) -> CollectionPage:
        calls.append((start, limit))
        return CollectionPage(
            items=[
                {"id": start + 1, "title": f"Item {start + 1}"},
                {"id": start + 2, "title": f"Item {start + 2}"},
            ],
            start=start,
            limit=limit,
            total=4,
        )

    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=fetch_page,
        fetch_detail=lambda item: {"id": item["id"], "title": item["title"], "description": "Detail"},
        render_item=lambda index, item: f"{index}. {item['title']}",
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.move(1)
    state.move(1)

    assert calls == [(0, 2), (2, 2)]
    assert state.selected_index == 2


def test_collection_browser_state_opens_detail_and_returns_to_list() -> None:
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=1,
        fetch_page=lambda start, limit: CollectionPage(
            items=[{"id": 1, "title": "OPS-1"}],
            start=start,
            limit=limit,
            total=1,
        ),
        fetch_detail=lambda item: {"id": item["id"], "title": item["title"], "description": "Broken deploy"},
        render_item=lambda index, item: f"{index}. {item['title']}",
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.open_selected_detail()
    assert state.mode == "detail"
    assert state.detail_text == "Broken deploy"

    state.close_detail()
    assert state.mode == "list"
