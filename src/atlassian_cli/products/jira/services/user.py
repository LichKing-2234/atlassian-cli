class UserService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, username: str) -> dict:
        return self.provider.get_user(username)

    def search(self, query: str) -> list[dict]:
        return self.provider.search_users(query)
