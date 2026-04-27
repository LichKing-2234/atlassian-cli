import json
from collections.abc import Mapping, Sequence
from io import StringIO

from rich.console import Console
from rich.table import Table

from atlassian_cli.output.formatters import to_json, to_yaml
from atlassian_cli.output.modes import normalized_output

MAX_TABLE_SEQUENCE_ITEMS = 3


def _coerce_table_row(value) -> dict:
    if isinstance(value, dict):
        return value
    return {"value": value}


def _extract_table_rows(value) -> list[dict]:
    if isinstance(value, dict):
        for key in ("results", "issues"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [_coerce_table_row(item) for item in candidate]
        return [_coerce_table_row(value)]
    if isinstance(value, list):
        return [_coerce_table_row(item) for item in value]
    return [_coerce_table_row(value)]


def _compact_scalar(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(part.strip() for part in value.splitlines()).strip()
    return str(value)


def _fallback_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _summarize_mapping(value: Mapping[str, object]) -> str:
    display_name = _compact_scalar(value.get("display_name"))
    email = _compact_scalar(value.get("email"))
    if display_name:
        return f"{display_name} <{email}>" if email else display_name

    display_id = _compact_scalar(value.get("display_id"))
    if display_id:
        return display_id

    name = _compact_scalar(value.get("name"))
    key = _compact_scalar(value.get("key"))
    if key and name and key != name:
        return f"{key} ({name})"

    for field in ("name", "title", "key", "id"):
        candidate = _compact_scalar(value.get(field))
        if candidate:
            return candidate

    return _fallback_json(dict(value))


def _summarize_sequence(value: Sequence[object]) -> str:
    parts: list[str] = []
    for item in value:
        text = _format_table_cell(item)
        if text:
            parts.append(text)
    if len(parts) > MAX_TABLE_SEQUENCE_ITEMS:
        hidden_count = len(parts) - MAX_TABLE_SEQUENCE_ITEMS
        parts = [*parts[:MAX_TABLE_SEQUENCE_ITEMS], f"+{hidden_count} more"]
    return ", ".join(parts)


def _format_table_cell(value: object) -> str:
    if isinstance(value, Mapping):
        return _summarize_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _summarize_sequence(value)
    return _compact_scalar(value)


def render_output(value, *, output: str) -> str:
    output = normalized_output(output)
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)

    rows = _extract_table_rows(value)
    if not rows:
        return ""

    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)

    table = Table()
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*[_format_table_cell(row.get(column, "")) for column in columns])
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120)
    console.print(table)
    return buffer.getvalue()
