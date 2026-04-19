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
