from __future__ import annotations

from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequestComment


class PullRequestCommentService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> dict:
        comments = [
            BitbucketPullRequestComment.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_pull_request_comments(
                project_key,
                repo_slug,
                pr_id,
                start=start,
                limit=limit,
            )
        ]
        return {"results": comments, "start_at": start, "max_results": limit}

    def list_raw(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> list[dict]:
        return self.provider.list_pull_request_comments(
            project_key,
            repo_slug,
            pr_id,
            start=start,
            limit=limit,
        )

    def get(self, project_key: str, repo_slug: str, pr_id: int, comment_id: str) -> dict:
        return BitbucketPullRequestComment.from_api_response(
            self.provider.get_pull_request_comment(project_key, repo_slug, pr_id, comment_id)
        ).to_simplified_dict()

    def get_raw(self, project_key: str, repo_slug: str, pr_id: int, comment_id: str) -> dict:
        return self.provider.get_pull_request_comment(project_key, repo_slug, pr_id, comment_id)

    def add(self, project_key: str, repo_slug: str, pr_id: int, text: str) -> dict:
        return BitbucketPullRequestComment.from_api_response(
            self.provider.add_pull_request_comment(project_key, repo_slug, pr_id, text)
        ).to_simplified_dict()

    def add_raw(self, project_key: str, repo_slug: str, pr_id: int, text: str) -> dict:
        return self.provider.add_pull_request_comment(project_key, repo_slug, pr_id, text)

    def reply(
        self, project_key: str, repo_slug: str, pr_id: int, parent_id: str, text: str
    ) -> dict:
        return BitbucketPullRequestComment.from_api_response(
            self.provider.add_pull_request_comment(
                project_key,
                repo_slug,
                pr_id,
                text,
                parent_id=parent_id,
            )
        ).to_simplified_dict()

    def reply_raw(
        self, project_key: str, repo_slug: str, pr_id: int, parent_id: str, text: str
    ) -> dict:
        return self.provider.add_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            text,
            parent_id=parent_id,
        )

    def edit(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        text: str,
        *,
        version: int,
    ) -> dict:
        return BitbucketPullRequestComment.from_api_response(
            self.provider.update_pull_request_comment(
                project_key,
                repo_slug,
                pr_id,
                comment_id,
                text,
                version=version,
            )
        ).to_simplified_dict()

    def edit_raw(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        text: str,
        *,
        version: int,
    ) -> dict:
        return self.provider.update_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            text,
            version=version,
        )

    def delete(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        *,
        version: int,
    ) -> dict:
        self.provider.delete_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            version=version,
        )
        return {"id": comment_id, "deleted": True}

    def delete_raw(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        *,
        version: int,
    ) -> dict:
        result = self.provider.delete_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            version=version,
        )
        return result or {}
