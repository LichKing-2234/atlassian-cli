from collections.abc import Callable

import click
import typer
from typer._click.exceptions import Abort as TyperAbort
from typer._click.exceptions import BadParameter as TyperBadParameter

from atlassian_cli.core.errors import AtlassianCliError, MissingCredentialError
from atlassian_cli.products.bitbucket.gh_compat.pr_output import GhPreflightError
from atlassian_cli.products.bitbucket.gh_compat.selectors import RepositoryHostMismatchError


def run_gh_read(action: Callable[[], None]) -> None:
    try:
        action()
    except typer.Exit:
        raise
    except (KeyboardInterrupt, click.Abort, TyperAbort):
        raise typer.Exit(2) from None
    except GhPreflightError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    except RepositoryHostMismatchError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(4) from None
    except MissingCredentialError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(4) from None
    except (click.BadParameter, TyperBadParameter) as exc:
        if isinstance(exc.__cause__, MissingCredentialError):
            typer.echo(f"Error: {exc.__cause__}", err=True)
            raise typer.Exit(4) from None
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
    except AtlassianCliError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
