# Bitbucket PR Comments and Build Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bitbucket pull request comment management and build status lookup without slowing down `bitbucket pr get`.

**Architecture:** Keep the existing `command -> service -> provider -> schema -> renderer` flow. Add focused schemas and services for comments and build statuses, then wire resource-oriented Typer commands under `bitbucket pr comment`, `bitbucket pr build-status`, and `bitbucket commit build-status`.

**Tech Stack:** Python 3.12+, Typer, pydantic, atlassian-python-api, pytest, ruff.

---

## File Structure

- Modify `src/atlassian_cli/products/bitbucket/schemas.py`: add comment and build-status models.
- Modify `src/atlassian_cli/products/bitbucket/providers/base.py`: extend the provider protocol.
- Modify `src/atlassian_cli/products/bitbucket/providers/server.py`: add Bitbucket Server/Data Center API wrappers.
- Create `src/atlassian_cli/products/bitbucket/services/pr_comment.py`: normalize pull request comment workflows.
- Create `src/atlassian_cli/products/bitbucket/services/build_status.py`: normalize commit and pull request build status workflows.
- Create `src/atlassian_cli/products/bitbucket/commands/pr_comment.py`: expose `bitbucket pr comment` commands.
- Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`: register `comment` and add `build-status`.
- Create `src/atlassian_cli/products/bitbucket/commands/commit.py`: expose `bitbucket commit build-status`.
- Modify `src/atlassian_cli/cli.py`: register the Bitbucket commit command group.
- Modify `tests/products/bitbucket/test_schemas.py`: schema coverage.
- Modify `tests/products/bitbucket/test_provider.py`: provider coverage.
- Create `tests/products/bitbucket/test_pr_comment_service.py`: comment service coverage.
- Create `tests/products/bitbucket/test_build_status_service.py`: build status service coverage.
- Create `tests/products/bitbucket/test_pr_comment_command.py`: comment command coverage.
- Create `tests/products/bitbucket/test_build_status_command.py`: build status command coverage.
- Modify `tests/e2e/coverage_manifest.py`: register every new leaf command.
- Modify `tests/e2e/test_bitbucket_live.py`: extend live PR round-trip coverage.
- Modify `README.md`: add public placeholder examples.

### Task 1: Add Bitbucket Comment and Build Status Schemas

**Files:**
- Modify: `tests/products/bitbucket/test_schemas.py`
- Modify: `src/atlassian_cli/products/bitbucket/schemas.py`

- [ ] **Step 1: Write failing schema tests**

Append these tests to `tests/products/bitbucket/test_schemas.py`:

```python
from atlassian_cli.products.bitbucket.schemas import (
    BitbucketBuildStatus,
    BitbucketPullRequestBuildStatusSummary,
    BitbucketPullRequestComment,
)


def test_bitbucket_pr_comment_schema_normalizes_parent_and_anchor() -> None:
    comment = BitbucketPullRequestComment.from_api_response(
        {
            "id": 1001,
            "version": 3,
            "text": "example comment",
            "author": {"displayName": "Example Author", "name": "example-user-id"},
            "createdDate": 1704153600000,
            "updatedDate": 1704153600000,
            "parent": {"id": 1000},
            "anchor": {"path": "src/example.py", "line": 12, "lineType": "ADDED"},
        }
    )

    assert comment.to_simplified_dict() == {
        "id": "1001",
        "version": 3,
        "text": "example comment",
        "author": {"display_name": "Example Author", "name": "example-user-id"},
        "created_date": "1704153600000",
        "updated_date": "1704153600000",
        "parent": {"id": "1000"},
        "anchor": {"path": "src/example.py", "line": 12, "line_type": "ADDED"},
    }


def test_bitbucket_build_status_schema_normalizes_common_fields() -> None:
    status = BitbucketBuildStatus.from_api_response(
        {
            "key": "DEMO",
            "name": "Example build",
            "state": "SUCCESSFUL",
            "url": "https://bitbucket.example.com/build/DEMO",
            "description": "example response",
            "dateAdded": 1704153600000,
        }
    )

    assert status.to_simplified_dict() == {
        "key": "DEMO",
        "name": "Example build",
        "state": "SUCCESSFUL",
        "url": "https://bitbucket.example.com/build/DEMO",
        "description": "example response",
        "date_added": "1704153600000",
    }


def test_bitbucket_pr_build_status_summary_preserves_empty_commits() -> None:
    summary = BitbucketPullRequestBuildStatusSummary(
        pull_request={"id": 42, "project_key": "DEMO", "repo_slug": "example-repo"},
        overall_state="UNKNOWN",
        commits=[],
    )

    assert summary.to_simplified_dict() == {
        "pull_request": {"id": 42, "project_key": "DEMO", "repo_slug": "example-repo"},
        "overall_state": "UNKNOWN",
        "commits": [],
    }
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_schemas.py -v
```

Expected: FAIL with import errors for `BitbucketPullRequestComment`, `BitbucketBuildStatus`, and `BitbucketPullRequestBuildStatusSummary`.

- [ ] **Step 3: Add schema classes**

Append this code to `src/atlassian_cli/products/bitbucket/schemas.py` after `BitbucketPullRequest`:

```python
class BitbucketCommentAnchor(ApiModel):
    path: str | None = None
    line: int | None = None
    line_type: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketCommentAnchor":
        data = data or {}
        return cls(
            path=coerce_str(data.get("path")),
            line=data.get("line"),
            line_type=coerce_str(first_present(data.get("lineType"), data.get("line_type"))),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"path": self.path, "line": self.line, "line_type": self.line_type}
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketCommentParent(ApiModel):
    id: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketCommentParent":
        data = data or {}
        return cls(id=coerce_str(data.get("id")))

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id}
        return {key: value for key, value in payload.items() if value not in (None, "")}


class BitbucketPullRequestComment(ApiModel):
    id: str
    version: int | None = None
    text: str | None = None
    author: BitbucketUserRef | None = None
    created_date: str | None = None
    updated_date: str | None = None
    parent: BitbucketCommentParent | None = None
    anchor: BitbucketCommentAnchor | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketPullRequestComment":
        data = data or {}
        author_data = data.get("author") if isinstance(data.get("author"), dict) else {}
        if isinstance(author_data.get("user"), dict):
            author_data = author_data["user"]
        parent_data = data.get("parent") if isinstance(data.get("parent"), dict) else None
        anchor_data = data.get("anchor") if isinstance(data.get("anchor"), dict) else None
        return cls(
            id=str(data.get("id", "")),
            version=data.get("version"),
            text=coerce_str(data.get("text")),
            author=BitbucketUserRef.from_api_response(author_data) if author_data else None,
            created_date=coerce_str(first_present(data.get("createdDate"), data.get("created_date"))),
            updated_date=coerce_str(first_present(data.get("updatedDate"), data.get("updated_date"))),
            parent=BitbucketCommentParent.from_api_response(parent_data) if parent_data else None,
            anchor=BitbucketCommentAnchor.from_api_response(anchor_data) if anchor_data else None,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "version": self.version,
            "text": self.text,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
        }
        if self.author:
            payload["author"] = self.author.to_simplified_dict()
        if self.parent:
            payload["parent"] = self.parent.to_simplified_dict()
        if self.anchor:
            payload["anchor"] = self.anchor.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketBuildStatus(ApiModel):
    key: str | None = None
    name: str | None = None
    state: str | None = None
    url: str | None = None
    description: str | None = None
    date_added: str | None = None

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketBuildStatus":
        data = data or {}
        return cls(
            key=coerce_str(data.get("key")),
            name=coerce_str(data.get("name")),
            state=coerce_str(data.get("state")),
            url=coerce_str(data.get("url")),
            description=coerce_str(data.get("description")),
            date_added=coerce_str(first_present(data.get("dateAdded"), data.get("date_added"))),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "key": self.key,
            "name": self.name,
            "state": self.state,
            "url": self.url,
            "description": self.description,
            "date_added": self.date_added,
        }
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketCommitBuildStatusSummary(ApiModel):
    commit: str
    overall_state: str
    results: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketCommitBuildStatusSummary":
        data = data or {}
        return cls(
            commit=str(data.get("commit", "")),
            overall_state=str(data.get("overall_state", "UNKNOWN")),
            results=[item for item in data.get("results", []) if isinstance(item, dict)],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "commit": self.commit,
            "overall_state": self.overall_state,
            "results": self.results,
        }


class BitbucketPullRequestBuildStatusSummary(ApiModel):
    pull_request: dict[str, Any]
    overall_state: str
    commits: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any] | None, **kwargs: Any
    ) -> "BitbucketPullRequestBuildStatusSummary":
        data = data or {}
        return cls(
            pull_request=data.get("pull_request", {}),
            overall_state=str(data.get("overall_state", "UNKNOWN")),
            commits=[item for item in data.get("commits", []) if isinstance(item, dict)],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "pull_request": self.pull_request,
            "overall_state": self.overall_state,
            "commits": self.commits,
        }
```

- [ ] **Step 4: Run schema tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_schemas.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit schema work**

Run:

```bash
git add src/atlassian_cli/products/bitbucket/schemas.py tests/products/bitbucket/test_schemas.py
git commit -m "feat: add bitbucket workflow schemas"
```

### Task 2: Add Bitbucket Provider Methods

**Files:**
- Modify: `tests/products/bitbucket/test_provider.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`

- [ ] **Step 1: Write failing provider tests**

Append these tests to `tests/products/bitbucket/test_provider.py`:

```python
def test_bitbucket_provider_list_pull_request_comments_uses_comments_endpoint() -> None:
    calls = {}

    class FakeClient:
        def _url_pull_request_comments(self, project_key, repo_slug, pr_id):
            return f"rest/api/latest/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/comments"

        def get(self, url, params=None):
            calls["args"] = (url, params)
            return {"values": [{"id": 1001, "text": "example comment"}]}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_pull_request_comments("DEMO", "example-repo", 42, start=0, limit=25)

    assert result == [{"id": 1001, "text": "example comment"}]
    assert calls["args"] == (
        "rest/api/latest/projects/DEMO/repos/example-repo/pull-requests/42/comments",
        {"start": 0, "limit": 25},
    )


def test_bitbucket_provider_comment_methods_forward_to_sdk() -> None:
    calls = {}

    class FakeClient:
        def get_pull_request_comment(self, project_key, repo_slug, pr_id, comment_id):
            calls["get"] = (project_key, repo_slug, pr_id, comment_id)
            return {"id": comment_id, "text": "example comment"}

        def add_pull_request_comment(self, project_key, repo_slug, pr_id, text, parent_id=None):
            calls["add"] = (project_key, repo_slug, pr_id, text, parent_id)
            return {"id": 1001, "text": text}

        def update_pull_request_comment(
            self, project_key, repo_slug, pr_id, comment_id, comment, comment_version
        ):
            calls["update"] = (project_key, repo_slug, pr_id, comment_id, comment, comment_version)
            return {"id": comment_id, "version": comment_version + 1, "text": comment}

        def delete_pull_request_comment(
            self, project_key, repo_slug, pr_id, comment_id, comment_version
        ):
            calls["delete"] = (project_key, repo_slug, pr_id, comment_id, comment_version)
            return None

    provider = build_provider_with_client(FakeClient())

    assert provider.get_pull_request_comment("DEMO", "example-repo", 42, "1001")["id"] == "1001"
    assert provider.add_pull_request_comment("DEMO", "example-repo", 42, "example comment")["text"] == "example comment"
    assert provider.add_pull_request_comment("DEMO", "example-repo", 42, "example response", parent_id="1001")["text"] == "example response"
    assert provider.update_pull_request_comment("DEMO", "example-repo", 42, "1001", "example comment", version=3)["version"] == 4
    assert provider.delete_pull_request_comment("DEMO", "example-repo", 42, "1001", version=4) is None
    assert calls["get"] == ("DEMO", "example-repo", 42, "1001")
    assert calls["add"] == ("DEMO", "example-repo", 42, "example response", "1001")
    assert calls["update"] == ("DEMO", "example-repo", 42, "1001", "example comment", 3)
    assert calls["delete"] == ("DEMO", "example-repo", 42, "1001", 4)


def test_bitbucket_provider_build_status_methods_forward_to_sdk() -> None:
    calls = {}

    class FakeClient:
        def get_pull_requests_commits(self, project_key, repo_slug, pr_id, start=0, limit=None):
            calls["commits"] = (project_key, repo_slug, pr_id, start, limit)
            return {"values": [{"id": "abc123"}, {"id": "def456"}]}

        def get_associated_build_statuses(self, commit):
            calls["build"] = commit
            return {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]}

    provider = build_provider_with_client(FakeClient())

    commits = provider.list_pull_request_commits("DEMO", "example-repo", 42, start=0, limit=25)
    statuses = provider.get_associated_build_statuses("abc123")

    assert commits == [{"id": "abc123"}, {"id": "def456"}]
    assert statuses == {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]}
    assert calls["commits"] == ("DEMO", "example-repo", 42, 0, 25)
    assert calls["build"] == "abc123"
```

- [ ] **Step 2: Run provider tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py -v
```

Expected: FAIL with missing provider methods.

- [ ] **Step 3: Extend the provider protocol**

Add these methods to `src/atlassian_cli/products/bitbucket/providers/base.py` under the pull request methods:

```python
    def list_pull_request_comments(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        pass

    def get_pull_request_comment(
        self, project_key: str, repo_slug: str, pr_id: int, comment_id: str
    ) -> dict:
        pass

    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        parent_id: str | None = None,
    ) -> dict:
        pass

    def update_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        text: str,
        *,
        version: int,
    ) -> dict:
        pass

    def delete_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        *,
        version: int,
    ) -> dict | None:
        pass

    def list_pull_request_commits(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int | None,
    ) -> list[dict]:
        pass

    def get_associated_build_statuses(self, commit: str) -> dict:
        pass
```

- [ ] **Step 4: Implement provider methods**

Add these methods to `src/atlassian_cli/products/bitbucket/providers/server.py` after `get_pull_request_diff`:

```python
    def list_pull_request_comments(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        url = self.client._url_pull_request_comments(project_key, repo_slug, pr_id)
        return self._paged_items(
            self.client.get(url, params={"start": start, "limit": limit}),
            limit=limit,
        )

    def get_pull_request_comment(
        self, project_key: str, repo_slug: str, pr_id: int, comment_id: str
    ) -> dict:
        return self.client.get_pull_request_comment(project_key, repo_slug, pr_id, comment_id)

    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        parent_id: str | None = None,
    ) -> dict:
        return self.client.add_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            text,
            parent_id=parent_id,
        )

    def update_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        text: str,
        *,
        version: int,
    ) -> dict:
        return self.client.update_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            text,
            version,
        )

    def delete_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        *,
        version: int,
    ) -> dict | None:
        return self.client.delete_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            version,
        )

    def list_pull_request_commits(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int | None,
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_pull_requests_commits(
                project_key,
                repo_slug,
                pr_id,
                start=start,
                limit=limit,
            ),
            limit=limit,
        )

    def get_associated_build_statuses(self, commit: str) -> dict:
        return self.client.get_associated_build_statuses(commit)
```

- [ ] **Step 5: Run provider tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit provider work**

Run:

```bash
git add src/atlassian_cli/products/bitbucket/providers/base.py src/atlassian_cli/products/bitbucket/providers/server.py tests/products/bitbucket/test_provider.py
git commit -m "feat: add bitbucket workflow provider methods"
```

### Task 3: Add Pull Request Comment Service

**Files:**
- Create: `tests/products/bitbucket/test_pr_comment_service.py`
- Create: `src/atlassian_cli/products/bitbucket/services/pr_comment.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/products/bitbucket/test_pr_comment_service.py`:

```python
from atlassian_cli.products.bitbucket.services.pr_comment import PullRequestCommentService


class FakeCommentProvider:
    def __init__(self) -> None:
        self.calls = []

    def list_pull_request_comments(self, project_key, repo_slug, pr_id, *, start, limit):
        self.calls.append(("list", project_key, repo_slug, pr_id, start, limit))
        return [
            {
                "id": 1001,
                "version": 3,
                "text": "example comment",
                "author": {"displayName": "Example Author", "name": "example-user-id"},
            }
        ]

    def get_pull_request_comment(self, project_key, repo_slug, pr_id, comment_id):
        self.calls.append(("get", project_key, repo_slug, pr_id, comment_id))
        return {"id": comment_id, "version": 3, "text": "example comment"}

    def add_pull_request_comment(self, project_key, repo_slug, pr_id, text, *, parent_id=None):
        self.calls.append(("add", project_key, repo_slug, pr_id, text, parent_id))
        return {"id": 1002, "version": 1, "text": text}

    def update_pull_request_comment(
        self, project_key, repo_slug, pr_id, comment_id, text, *, version
    ):
        self.calls.append(("edit", project_key, repo_slug, pr_id, comment_id, text, version))
        return {"id": comment_id, "version": version + 1, "text": text}

    def delete_pull_request_comment(self, project_key, repo_slug, pr_id, comment_id, *, version):
        self.calls.append(("delete", project_key, repo_slug, pr_id, comment_id, version))
        return None


def test_comment_service_lists_normalized_envelope() -> None:
    service = PullRequestCommentService(FakeCommentProvider())

    result = service.list("DEMO", "example-repo", 42, start=0, limit=25)

    assert result == {
        "results": [
            {
                "id": "1001",
                "version": 3,
                "text": "example comment",
                "author": {"display_name": "Example Author", "name": "example-user-id"},
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }


def test_comment_service_get_add_reply_edit_and_delete() -> None:
    provider = FakeCommentProvider()
    service = PullRequestCommentService(provider)

    assert service.get("DEMO", "example-repo", 42, "1001")["id"] == "1001"
    assert service.add("DEMO", "example-repo", 42, "example comment")["text"] == "example comment"
    assert service.reply("DEMO", "example-repo", 42, "1001", "example response")["text"] == "example response"
    assert service.edit("DEMO", "example-repo", 42, "1001", "example comment", version=3)["version"] == 4
    assert service.delete("DEMO", "example-repo", 42, "1001", version=4) == {
        "id": "1001",
        "deleted": True,
    }
    assert provider.calls[-2:] == [
        ("edit", "DEMO", "example-repo", 42, "1001", "example comment", 3),
        ("delete", "DEMO", "example-repo", 42, "1001", 4),
    ]


def test_comment_service_raw_methods_preserve_provider_payloads() -> None:
    service = PullRequestCommentService(FakeCommentProvider())

    assert service.list_raw("DEMO", "example-repo", 42, start=0, limit=25)[0]["id"] == 1001
    assert service.get_raw("DEMO", "example-repo", 42, "1001")["id"] == "1001"
    assert service.add_raw("DEMO", "example-repo", 42, "example comment")["id"] == 1002
    assert service.reply_raw("DEMO", "example-repo", 42, "1001", "example response")["text"] == "example response"
    assert service.edit_raw("DEMO", "example-repo", 42, "1001", "example comment", version=3)["version"] == 4
    assert service.delete_raw("DEMO", "example-repo", 42, "1001", version=4) == {}
```

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_pr_comment_service.py -v
```

Expected: FAIL because `atlassian_cli.products.bitbucket.services.pr_comment` does not exist.

- [ ] **Step 3: Implement the comment service**

Create `src/atlassian_cli/products/bitbucket/services/pr_comment.py`:

```python
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
```

- [ ] **Step 4: Run comment service tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_pr_comment_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit comment service work**

Run:

```bash
git add src/atlassian_cli/products/bitbucket/services/pr_comment.py tests/products/bitbucket/test_pr_comment_service.py
git commit -m "feat: add bitbucket pull request comment service"
```

### Task 4: Add Pull Request Comment Commands

**Files:**
- Create: `tests/products/bitbucket/test_pr_comment_command.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/pr_comment.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`

- [ ] **Step 1: Write failing command tests**

Create `tests/products/bitbucket/test_pr_comment_command.py`:

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


class FakeCommentService:
    def list(self, project_key, repo_slug, pr_id, start=0, limit=25):
        return {"results": [{"id": "1001", "text": "example comment"}], "start_at": start, "max_results": limit}

    def list_raw(self, project_key, repo_slug, pr_id, start=0, limit=25):
        return [{"id": 1001, "text": "example comment"}]

    def get(self, project_key, repo_slug, pr_id, comment_id):
        return {"id": comment_id, "text": "example comment"}

    def get_raw(self, project_key, repo_slug, pr_id, comment_id):
        return {"id": int(comment_id), "text": "example comment"}

    def add(self, project_key, repo_slug, pr_id, text):
        return {"id": "1002", "text": text}

    def add_raw(self, project_key, repo_slug, pr_id, text):
        return {"id": 1002, "text": text}

    def reply(self, project_key, repo_slug, pr_id, parent_id, text):
        return {"id": "1003", "text": text, "parent": {"id": parent_id}}

    def reply_raw(self, project_key, repo_slug, pr_id, parent_id, text):
        return {"id": 1003, "text": text, "parent": {"id": int(parent_id)}}

    def edit(self, project_key, repo_slug, pr_id, comment_id, text, version):
        return {"id": comment_id, "version": version + 1, "text": text}

    def edit_raw(self, project_key, repo_slug, pr_id, comment_id, text, version):
        return {"id": int(comment_id), "version": version + 1, "text": text}

    def delete(self, project_key, repo_slug, pr_id, comment_id, version):
        return {"id": comment_id, "deleted": True}

    def delete_raw(self, project_key, repo_slug, pr_id, comment_id, version):
        return {}


def test_bitbucket_pr_comment_commands_output_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeCommentService())

    commands = [
        ["list", "DEMO", "example-repo", "42"],
        ["get", "DEMO", "example-repo", "42", "1001"],
        ["add", "DEMO", "example-repo", "42", "example comment"],
        ["reply", "DEMO", "example-repo", "42", "1001", "example response"],
        ["edit", "DEMO", "example-repo", "42", "1001", "example comment", "--version", "3"],
        ["delete", "DEMO", "example-repo", "42", "1001", "--version", "4"],
    ]

    for command in commands:
        result = runner.invoke(
            app,
            ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "comment", *command, "--output", "json"],
        )
        assert result.exit_code == 0
        assert result.stdout.strip().startswith("{")


def test_bitbucket_pr_comment_raw_output_uses_raw_service(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeCommentService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "get",
            "DEMO",
            "example-repo",
            "42",
            "1001",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": 1001' in result.stdout


def test_bitbucket_pr_comment_edit_requires_version(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(comment_module, "build_comment_service", lambda *_args: FakeCommentService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "edit",
            "DEMO",
            "example-repo",
            "42",
            "1001",
            "example comment",
        ],
    )

    assert result.exit_code != 0
    assert "--version" in result.stdout
```

- [ ] **Step 2: Run command tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_pr_comment_command.py -v
```

Expected: FAIL because the command module and `bitbucket pr comment` command group do not exist.

- [ ] **Step 3: Implement comment commands**

Create `src/atlassian_cli/products/bitbucket/commands/pr_comment.py`:

```python
import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.pr_comment import PullRequestCommentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket pull request comment commands")


def build_comment_service(context) -> PullRequestCommentService:
    return PullRequestCommentService(provider=build_provider(context))


@app.command("list")
def list_comments(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.list_raw(project_key, repo_slug, pr_id, start=start, limit=limit)
        if is_raw_output(output)
        else service.list(project_key, repo_slug, pr_id, start=start, limit=limit)
    )
    typer.echo(render_output(payload, output=output))


@app.command("get")
def get_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    comment_id: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.get_raw(project_key, repo_slug, pr_id, comment_id)
        if is_raw_output(output)
        else service.get(project_key, repo_slug, pr_id, comment_id)
    )
    typer.echo(render_output(payload, output=output))


@app.command("add")
def add_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    text: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.add_raw(project_key, repo_slug, pr_id, text)
        if is_raw_output(output)
        else service.add(project_key, repo_slug, pr_id, text)
    )
    typer.echo(render_output(payload, output=output))


@app.command("reply")
def reply_to_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    parent_id: str,
    text: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.reply_raw(project_key, repo_slug, pr_id, parent_id, text)
        if is_raw_output(output)
        else service.reply(project_key, repo_slug, pr_id, parent_id, text)
    )
    typer.echo(render_output(payload, output=output))


@app.command("edit")
def edit_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    comment_id: str,
    text: str,
    version: int | None = typer.Option(None, "--version"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if version is None:
        raise typer.BadParameter("--version is required", param_hint="--version")
    service = build_comment_service(ctx.obj)
    payload = (
        service.edit_raw(project_key, repo_slug, pr_id, comment_id, text, version=version)
        if is_raw_output(output)
        else service.edit(project_key, repo_slug, pr_id, comment_id, text, version=version)
    )
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    comment_id: str,
    version: int | None = typer.Option(None, "--version"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if version is None:
        raise typer.BadParameter("--version is required", param_hint="--version")
    service = build_comment_service(ctx.obj)
    payload = (
        service.delete_raw(project_key, repo_slug, pr_id, comment_id, version=version)
        if is_raw_output(output)
        else service.delete(project_key, repo_slug, pr_id, comment_id, version=version)
    )
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Register `pr comment`**

Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`:

```python
from atlassian_cli.products.bitbucket.commands.pr_comment import app as pr_comment_app
```

Place this line after the `app = typer.Typer(help="Bitbucket pull request commands")` constructor:

```python
app.add_typer(pr_comment_app, name="comment")
```

- [ ] **Step 5: Run comment command tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_pr_comment_command.py -v
```

Expected: PASS.

- [ ] **Step 6: Run coverage manifest test and verify it fails for new commands**

Run:

```bash
.venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py -v
```

Expected: FAIL because `bitbucket pr comment list`, `get`, `add`, `reply`, `edit`, and `delete` are not yet in `tests/e2e/coverage_manifest.py`.

- [ ] **Step 7: Commit comment command work**

Run:

```bash
git add src/atlassian_cli/products/bitbucket/commands/pr.py src/atlassian_cli/products/bitbucket/commands/pr_comment.py tests/products/bitbucket/test_pr_comment_command.py
git commit -m "feat: add bitbucket pull request comment commands"
```

### Task 5: Add Build Status Service

**Files:**
- Create: `tests/products/bitbucket/test_build_status_service.py`
- Create: `src/atlassian_cli/products/bitbucket/services/build_status.py`

- [ ] **Step 1: Write failing build status service tests**

Create `tests/products/bitbucket/test_build_status_service.py`:

```python
import pytest

from atlassian_cli.core.errors import TransportError
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService


class FakeBuildStatusProvider:
    def __init__(self) -> None:
        self.calls = []

    def get_pull_request(self, project_key, repo_slug, pr_id):
        self.calls.append(("pr", project_key, repo_slug, pr_id))
        return {"id": pr_id, "fromRef": {"latestCommit": "head123"}}

    def list_pull_request_commits(self, project_key, repo_slug, pr_id, *, start, limit):
        self.calls.append(("commits", project_key, repo_slug, pr_id, start, limit))
        return [{"id": "abc123"}, {"id": "def456"}]

    def get_associated_build_statuses(self, commit):
        self.calls.append(("status", commit))
        if commit == "abc123":
            return {"values": [{"key": "DEMO", "state": "SUCCESSFUL"}]}
        if commit == "def456":
            return {"values": [{"key": "DEMO", "state": "FAILED"}]}
        if commit == "head123":
            return {"values": [{"key": "DEMO", "state": "INPROGRESS"}]}
        return {"values": []}


def test_commit_build_status_normalizes_results() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_commit("abc123")

    assert result == {
        "commit": "abc123",
        "overall_state": "SUCCESSFUL",
        "results": [{"key": "DEMO", "state": "SUCCESSFUL"}],
    }


def test_commit_build_status_empty_results_are_unknown() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_commit("empty123")

    assert result == {"commit": "empty123", "overall_state": "UNKNOWN", "results": []}


def test_pull_request_build_status_aggregates_all_commits() -> None:
    service = BuildStatusService(FakeBuildStatusProvider())

    result = service.for_pull_request("DEMO", "example-repo", 42)

    assert result["pull_request"] == {"id": 42, "project_key": "DEMO", "repo_slug": "example-repo"}
    assert result["overall_state"] == "FAILED"
    assert [item["commit"] for item in result["commits"]] == ["abc123", "def456"]


def test_pull_request_build_status_latest_only_uses_head_commit() -> None:
    provider = FakeBuildStatusProvider()
    service = BuildStatusService(provider)

    result = service.for_pull_request("DEMO", "example-repo", 42, latest_only=True)

    assert result["overall_state"] == "INPROGRESS"
    assert [item["commit"] for item in result["commits"]] == ["head123"]
    assert ("commits", "DEMO", "example-repo", 42, 0, None) not in provider.calls


def test_build_status_rejects_non_json_status_payload() -> None:
    class TextStatusProvider(FakeBuildStatusProvider):
        def get_associated_build_statuses(self, commit):
            return "<html>example response</html>"

    service = BuildStatusService(TextStatusProvider())

    with pytest.raises(TransportError, match="Bitbucket build status response"):
        service.for_commit("abc123")
```

- [ ] **Step 2: Run build status service tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_build_status_service.py -v
```

Expected: FAIL because `atlassian_cli.products.bitbucket.services.build_status` does not exist.

- [ ] **Step 3: Implement build status service**

Create `src/atlassian_cli/products/bitbucket/services/build_status.py`:

```python
from typing import Any

from atlassian_cli.core.errors import TransportError
from atlassian_cli.models.common import first_present, nested_get
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import (
    BitbucketBuildStatus,
    BitbucketCommitBuildStatusSummary,
    BitbucketPullRequestBuildStatusSummary,
)

STATE_RANK = {"FAILED": 3, "INPROGRESS": 2, "SUCCESSFUL": 1, "UNKNOWN": 0}


def _extract_items(value: object, *, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        values = value.get("values", [])
        return [item for item in values if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise TransportError(
        f"{label} was not a JSON object or array. "
        "The server returned a non-JSON response; check authentication headers."
    )


def _state_for_items(items: list[dict[str, Any]]) -> str:
    state = "UNKNOWN"
    for item in items:
        candidate = str(item.get("state") or "UNKNOWN").upper()
        if STATE_RANK.get(candidate, 0) > STATE_RANK[state]:
            state = candidate if candidate in STATE_RANK else "UNKNOWN"
    return state


def _state_for_summaries(items: list[dict[str, Any]]) -> str:
    state = "UNKNOWN"
    for item in items:
        candidate = str(item.get("overall_state") or "UNKNOWN").upper()
        if STATE_RANK.get(candidate, 0) > STATE_RANK[state]:
            state = candidate if candidate in STATE_RANK else "UNKNOWN"
    return state


class BuildStatusService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def for_commit(self, commit: str) -> dict:
        raw = self.provider.get_associated_build_statuses(commit)
        return self._commit_summary(commit, raw)

    def for_commit_raw(self, commit: str) -> dict:
        return self.provider.get_associated_build_statuses(commit)

    def for_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        latest_only: bool = False,
    ) -> dict:
        commits = self._latest_commit(project_key, repo_slug, pr_id) if latest_only else self._all_commits(project_key, repo_slug, pr_id)
        commit_summaries = [self.for_commit(commit) for commit in commits]
        summary = BitbucketPullRequestBuildStatusSummary(
            pull_request={"id": pr_id, "project_key": project_key, "repo_slug": repo_slug},
            overall_state=_state_for_summaries(commit_summaries),
            commits=commit_summaries,
        )
        return summary.to_simplified_dict()

    def for_pull_request_raw(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        latest_only: bool = False,
    ) -> dict:
        return self.for_pull_request(
            project_key,
            repo_slug,
            pr_id,
            latest_only=latest_only,
        )

    def _commit_summary(self, commit: str, raw: object) -> dict:
        statuses = [
            BitbucketBuildStatus.from_api_response(item).to_simplified_dict()
            for item in _extract_items(raw, label="Bitbucket build status response")
        ]
        summary = BitbucketCommitBuildStatusSummary(
            commit=commit,
            overall_state=_state_for_items(statuses),
            results=statuses,
        )
        return summary.to_simplified_dict()

    def _all_commits(self, project_key: str, repo_slug: str, pr_id: int) -> list[str]:
        commits = self.provider.list_pull_request_commits(
            project_key,
            repo_slug,
            pr_id,
            start=0,
            limit=None,
        )
        return [commit for commit in [self._commit_id(item) for item in commits] if commit]

    def _latest_commit(self, project_key: str, repo_slug: str, pr_id: int) -> list[str]:
        pull_request = self.provider.get_pull_request(project_key, repo_slug, pr_id)
        latest = nested_get(pull_request, "fromRef", "latestCommit")
        if latest:
            return [str(latest)]
        commits = self._all_commits(project_key, repo_slug, pr_id)
        return commits[:1]

    @staticmethod
    def _commit_id(item: dict[str, Any]) -> str | None:
        value = first_present(item.get("id"), item.get("displayId"), item.get("hash"))
        return str(value) if value else None
```

- [ ] **Step 4: Run build status service tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_build_status_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit build status service work**

Run:

```bash
git add src/atlassian_cli/products/bitbucket/services/build_status.py tests/products/bitbucket/test_build_status_service.py
git commit -m "feat: add bitbucket build status service"
```

### Task 6: Add Build Status Commands

**Files:**
- Create: `tests/products/bitbucket/test_build_status_command.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/commit.py`
- Modify: `src/atlassian_cli/cli.py`

- [ ] **Step 1: Write failing build status command tests**

Create `tests/products/bitbucket/test_build_status_command.py`:

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


class FakeBuildStatusService:
    def for_pull_request(self, project_key, repo_slug, pr_id, latest_only=False):
        return {
            "pull_request": {"id": pr_id, "project_key": project_key, "repo_slug": repo_slug},
            "overall_state": "SUCCESSFUL" if latest_only else "FAILED",
            "commits": [{"commit": "abc123", "overall_state": "SUCCESSFUL", "results": []}],
        }

    def for_pull_request_raw(self, project_key, repo_slug, pr_id, latest_only=False):
        return self.for_pull_request(project_key, repo_slug, pr_id, latest_only=latest_only)

    def for_commit(self, commit):
        return {"commit": commit, "overall_state": "SUCCESSFUL", "results": []}

    def for_commit_raw(self, commit):
        return {"values": []}


def test_bitbucket_pr_build_status_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "build_build_status_service", lambda *_args: FakeBuildStatusService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "build-status",
            "DEMO",
            "example-repo",
            "42",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"overall_state": "FAILED"' in result.stdout


def test_bitbucket_pr_build_status_latest_only_forwards_flag(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "build_build_status_service", lambda *_args: FakeBuildStatusService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "build-status",
            "DEMO",
            "example-repo",
            "42",
            "--latest-only",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"overall_state": "SUCCESSFUL"' in result.stdout


def test_bitbucket_commit_build_status_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import commit as commit_module

    monkeypatch.setattr(commit_module, "build_build_status_service", lambda *_args: FakeBuildStatusService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "commit",
            "build-status",
            "abc123",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"commit": "abc123"' in result.stdout
```

- [ ] **Step 2: Run command tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_build_status_command.py -v
```

Expected: FAIL because build status commands are not wired.

- [ ] **Step 3: Wire `bitbucket pr build-status`**

Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`.

Add this import:

```python
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService
```

Add this builder below `build_pr_service`:

```python
def build_build_status_service(context) -> BuildStatusService:
    return BuildStatusService(provider=build_provider(context))
```

Add this command before `create_pull_request`:

```python
@app.command("build-status")
def get_pull_request_build_status(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    latest_only: bool = typer.Option(False, "--latest-only"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_build_status_service(ctx.obj)
    payload = (
        service.for_pull_request_raw(
            project_key,
            repo_slug,
            pr_id,
            latest_only=latest_only,
        )
        if is_raw_output(output)
        else service.for_pull_request(
            project_key,
            repo_slug,
            pr_id,
            latest_only=latest_only,
        )
    )
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Create commit command group**

Create `src/atlassian_cli/products/bitbucket/commands/commit.py`:

```python
import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket commit commands")


def build_build_status_service(context) -> BuildStatusService:
    return BuildStatusService(provider=build_provider(context))


@app.command("build-status")
def get_commit_build_status(
    ctx: typer.Context,
    commit: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_build_status_service(ctx.obj)
    payload = service.for_commit_raw(commit) if is_raw_output(output) else service.for_commit(commit)
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 5: Register `bitbucket commit` in root CLI**

Modify `src/atlassian_cli/cli.py`.

Add this import near the other Bitbucket command imports:

```python
from atlassian_cli.products.bitbucket.commands.commit import app as bitbucket_commit_app
```

Add this registration between branch and PR or between repo and branch:

```python
bitbucket_app.add_typer(bitbucket_commit_app, name="commit")
```

- [ ] **Step 6: Run build status command tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_build_status_command.py -v
```

Expected: PASS.

- [ ] **Step 7: Run coverage manifest test and verify it fails for build status commands**

Run:

```bash
.venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py -v
```

Expected: FAIL because `bitbucket pr build-status` and `bitbucket commit build-status` are not yet in `tests/e2e/coverage_manifest.py`.

- [ ] **Step 8: Commit build status command work**

Run:

```bash
git add src/atlassian_cli/cli.py src/atlassian_cli/products/bitbucket/commands/pr.py src/atlassian_cli/products/bitbucket/commands/commit.py tests/products/bitbucket/test_build_status_command.py
git commit -m "feat: add bitbucket build status commands"
```

### Task 7: Add README and Live E2E Coverage

**Files:**
- Modify: `README.md`
- Modify: `tests/e2e/coverage_manifest.py`
- Modify: `tests/e2e/test_bitbucket_live.py`
- Modify: `tests/test_readme.py`

- [ ] **Step 1: Add README assertions first**

Append this test to `tests/test_readme.py`:

```python
def test_readme_mentions_bitbucket_comments_and_build_status() -> None:
    readme = Path("README.md").read_text()

    assert "bitbucket pr comment list demo example-repo 42" in readme.lower()
    assert "bitbucket pr build-status demo example-repo 42" in readme.lower()
    assert "bitbucket commit build-status abc123" in readme.lower()
```

- [ ] **Step 2: Run README test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -v
```

Expected: FAIL because README does not mention the new commands.

- [ ] **Step 3: Update README examples**

Add these bullets to the README examples sections where Bitbucket examples already appear:

```markdown
- `atlassian bitbucket pr comment list DEMO example-repo 42`
- `atlassian bitbucket pr comment add DEMO example-repo 42 "example comment"`
- `atlassian bitbucket pr build-status DEMO example-repo 42`
- `atlassian bitbucket commit build-status abc123`
```

Add this short behavior note near the Bitbucket pull request diff behavior section:

```markdown
Bitbucket pull request comments and build status behavior:

- `atlassian bitbucket pr comment list DEMO example-repo 42` lists pull request comments.
- `atlassian bitbucket pr comment edit DEMO example-repo 42 1001 "example comment" --version 3` requires the current comment version.
- `atlassian bitbucket pr build-status DEMO example-repo 42` summarizes build statuses for pull request commits.
- `atlassian bitbucket pr build-status DEMO example-repo 42 --latest-only` checks only the pull request head commit.
- `atlassian bitbucket commit build-status abc123` checks a specific commit.
```

- [ ] **Step 4: Update coverage manifest**

Add these mappings to `tests/e2e/coverage_manifest.py`:

```python
    "bitbucket pr comment list": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr comment get": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr comment add": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr comment reply": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr comment edit": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr comment delete": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr build-status": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket commit build-status": "test_bitbucket_branch_and_pr_round_trip_live",
```

- [ ] **Step 5: Extend live Bitbucket PR test**

In `tests/e2e/test_bitbucket_live.py`, after the existing `diff_payload` assertions and before merge, add:

```python
    added_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "add",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "example comment",
        "--output",
        "json",
    )
    comment_id = added_comment["id"]
    comment_version = added_comment["version"]

    comments = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "list",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert any(item["id"] == comment_id for item in comments["results"])

    fetched_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "get",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        comment_id,
        "--output",
        "json",
    )
    assert fetched_comment["id"] == comment_id

    reply = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "reply",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        comment_id,
        "example response",
        "--output",
        "json",
    )
    assert reply["parent"]["id"] == comment_id

    edited_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "edit",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        comment_id,
        "example comment",
        "--version",
        str(comment_version),
        "--output",
        "json",
    )
    assert edited_comment["id"] == comment_id

    deleted_reply = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "delete",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        reply["id"],
        "--version",
        str(reply["version"]),
        "--output",
        "json",
    )
    assert deleted_reply["deleted"] is True

    pr_build_status = run_json(
        live_env,
        "bitbucket",
        "pr",
        "build-status",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--output",
        "json",
    )
    assert pr_build_status["pull_request"]["id"] == pr_id
    assert "overall_state" in pr_build_status
    assert "commits" in pr_build_status

    head_commit = fetched["from_ref"]["latest_commit"]
    commit_build_status = run_json(
        live_env,
        "bitbucket",
        "commit",
        "build-status",
        head_commit,
        "--output",
        "json",
    )
    assert commit_build_status["commit"] == head_commit
    assert "overall_state" in commit_build_status
    assert "results" in commit_build_status
```

- [ ] **Step 6: Run focused non-live tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py tests/e2e/test_coverage_manifest.py -v
```

Expected: PASS.

- [ ] **Step 7: Scan public examples**

Run:

```bash
INTERNAL_PATTERN='ago''ra|ago''ralab'
EMAIL_PATTERN='[A-Za-z0-9._%+-]''+@''[A-Za-z0-9.-]+\\.[A-Za-z]{2,}'
ISSUE_PATTERN='[A-Z]{2,10}''-[0-9]{2,}'
rg -n "${INTERNAL_PATTERN}|${EMAIL_PATTERN}|${ISSUE_PATTERN}" README.md tests docs/superpowers/specs --glob '!docs/superpowers/plans/*'
```

Expected: no matches except approved neutral placeholders already allowed by `AGENTS.md`.

- [ ] **Step 8: Commit docs and e2e ownership**

Run:

```bash
git add README.md tests/test_readme.py tests/e2e/coverage_manifest.py tests/e2e/test_bitbucket_live.py
git commit -m "docs: document bitbucket comments and build status"
```

### Task 8: Final Verification

**Files:**
- Verify: full repository

- [ ] **Step 1: Run Bitbucket product tests**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket -v
```

Expected: PASS.

- [ ] **Step 2: Run coverage manifest and README tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py tests/e2e/test_coverage_manifest.py -v
```

Expected: PASS.

- [ ] **Step 3: Run repository format check**

Run:

```bash
.venv/bin/ruff format --check .
```

Expected: PASS with `files already formatted`.

- [ ] **Step 4: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 5: Run lint**

Run:

```bash
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: PASS with `All checks passed!`.

- [ ] **Step 6: Optionally run live Bitbucket e2e**

Run only when live Atlassian e2e environment variables are configured:

```bash
ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_bitbucket_live.py -m e2e -v
```

Expected: PASS or SKIP when the local live e2e configuration is intentionally absent.

- [ ] **Step 7: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the feature branch, with only intentional commits ahead of the base branch.

- [ ] **Step 8: Final implementation commit check**

Run:

```bash
git log --oneline -8
```

Expected: recent commits include:

```text
feat: add bitbucket workflow schemas
feat: add bitbucket workflow provider methods
feat: add bitbucket pull request comment service
feat: add bitbucket pull request comment commands
feat: add bitbucket build status service
feat: add bitbucket build status commands
docs: document bitbucket comments and build status
```

## Self-Review

Spec coverage:

- PR comment `list/get/add/reply/edit/delete`: Tasks 1, 2, 3, 4, and 7.
- PR build status: Tasks 1, 2, 5, 6, and 7.
- Commit build status: Tasks 1, 2, 5, 6, and 7.
- `bitbucket pr get` remains lightweight: no task modifies `PullRequestService.get`; `pr.py` keeps `get_pull_request` unchanged.
- Raw output modes: command tasks call raw service methods when `is_raw_output(output)` is true.
- README and e2e coverage ownership: Task 7.
- Repository verification: Task 8.

Placeholder scan:

- This plan uses concrete file paths, commands, tests, and code snippets.
- No unresolved placeholder markers are intentionally present.

Type consistency:

- Provider method names match service usage.
- Service method names match command usage.
- Schema class names match test imports and service imports.
