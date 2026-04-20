from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context


def test_flag_values_override_env_and_profile() -> None:
    profile = ProfileConfig(
        name="prod-jira",
        product=Product.JIRA,
        deployment=Deployment.SERVER,
        url="https://jira.profile.local",
        auth=AuthMode.BASIC,
        username="profile-user",
        token="profile-token",
    )
    env = {
        "ATLASSIAN_URL": "https://jira.env.local",
        "ATLASSIAN_USERNAME": "env-user",
    }
    overrides = RuntimeOverrides(
        url="https://jira.flag.local",
        username="flag-user",
        profile="prod-jira",
    )

    context = resolve_runtime_context(profile=profile, env=env, overrides=overrides)

    assert context.url == "https://jira.flag.local"
    assert context.profile == "prod-jira"
    assert context.auth.username == "flag-user"
    assert context.product is Product.JIRA


def test_flag_headers_override_environment_headers() -> None:
    profile = ProfileConfig(
        name="prod-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        auth=AuthMode.PAT,
        token="legacy-token",
    )
    env = {
        "ATLASSIAN_HEADER_AUTHORIZATION": "Bearer env-token",
        "ATLASSIAN_HEADER_X_REQUEST_SOURCE": "agora-oauth",
    }
    overrides = RuntimeOverrides(
        url="https://bitbucket.example.com",
        headers={"Authorization": "Bearer flag-token"},
    )

    context = resolve_runtime_context(profile=profile, env=env, overrides=overrides)

    assert context.auth.headers == {
        "Authorization": "Bearer flag-token",
        "X-Request-Source": "agora-oauth",
    }
