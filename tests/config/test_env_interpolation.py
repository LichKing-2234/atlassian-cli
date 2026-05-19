import pytest

from atlassian_cli.config.env_interpolation import resolve_active_product_input
from atlassian_cli.config.models import Product
from atlassian_cli.core.errors import ConfigError


def test_resolve_active_product_input_interpolates_product_fields_and_headers() -> None:
    resolved = resolve_active_product_input(
        {
            "headers": {
                "X-Request-Source": "${ATLASSIAN_SOURCE}",
            },
            "jira": {
                "deployment": "server",
                "url": "https://${ATLASSIAN_HOST}",
                "auth": "basic",
                "username": "${ATLASSIAN_USER}",
                "password": "${ATLASSIAN_PASSWORD}",
                "headers": {
                    "Authorization": "Bearer ${ATLASSIAN_TOKEN}",
                },
            },
        },
        product=Product.JIRA,
        env={
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


def test_resolve_active_product_input_reports_missing_variable_with_source_path() -> None:
    with pytest.raises(
        ConfigError,
        match=r"Missing environment variable 'ATLASSIAN_TOKEN' for \[jira\]\.headers\.Authorization",
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


def test_resolve_active_product_input_rejects_malformed_interpolation() -> None:
    with pytest.raises(
        ConfigError,
        match=r"Malformed environment interpolation in \[headers\]\.Authorization",
    ):
        resolve_active_product_input(
            {
                "headers": {
                    "Authorization": "${atl-token}",
                },
            },
            product=Product.JIRA,
            env={},
        )
