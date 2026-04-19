from io import StringIO

from rich.console import Console
from rich.table import Table

from atlassian_cli.output.formatters import to_json, to_yaml


def render_output(value, *, output: str) -> str:
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)

    rows = value if isinstance(value, list) else [value]
    table = Table()
    for column in rows[0].keys():
        table.add_column(column)
    for row in rows:
        table.add_row(*[str(row[column]) for column in row])
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120)
    console.print(table)
    return buffer.getvalue()
