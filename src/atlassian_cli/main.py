import typer

from atlassian_cli.cli import app
from atlassian_cli.core.errors import AtlassianCliError, exit_code_for_error


def main() -> None:
    try:
        app()
    except AtlassianCliError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(exit_code_for_error(exc)) from None


if __name__ == "__main__":
    main()
