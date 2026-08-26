JIRA_VERSION = "7.11.0"
JIRA_BUILD = "711000"
CONFLUENCE_VERSION = "6.12.4"


def assert_jira_fixed_version(provider) -> None:
    info = provider.client.get_server_info()
    actual = (
        str(info.get("version")),
        str(info.get("buildNumber")),
        str(info.get("deploymentType")),
    )
    expected = (JIRA_VERSION, JIRA_BUILD, "Server")
    if actual != expected:
        raise AssertionError(
            f"expected Jira {JIRA_VERSION} build {JIRA_BUILD} Server; "
            f"got version {actual[0]} build {actual[1]} {actual[2]}"
        )


def assert_confluence_fixed_version(provider) -> None:
    # Confluence 6.12.4 has no REST system-info resource; its application manifest owns this.
    manifest = provider.client.get("rest/applinks/1.0/manifest")
    product = str(manifest.get("typeId")) if isinstance(manifest, dict) else "unknown"
    version = str(manifest.get("version")) if isinstance(manifest, dict) else "unknown"
    if (product, version) != ("confluence", CONFLUENCE_VERSION):
        raise AssertionError(
            f"expected Confluence {CONFLUENCE_VERSION}; got {product} version {version}"
        )
