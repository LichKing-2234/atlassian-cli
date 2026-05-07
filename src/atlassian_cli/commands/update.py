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


def _echo_payload(payload: dict, *, output: OutputMode) -> None:
    if is_machine_output(output):
        typer.echo(render_output(payload, output=output))
        return
    message = payload.get("message")
    typer.echo(str(message) if message else render_output(payload, output=OutputMode.MARKDOWN))


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


def _format_install(result: InstallResult) -> str:
    if result.updated and result.installer_stderr:
        return "\n".join([result.message, result.installer_stderr])
    if result.updated:
        return result.message
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
    try:
        result = install_update(
            current_version=__version__,
            version=version,
            install_dir=install_dir,
            force=force,
        )
    except UpdateError as exc:
        _fail(exc)

    payload = result.to_dict() | {"message": _format_install(result)}
    _echo_payload(payload, output=output)
