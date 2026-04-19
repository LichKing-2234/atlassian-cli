from atlassian_cli.core.errors import UnsupportedError


class BitbucketCloudProvider:
    def __init__(self) -> None:
        raise UnsupportedError("Cloud support is not available in v1")
