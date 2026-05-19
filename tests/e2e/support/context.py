import os

from atlassian_cli.config.env_interpolation import resolve_active_product_input
from atlassian_cli.config.loader import load_raw_config_data
from atlassian_cli.config.models import Product, ProductConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.products.factory import build_provider
from tests.e2e.support.env import LiveEnv


def build_live_context(product: Product, live_env: LiveEnv):
    raw_config = load_raw_config_data(live_env.config_file)
    resolved_input = resolve_active_product_input(
        raw_config,
        product=product,
        env=dict(os.environ),
    )
    if not resolved_input.product_data:
        raise AssertionError(f"missing [{product.value}] config in {live_env.config_file}")
    profile = ProductConfig(
        **resolved_input.product_data,
        headers=resolved_input.product_headers,
    ).to_profile_config(product=product, name=product.value)
    return resolve_runtime_context(
        profile=profile,
        env=dict(os.environ),
        default_headers=resolved_input.default_headers,
        overrides=RuntimeOverrides(product=product, output="json"),
    )


def build_live_provider(product: Product, live_env: LiveEnv):
    return build_provider(build_live_context(product, live_env))
