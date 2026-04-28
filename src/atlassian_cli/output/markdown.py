from collections.abc import Mapping, Sequence
from typing import Any


MAX_SUMMARY_LIST_ITEMS = 3
DETAIL_BODY_FIELDS = {"description", "content"}


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
        text = _inline_value(value.get(field))
        if text:
            lines.extend(["", f"## {field.title()}", text])

    return "\n".join(lines).strip()
