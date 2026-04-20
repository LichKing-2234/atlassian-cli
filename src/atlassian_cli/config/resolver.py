from atlassian_cli.auth.headers import collect_env_headers
from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.core.context import ExecutionContext


def resolve_runtime_context(*, profile, env: dict[str, str], overrides):
    product = overrides.product or profile.product
    deployment = overrides.deployment or profile.deployment
    url = overrides.url or env.get("ATLASSIAN_URL") or profile.url
    username = overrides.username or env.get("ATLASSIAN_USERNAME") or profile.username
    password = overrides.password or env.get("ATLASSIAN_PASSWORD") or profile.password
    token = overrides.token or env.get("ATLASSIAN_TOKEN") or profile.token
    auth = overrides.auth or profile.auth
    env_headers = collect_env_headers(env)
    headers = {**env_headers, **overrides.headers}
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
