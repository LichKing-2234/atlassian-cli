import sys

from atlassian_cli.output.modes import is_machine_output


def should_use_interactive_output(
    output: str,
    *,
    command_kind: str,
    stdin_isatty=None,
    stdout_isatty=None,
) -> bool:
    stdin_isatty = stdin_isatty or sys.stdin.isatty
    stdout_isatty = stdout_isatty or sys.stdout.isatty
    return (
        output == "markdown"
        and command_kind == "collection"
        and stdin_isatty()
        and stdout_isatty()
        and not is_machine_output(output)
    )
