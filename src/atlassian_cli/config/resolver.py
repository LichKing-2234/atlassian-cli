from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.config.header_substitution import resolve_header_map
from atlassian_cli.core.context import ExecutionContext


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
    username = overrides.username or env.get("ATLASSIAN_USERNAME") or profile.username
    password = overrides.password or env.get("ATLASSIAN_PASSWORD") or profile.password
    token = overrides.token or env.get("ATLASSIAN_TOKEN") or profile.token
    auth = overrides.auth or profile.auth
    config_headers = resolve_header_map(
        default_headers or {},
        source="[headers]",
        runner=command_runner,
    )
    profile_headers = resolve_header_map(
        profile.headers,
        source=f"[profiles.{profile.name}.headers]",
        runner=command_runner,
    )
    headers = {**config_headers, **profile_headers, **overrides.headers}
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
