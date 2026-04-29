import os

from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Product, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.products.factory import build_provider
from tests.e2e.support.env import LiveEnv


def build_live_context(product: Product, live_env: LiveEnv):
    config = load_config(live_env.config_file)
    product_config = config.product_config(product)
    if product_config is None:
        raise AssertionError(f"missing [{product.value}] config in {live_env.config_file}")
    profile = product_config.to_profile_config(product=product, name=product.value)
    return resolve_runtime_context(
        profile=profile,
        env=dict(os.environ),
        default_headers=config.headers,
        overrides=RuntimeOverrides(product=product, output="json"),
    )


def build_live_provider(product: Product, live_env: LiveEnv):
    return build_provider(build_live_context(product, live_env))
