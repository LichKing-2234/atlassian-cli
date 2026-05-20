from pathlib import Path
from typing import Any

import click
import typer

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProductConfig
from atlassian_cli.config.ssh_accept_env import (
    ATLASSIAN_ACCEPT_ENV_PATTERN,
    SshAcceptEnvSetupResult,
    ensure_local_ssh_accept_env,
)
from atlassian_cli.config.writer import (
    ConfigWriteError,
    product_config_exists,
    write_product_configs,
    write_product_tables,
)

DEFAULT_CONFIG_FILE = Path("~/.config/atlassian-cli/config.toml").expanduser()


def init_command(
    product: Product | None = typer.Argument(None),
    config_file: Path = typer.Option(
        DEFAULT_CONFIG_FILE,
        "--config-file",
        help="Path to config.toml.",
    ),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    env_template: bool = typer.Option(False, "--env-template"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Create or update atlassian-cli config."""
    products = [product] if product is not None else list(Product)
    updates: dict[Product, ProductConfig] = {}
    template_updates: dict[Product, dict[str, Any]] = {}
    force_products: set[Product] = set()

    for selected_product in products:
        if product is None and not typer.confirm(
            f"Configure {selected_product.value}?",
            default=True,
        ):
            continue

        exists = product_config_exists(config_file, selected_product)
        if not force and exists and not _confirm_overwrite(selected_product):
            typer.echo(f"Skipped [{selected_product.value}].")
            continue
        if force or exists:
            force_products.add(selected_product)

        if env_template:
            template_updates[selected_product] = _build_env_template_table(selected_product)
        else:
            updates[selected_product] = _build_product_config(
                deployment=deployment,
                url=url,
                auth=auth,
                username=username,
                password=password,
                token=token,
            )

    if not updates and not template_updates:
        if product is None:
            typer.echo("No product config changed.")
        return

    try:
        if env_template:
            write_product_tables(
                config_file,
                template_updates,
                force_products=force_products,
            )
        else:
            write_product_configs(config_file, updates, force_products=force_products)
    except ConfigWriteError as exc:
        raise typer.BadParameter(str(exc)) from exc

    for selected_product in template_updates or updates:
        typer.echo(f"Wrote [{selected_product.value}] to {config_file}")
    if env_template:
        _emit_ssh_accept_env_setup_message(ensure_local_ssh_accept_env())


def _confirm_overwrite(product: Product) -> bool:
    try:
        return typer.confirm(f"[{product.value}] already exists. Overwrite?", default=False)
    except click.Abort as exc:
        raise typer.BadParameter(
            f"[{product.value}] already exists. Use --force to overwrite it."
        ) from exc


def _build_product_config(
    *,
    deployment: Deployment | None,
    url: str | None,
    auth: AuthMode | None,
    username: str | None,
    password: str | None,
    token: str | None,
) -> ProductConfig:
    resolved_deployment = deployment or _prompt_enum("Deployment", Deployment, "--deployment")
    resolved_url = url or _prompt_value("URL", "--url")
    resolved_auth = auth or _prompt_enum("Auth", AuthMode, "--auth")

    resolved_username = username
    resolved_password = password
    resolved_token = token
    if resolved_auth is AuthMode.BASIC:
        resolved_username = resolved_username or _prompt_value("Username", "--username")
        if resolved_password is None and resolved_token is None:
            resolved_token = _prompt_value(
                "Token/password",
                "--token or --password",
                hide_input=True,
            )
    elif resolved_token is None:
        resolved_token = _prompt_value("Token", "--token", hide_input=True)

    return ProductConfig(
        deployment=resolved_deployment,
        url=resolved_url,
        auth=resolved_auth,
        username=resolved_username if resolved_auth is AuthMode.BASIC else None,
        password=resolved_password if resolved_auth is AuthMode.BASIC else None,
        token=resolved_token,
    )


def _build_env_template_table(product: Product) -> dict[str, Any]:
    prefix = f"ATLASSIAN_{product.value.upper()}"
    return {
        "deployment": f"${{{prefix}_DEPLOYMENT}}",
        "url": f"${{{prefix}_URL}}",
        "auth": f"${{{prefix}_AUTH}}",
        "username": f"${{{prefix}_USERNAME}}",
        "token": f"${{{prefix}_TOKEN}}",
    }


def _emit_ssh_accept_env_setup_message(result: SshAcceptEnvSetupResult) -> None:
    if result.status == "updated":
        typer.echo(
            f"Configured local sshd AcceptEnv {ATLASSIAN_ACCEPT_ENV_PATTERN} in {result.path}"
        )
        if result.reloaded:
            typer.echo("Reloaded sshd to apply it.")
        elif result.reload_command:
            typer.echo(f"Reload sshd to apply it: {result.reload_command}")
        return

    if result.status == "permission_denied":
        typer.echo(
            "Could not update local sshd AcceptEnv automatically. "
            f"Add AcceptEnv {ATLASSIAN_ACCEPT_ENV_PATTERN} to {result.path}.",
            err=True,
        )
        if result.reload_command:
            typer.echo(f"Reload sshd to apply it: {result.reload_command}", err=True)
        return

    if result.status == "write_failed":
        typer.echo(
            "Could not update local sshd AcceptEnv automatically. "
            f"{result.error or 'Unknown error.'}",
            err=True,
        )
        if result.reload_command:
            typer.echo(f"Reload sshd to apply it: {result.reload_command}", err=True)


def _prompt_enum(label: str, enum_type, option_name: str):
    options = "/".join(item.value for item in enum_type)
    value = _prompt_value(f"{label} ({options})", option_name)
    try:
        return enum_type(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid {label.lower()}: {value}") from exc


def _prompt_value(label: str, option_name: str, *, hide_input: bool = False) -> str:
    try:
        return typer.prompt(label, hide_input=hide_input)
    except click.Abort as exc:
        raise typer.BadParameter(
            f"Missing required option for non-interactive init: {option_name}"
        ) from exc
