import json

from atlassian_cli.core.errors import ConflictError, TransportError, ValidationError
from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.jira.markup import markdown_to_jira
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraIssue, JiraSearchResult


class IssueService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        raw = self.provider.get_issue(
            issue_key,
            fields=fields,
            expand=expand,
            comment_limit=comment_limit,
            properties=properties,
            update_history=update_history,
        )
        return JiraIssue.from_api_response(raw).to_simplified_dict()

    def get_raw(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        return self.provider.get_issue(
            issue_key,
            fields=fields,
            expand=expand,
            comment_limit=comment_limit,
            properties=properties,
            update_history=update_history,
        )

    def search(
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
        raw = self.provider.search_issues(
            jql,
            fields=fields,
            expand=expand,
            start_at=start if start_at is None else start_at,
            limit=limit,
            projects_filter=projects_filter,
        )
        return JiraSearchResult.from_api_response(raw).to_simplified_dict()

    def search_page(self, jql: str, start: int, limit: int) -> CollectionPage:
        payload = self.search(jql, start, limit)
        return CollectionPage(
            items=payload["issues"],
            start=payload["start_at"],
            limit=payload["max_results"],
            total=payload["total"],
        )

    def search_raw(
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
        return self.provider.search_issues(
            jql,
            fields=fields,
            expand=expand,
            start_at=start if start_at is None else start_at,
            limit=limit,
            projects_filter=projects_filter,
        )

    def _prepare_create_fields(
        self,
        *,
        project_key: str | None = None,
        summary: str | None = None,
        issue_type: str | None = None,
        assignee: str | None = None,
        description: str | None = None,
        description_format: str = "markdown",
        components: list[str] | None = None,
        additional_fields: dict | None = None,
        validate_metadata: bool = True,
    ) -> dict:
        if description_format not in {"jira", "markdown"}:
            raise ValueError("description_format must be 'markdown' or 'jira'")
        additional_fields = additional_fields or {}
        if not all(
            isinstance(value, str) and value.strip() for value in (project_key, summary, issue_type)
        ):
            raise ValueError("non-empty project_key, summary, and issue_type are required")
        if validate_metadata:
            meta = self.provider.get_create_meta(project_key, issue_type)
            ignored_required = {"project", "issuetype", "summary", "description"}
            missing = [
                field
                for field in meta.get("required", [])
                if field not in ignored_required and field not in additional_fields
            ]
            if missing:
                raise ValueError(f"missing required Jira fields: {', '.join(sorted(missing))}")
        fields = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if assignee:
            fields["assignee"] = {"name": assignee}
        if description:
            fields["description"] = (
                markdown_to_jira(description) if description_format == "markdown" else description
            )
        if components:
            fields["components"] = [{"name": name} for name in components]
        fields.update(additional_fields)
        return fields

    def create(
        self,
        *,
        project_key: str,
        summary: str,
        issue_type: str,
        assignee: str | None = None,
        description: str | None = None,
        description_format: str = "markdown",
        components: list[str] | None = None,
        additional_fields: dict | None = None,
    ) -> dict:
        fields = self._prepare_create_fields(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            assignee=assignee,
            description=description,
            description_format=description_format,
            components=components,
            additional_fields=additional_fields,
        )

        raw = self.provider.create_issue(fields)
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            issue = JiraIssue.from_api_response(raw).to_simplified_dict()
        elif isinstance(raw, dict) and "key" in raw:
            issue = {"key": raw["key"]}
        else:
            issue = raw
        return {"message": "Issue created successfully", "issue": issue}

    def create_raw(
        self,
        *,
        project_key: str,
        summary: str,
        issue_type: str,
        assignee: str | None = None,
        description: str | None = None,
        description_format: str = "markdown",
        components: list[str] | None = None,
        additional_fields: dict | None = None,
    ) -> dict:
        return self.provider.create_issue(
            self._prepare_create_fields(
                project_key=project_key,
                summary=summary,
                issue_type=issue_type,
                assignee=assignee,
                description=description,
                description_format=description_format,
                components=components,
                additional_fields=additional_fields,
            )
        )

    def _prepare_batch_fields(self, issues: list[dict]) -> list[dict]:
        prepared = []
        for index, issue in enumerate(issues, start=1):
            if not isinstance(issue, dict):
                raise ValueError(f"issue {index} must be a JSON object")
            semantic = dict(issue)
            if "project_key" not in semantic and {
                "project",
                "issuetype",
                "summary",
            }.issubset(semantic):
                project = semantic.get("project")
                issue_type_value = semantic.get("issuetype")
                if (
                    not isinstance(project, dict)
                    or not project.get("key")
                    or not isinstance(issue_type_value, dict)
                    or not (issue_type_value.get("name") or issue_type_value.get("id"))
                    or not isinstance(semantic.get("summary"), str)
                    or not semantic["summary"].strip()
                ):
                    raise ValueError(f"issue {index} has invalid Jira REST fields")
                prepared.append(semantic)
                continue
            project_key = semantic.pop("project_key", None)
            summary = semantic.pop("summary", None)
            issue_type = semantic.pop("issue_type", None)
            description = semantic.pop("description", None)
            description_format = semantic.pop("description_format", "markdown")
            assignee = semantic.pop("assignee", None)
            components = semantic.pop("components", None)
            if not all(
                isinstance(value, str) and value.strip()
                for value in (project_key, summary, issue_type)
            ):
                raise ValueError(
                    f"issue {index} requires non-empty project_key, summary, and issue_type"
                )
            if description is not None and not isinstance(description, str):
                raise ValueError(f"issue {index} description must be a string")
            if not isinstance(description_format, str):
                raise ValueError(f"issue {index} description_format must be markdown or jira")
            if assignee is not None and not isinstance(assignee, str):
                raise ValueError(f"issue {index} assignee must be a string")
            if components is not None and (
                not isinstance(components, list)
                or any(not isinstance(component, str) for component in components)
            ):
                raise ValueError(f"issue {index} components must be an array of strings")
            prepared.append(
                self._prepare_create_fields(
                    project_key=project_key,
                    summary=summary,
                    issue_type=issue_type,
                    assignee=assignee,
                    description=description,
                    description_format=description_format,
                    components=(
                        [component.strip() for component in components if component.strip()]
                        if components
                        else None
                    ),
                    additional_fields=semantic,
                    validate_metadata=False,
                )
            )
        return prepared

    def batch_create(self, issues: list[dict], *, validate_only: bool = False) -> dict:
        prepared = self._prepare_batch_fields(issues)
        if validate_only:
            return {"message": "Issues validated successfully", "issues": []}
        return {
            "message": "Issues created successfully",
            "issues": [
                JiraIssue.from_api_response(item).to_simplified_dict()
                if isinstance(item, dict) and "fields" in item and "key" in item
                else {"key": item["key"]}
                if isinstance(item, dict) and "key" in item
                else item
                for item in self.provider.create_issues(prepared)
            ],
        }

    def batch_create_raw(self, issues: list[dict], *, validate_only: bool = False) -> list[dict]:
        prepared = self._prepare_batch_fields(issues)
        return [] if validate_only else self.provider.create_issues(prepared)

    def update(
        self,
        issue_key: str,
        fields: dict | None = None,
        *,
        additional_fields: dict | None = None,
        components: list[str] | None = None,
        attachments: list[str] | None = None,
        transition: str | None = None,
        comment: str | None = None,
        comment_format: str = "markdown",
        comment_visibility: dict[str, str] | None = None,
        worklog: str | None = None,
        worklog_started: str | None = None,
        description_format: str = "markdown",
    ) -> dict:
        raw, attachment_results, operations = self._run_update_operations(
            issue_key,
            fields=fields,
            additional_fields=additional_fields,
            components=components,
            attachments=attachments,
            transition=transition,
            comment=comment,
            comment_format=comment_format,
            comment_visibility=comment_visibility,
            worklog=worklog,
            worklog_started=worklog_started,
            description_format=description_format,
        )
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            issue = JiraIssue.from_api_response(raw).to_simplified_dict()
        else:
            issue = {"key": issue_key, **raw} if isinstance(raw, dict) else {"key": issue_key}
        if attachment_results:
            issue["attachment_results"] = attachment_results
        return {
            "message": (
                "Issue updated successfully" if operations else "No issue updates were requested"
            ),
            "issue": issue,
            "operations_performed": operations,
        }

    def _run_update_operations(
        self,
        issue_key: str,
        *,
        fields: dict | None = None,
        additional_fields: dict | None = None,
        components: list[str] | None = None,
        attachments: list[str] | None = None,
        transition: str | None = None,
        comment: str | None = None,
        comment_format: str = "markdown",
        comment_visibility: dict[str, str] | None = None,
        worklog: str | None = None,
        worklog_started: str | None = None,
        description_format: str = "markdown",
    ) -> tuple[dict, list[dict] | None, list[str]]:
        if description_format not in {"markdown", "jira"}:
            raise ValueError("description_format must be 'markdown' or 'jira'")
        if comment_format not in {"markdown", "jira"}:
            raise ValueError("comment_format must be 'markdown' or 'jira'")
        payload = {**(fields or {}), **(additional_fields or {})}
        if isinstance(payload.get("description"), str) and description_format == "markdown":
            payload["description"] = markdown_to_jira(payload["description"])
        if components:
            payload["components"] = [{"name": name} for name in components]
        operations: list[str] = []
        attachment_results = None
        raw = None
        if payload or attachments:
            raw = self.provider.update_issue(issue_key, payload, attachments=attachments)
            if payload:
                operations.append("fields_updated")
            if isinstance(raw, dict) and raw.get("attachment_results"):
                attachment_results = raw["attachment_results"]
                operations.append("attachments_uploaded")
        if transition:
            transition_id = self._resolve_transition_id(issue_key, transition)
            self.provider.transition_issue(issue_key, transition_id, fields=None, comment=None)
            operations.append(f"transitioned:{transition}")
        if comment:
            body = markdown_to_jira(comment) if comment_format == "markdown" else comment
            self.provider.add_comment(issue_key, body, comment_visibility)
            operations.append("comment_added")
        if worklog:
            self.provider.add_worklog(issue_key, worklog, started=worklog_started)
            operations.append("worklog_added")
        if raw is None or transition or comment or worklog:
            raw = self.provider.get_issue(issue_key)
        return raw, attachment_results, operations

    def update_raw(
        self,
        issue_key: str,
        fields: dict | None = None,
        **kwargs,
    ) -> dict:
        raw, attachment_results, operations = self._run_update_operations(
            issue_key, fields=fields, **kwargs
        )
        result = {
            "message": (
                "Issue updated successfully" if operations else "No issue updates were requested"
            ),
            "issue": raw,
            "operations_performed": operations,
        }
        if attachment_results:
            result["attachment_results"] = attachment_results
        return result

    @staticmethod
    def _resolve_assignee(assignee: str | None) -> str | None:
        if assignee is None or not assignee.strip():
            return None
        if not assignee.lstrip().startswith("{"):
            return assignee
        try:
            parsed = json.loads(assignee)
        except json.JSONDecodeError as exc:
            raise ValueError("assignee must be a username or valid user JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("assignee JSON must be an object")
        identifier = next(
            (
                parsed.get(key)
                for key in ("name", "username", "key", "accountId", "account_id")
                if parsed.get(key)
            ),
            None,
        )
        if not isinstance(identifier, str):
            raise ValueError("assignee JSON has no Jira Server user identifier")
        return identifier

    def assign(self, issue_key: str, assignee: str | None) -> dict:
        self.provider.assign_issue(issue_key, self._resolve_assignee(assignee))
        raw = self.provider.get_issue(issue_key)
        return {
            "message": "Issue assigned successfully",
            "issue": JiraIssue.from_api_response(raw).to_simplified_dict(),
        }

    def assign_raw(self, issue_key: str, assignee: str | None) -> dict:
        self.provider.assign_issue(issue_key, self._resolve_assignee(assignee))
        return {
            "message": "Issue assigned successfully",
            "issue": self.provider.get_issue(issue_key),
        }

    def reparent_subtask(self, issue_key: str, parent_key: str) -> dict:
        source = self.provider.get_issue(issue_key, fields="id,key,parent,issuetype,project")
        destination = self.provider.get_issue(parent_key, fields="key,issuetype,project")
        source_fields = source.get("fields", {})
        destination_fields = destination.get("fields", {})
        source_type = source_fields.get("issuetype", {})
        destination_type = destination_fields.get("issuetype", {})
        previous_parent = source_fields.get("parent", {}).get("key")
        canonical_issue_key = source.get("key") or issue_key
        canonical_parent_key = destination.get("key") or parent_key

        if source_type.get("subtask") is not True or not previous_parent:
            raise ValidationError(f"{issue_key} is not a sub-task")
        if destination_type.get("subtask") is True:
            raise ValidationError(f"destination parent {parent_key} is a sub-task")
        source_project = source_fields.get("project", {}).get("key")
        destination_project = destination_fields.get("project", {}).get("key")
        if not source_project or not destination_project:
            raise TransportError("Jira issue response is missing project metadata")
        if source_project != destination_project:
            raise ValidationError(
                "source sub-task and destination parent must be in the same project"
            )
        if previous_parent == canonical_parent_key:
            raise ConflictError(f"{canonical_issue_key} already has parent {canonical_parent_key}")
        issue_id = source.get("id")
        if not issue_id:
            raise TransportError("Jira issue response is missing the source issue id")

        self.provider.reparent_subtask(str(issue_id), canonical_parent_key)
        updated = self.provider.get_issue(canonical_issue_key, fields="parent")
        new_parent = updated.get("fields", {}).get("parent", {}).get("key")
        if new_parent != canonical_parent_key:
            raise ConflictError(
                "Jira Move Sub-task workflow returned without changing the parent; "
                "verify the destination and Move Issues permission"
            )
        return {
            "issue_key": canonical_issue_key,
            "previous_parent": previous_parent,
            "new_parent": new_parent,
        }

    def _resolve_transition_id(self, issue_key: str, transition: str) -> str:
        selector = transition.strip().casefold()
        resolved = next(
            (
                item.get("id")
                for item in self.provider.get_issue_transitions(issue_key)
                if str(item.get("id", "")).casefold() == selector
                or str(item.get("name", "")).casefold() == selector
            ),
            None,
        )
        if resolved is None:
            raise ValidationError(f"transition not available for {issue_key}: {transition}")
        return str(resolved)

    def transition(
        self,
        issue_key: str,
        transition: str,
        *,
        fields: dict | None = None,
        comment: str | None = None,
        comment_format: str = "markdown",
    ) -> dict:
        if comment_format not in {"markdown", "jira"}:
            raise ValueError("comment_format must be 'markdown' or 'jira'")
        transition_id = self._resolve_transition_id(issue_key, transition)
        body = markdown_to_jira(comment) if comment and comment_format == "markdown" else comment
        self.provider.transition_issue(
            issue_key, transition_id, fields=fields or None, comment=body
        )
        raw = self.provider.get_issue(issue_key)
        return {
            "message": "Issue transitioned successfully",
            "transition": transition,
            "issue": JiraIssue.from_api_response(raw).to_simplified_dict(),
        }

    def transition_raw(
        self,
        issue_key: str,
        transition: str,
        *,
        fields: dict | None = None,
        comment: str | None = None,
        comment_format: str = "markdown",
    ) -> dict:
        if comment_format not in {"markdown", "jira"}:
            raise ValueError("comment_format must be 'markdown' or 'jira'")
        transition_id = self._resolve_transition_id(issue_key, transition)
        body = markdown_to_jira(comment) if comment and comment_format == "markdown" else comment
        self.provider.transition_issue(
            issue_key, transition_id, fields=fields or None, comment=body
        )
        return {
            "message": "Issue transitioned successfully",
            "transition": transition,
            "issue": self.provider.get_issue(issue_key),
        }

    def get_transitions(self, issue_key: str) -> dict:
        return {"results": self.provider.get_issue_transitions(issue_key)}

    def get_transitions_raw(self, issue_key: str) -> list[dict]:
        return self.provider.get_issue_transitions(issue_key)

    def delete(self, issue_key: str) -> dict:
        self.provider.delete_issue(issue_key)
        return {"key": issue_key, "deleted": True}

    def delete_raw(self, issue_key: str) -> dict:
        self.provider.delete_issue(issue_key)
        return {"key": issue_key, "deleted": True}
