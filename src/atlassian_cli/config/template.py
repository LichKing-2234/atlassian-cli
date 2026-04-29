from pathlib import Path

DEFAULT_CONFIG_TEMPLATE = """[headers]
# accessToken = "$(example-oauth token)"

[jira]
# deployment = "server"
# url = "https://jira.example.com"
# auth = "basic"
# username = "example-user"
# token = "secret"

[jira.headers]
# accessToken = "$(example-oauth token)"

[confluence]
# deployment = "dc"
# url = "https://confluence.example.com"
# auth = "pat"
# token = "secret"

[confluence.headers]
# accessToken = "$(example-oauth token)"

[bitbucket]
# deployment = "dc"
# url = "https://bitbucket.example.com"
# auth = "pat"
# token = "secret"

[bitbucket.headers]
# accessToken = "$(example-oauth token)"
"""


def ensure_default_config(path: Path, *, default_path: Path) -> bool:
    if path != default_path or path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE)
    return True
