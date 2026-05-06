import re
from collections.abc import Mapping, Sequence
from typing import Any

from markdownify import markdownify as convert_html_to_markdown

MAX_SUMMARY_LIST_ITEMS = 3
DETAIL_BODY_FIELDS = {"description", "content"}
PREVIEW_FIELDS = (
    ("state", "State"),
    ("status", "Status"),
    ("author", "Author"),
    ("assignee", "Assignee"),
    ("reporter", "Reporter"),
    ("from_ref", "From"),
    ("to_ref", "To"),
    ("updated", "Updated"),
    ("updated_date", "Updated"),
)
HTML_CONTENT_RE = re.compile(
    r"<(?:p|br|a|table|thead|tbody|tr|th|td|ol|ul|li)\b|<(?:ac|ri):",
    re.IGNORECASE,
)


def _collection_items(value: Any) -> list[dict]:
    if isinstance(value, dict):
        for key in ("results", "issues"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _inline_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        for field in ("display_name", "display_id", "name", "title", "key", "id"):
            candidate = value.get(field)
            if candidate not in (None, ""):
                return str(candidate)
        return ""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = [_inline_value(item) for item in value]
        values = [item for item in values if item]
        if len(values) > MAX_SUMMARY_LIST_ITEMS:
            hidden = len(values) - MAX_SUMMARY_LIST_ITEMS
            values = [*values[:MAX_SUMMARY_LIST_ITEMS], f"+{hidden} more"]
        return ", ".join(values)
    return " ".join(str(value).split())


def _heading(record: Mapping[str, Any]) -> str:
    identifier = next(
        (
            str(record[field])
            for field in ("key", "id", "slug", "name")
            if record.get(field) not in (None, "")
        ),
        "Item",
    )
    title = next(
        (
            str(record[field])
            for field in ("summary", "title", "name")
            if record.get(field) not in (None, "")
        ),
        "",
    )
    return f"{identifier} - {title}" if title and title != identifier else identifier


def _unwrap_record(value: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("issue", "page"):
        candidate = value.get(key)
        if isinstance(candidate, Mapping):
            return _unwrap_record(candidate)
    if isinstance(value.get("metadata"), Mapping):
        record = dict(value["metadata"])
        content = value.get("content")
        if isinstance(content, Mapping) and content.get("value") not in (None, ""):
            record["content"] = content["value"]
        return record
    return value


def render_heading(record: Mapping[str, Any]) -> str:
    return _heading(record)


def excerpt_text(value: Any, *, max_lines: int = 3) -> str:
    if value in (None, ""):
        return ""

    lines = [" ".join(line.split()) for line in str(value).splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join([*lines[: max_lines - 1], f"{lines[max_lines - 1]}..."])


def _normalize_markdown_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _render_detail_body(field: str, value: Any) -> str:
    if field != "content":
        return _inline_value(value)
    if value in (None, ""):
        return ""

    text = str(value) if isinstance(value, str) else _inline_value(value)
    if not HTML_CONTENT_RE.search(text):
        return _normalize_markdown_block(text)

    rendered = convert_html_to_markdown(text, heading_style="ATX")
    return _normalize_markdown_block(rendered)


def render_markdown_list_item(item: Mapping[str, Any]) -> str:
    identifier = next(
        (
            str(item[field])
            for field in ("key", "id", "slug", "name")
            if item.get(field) not in (None, "")
        ),
        "Item",
    )
    status = _inline_value(item.get("state") or item.get("status"))
    owner = _inline_value(item.get("author") or item.get("assignee"))
    title = next(
        (
            str(item[field])
            for field in ("summary", "title", "name")
            if item.get(field) not in (None, "")
        ),
        "",
    )
    return "  ".join(part for part in (identifier, status, owner, title) if part)


def render_markdown_preview(item: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for field, label in PREVIEW_FIELDS:
        text = _inline_value(item.get(field))
        if text:
            lines.append(f"{label}: {text}")

    description = excerpt_text(item.get("description"), max_lines=3)
    if description:
        lines.extend(["", "Description:", description])

    return "\n".join(lines) or _heading(item)


def render_markdown(value: Any) -> str:
    items = _collection_items(value)
    if items:
        blocks: list[str] = []
        for index, item in enumerate(items, start=1):
            lines = [f"{index}. {_heading(item)}"]
            for field, label in (
                ("state", "State"),
                ("status", "Status"),
                ("author", "Author"),
                ("assignee", "Assignee"),
                ("reviewers", "Reviewers"),
                ("from_ref", "From"),
                ("to_ref", "To"),
                ("updated", "Updated"),
                ("updated_date", "Updated"),
            ):
                text = _inline_value(item.get(field))
                if text:
                    lines.append(f"   - {label}: {text}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    if isinstance(value, list):
        return ""

    if not isinstance(value, Mapping):
        return _inline_value(value)

    value = _unwrap_record(value)

    lines = [f"# {_heading(value)}"]
    for field, label in (
        ("state", "State"),
        ("status", "Status"),
        ("author", "Author"),
        ("assignee", "Assignee"),
        ("reporter", "Reporter"),
        ("from_ref", "From"),
        ("to_ref", "To"),
        ("created", "Created"),
        ("created_date", "Created"),
        ("updated", "Updated"),
        ("updated_date", "Updated"),
    ):
        text = _inline_value(value.get(field))
        if text:
            lines.append(f"- {label}: {text}")

    for field in DETAIL_BODY_FIELDS:
        text = _render_detail_body(field, value.get(field))
        if text:
            lines.extend(["", f"## {field.title()}", text])

    return "\n".join(lines).strip()
