from atlassian_cli.output.modes import OutputMode, is_machine_output, is_raw_output, normalized_output


def test_normalized_output_preserves_markdown() -> None:
    assert normalized_output(OutputMode.MARKDOWN) == "markdown"
    assert normalized_output(OutputMode.RAW_JSON) == "json"
    assert normalized_output(OutputMode.RAW_YAML) == "yaml"


def test_machine_output_detection_excludes_markdown() -> None:
    assert is_machine_output(OutputMode.JSON) is True
    assert is_machine_output(OutputMode.YAML) is True
    assert is_machine_output(OutputMode.MARKDOWN) is False
    assert is_raw_output(OutputMode.RAW_JSON) is True
