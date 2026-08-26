from html.parser import HTMLParser
from pathlib import Path
from typing import NoReturn
from urllib.parse import urljoin, urlparse

from atlassian import Jira
from requests import HTTPError

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.auth.session_patch import patch_session_headers
from atlassian_cli.core.errors import (
    AuthError,
    ConflictError,
    NotFoundError,
    TransportError,
    UnsupportedError,
    ValidationError,
)


class _MoveSubTaskFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict] = []
        self._form: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form":
            self._form = {
                "action": values.get("action", ""),
                "method": values.get("method", "get").lower(),
                "inputs": {},
            }
            self.forms.append(self._form)
        elif tag == "input" and self._form is not None and values.get("name"):
            self._form["inputs"][values["name"]] = values.get("value")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form = None


class JiraServerProvider:
    def __init__(
        self,
        *,
        auth_mode: AuthMode = AuthMode.BASIC,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if auth_mode in {AuthMode.PAT, AuthMode.BEARER} and token is not None:
            kwargs["token"] = token
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Jira(**kwargs)
        session = getattr(self.client, "_session", None)
        if session is not None:
            patch_session_headers(session, headers or {})

    def get_issue(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        requested_fields = fields
        if comment_limit > 0 and fields not in (None, "*all"):
            if isinstance(fields, list):
                requested_fields = [*fields]
                if "comment" not in requested_fields:
                    requested_fields.append("comment")
            else:
                field_names = [item.strip() for item in fields.split(",") if item.strip()]
                if "comment" not in field_names:
                    field_names.append("comment")
                requested_fields = ",".join(field_names)

        issue = self.client.get_issue(
            issue_key,
            fields=requested_fields,
            properties=",".join(properties) if properties else None,
            update_history=update_history,
            expand=expand,
        )
        fields_data = issue.get("fields", {}) if isinstance(issue, dict) else {}
        comment_field = fields_data.get("comment") if isinstance(fields_data, dict) else None
        if isinstance(comment_field, dict):
            if comment_limit == 0:
                comment_field["comments"] = []
            elif comment_limit > 0:
                try:
                    response = self.client.issue_get_comments(issue_key)
                    comments = response.get("comments", []) if isinstance(response, dict) else []
                except Exception:
                    comments = []
                comment_field["comments"] = comments[-comment_limit:]
        return issue

    def search_issues(
        self,
        jql: str,
        start: int = 0,
        limit: int = 25,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        start_at: int | None = None,
        projects_filter: list[str] | None = None,
    ) -> dict:
        scoped_jql = jql
        if projects_filter:
            project_clause = ", ".join(projects_filter)
            scoped_jql = f"project in ({project_clause}) AND ({jql})"
        resolved_start = start if start_at is None else start_at
        if fields is None and expand is None:
            return self.client.jql(scoped_jql, start=resolved_start, limit=limit)
        return self.client.jql(
            scoped_jql,
            fields=fields or "*all",
            start=resolved_start,
            limit=limit,
            expand=expand,
        )

    def get_issue_watchers(self, issue_key: str) -> dict:
        return self.client.issue_get_watchers(issue_key)

    def add_watcher(self, issue_key: str, user_identifier: str) -> dict | None:
        return self.client.issue_add_watcher(issue_key, user_identifier)

    def remove_watcher(self, issue_key: str, username: str) -> dict | None:
        return self.client.issue_delete_watcher(issue_key, user=username)

    def create_issue(self, fields: dict) -> dict:
        return self.client.issue_create(fields=fields)

    def create_issues(self, issues: list[dict]) -> list[dict]:
        try:
            response = self.client.create_issues([{"fields": issue} for issue in issues])
        except HTTPError as exc:
            response = getattr(exc, "response", None)
            if response is None or response.status_code < 500:
                raise
            return [self.client.issue_create(fields=issue) for issue in issues]
        if isinstance(response, list):
            return response
        if not isinstance(response, dict) or not isinstance(response.get("issues"), list):
            raise TransportError("Jira batch create returned an invalid response")
        if response.get("errors"):
            raise ValidationError(f"Jira batch create failed: {response['errors']}")
        return response["issues"]

    def update_issue(
        self, issue_key: str, fields: dict, *, attachments: list[str] | None = None
    ) -> dict:
        if fields:
            self.client.issue_update(issue_key, fields=fields)
        result = {"key": issue_key, "updated": True}
        if attachments:
            result["attachment_results"] = [
                self.upload_issue_attachment(issue_key, path) for path in attachments
            ]
        return result

    @staticmethod
    def _reparent_form(response, *, field: str, action_name: str) -> tuple[str, dict]:
        parser = _MoveSubTaskFormParser()
        parser.feed(response.text)
        form = next(
            (
                item
                for item in parser.forms
                if field in item["inputs"]
                and item["method"] == "post"
                and urlparse(item["action"]).path.endswith(action_name)
            ),
            None,
        )
        if form is None or not form["inputs"].get("atl_token"):
            raise UnsupportedError(
                "Jira Move Sub-task workflow is unavailable; verify Jira 7.11.0 "
                "and the Move Issues permission"
            )
        action_url = urljoin(response.url, form["action"])
        response_origin = urlparse(response.url)
        action_origin = urlparse(action_url)
        if (action_origin.scheme, action_origin.netloc) != (
            response_origin.scheme,
            response_origin.netloc,
        ):
            raise UnsupportedError("Jira Move Sub-task form action is not same-origin")
        return action_url, form["inputs"]

    @staticmethod
    def _raise_reparent_http_error(exc: HTTPError) -> None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in {401, 403}:
            raise AuthError(
                "Jira denied the Move Sub-task workflow; verify authentication and "
                "the Move Issues permission"
            ) from exc
        if status_code == 404:
            raise UnsupportedError(
                "Jira Move Sub-task workflow is unavailable on this server"
            ) from exc
        raise TransportError("Jira Move Sub-task workflow request failed") from exc

    def reparent_subtask(self, issue_id: str, parent_key: str) -> None:
        try:
            server_info = self.client.get_server_info()
        except HTTPError as exc:
            self._raise_reparent_http_error(exc)
        version = str(server_info.get("version", "unknown"))
        build = str(server_info.get("buildNumber", "unknown"))
        if (version, build) != ("7.11.0", "711000"):
            raise UnsupportedError(
                "jira issue reparent-subtask supports only Jira Server 7.11.0 "
                f"build 711000; connected server is {version} build {build}"
            )

        session = getattr(self.client, "_session", None)
        if session is None:
            raise UnsupportedError(
                "Jira Move Sub-task workflow requires an authenticated HTTP session"
            )

        try:
            first = session.get(
                f"{self.client.url.rstrip('/')}/secure/MoveSubTaskChooseOperation!default.jspa",
                params={"id": issue_id},
            )
            first.raise_for_status()
            first_action, first_inputs = self._reparent_form(
                first,
                field="operation",
                action_name="MoveSubTaskChooseOperation.jspa",
            )
            second = session.post(
                first_action,
                data={
                    "operation": first_inputs["operation"],
                    "atl_token": first_inputs["atl_token"],
                },
            )
            second.raise_for_status()
            second_action, second_inputs = self._reparent_form(
                second,
                field="parentIssue",
                action_name="MoveSubTaskParent.jspa",
            )
            final = session.post(
                second_action,
                data={
                    "parentIssue": parent_key,
                    "id": second_inputs.get("id", issue_id),
                    "atl_token": second_inputs["atl_token"],
                },
            )
            final.raise_for_status()
        except HTTPError as exc:
            self._raise_reparent_http_error(exc)

        if urlparse(final.url).path.endswith(
            ("/MoveSubTaskParent.jspa", "/MoveSubTaskParent!default.jspa")
        ):
            raise ConflictError(
                "Jira did not complete Move Sub-task; verify the destination parent "
                "and the Move Issues permission"
            )

    @staticmethod
    def _raise_issue_link_http_error(exc: HTTPError) -> NoReturn:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in {401, 403}:
            raise AuthError(
                "Jira denied the issue link operation; verify authentication and "
                "the Link Issues permission"
            ) from exc
        if status_code == 404:
            raise NotFoundError("Jira issue link resource was not found or is not visible") from exc
        if status_code == 409:
            raise ConflictError("Jira issue link operation conflicted with current state") from exc
        if status_code == 400:
            raise ValidationError(
                "Jira rejected the issue link request; verify its type, issues, and comment"
            ) from exc
        raise TransportError("Jira issue link request failed") from exc

    def list_issue_links(self, issue_key: str) -> list[dict]:
        try:
            issue = self.client.issue(issue_key, fields="issuelinks")
        except HTTPError as exc:
            self._raise_issue_link_http_error(exc)
        fields = issue.get("fields") if isinstance(issue, dict) else {}
        links = fields.get("issuelinks", []) if isinstance(fields, dict) else []
        return [item for item in links if isinstance(item, dict)]

    def create_issue_link(self, data: dict) -> dict | None:
        try:
            return self.client.create_issue_link(data)
        except HTTPError as exc:
            self._raise_issue_link_http_error(exc)

    def delete_issue_link(self, link_id: str) -> dict | None:
        try:
            return self.client.remove_issue_link(link_id)
        except HTTPError as exc:
            self._raise_issue_link_http_error(exc)

    def get_issue_link_types(self) -> list[dict]:
        try:
            return self.client.get_issue_link_types()
        except HTTPError as exc:
            self._raise_issue_link_http_error(exc)

    def list_issue_attachments(self, issue_key: str) -> list[dict]:
        issue = self.client.issue(issue_key, fields="attachment")
        fields = issue.get("fields") if isinstance(issue, dict) else {}
        attachments = fields.get("attachment", []) if isinstance(fields, dict) else []
        return [item for item in attachments if isinstance(item, dict)]

    def upload_issue_attachment(self, issue_key: str, file_path: str) -> dict:
        response = self.client.add_attachment(issue_key, file_path)
        if isinstance(response, dict):
            return response
        if isinstance(response, list) and response and isinstance(response[0], dict):
            return response[0]
        return {"uploaded": bool(response)}

    def download_issue_attachment(
        self, attachment: dict, destination: str, *, issue_key: str
    ) -> dict:
        filename = str(attachment.get("filename") or attachment.get("id") or "attachment")
        download_url = attachment.get("content") or attachment.get("download_url")
        if not isinstance(download_url, str) or not download_url:
            raise RuntimeError(f"attachment download url missing for {filename}")

        target = Path(destination)
        if target.exists() and target.is_dir():
            target = target / Path(filename).name
        elif destination.endswith("/") or destination.endswith("\\"):
            target.mkdir(parents=True, exist_ok=True)
            target = target / Path(filename).name
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        session = getattr(self.client, "_session", None)
        if session is None:
            raise RuntimeError("attachment download is unavailable without an HTTP session")

        bytes_written = 0
        response = session.get(download_url, stream=True)
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                bytes_written += len(chunk)

        return {
            "issue_key": issue_key,
            "attachment_id": str(attachment.get("id", "")),
            "filename": filename,
            "path": str(target),
            "bytes_written": bytes_written,
        }

    def get_create_meta(self, project_key: str, issue_type: str) -> dict:
        meta = self.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
        projects = meta.get("projects", []) if isinstance(meta, dict) else []
        issue_types = projects[0].get("issuetypes", []) if projects else []
        selected = next(
            (
                item
                for item in issue_types
                if item.get("name") == issue_type or str(item.get("id")) == issue_type
            ),
            None,
        )
        if selected is None:
            return {"required": [], "allowed_values": {}}
        fields = selected.get("fields", {})
        return {
            "required": [
                field_id
                for field_id, info in fields.items()
                if isinstance(info, dict) and info.get("required")
            ],
            "allowed_values": {
                field_id: info.get("allowedValues", [])
                for field_id, info in fields.items()
                if isinstance(info, dict) and info.get("allowedValues")
            },
        }

    def delete_issue(self, issue_key: str) -> None:
        self.client.delete_issue(issue_key)

    def transition_issue(
        self,
        issue_key: str,
        transition: str,
        *,
        fields: dict | None = None,
        comment: str | None = None,
    ) -> dict:
        try:
            transition_id = int(transition)
        except ValueError as exc:
            raise ValidationError("transition ID must be numeric") from exc
        data = {"transition": {"id": transition_id}}
        if fields:
            data["fields"] = fields
        if comment:
            data["update"] = {"comment": [{"add": {"body": comment}}]}
        self.client.post(
            f"{self.client.resource_url('issue')}/{issue_key}/transitions",
            data=data,
        )
        return {"key": issue_key, "transition": transition}

    def get_issue_transitions(self, issue_key: str) -> list[dict]:
        return self.client.get_issue_transitions(issue_key)

    def get_worklogs(self, issue_key: str) -> dict:
        url = f"{self.client.resource_url('issue')}/{issue_key}/worklog"
        worklogs = []
        start_at = 0
        total = 0
        while True:
            response = self.client.get(
                url,
                params={"startAt": start_at, "maxResults": 100},
            )
            if not isinstance(response, dict) or not isinstance(response.get("worklogs"), list):
                raise TransportError("Jira worklog list returned an invalid response")
            page = response["worklogs"]
            worklogs.extend(page)
            try:
                total = int(response.get("total", len(worklogs)))
            except (TypeError, ValueError):
                total = len(worklogs)
            start_at += len(page)
            if not page or start_at >= total:
                break
        return {
            "startAt": 0,
            "maxResults": len(worklogs),
            "total": total,
            "worklogs": worklogs,
        }

    def add_worklog(
        self,
        issue_key: str,
        time_spent: str,
        *,
        comment: str | None = None,
        started: str | None = None,
        original_estimate: str | None = None,
        remaining_estimate: str | None = None,
    ) -> dict:
        if original_estimate:
            self.client.issue_update(
                issue_key,
                fields={"timetracking": {"originalEstimate": original_estimate}},
            )
        data = {"timeSpent": time_spent}
        if comment:
            data["comment"] = comment
        if started:
            data["started"] = started
        url = f"{self.client.resource_url('issue')}/{issue_key}/worklog"
        if remaining_estimate:
            return self.client.post(
                url,
                data=data,
                params={"adjustEstimate": "new", "newEstimate": remaining_estimate},
            )
        return self.client.post(url, data=data)

    def assign_issue(self, issue_key: str, assignee: str | None) -> dict:
        self.client.assign_issue(issue_key, assignee)
        return {"key": issue_key}

    def search_fields(self, keyword: str, *, limit: int) -> list[dict]:
        fields = self.client.get_all_fields()
        keyword_lower = keyword.lower()
        return [
            field
            for field in fields
            if not keyword or keyword_lower in str(field.get("name", "")).lower()
        ][:limit]

    def get_field_options(
        self,
        field_id: str,
        project_key: str,
        issue_type: str,
        *,
        contains: str | None = None,
        return_limit: int = 50,
    ) -> list[dict]:
        meta = self.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
        projects = meta.get("projects", [])
        if not projects:
            return []
        issue_types = projects[0].get("issuetypes", [])
        if not issue_types:
            return []
        issue_type_meta = next(
            (
                item
                for item in issue_types
                if item.get("name") == issue_type or str(item.get("id")) == issue_type
            ),
            None,
        )
        if issue_type_meta is None:
            return []
        fields = issue_type_meta.get("fields", {})
        field_meta = fields.get(field_id, {})
        options = field_meta.get("allowedValues", [])
        if contains:
            token = contains.casefold()
            options = [
                item
                for item in options
                if token in str(item.get("value") or item.get("name") or "").casefold()
            ]
        return options[:return_limit]

    def add_comment(
        self, issue_key: str, body: str, visibility: dict[str, str] | None = None
    ) -> dict:
        return self.client.issue_add_comment(issue_key, body, visibility)

    def edit_comment(
        self,
        issue_key: str,
        comment_id: str,
        body: str,
        visibility: dict[str, str] | None = None,
    ) -> dict:
        return self.client.issue_edit_comment(issue_key, comment_id, body, visibility)

    def list_projects(self) -> list[dict]:
        return self.client.projects()

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def get_user(self, username: str) -> dict:
        return self.client.user(username)

    def search_users(
        self,
        query: str,
        *,
        project_key: str | None,
        issue_key: str | None,
        limit: int,
    ) -> list[dict]:
        params = {"username": query, "maxResults": limit}
        if project_key is not None:
            params["project"] = project_key
        elif issue_key is not None:
            params["issueKey"] = issue_key
        return self.client.get(self.client.resource_url("user/assignable/search"), params=params)
