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


def test_profile_headers_override_top_level_headers() -> None:
    profile = ProfileConfig(
        name="prod-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        auth=AuthMode.PAT,
        token="legacy-token",
        headers={
            "accessToken": "$(example-oauth token --profile prod-bitbucket)",
            "X-Request-Source": "profile-default",
        },
    )

    context = resolve_runtime_context(
        profile=profile,
        env={},
        default_headers={
            "X-Request-Source": "top-level-default",
            "X-Trace": "top-level-trace",
        },
        overrides=RuntimeOverrides(url="https://bitbucket.example.com"),
        command_runner=lambda command: "profile-token",
    )

    assert context.auth.headers == {
        "accessToken": "profile-token",
        "X-Request-Source": "profile-default",
        "X-Trace": "top-level-trace",
    }


def test_flag_headers_override_config_headers() -> None:
    profile = ProfileConfig(
        name="prod-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        auth=AuthMode.PAT,
        token="legacy-token",
        headers={"accessToken": "$(example-oauth token)"},
    )

    context = resolve_runtime_context(
        profile=profile,
        env={},
        default_headers={"X-Trace": "top-level-trace"},
        overrides=RuntimeOverrides(
            url="https://bitbucket.example.com",
            headers={"accessToken": "flag-token"},
        ),
        command_runner=lambda command: "profile-token",
    )

    assert context.auth.headers == {
        "accessToken": "flag-token",
        "X-Trace": "top-level-trace",
    }
