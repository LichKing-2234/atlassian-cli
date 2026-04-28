import os
from pathlib import Path

import typer

from atlassian_cli.auth.headers import parse_cli_headers
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import (
    Deployment,
    LoadedConfig,
    Product,
    ProfileConfig,
    RuntimeOverrides,
)
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.config.template import ensure_default_config
from atlassian_cli.core.context import LazyExecutionContext
from atlassian_cli.core.errors import ConfigError
from atlassian_cli.output.modes import OutputMode
from atlassian_cli.products.bitbucket.commands.branch import app as bitbucket_branch_app
from atlassian_cli.products.bitbucket.commands.pr import app as bitbucket_pr_app
from atlassian_cli.products.bitbucket.commands.project import app as bitbucket_project_app
from atlassian_cli.products.bitbucket.commands.repo import app as bitbucket_repo_app
from atlassian_cli.products.confluence.commands.attachment import app as confluence_attachment_app
from atlassian_cli.products.confluence.commands.comment import app as confluence_comment_app
from atlassian_cli.products.confluence.commands.page import app as confluence_page_app
from atlassian_cli.products.confluence.commands.space import app as confluence_space_app
from atlassian_cli.products.jira.commands.comment import app as jira_comment_app
from atlassian_cli.products.jira.commands.field import app as jira_field_app
from atlassian_cli.products.jira.commands.issue import app as jira_issue_app
from atlassian_cli.products.jira.commands.project import app as jira_project_app
from atlassian_cli.products.jira.commands.user import app as jira_user_app

app = typer.Typer(help="Atlassian Server/Data Center CLI")

jira_app = typer.Typer(help="Jira commands")
confluence_app = typer.Typer(help="Confluence commands")
bitbucket_app = typer.Typer(help="Bitbucket commands")

jira_app.add_typer(jira_issue_app, name="issue")
jira_app.add_typer(jira_field_app, name="field")
jira_app.add_typer(jira_comment_app, name="comment")
jira_app.add_typer(jira_project_app, name="project")
jira_app.add_typer(jira_user_app, name="user")
confluence_app.add_typer(confluence_page_app, name="page")
confluence_app.add_typer(confluence_comment_app, name="comment")
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


def _missing_product_message(config_file: Path, product: Product, *, created: bool) -> str:
    if created:
        return f"Created {config_file}. Fill in [{product.value}] or pass --url."
    return f"Fill in [{product.value}] in {config_file} or pass --url."


@app.callback()
def root_callback(
    ctx: typer.Context,
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, "--config-file"),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    header: list[str] = typer.Option([], "--header"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if ctx.invoked_subcommand is None:
        return

    product = Product(ctx.invoked_subcommand)
    try:
        headers = parse_cli_headers(header)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--header") from exc

    def load_runtime_context():
        created_template = ensure_default_config(config_file, default_path=DEFAULT_CONFIG_FILE)
        config = load_config(config_file) if config_file.exists() else LoadedConfig()
        if url is None:
            product_config = config.product_config(product)
            if product_config is None:
                raise typer.BadParameter(
                    _missing_product_message(config_file, product, created=created_template)
                )
            try:
                base_profile = product_config.to_profile_config(
                    product=product,
                    name=product.value,
                )
            except ConfigError as exc:
                raise typer.BadParameter(
                    _missing_product_message(config_file, product, created=created_template)
                ) from exc
        else:
            base_profile = ProfileConfig(
                name=f"inline-{product.value}",
                product=product,
                deployment=deployment or Deployment.SERVER,
                url=url,
                auth=auth or AuthMode.BASIC,
                username=username,
                password=password,
                token=token,
                headers={},
            )
        try:
            return resolve_runtime_context(
                profile=base_profile,
                env=dict(os.environ),
                default_headers=config.headers,
                overrides=RuntimeOverrides(
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
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

    ctx.obj = LazyExecutionContext(load_runtime_context)
