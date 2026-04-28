from atlassian_cli.output.tty import should_use_interactive_output


def test_should_use_interactive_output_requires_markdown_collection_and_tty() -> None:
    assert should_use_interactive_output(
        "markdown",
        command_kind="collection",
        stdin_isatty=lambda: True,
        stdout_isatty=lambda: True,
    ) is True
    assert should_use_interactive_output(
        "json",
        command_kind="collection",
        stdin_isatty=lambda: True,
        stdout_isatty=lambda: True,
    ) is False
    assert should_use_interactive_output(
        "markdown",
        command_kind="detail",
        stdin_isatty=lambda: True,
        stdout_isatty=lambda: True,
    ) is False
    assert should_use_interactive_output(
        "markdown",
        command_kind="collection",
        stdin_isatty=lambda: False,
        stdout_isatty=lambda: True,
    ) is False
