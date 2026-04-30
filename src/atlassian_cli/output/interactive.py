from dataclasses import dataclass, field
from typing import Any, Callable

MAX_LIST_LINE_WIDTH = 96
MAX_PREVIEW_LINES = 7
LIST_FOOTER = "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit"


@dataclass
class CollectionPage:
    items: list[dict[str, Any]]
    start: int
    limit: int
    total: int | None = None


@dataclass
class InteractiveCollectionSource:
    title: str
    page_size: int
    fetch_page: Callable[[int, int], CollectionPage]
    fetch_detail: Callable[[dict[str, Any]], dict[str, Any]]
    render_item: Callable[[int, dict[str, Any]], str]
    render_detail: Callable[[dict[str, Any]], str]
    render_preview: Callable[[dict[str, Any]], str] | None = None
    filter_text: Callable[[dict[str, Any]], str] | None = None


@dataclass
class CollectionBrowserState:
    source: InteractiveCollectionSource
    items: list[dict[str, Any]] = field(default_factory=list)
    selected_index: int = 0
    mode: str = "list"
    detail_text: str = ""
    detail_offset: int = 0
    filter_query: str = ""
    filter_buffer: str = ""
    next_start: int = 0
    total: int | None = None
    has_more: bool = False

    def load_initial(self) -> None:
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self._apply_page(page)

    def _apply_page(self, page: CollectionPage) -> None:
        self.next_start = page.start + len(page.items)
        self.total = page.total
        if page.total is not None:
            self.has_more = self.next_start < page.total
        else:
            self.has_more = len(page.items) == page.limit and len(page.items) > 0

    def move(self, delta: int) -> None:
        visible_count = len(self.visible_items())
        target = self.selected_index + delta
        if target >= visible_count and not self.current_filter() and self.has_more:
            page = self.source.fetch_page(self.next_start, self.source.page_size)
            if page.items:
                self.items.extend(page.items)
                self._apply_page(page)
            else:
                self.has_more = False
            visible_count = len(self.visible_items())
        self.selected_index = max(0, min(target, visible_count - 1))

    def page_down(self) -> None:
        self.move(self.source.page_size)

    def page_up(self) -> None:
        self.move(-self.source.page_size)

    def open_selected_detail(self) -> None:
        visible_items = self.visible_items()
        if not visible_items:
            return
        detail = self.source.fetch_detail(visible_items[self.selected_index])
        self.detail_text = self.source.render_detail(detail)
        self.detail_offset = 0
        self.mode = "detail"

    def close_detail(self) -> None:
        self.detail_offset = 0
        self.mode = "list"

    def detail_lines(self) -> list[str]:
        lines = self.detail_text.splitlines()
        return lines or [""]

    def scroll_detail(self, delta: int, *, window_size: int) -> None:
        lines = self.detail_lines()
        max_offset = max(0, len(lines) - window_size)
        self.detail_offset = max(0, min(self.detail_offset + delta, max_offset))

    def page_detail_down(self, *, window_size: int) -> None:
        self.scroll_detail(window_size, window_size=window_size)

    def page_detail_up(self, *, window_size: int) -> None:
        self.scroll_detail(-window_size, window_size=window_size)

    def refresh(self) -> None:
        self.selected_index = 0
        self.mode = "list"
        self.detail_text = ""
        self.detail_offset = 0
        self.filter_query = ""
        self.filter_buffer = ""
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self._apply_page(page)

    def current_filter(self) -> str:
        if self.mode == "filter":
            return self.filter_buffer
        return self.filter_query

    def visible_items(self) -> list[dict[str, Any]]:
        query = self.current_filter().strip().lower()
        if not query:
            return self.items
        return [item for item in self.items if query in self._item_filter_text(item).lower()]

    def start_filter(self) -> None:
        self.mode = "filter"
        self.filter_buffer = self.filter_query
        self.selected_index = 0

    def append_filter(self, text: str) -> None:
        self.filter_buffer += text
        self.selected_index = 0

    def backspace_filter(self) -> None:
        self.filter_buffer = self.filter_buffer[:-1]
        self.selected_index = 0

    def apply_filter(self) -> None:
        self.filter_query = self.filter_buffer.strip()
        self.mode = "list"
        self.selected_index = 0

    def cancel_filter(self) -> None:
        self.filter_buffer = ""
        self.mode = "list"
        self.selected_index = 0

    def current_item(self) -> dict[str, Any] | None:
        visible_items = self.visible_items()
        if not visible_items:
            return None
        return visible_items[self.selected_index]

    def current_preview(self) -> str:
        item = self.current_item()
        if item is None:
            return "No results."
        if self.source.render_preview is None:
            return ""
        return self.source.render_preview(item)

    def _item_filter_text(self, item: dict[str, Any]) -> str:
        if self.source.filter_text is not None:
            return self.source.filter_text(item)
        parts = [self.source.render_item(1, item)]
        if self.source.render_preview is not None:
            parts.append(self.source.render_preview(item))
        return "\n".join(part for part in parts if part)


def browse_collection(source: InteractiveCollectionSource) -> None:
    from prompt_toolkit import Application
    from prompt_toolkit.application.current import get_app
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    state = CollectionBrowserState(source)
    state.load_initial()
    body = FormattedTextControl(
        text=lambda: _render_state(
            state,
            max_width=max(20, get_app().output.get_size().columns - 1),
            max_height=max(8, get_app().output.get_size().rows),
        )
    )
    bindings = KeyBindings()

    @bindings.add("q")
    def _quit(event) -> None:
        if state.mode == "filter":
            state.append_filter("q")
            event.app.invalidate()
            return
        event.app.exit()

    @bindings.add("down")
    @bindings.add("j")
    def _down(event) -> None:
        if state.mode == "filter":
            state.append_filter("j")
            event.app.invalidate()
            return
        if state.mode == "detail":
            state.scroll_detail(1, window_size=_detail_window_size(get_app().output.get_size().rows))
            event.app.invalidate()
            return
        if state.mode == "list":
            state.move(1)
            event.app.invalidate()

    @bindings.add("up")
    @bindings.add("k")
    def _up(event) -> None:
        if state.mode == "filter":
            state.append_filter("k")
            event.app.invalidate()
            return
        if state.mode == "detail":
            state.scroll_detail(
                -1, window_size=_detail_window_size(get_app().output.get_size().rows)
            )
            event.app.invalidate()
            return
        if state.mode == "list":
            state.move(-1)
            event.app.invalidate()

    @bindings.add("n")
    @bindings.add("pagedown")
    def _page_down(event) -> None:
        if state.mode == "filter":
            state.append_filter("n")
            event.app.invalidate()
            return
        if state.mode == "detail":
            state.page_detail_down(
                window_size=_detail_window_size(get_app().output.get_size().rows)
            )
            event.app.invalidate()
            return
        if state.mode == "list":
            state.page_down()
            event.app.invalidate()

    @bindings.add("p")
    @bindings.add("pageup")
    def _page_up(event) -> None:
        if state.mode == "filter":
            state.append_filter("p")
            event.app.invalidate()
            return
        if state.mode == "detail":
            state.page_detail_up(
                window_size=_detail_window_size(get_app().output.get_size().rows)
            )
            event.app.invalidate()
            return
        if state.mode == "list":
            state.page_up()
            event.app.invalidate()

    @bindings.add("enter")
    def _open(event) -> None:
        if state.mode == "filter":
            state.apply_filter()
            event.app.invalidate()
            return
        if state.mode == "list":
            state.open_selected_detail()
            event.app.invalidate()

    @bindings.add("/")
    def _filter(event) -> None:
        if state.mode == "filter":
            state.append_filter("/")
        else:
            state.start_filter()
        event.app.invalidate()

    @bindings.add("escape")
    @bindings.add("b")
    def _back(event) -> None:
        if state.mode == "filter":
            if event.data == "b":
                state.append_filter("b")
            else:
                state.cancel_filter()
            event.app.invalidate()
            return
        if state.mode == "detail":
            state.close_detail()
            event.app.invalidate()

    @bindings.add("r")
    def _refresh(event) -> None:
        if state.mode == "filter":
            state.append_filter("r")
            event.app.invalidate()
            return
        state.refresh()
        event.app.invalidate()

    @bindings.add("backspace")
    @bindings.add("c-h")
    def _backspace(event) -> None:
        if state.mode == "filter":
            state.backspace_filter()
            event.app.invalidate()

    @bindings.add(Keys.Any)
    def _text(event) -> None:
        if state.mode == "filter" and event.data and event.data.isprintable():
            state.append_filter(event.data)
            event.app.invalidate()

    app = Application(
        layout=Layout(HSplit([Window(content=body)])),
        key_bindings=bindings,
        full_screen=False,
    )
    app.run()


def _truncate_line(text: str, *, max_width: int = MAX_LIST_LINE_WIDTH) -> str:
    if len(text) <= max_width:
        return text
    if max_width <= 1:
        return "…"
    return text[: max_width - 1] + "…"


def _truncate_block(
    text: str,
    *,
    max_lines: int = MAX_PREVIEW_LINES,
    max_width: int = MAX_LIST_LINE_WIDTH,
) -> list[str]:
    raw_lines = [line for line in text.splitlines() if line.strip()]
    truncated = [_truncate_line(line, max_width=max_width) for line in raw_lines]
    if len(truncated) <= max_lines:
        return truncated
    visible = truncated[:max_lines]
    visible[-1] = _truncate_line(f"{visible[-1]}…", max_width=max_width)
    return visible


def _window_bounds(total_items: int, selected_index: int, window_size: int) -> tuple[int, int]:
    if total_items <= window_size:
        return 0, total_items

    start = max(0, selected_index - (window_size // 2))
    end = start + window_size
    if end > total_items:
        end = total_items
        start = end - window_size
    return start, end


def _detail_window_size(max_height: int | None) -> int:
    if max_height is None:
        return 20
    return max(1, max_height - 4)


def _render_state(
    state: CollectionBrowserState,
    *,
    max_width: int = MAX_LIST_LINE_WIDTH,
    max_height: int | None = None,
) -> str:
    if state.mode == "detail":
        detail_lines = state.detail_lines()
        window_size = _detail_window_size(max_height)
        start = min(state.detail_offset, max(0, len(detail_lines) - window_size))
        end = min(len(detail_lines), start + window_size)
        visible = [_truncate_line(line, max_width=max_width) for line in detail_lines[start:end]]
        return "\n".join(
            [
                f"Detail ({start + 1}-{end}/{len(detail_lines)})",
                "",
                *visible,
                "",
                "j/k scroll  n/p page  b/esc back  q quit",
            ]
        )

    visible_items = state.visible_items()
    preview_max_lines = MAX_PREVIEW_LINES
    if max_height is not None:
        preview_max_lines = max(1, min(MAX_PREVIEW_LINES, max_height - 7))
    preview_lines = _truncate_block(
        state.current_preview(),
        max_lines=preview_max_lines,
        max_width=max_width,
    )

    if max_height is None:
        start, end = 0, len(visible_items)
    else:
        list_capacity = max(1, max_height - 6 - len(preview_lines))
        start, end = _window_bounds(len(visible_items), state.selected_index, list_capacity)

    lines = [_truncate_line(state.source.title, max_width=max_width), ""]
    for item_index in range(start, end):
        item = visible_items[item_index]
        display_index = item_index + 1
        prefix = "> " if item_index == state.selected_index else "  "
        line = f"{prefix}{display_index}. {state.source.render_item(display_index, item)}"
        lines.append(_truncate_line(line, max_width=max_width))

    lines.extend(["", "Preview:"])
    lines.extend(preview_lines or ["No preview."])

    if state.mode == "filter":
        footer = f"Filter: {state.filter_buffer}_"
    else:
        footer = LIST_FOOTER
        if state.filter_query:
            footer = f"{footer}  active filter: {state.filter_query}"

    lines.extend(["", _truncate_line(footer, max_width=max_width)])
    return "\n".join(lines)
