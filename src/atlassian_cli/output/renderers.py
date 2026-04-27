from collections.abc import Mapping, Sequence
from io import StringIO

from rich.console import Console
from rich.table import Table

from atlassian_cli.output.formatters import to_json, to_yaml
from atlassian_cli.output.modes import normalized_output


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


def _summarize_mapping(value: Mapping[str, object]) -> str:
    display_name = value.get("display_name")
    email = value.get("email")
    if display_name not in (None, ""):
        display = str(display_name)
        return f"{display} <{email}>" if email not in (None, "") else display

    name = value.get("name")
    key = value.get("key")
    if key not in (None, "") and name not in (None, "") and str(key) != str(name):
        return f"{key} ({name})"

    for field in ("name", "title", "key", "id"):
        candidate = value.get(field)
        if candidate not in (None, ""):
            return str(candidate)

    return str(dict(value))


def _summarize_sequence(value: Sequence[object]) -> str:
    parts: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            parts.append(_summarize_mapping(item))
        elif item not in (None, ""):
            parts.append(str(item))
    return ", ".join(parts)


def _format_table_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return _summarize_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _summarize_sequence(value)
    return str(value)


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
