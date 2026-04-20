from atlassian_cli.output.renderers import render_output


def test_render_output_json_returns_pretty_json() -> None:
    payload = [{"key": "OPS-1", "summary": "Broken deploy"}]

    rendered = render_output(payload, output="json")

    assert '"key": "OPS-1"' in rendered
    assert rendered.startswith("[")


def test_render_output_table_includes_columns() -> None:
    payload = [{"key": "OPS-1", "summary": "Broken deploy"}]

    rendered = render_output(payload, output="table")

    assert "key" in rendered.lower()
    assert "broken deploy" in rendered.lower()


def test_render_output_table_returns_empty_string_for_empty_lists() -> None:
    assert render_output([], output="table") == ""


def test_render_output_table_uses_first_row_column_order() -> None:
    payload = [
        {"key": "OPS-1", "summary": "First"},
        {"summary": "Second", "key": "OPS-2"},
    ]

    rendered = render_output(payload, output="table")

    row = next(line for line in rendered.splitlines() if "OPS-2" in line and "Second" in line)
    assert row.index("OPS-2") < row.index("Second")
