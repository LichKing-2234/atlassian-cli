from atlassian_cli.output.interactive import (
    CollectionBrowserState,
    CollectionPage,
    InteractiveCollectionSource,
    _render_state,
    _truncate_line,
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
        fetch_detail=lambda item: {
            "id": item["id"],
            "title": item["title"],
            "description": "Detail",
        },
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
            items=[{"id": 1, "title": "DEMO-1"}],
            start=start,
            limit=limit,
            total=1,
        ),
        fetch_detail=lambda item: {
            "id": item["id"],
            "title": item["title"],
            "description": "Example issue summary",
        },
        render_item=lambda index, item: f"{index}. {item['title']}",
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.open_selected_detail()
    assert state.mode == "detail"
    assert state.detail_text == "Example issue summary"

    state.close_detail()
    assert state.mode == "list"


def test_collection_browser_state_loads_next_page_without_total_when_page_is_full() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_page(start: int, limit: int) -> CollectionPage:
        calls.append((start, limit))
        if start == 0:
            return CollectionPage(
                items=[
                    {"id": 1, "title": "Item 1"},
                    {"id": 2, "title": "Item 2"},
                ],
                start=start,
                limit=limit,
                total=None,
            )
        return CollectionPage(
            items=[{"id": 3, "title": "Item 3"}],
            start=start,
            limit=limit,
            total=None,
        )

    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=fetch_page,
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["title"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.move(1)
    state.move(1)

    assert calls == [(0, 2), (2, 2)]
    assert state.selected_index == 2
    assert [item["title"] for item in state.items] == ["Item 1", "Item 2", "Item 3"]


def test_render_state_uses_incrementing_list_numbers() -> None:
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=lambda start, limit: CollectionPage(
            items=[{"id": 1, "title": "Item 1"}, {"id": 2, "title": "Item 2"}],
            start=start,
            limit=limit,
            total=2,
        ),
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["title"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()

    rendered = _render_state(state)

    assert "> 1. Item 1" in rendered
    assert "  2. Item 2" in rendered


def test_render_state_in_detail_mode_has_detail_header_and_back_hint() -> None:
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=1,
        fetch_page=lambda start, limit: CollectionPage(
            items=[{"id": 1, "title": "DEMO-1"}],
            start=start,
            limit=limit,
            total=1,
        ),
        fetch_detail=lambda item: {
            "id": item["id"],
            "title": item["title"],
            "description": "Example issue summary",
        },
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.open_selected_detail()

    rendered = _render_state(state)

    assert rendered.startswith("Detail")
    assert "Example issue summary" in rendered
    assert "b/esc: back" in rendered


def test_truncate_line_adds_ellipsis_for_long_lines() -> None:
    text = "1234567890"

    assert _truncate_line(text, max_width=6) == "12345…"


def test_collection_browser_state_page_down_and_page_up_follow_page_size() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_page(start: int, limit: int) -> CollectionPage:
        calls.append((start, limit))
        if start == 0:
            return CollectionPage(
                items=[
                    {"id": 1, "title": "Item 1"},
                    {"id": 2, "title": "Item 2"},
                ],
                start=start,
                limit=limit,
                total=4,
            )
        return CollectionPage(
            items=[
                {"id": 3, "title": "Item 3"},
                {"id": 4, "title": "Item 4"},
            ],
            start=start,
            limit=limit,
            total=4,
        )

    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=fetch_page,
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["title"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.page_down()
    state.page_up()

    assert calls == [(0, 2), (2, 2)]
    assert state.selected_index == 0
    assert [item["title"] for item in state.items] == ["Item 1", "Item 2", "Item 3", "Item 4"]


def test_collection_browser_state_refresh_reloads_first_page_and_resets_selection() -> None:
    responses = [
        CollectionPage(
            items=[{"id": 1, "title": "Old 1"}, {"id": 2, "title": "Old 2"}],
            start=0,
            limit=2,
            total=4,
        ),
        CollectionPage(
            items=[{"id": 1, "title": "New 1"}, {"id": 2, "title": "New 2"}],
            start=0,
            limit=2,
            total=4,
        ),
    ]
    calls: list[tuple[int, int]] = []

    def fetch_page(start: int, limit: int) -> CollectionPage:
        calls.append((start, limit))
        return responses.pop(0)

    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=fetch_page,
        fetch_detail=lambda item: {"description": item["title"]},
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.move(1)
    state.open_selected_detail()
    state.refresh()

    assert calls == [(0, 2), (0, 2)]
    assert state.mode == "list"
    assert state.selected_index == 0
    assert [item["title"] for item in state.items] == ["New 1", "New 2"]


def test_collection_browser_state_filters_loaded_items_locally() -> None:
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=3,
        fetch_page=lambda start, limit: CollectionPage(
            items=[
                {"id": 1, "title": "Apple"},
                {"id": 2, "title": "Banana"},
                {"id": 3, "title": "Apricot"},
            ],
            start=start,
            limit=limit,
            total=3,
        ),
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["title"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.move(2)
    state.start_filter()
    state.append_filter("a")
    state.append_filter("p")
    state.apply_filter()

    assert state.selected_index == 0
    assert [item["title"] for item in state.visible_items()] == ["Apple", "Apricot"]


def test_collection_browser_state_filter_mode_uses_live_buffer() -> None:
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=lambda start, limit: CollectionPage(
            items=[{"id": 1, "title": "Apple"}, {"id": 2, "title": "Banana"}],
            start=start,
            limit=limit,
            total=2,
        ),
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_detail=lambda item: item["title"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.start_filter()
    state.append_filter("a")

    rendered = _render_state(state)

    assert state.mode == "filter"
    assert "Filter: a" in rendered


def build_preview_source() -> InteractiveCollectionSource:
    items = [
        {
            "id": 24990,
            "state": "OPEN",
            "author": "Example Author",
            "title": "[FEAT] DEMO-1234 example preview change with extended summary text",
            "preview": "\n".join(
                [
                    "State: OPEN",
                    "Author: Example Author",
                    "Reviewers: reviewer-one, reviewer-two, reviewer-three, +1 more",
                    "From: feature/DEMO-1234/example-change",
                    "To: main",
                    "Updated: 2026-04-27 13:19:55",
                    "",
                    "Description:",
                    "Example description for preview rendering.",
                ]
            ),
            "detail": "# PR #24990\n\nFull markdown detail",
        },
        {
            "id": 24991,
            "state": "MERGED",
            "author": "Example Collaborator",
            "title": "Example merged change",
            "preview": "State: MERGED\nAuthor: Example Collaborator",
            "detail": "# PR #24991\n\nMerged detail",
        },
    ]

    return InteractiveCollectionSource(
        title="Bitbucket pull requests",
        page_size=2,
        fetch_page=lambda start, limit: CollectionPage(
            items=items[start : start + limit],
            start=start,
            limit=limit,
            total=len(items),
        ),
        fetch_detail=lambda item: item,
        render_item=lambda index, item: (
            f"{item['id']}  {item['state']}  {item['author']}  {item['title']}"
        ),
        render_preview=lambda item: item["preview"],
        render_detail=lambda item: item["detail"],
    )


def test_render_state_stacks_list_preview_and_footer() -> None:
    state = CollectionBrowserState(build_preview_source())
    state.load_initial()

    rendered = _render_state(state)

    assert "Preview:" in rendered
    assert "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit" in rendered
    selected_line = next(line for line in rendered.splitlines() if line.startswith("> "))
    assert "\n" not in selected_line
    assert selected_line.endswith("…")


def test_collection_browser_state_updates_preview_when_selection_changes() -> None:
    state = CollectionBrowserState(build_preview_source())
    state.load_initial()

    assert "Author: Example Author" in _render_state(state)

    state.move(1)

    rendered = _render_state(state)
    assert "Author: Example Collaborator" in rendered
    assert "Author: Example Author" not in rendered


def test_render_state_clips_to_terminal_height_and_keeps_preview_visible() -> None:
    items = [
        {
            "id": index,
            "title": f"Item {index} with a very long title that should be width bounded",
            "preview": f"Preview for item {index}",
            "detail": f"Detail for item {index}",
        }
        for index in range(1, 21)
    ]
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=20,
        fetch_page=lambda start, limit: CollectionPage(
            items=items[start : start + limit],
            start=start,
            limit=limit,
            total=len(items),
        ),
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_preview=lambda item: item["preview"],
        render_detail=lambda item: item["detail"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.move(14)

    rendered = _render_state(state, max_width=40, max_height=12)
    lines = rendered.splitlines()

    assert len(lines) <= 12
    assert lines[-1].startswith("j/k move")
    assert len(lines[-1]) <= 40
    assert "Preview:" in rendered
    assert "Preview for item 15" in rendered
    assert any("> 15. Item 15" in line for line in lines)
    assert not any("Item 1 with" in line for line in lines)


def test_render_state_uses_terminal_width_for_all_lines() -> None:
    state = CollectionBrowserState(build_preview_source())
    state.load_initial()

    rendered = _render_state(state, max_width=32, max_height=12)

    assert all(len(line) <= 32 for line in rendered.splitlines())
