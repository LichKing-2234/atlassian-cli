import os
from pathlib import Path

import typer

from atlassian_cli.auth.headers import parse_cli_headers
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_profiles
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.products.bitbucket.commands.branch import app as bitbucket_branch_app
from atlassian_cli.products.bitbucket.commands.pr import app as bitbucket_pr_app
from atlassian_cli.products.bitbucket.commands.project import app as bitbucket_project_app
from atlassian_cli.products.bitbucket.commands.repo import app as bitbucket_repo_app
from atlassian_cli.products.confluence.commands.attachment import app as confluence_attachment_app
from atlassian_cli.products.confluence.commands.page import app as confluence_page_app
from atlassian_cli.products.confluence.commands.space import app as confluence_space_app
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
confluence_app.add_typer(confluence_page_app, name="page")
confluence_app.add_typer(confluence_space_app, name="space")
confluence_app.add_typer(confluence_attachment_app, name="attachment")
bitbucket_app.add_typer(bitbucket_project_app, name="project")
bitbucket_app.add_typer(bitbucket_repo_app, name="repo")
bitbucket_app.add_typer(bitbucket_branch_app, name="branch")
bitbucket_app.add_typer(bitbucket_pr_app, name="pr")

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
    header: list[str] = typer.Option([], "--header"),
    output: str = typer.Option("table", "--output"),
) -> None:
    if ctx.invoked_subcommand is None:
        return

    profiles = load_profiles(config_file) if config_file.exists() else {}
    if profile:
        selected_profile = profiles.get(profile)
        if selected_profile is None:
            raise typer.BadParameter(f"Unknown profile: {profile}", param_hint="--profile")
    elif url is None:
        selected_profile = next(iter(profiles.values()), None)
    else:
        selected_profile = None
    if selected_profile is None and url is None:
        raise typer.BadParameter("provide --profile or --url")
    try:
        headers = parse_cli_headers(header)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--header") from exc

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
            headers=headers,
            output=output,
        ),
    )
