from atlassian_cli.products.confluence.providers.base import ConfluenceProvider


class RestrictionService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    @staticmethod
    def _subjects(operation: object) -> dict[str, list[str]]:
        op_data = operation if isinstance(operation, dict) else {}
        restrictions = op_data.get("restrictions", {})
        if not isinstance(restrictions, dict):
            restrictions = {}

        users: list[str] = []
        user_data = restrictions.get("user", {})
        if isinstance(user_data, dict):
            for item in user_data.get("results", []):
                if not isinstance(item, dict):
                    continue
                identifier = item.get("accountId") or item.get("username") or item.get("name")
                if identifier:
                    users.append(str(identifier))

        groups: list[str] = []
        group_data = restrictions.get("group", {})
        if isinstance(group_data, dict):
            for item in group_data.get("results", []):
                if isinstance(item, dict) and item.get("name"):
                    groups.append(str(item["name"]))

        return {"users": users, "groups": groups}

    def get(self, page_id: str) -> dict:
        raw = self.provider.get_page_restrictions(page_id)
        return {
            "read": self._subjects(raw.get("read")),
            "update": self._subjects(raw.get("update")),
        }

    def get_raw(self, page_id: str) -> dict:
        return self.provider.get_page_restrictions(page_id)
