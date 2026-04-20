import subprocess
from collections.abc import Callable

from atlassian_cli.core.errors import ConfigError

CommandRunner = Callable[[str], str]


def run_header_command(command: str) -> str:
    completed = subprocess.run(
        ["/bin/sh", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ConfigError(
            f"Header command failed with exit code {completed.returncode}: {command}"
        )
    return completed.stdout


def substitute_header_commands(
    *,
    value: str,
    source: str,
    header_name: str,
    runner: CommandRunner | None = None,
) -> str:
    resolved = value
    runner = runner or run_header_command
    while "$(" in resolved:
        start = resolved.find("$(")
        end = resolved.find(")", start + 2)
        if start == -1 or end == -1:
            raise ConfigError(f"Malformed command substitution in {source}.{header_name}")
        command = resolved[start + 2 : end].strip()
        if not command or "$(" in command:
            raise ConfigError(f"Malformed command substitution in {source}.{header_name}")
        output = runner(command).strip()
        if not output:
            raise ConfigError(
                f"Header command produced empty output for {source}.{header_name}"
            )
        if "\n" in output:
            raise ConfigError(
                f"Header command must produce a single line for {source}.{header_name}"
            )
        resolved = f"{resolved[:start]}{output}{resolved[end + 1:]}"
    return resolved
