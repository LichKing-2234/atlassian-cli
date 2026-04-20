from atlassian_cli.products.bitbucket.schemas import (
    BitbucketNamedRef,
    BitbucketPullRequest,
    BitbucketReviewer,
)


class PullRequestService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, state: str) -> "list[dict]":
        return [
            self._normalize_pull_request(item)
            for item in self.provider.list_pull_requests(project_key, repo_slug, state)
        ]

    def list_raw(self, project_key: str, repo_slug: str, state: str) -> "list[dict]":
        return self.provider.list_pull_requests(project_key, repo_slug, state)

    def get(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self._normalize_pull_request(
            self.provider.get_pull_request(project_key, repo_slug, pr_id)
        )

    def get_raw(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.get_pull_request(project_key, repo_slug, pr_id)

    def create(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.provider.create_pull_request(project_key, repo_slug, payload)

    def merge(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.merge_pull_request(project_key, repo_slug, pr_id)

    def _normalize_pull_request(self, raw: dict) -> dict:
        pr = BitbucketPullRequest(
            id=raw["id"],
            title=raw["title"],
            state=raw["state"],
            author={
                "display_name": ((raw.get("author") or {}).get("user") or {}).get("displayName")
            },
            from_ref=BitbucketNamedRef(display_id=(raw.get("fromRef") or {}).get("displayId")),
            to_ref=BitbucketNamedRef(display_id=(raw.get("toRef") or {}).get("displayId")),
            reviewers=[
                BitbucketReviewer(
                    display_name=((item.get("user") or {}).get("displayName")),
                    approved=bool(item.get("approved")),
                )
                for item in raw.get("reviewers") or []
            ],
        )
        return pr.model_dump(exclude_none=True)
