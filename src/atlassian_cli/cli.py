import os
from pathlib import Path

import typer

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_profiles
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.products.jira.commands.issue import app as jira_issue_app
from atlassian_cli.products.jira.commands.project import app as jira_project_app
from atlassian_cli.products.jira.commands.user import app as jira_user_app

app = typer.Typer(help="Atlassian Server/Data Center CLI")

jira_app = typer.Typer(help="Jira commands")
confluence_app = typer.Typer(help="Confluence commands")
bitbucket_app = typer.Typer(help="Bitbucket commands")

jira_app.add_typer(jira_issue_app, name="issue")
jira_app.add_typer(jira_project_app, name="project")
jira_app.add_typer(jira_user_app, name="user")

app.add_typer(jira_app, name="jira")
app.add_typer(confluence_app, name="confluence")
app.add_typer(bitbucket_app, name="bitbucket")

DEFAULT_CONFIG_FILE = Path("~/.config/atlassian-cli/config.toml").expanduser()


@app.callback()
def root_callback(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile"),
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, "--config-file"),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    output: str = typer.Option("table", "--output"),
) -> None:
    if ctx.invoked_subcommand is None:
        return

    profiles = load_profiles(config_file) if config_file.exists() else {}
    selected_profile = profiles.get(profile) if profile else next(iter(profiles.values()), None)
    if selected_profile is None and url is None:
        raise typer.BadParameter("provide --profile or --url")

    product = Product(ctx.invoked_subcommand)
    base_profile = selected_profile or ProfileConfig(
        name=profile or f"inline-{product.value}",
        product=product,
        deployment=deployment or Deployment.SERVER,
        url=url or "",
        auth=auth or AuthMode.BASIC,
        username=username,
        password=password,
        token=token,
    )
    ctx.obj = resolve_runtime_context(
        profile=base_profile,
        env=dict(os.environ),
        overrides=RuntimeOverrides(
            profile=profile,
            product=product,
            deployment=deployment,
            url=url,
            username=username,
            password=password,
            token=token,
            auth=auth,
            output=output,
        ),
    )
