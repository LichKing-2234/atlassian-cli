from atlassian_cli.output.modes import is_raw_output, normalized_output
from atlassian_cli.output.renderers import render_output


def test_render_output_json_returns_pretty_json() -> None:
    payload = [{"key": "PROJ-1", "summary": "Example issue summary"}]

    rendered = render_output(payload, output="json")

    assert '"key": "PROJ-1"' in rendered
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


def test_render_output_markdown_dispatches_to_markdown_renderer() -> None:
    payload = {"key": "PROJ-1", "summary": "Example issue summary"}

    rendered = render_output(payload, output="markdown")

    assert rendered.startswith("# PROJ-1 - Example issue summary")


def test_render_output_markdown_returns_empty_string_for_empty_lists() -> None:
    assert render_output([], output="markdown") == ""
