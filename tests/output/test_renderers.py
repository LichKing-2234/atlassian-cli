from atlassian_cli.output.modes import is_raw_output, normalized_output
from atlassian_cli.output.renderers import render_output


def test_render_output_json_returns_pretty_json() -> None:
    payload = [{"key": "OPS-1", "summary": "Broken deploy"}]

    rendered = render_output(payload, output="json")

    assert '"key": "OPS-1"' in rendered
    assert rendered.startswith("[")


def test_render_output_raw_json_returns_json() -> None:
    payload = {"_links": {"self": "https://example.com"}}

    rendered = render_output(payload, output="raw-json")

    assert '"_links"' in rendered


def test_render_output_raw_yaml_returns_yaml() -> None:
    payload = {"_links": {"self": "https://example.com"}}

    rendered = render_output(payload, output="raw-yaml")

    assert "_links:" in rendered


def test_normalized_output_maps_raw_modes_to_base_serializers() -> None:
    assert normalized_output("raw-json") == "json"
    assert normalized_output("raw-yaml") == "yaml"
    assert normalized_output("json") == "json"


def test_is_raw_output_detects_raw_variants() -> None:
    assert is_raw_output("raw-json") is True
    assert is_raw_output("raw-yaml") is True
    assert is_raw_output("json") is False


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


def test_render_output_table_uses_results_envelope_rows() -> None:
    payload = {
        "start_at": 0,
        "max_results": 2,
        "results": [
            {"key": "OPS-1", "summary": "First"},
            {"key": "OPS-2", "summary": "Second", "assignee": {"display_name": "Alice"}},
        ],
    }

    rendered = render_output(payload, output="table")

    assert "OPS-1" in rendered
    assert "OPS-2" in rendered
    assert "assignee" in rendered.lower()


def test_render_output_table_unions_columns_across_sparse_rows() -> None:
    payload = [
        {"key": "OPS-1", "summary": "First"},
        {"key": "OPS-2", "summary": "Second", "priority": {"name": "High"}},
    ]

    rendered = render_output(payload, output="table")

    assert "priority" in rendered.lower()


def test_render_output_table_wraps_scalar_rows() -> None:
    payload = ["first", "second"]

    rendered = render_output(payload, output="table")

    assert "value" in rendered.lower()
    assert "first" in rendered.lower()
    assert "second" in rendered.lower()


def test_render_output_table_summarizes_name_mappings() -> None:
    payload = [{"key": "OPS-1", "status": {"name": "In Progress"}}]

    rendered = render_output(payload, output="table")

    assert "In Progress" in rendered
    assert "{'name': 'In Progress'}" not in rendered


def test_render_output_table_summarizes_display_name_and_email_mappings() -> None:
    payload = [
        {
            "key": "OPS-1",
            "assignee": {
                "display_name": "Alice Zhang",
                "email": "alice@example.com",
            },
        }
    ]

    rendered = render_output(payload, output="table")

    assert "Alice Zhang <alice@example.com>" in rendered
    assert "display_name" not in rendered


def test_render_output_table_summarizes_string_lists() -> None:
    payload = [{"key": "OPS-1", "labels": ["prod", "sev1", "backend"]}]

    rendered = render_output(payload, output="table")

    assert "prod, sev1, backend" in rendered
    assert "['prod', 'sev1', 'backend']" not in rendered


def test_render_output_table_summarizes_lists_of_mappings() -> None:
    payload = [
        {
            "key": "OPS-1",
            "reviewers": [
                {"display_name": "Alice"},
                {"display_name": "Bob"},
            ],
        }
    ]

    rendered = render_output(payload, output="table")

    assert "Alice, Bob" in rendered
    assert "display_name" not in rendered


def test_render_output_table_flattens_multiline_strings() -> None:
    payload = [{"key": "OPS-1", "summary": "First line\nSecond line"}]

    rendered = render_output(payload, output="table")

    assert "First line Second line" in rendered
    assert "First line\nSecond line" not in rendered


def test_render_output_table_uses_compact_json_fallback_for_unknown_mappings() -> None:
    payload = [
        {
            "key": "OPS-1",
            "metadata": {
                "beta": {"x": 2},
                "alpha": 1,
            },
        }
    ]

    rendered = render_output(payload, output="table")

    assert '{"alpha":1,"beta":{"x":2}}' in rendered
    assert "{'beta': {'x': 2}, 'alpha': 1}" not in rendered
