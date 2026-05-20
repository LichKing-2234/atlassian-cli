import pytest

from atlassian_cli.config.env_interpolation import (
    interpolate_env_value,
    resolve_active_product_input,
)
from atlassian_cli.config.models import Product
from atlassian_cli.core.errors import ConfigError


def test_resolve_active_product_input_interpolates_product_fields_and_headers() -> None:
    resolved = resolve_active_product_input(
        {
            "headers": {
                "X-Request-Source": "${ATLASSIAN_SOURCE}",
            },
            "jira": {
                "deployment": "${ATLASSIAN_DEPLOYMENT}",
                "url": "https://${ATLASSIAN_HOST}",
                "auth": "${ATLASSIAN_AUTH}",
                "username": "${ATLASSIAN_USER}",
                "password": "${ATLASSIAN_PASSWORD}",
                "headers": {
                    "Authorization": "Bearer ${ATLASSIAN_TOKEN}",
                    "X-Request-Source": "$(example-token-helper --host ${ATLASSIAN_HOST})",
                },
            },
        },
        product=Product.JIRA,
        env={
            "ATLASSIAN_DEPLOYMENT": "server",
            "ATLASSIAN_AUTH": "basic",
            "ATLASSIAN_SOURCE": "config-default",
            "ATLASSIAN_HOST": "jira.example.com",
            "ATLASSIAN_USER": "example-user",
            "ATLASSIAN_PASSWORD": "secret",
            "ATLASSIAN_TOKEN": "example-token",
        },
    )

    assert resolved.product_data == {
        "deployment": "server",
        "url": "https://jira.example.com",
        "auth": "basic",
        "username": "example-user",
        "password": "secret",
    }
    assert resolved.default_headers == {
        "X-Request-Source": "config-default",
    }
    assert resolved.product_headers == {
        "Authorization": "Bearer example-token",
        "X-Request-Source": "$(example-token-helper --host jira.example.com)",
    }


def test_resolve_active_product_input_only_resolves_active_product() -> None:
    resolved = resolve_active_product_input(
        {
            "jira": {
                "url": "https://jira.example.com",
            },
            "confluence": {
                "url": "https://${MISSING_CONFLUENCE_HOST}",
            },
        },
        product=Product.JIRA,
        env={},
    )

    assert resolved.product_data == {
        "url": "https://jira.example.com",
    }
    assert resolved.default_headers == {}
    assert resolved.product_headers == {}


def test_resolve_active_product_input_reports_missing_variable_for_product_field() -> None:
    with pytest.raises(
        ConfigError,
        match=r"Missing environment variable ATLASSIAN_TOKEN for \[jira\]\.token",
    ):
        resolve_active_product_input(
            {
                "jira": {
                    "token": "${ATLASSIAN_TOKEN}",
                },
            },
            product=Product.JIRA,
            env={},
        )


def test_resolve_active_product_input_reports_missing_variable_for_product_header() -> None:
    with pytest.raises(
        ConfigError,
        match=r"Missing environment variable ATLASSIAN_TOKEN for \[jira\.headers\]\.Authorization",
    ):
        resolve_active_product_input(
            {
                "jira": {
                    "headers": {
                        "Authorization": "Bearer ${ATLASSIAN_TOKEN}",
                    },
                },
            },
            product=Product.JIRA,
            env={},
        )


def test_interpolate_env_value_keeps_surrounding_text_intact() -> None:
    assert (
        interpolate_env_value(
            "$(example-token-helper --host ${ATLASSIAN_HOST})",
            source="[headers].X-Request-Source",
            env={"ATLASSIAN_HOST": "jira.example.com"},
        )
        == "$(example-token-helper --host jira.example.com)"
    )


@pytest.mark.parametrize(
    ("value", "source"),
    [
        ("${ATLASSIAN_TOKEN", r"\[headers\]\.Authorization"),
        ("${}", r"\[headers\]\.Authorization"),
        ("${atl-token}", r"\[headers\]\.Authorization"),
    ],
)
def test_resolve_active_product_input_rejects_malformed_interpolation(
    value: str,
    source: str,
) -> None:
    with pytest.raises(
        ConfigError,
        match=rf"Malformed environment interpolation in {source}",
    ):
        resolve_active_product_input(
            {
                "headers": {
                    "Authorization": value,
                },
            },
            product=Product.JIRA,
            env={},
        )


@pytest.mark.parametrize(
    ("raw_config", "source"),
    [
        ({"headers": "not-a-table"}, r"\[headers\]"),
        ({"jira": "not-a-table"}, r"\[jira\]"),
        ({"jira": {"headers": "not-a-table"}}, r"\[jira\.headers\]"),
    ],
)
def test_resolve_active_product_input_reports_bad_table_shape_with_source(
    raw_config: dict[str, object],
    source: str,
) -> None:
    with pytest.raises(
        ConfigError,
        match=rf"Invalid config\.toml configuration: {source} must be a TOML table",
    ):
        resolve_active_product_input(
            raw_config,
            product=Product.JIRA,
            env={},
        )


def test_resolve_active_product_input_rejects_non_string_product_fields() -> None:
    with pytest.raises(
        ConfigError,
        match=r"Invalid config\.toml configuration: \[jira\]\.token must be a string",
    ):
        resolve_active_product_input(
            {
                "jira": {
                    "token": 42,
                },
            },
            product=Product.JIRA,
            env={},
        )
