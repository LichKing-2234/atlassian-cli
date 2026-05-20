from pathlib import Path

DEFAULT_CONFIG_TEMPLATE = """[headers]
# X-Request-Source = "${ATLASSIAN_HEADER_X_REQUEST_SOURCE}"

[jira]
# deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
# url = "${ATLASSIAN_JIRA_URL}"
# auth = "${ATLASSIAN_JIRA_AUTH}"
# username = "${ATLASSIAN_JIRA_USERNAME}"
# password = "${ATLASSIAN_JIRA_PASSWORD}"
# token = "${ATLASSIAN_JIRA_TOKEN}"

[jira.headers]
# Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"
# X-Request-Source = "example-cli"

[confluence]
# deployment = "${ATLASSIAN_CONFLUENCE_DEPLOYMENT}"
# url = "${ATLASSIAN_CONFLUENCE_URL}"
# auth = "${ATLASSIAN_CONFLUENCE_AUTH}"
# username = "${ATLASSIAN_CONFLUENCE_USERNAME}"
# password = "${ATLASSIAN_CONFLUENCE_PASSWORD}"
# token = "${ATLASSIAN_CONFLUENCE_TOKEN}"

[confluence.headers]
# Authorization = "${ATLASSIAN_CONFLUENCE_HEADER_AUTHORIZATION}"
# X-Request-Source = "example-cli"

[bitbucket]
# deployment = "${ATLASSIAN_BITBUCKET_DEPLOYMENT}"
# url = "${ATLASSIAN_BITBUCKET_URL}"
# auth = "${ATLASSIAN_BITBUCKET_AUTH}"
# username = "${ATLASSIAN_BITBUCKET_USERNAME}"
# password = "${ATLASSIAN_BITBUCKET_PASSWORD}"
# token = "${ATLASSIAN_BITBUCKET_TOKEN}"

[bitbucket.headers]
# Authorization = "${ATLASSIAN_BITBUCKET_HEADER_AUTHORIZATION}"
# X-Request-Source = "example-cli"
"""


def ensure_default_config(path: Path, *, default_path: Path) -> bool:
    if path != default_path or path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE)
    return True
