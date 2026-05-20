from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.config.header_substitution import resolve_header_map
from atlassian_cli.config.models import Product
from atlassian_cli.core.context import ExecutionContext
from atlassian_cli.core.errors import ConfigError


class ConfigHeaderResolutionError(ConfigError):
    pass


def _header_name_from_env_suffix(suffix: str) -> str:
    parts = [part for part in suffix.split("_") if part]
    if not parts:
        raise ConfigError("Header environment variable name is missing a header suffix")
    if parts[0] == "X" and len(parts) > 1:
        return "-".join(["X", *[part.title() for part in parts[1:]]])
    if len(parts) == 1:
        return parts[0].title()
    return parts[0].lower() + "".join(part.title() for part in parts[1:])


def _headers_from_env(env: dict[str, str], *, prefix: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in env.items():
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :]
        header_name = _header_name_from_env_suffix(suffix)
        headers[header_name] = value
    return headers


def _product_env_value(env: dict[str, str], product: Product, suffix: str) -> str | None:
    return env.get(f"ATLASSIAN_{product.value.upper()}_{suffix}")


def resolve_runtime_context(
    *,
    profile,
    env: dict[str, str],
    default_headers: dict[str, str] | None = None,
    overrides,
    command_runner=None,
):
    product = overrides.product or profile.product
    deployment = overrides.deployment or profile.deployment
    url = overrides.url or env.get("ATLASSIAN_URL") or profile.url
    username = (
        overrides.username
        or _product_env_value(env, product, "USERNAME")
        or env.get("ATLASSIAN_USERNAME")
        or profile.username
    )
    password = (
        overrides.password
        or _product_env_value(env, product, "PASSWORD")
        or env.get("ATLASSIAN_PASSWORD")
        or profile.password
    )
    token = (
        overrides.token
        or _product_env_value(env, product, "TOKEN")
        or env.get("ATLASSIAN_TOKEN")
        or profile.token
    )
    auth = overrides.auth or profile.auth
    try:
        config_headers = resolve_header_map(
            default_headers or {},
            source="[headers]",
            runner=command_runner,
        )
    except ConfigError as exc:
        raise ConfigHeaderResolutionError(str(exc)) from exc
    profile_headers = resolve_header_map(
        profile.headers,
        source=f"[{product.value}.headers]",
        runner=command_runner,
    )
    env_headers = _headers_from_env(env, prefix="ATLASSIAN_HEADER_")
    env_product_headers = _headers_from_env(
        env,
        prefix=f"ATLASSIAN_{product.value.upper()}_HEADER_",
    )
    headers = {
        **config_headers,
        **profile_headers,
        **env_headers,
        **env_product_headers,
        **overrides.headers,
    }
    return ExecutionContext(
        profile=overrides.profile or profile.name,
        product=product,
        deployment=deployment,
        url=url,
        output=overrides.output,
        auth=resolve_auth(
            auth=auth,
            username=username,
            password=password,
            token=token,
            headers=headers,
        ),
    )
