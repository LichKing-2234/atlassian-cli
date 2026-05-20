from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.config.header_substitution import resolve_header_map
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
    url = overrides.url or profile.url
    username = overrides.username or profile.username
    password = overrides.password or profile.password
    token = overrides.token or profile.token
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
    headers = {
        **config_headers,
        **profile_headers,
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
