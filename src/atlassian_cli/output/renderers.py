from io import StringIO

from rich.console import Console
from rich.table import Table

from atlassian_cli.output.formatters import to_json, to_yaml


def render_output(value, *, output: str) -> str:
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)
    if isinstance(value, list) and not value:
        return ""

    rows = value if isinstance(value, list) else [value]
    columns = list(rows[0].keys())
    table = Table()
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*[str(row.get(column, "")) for column in columns])
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120)
    console.print(table)
    return buffer.getvalue()
