from dataclasses import dataclass, field
from typing import Any, Callable


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


@dataclass
class CollectionBrowserState:
    source: InteractiveCollectionSource
    items: list[dict[str, Any]] = field(default_factory=list)
    selected_index: int = 0
    mode: str = "list"
    detail_text: str = ""
    next_start: int = 0
    total: int | None = None

    def load_initial(self) -> None:
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self.next_start = page.start + page.limit
        self.total = page.total

    def move(self, delta: int) -> None:
        target = self.selected_index + delta
        if target >= len(self.items) and self.total is not None and len(self.items) < self.total:
            page = self.source.fetch_page(self.next_start, self.source.page_size)
            self.items.extend(page.items)
            self.next_start = page.start + page.limit
            self.total = page.total
        self.selected_index = max(0, min(target, len(self.items) - 1))

    def open_selected_detail(self) -> None:
        detail = self.source.fetch_detail(self.items[self.selected_index])
        self.detail_text = self.source.render_detail(detail)
        self.mode = "detail"

    def close_detail(self) -> None:
        self.mode = "list"


def browse_collection(source: InteractiveCollectionSource) -> None:
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    state = CollectionBrowserState(source)
    state.load_initial()
    body = FormattedTextControl(text=lambda: _render_state(state))
    bindings = KeyBindings()

    @bindings.add("q")
    def _quit(event) -> None:
        event.app.exit()

    @bindings.add("down")
    @bindings.add("j")
    def _down(event) -> None:
        if state.mode == "list":
            state.move(1)

    @bindings.add("up")
    @bindings.add("k")
    def _up(event) -> None:
        if state.mode == "list":
            state.move(-1)

    @bindings.add("enter")
    def _open(event) -> None:
        if state.mode == "list":
            state.open_selected_detail()

    @bindings.add("escape")
    @bindings.add("b")
    def _back(event) -> None:
        if state.mode == "detail":
            state.close_detail()

    app = Application(
        layout=Layout(HSplit([Window(content=body)])),
        key_bindings=bindings,
        full_screen=False,
    )
    app.run()


def _render_state(state: CollectionBrowserState) -> str:
    if state.mode == "detail":
        return state.detail_text
    lines = [state.source.title, ""]
    for index, item in enumerate(state.items):
        prefix = "> " if index == state.selected_index else "  "
        lines.append(prefix + state.source.render_item(index + 1, item))
    lines.extend(["", "j/k or arrows: move  enter: detail  b/esc: back  q: quit"])
    return "\n".join(lines)
