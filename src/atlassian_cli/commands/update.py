import re
import sys
from pathlib import Path

import typer

from atlassian_cli import __version__
from atlassian_cli.output.modes import OutputMode, is_machine_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.update import (
    InstallResult,
    UpdateError,
    UpdateInfo,
    get_update_info,
    install_update,
)

app = typer.Typer(help="CLI update commands")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _echo_payload(payload: dict, *, output: OutputMode) -> None:
    if is_machine_output(output):
        typer.echo(render_output(payload, output=output))
        return
    message = payload.get("message")
    typer.echo(str(message) if message else render_output(payload, output=OutputMode.MARKDOWN))


def _stderr_is_interactive() -> bool:
    return sys.stderr.isatty()


def _format_check(info: UpdateInfo) -> str:
    if info.update_available:
        lines = [
            f"atlassian-cli {info.current_version} can be updated to {info.latest.tag}.",
            "Run: atlassian update install",
        ]
        if info.latest.url:
            lines.append(f"Release: {info.latest.url}")
        return "\n".join(lines)
    return f"atlassian-cli {info.current_version} is up to date."


def _is_progress_line(line: str) -> bool:
    return all(char in "#O=-.% 0123456789" for char in line)


def _installer_notes(stderr: str) -> list[str]:
    normalized = _ANSI_ESCAPE_RE.sub("", stderr.replace("\r", "\n"))
    notes: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Downloading "):
            continue
        if _is_progress_line(line):
            continue
        notes.append(line)
    return notes


def _format_install(result: InstallResult) -> str:
    if result.updated:
        notes = _installer_notes(result.installer_stderr)
        return "\n".join([result.message, *notes])
    return f"{result.message}."


def _fail(exc: UpdateError) -> None:
    typer.echo(f"error: {exc}", err=True)
    raise typer.Exit(1)


@app.command("check")
def check_update(
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    """Check whether a newer GitHub release is available."""
    try:
        info = get_update_info(__version__)
    except UpdateError as exc:
        _fail(exc)

    if is_machine_output(output):
        typer.echo(render_output(info.to_dict(), output=output))
        return
    typer.echo(_format_check(info))


@app.command("install")
def install_update_command(
    version: str | None = typer.Option(
        None,
        "--version",
        help="Release tag or version to install, for example v0.1.0.",
    ),
    install_dir: Path | None = typer.Option(
        None,
        "--install-dir",
        help="Directory where the atlassian launcher should be installed.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reinstall the latest release even when the current version is up to date.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    """Install the latest release, or a specific release with --version."""
    stream_output = not is_machine_output(output) and _stderr_is_interactive()
    try:
        result = install_update(
            current_version=__version__,
            version=version,
            install_dir=install_dir,
            force=force,
            stream_output=stream_output,
        )
    except UpdateError as exc:
        _fail(exc)

    if result.output_streamed and not is_machine_output(output):
        return

    payload = result.to_dict() | {"message": _format_install(result)}
    _echo_payload(payload, output=output)
