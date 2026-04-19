from atlassian_cli.config.models import Deployment, Product
from atlassian_cli.core.errors import UnsupportedError
from atlassian_cli.products.bitbucket.providers.server import BitbucketServerProvider
from atlassian_cli.products.confluence.providers.server import ConfluenceServerProvider
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def build_provider(context):
    if context.deployment is Deployment.CLOUD:
        raise UnsupportedError("Cloud support is not available in v1")

    if context.product is Product.JIRA:
        return JiraServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
        )
    if context.product is Product.CONFLUENCE:
        return ConfluenceServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
        )
    if context.product is Product.BITBUCKET:
        return BitbucketServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
        )
    raise UnsupportedError(f"Unsupported product: {context.product}")
