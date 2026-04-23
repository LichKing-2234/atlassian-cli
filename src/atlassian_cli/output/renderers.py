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
        table.add_row(*[str(row.get(column, "")) for column in columns])
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120)
    console.print(table)
    return buffer.getvalue()
