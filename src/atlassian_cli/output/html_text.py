import re
from html.parser import HTMLParser

HTMLISH_RE = re.compile(r"<[A-Za-z/][^>]*>")
BLOCK_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "div",
    "blockquote",
    "tr",
}
LIST_TAGS = {"ul", "ol"}
CELL_TAGS = {"td", "th"}


def looks_like_htmlish(text: str) -> bool:
    return bool(HTMLISH_RE.search(text))


class ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.list_stack: list[str] = []
        self.link_href: str | None = None
        self.link_text: list[str] = []
        self.preformatted = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag in BLOCK_TAGS:
            self.parts.append("\n\n")
            return
        if tag in LIST_TAGS:
            self.list_stack.append(tag)
            self.parts.append("\n")
            return
        if tag == "li":
            bullet = "-" if not self.list_stack or self.list_stack[-1] == "ul" else "1."
            self.parts.append(f"\n{bullet} ")
            return
        if tag == "br":
            self.parts.append("\n")
            return
        if tag == "pre":
            self.preformatted = True
            self.parts.append("\n\n```\n")
            return
        if tag == "code" and not self.preformatted:
            self.parts.append("`")
            return
        if tag == "a":
            self.link_href = attrs_map.get("href")
            self.link_text = []
            return
        if tag in CELL_TAGS:
            if self.parts and not self.parts[-1].endswith((" ", "\n")):
                self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in LIST_TAGS and self.list_stack:
            self.list_stack.pop()
            self.parts.append("\n")
            return
        if tag == "pre":
            self.preformatted = False
            self.parts.append("\n```\n")
            return
        if tag == "code" and not self.preformatted:
            self.parts.append("`")
            return
        if tag == "a":
            text = "".join(self.link_text).strip()
            if text:
                self.parts.append(text)
            elif self.link_href:
                self.parts.append(self.link_href)
            self.link_href = None
            self.link_text = []
            return
        if tag in CELL_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not data:
            return
        chunk = data if self.preformatted else " ".join(data.split())
        if not chunk:
            return
        if self.link_href is not None:
            self.link_text.append(chunk)
        else:
            self.parts.append(chunk)


def render_htmlish_text(text: str) -> str:
    if not looks_like_htmlish(text):
        return text

    parser = ReadableHTMLParser()
    parser.feed(text)
    parser.close()

    lines = [line.rstrip() for line in "".join(parser.parts).splitlines()]
    collapsed: list[str] = []
    for line in lines:
        if line:
            collapsed.append(line)
        elif collapsed and collapsed[-1] != "":
            collapsed.append("")
    return "\n".join(collapsed).strip()
