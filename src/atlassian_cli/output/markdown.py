from collections.abc import Mapping, Sequence
from typing import Any

from atlassian_cli.output.html_text import render_htmlish_text

MAX_SUMMARY_LIST_ITEMS = 3
DETAIL_BODY_FIELDS = ("description", "content", "body", "diff")
CORE_DETAIL_FIELDS = (
    ("state", "State"),
    ("status", "Status"),
    ("issue_type", "Issue Type"),
    ("type", "Type"),
    ("priority", "Priority"),
    ("assignee", "Assignee"),
    ("author", "Author"),
    ("reporter", "Reporter"),
    ("project", "Project"),
    ("space", "Space"),
    ("from_ref", "From"),
    ("to_ref", "To"),
    ("version", "Version"),
    ("created", "Created"),
    ("created_date", "Created"),
    ("updated", "Updated"),
    ("updated_date", "Updated"),
    ("duedate", "Due Date"),
    ("resolutiondate", "Resolution Date"),
    ("url", "URL"),
)
DETAIL_SKIP_FIELDS = (
    {field for field, _ in CORE_DETAIL_FIELDS}
    | set(DETAIL_BODY_FIELDS)
    | {"id", "key", "slug", "name", "summary", "title"}
)
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
        for field in (
            "display_name",
            "display_id",
            "key",
            "name",
            "title",
            "summary",
            "filename",
            "id",
        ):
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


def _label_for_key(key: str) -> str:
    label = key.replace("_", " ").title()
    return label.replace("Url", "URL")


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, Mapping):
        return len(value) == 0
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) == 0
    return False


def _render_body_text(value: Any) -> str:
    return render_htmlish_text(str(value))


def _append_mapping_fields(lines: list[str], value: Mapping[str, Any], *, level: int) -> None:
    scalar_fields: list[tuple[str, Any]] = []
    nested_fields: list[tuple[str, Any]] = []
    for nested_key, nested_value in value.items():
        if _is_empty(nested_value):
            continue
        if isinstance(nested_value, Mapping) or (
            isinstance(nested_value, Sequence)
            and not isinstance(nested_value, (str, bytes, bytearray))
        ):
            nested_fields.append((nested_key, nested_value))
        else:
            scalar_fields.append((nested_key, nested_value))

    for nested_key, nested_value in scalar_fields:
        lines.append(f"- {_label_for_key(nested_key)}: {_inline_value(nested_value)}")

    for nested_key, nested_value in nested_fields:
        _append_remaining_detail(lines, nested_key, nested_value, level=min(level + 1, 6))


def _append_remaining_detail(lines: list[str], key: str, value: Any, *, level: int = 2) -> None:
    if _is_empty(value):
        return

    heading = "#" * level
    label = _label_for_key(key)

    if isinstance(value, Mapping):
        lines.extend(["", f"{heading} {label}"])
        _append_mapping_fields(lines, value, level=level)
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = [item for item in value if not _is_empty(item)]
        if not values:
            return

        lines.extend(["", f"{heading} {label}"])
        if all(
            not isinstance(item, Mapping)
            and not (isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)))
            for item in values
        ):
            lines.extend(f"- {_inline_value(item)}" for item in values)
            return

        item_heading = "#" * min(level + 1, 6)
        for index, item in enumerate(values, start=1):
            if isinstance(item, Mapping):
                title = _inline_value(item) or f"Item {index}"
                lines.append(f"{item_heading} Item {index}: {title}")
                _append_mapping_fields(lines, item, level=level + 1)
                continue
            if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
                lines.append(f"{item_heading} Item {index}")
                lines.extend(f"- {_inline_value(entry)}" for entry in item if not _is_empty(entry))
                continue
            lines.append(f"- {_inline_value(item)}")
        return

    lines.extend(["", f"{heading} {label}", _render_body_text(value)])


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
    for field, label in CORE_DETAIL_FIELDS:
        text = _inline_value(value.get(field))
        if text:
            lines.append(f"- {label}: {text}")

    for field in DETAIL_BODY_FIELDS:
        text = value.get(field)
        if text not in (None, ""):
            lines.extend(["", f"## {_label_for_key(field)}", _render_body_text(text)])

    for key, nested_value in value.items():
        if key in DETAIL_SKIP_FIELDS or _is_empty(nested_value):
            continue
        _append_remaining_detail(lines, key, nested_value)

    return "\n".join(lines).strip()
