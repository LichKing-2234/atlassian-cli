from dataclasses import dataclass, replace
from enum import StrEnum

from atlassian_cli.config.models import Product

MCP_ATLASSIAN_REVISION = "9b661295766b3eb9363c6135c549268538f0feff"


class GapKind(StrEnum):
    MISSING = "missing"
    DRIFTED = "drifted"


class ParityStatus(StrEnum):
    UNIMPLEMENTED = "unimplemented"
    IMPLEMENTED_UNVERIFIED = "implemented-but-unverified"
    VERIFIED = "verified"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ParityEvidence:
    product: Product
    gap: GapKind
    semantic_inputs: tuple[str, ...]
    implementation_issue: int
    mutation: bool
    status: ParityStatus = ParityStatus.UNIMPLEMENTED
    additional_implementation_issues: tuple[int, ...] = ()
    cli_command: str = ""
    readme_anchor: str = ""
    contract_test: str = ""
    live_test: str = ""
    upstream_operation: str = ""
    official_api: str = ""
    additional_contract_tests: tuple[str, ...] = ()
    fixed_version_limitations: tuple[str, ...] = ()

    @property
    def implementation_issues(self) -> tuple[int, ...]:
        return (self.implementation_issue, *self.additional_implementation_issues)


@dataclass(frozen=True)
class EvidenceReference:
    cli_command: str
    contract_test: str
    live_test: str
    official_api: str
    additional_contract_tests: tuple[str, ...] = ()
    fixed_version_limitations: tuple[str, ...] = ()


class NegativeDisposition(StrEnum):
    FOLLOW_ON = "follow-on"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class NegativeParityEvidence:
    disposition: NegativeDisposition
    reason: str
    forbidden_commands: tuple[str, ...] = ()
    forbidden_options: tuple[tuple[str, str], ...] = ()
    required_options: tuple[tuple[str, str], ...] = ()
    contract_test: str | None = None


PARITY_EVIDENCE = {
    "jira_get_issue_watchers": ParityEvidence(
        Product.JIRA,
        GapKind.MISSING,
        ("issue_key",),
        55,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_add_watcher": ParityEvidence(
        Product.JIRA,
        GapKind.MISSING,
        ("issue_key", "user_identifier"),
        55,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_remove_watcher": ParityEvidence(
        Product.JIRA,
        GapKind.MISSING,
        ("issue_key", "username"),
        55,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_get_worklog": ParityEvidence(
        Product.JIRA,
        GapKind.MISSING,
        ("issue_key",),
        55,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_add_worklog": ParityEvidence(
        Product.JIRA,
        GapKind.MISSING,
        (
            "issue_key",
            "time_spent",
            "comment",
            "started",
            "original_estimate",
            "remaining_estimate",
        ),
        55,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_create_remote_issue_link": ParityEvidence(
        Product.JIRA,
        GapKind.MISSING,
        ("issue_key", "url", "title", "summary", "relationship", "icon_url"),
        48,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_get_labels": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.MISSING,
        ("page_id",),
        59,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_add_label": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.MISSING,
        ("page_id", "name"),
        59,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_upload_attachments": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.MISSING,
        ("content_id", "file_paths", "comment", "minor_edit"),
        53,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_delete_attachment": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.MISSING,
        ("attachment_id",),
        53,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_get_page_restrictions": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.MISSING,
        ("page_id",),
        59,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_search_assignable_users": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("query", "project_key", "issue_key", "limit"),
        49,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_get_issue": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("issue_key", "fields", "expand", "comment_limit", "properties", "update_history"),
        56,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_search_fields": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("keyword", "limit"),
        49,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_get_field_options": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("field_id", "project_key", "issue_type", "contains", "return_limit"),
        49,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "jira_create_issue": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        (
            "project_key",
            "summary",
            "issue_type",
            "assignee",
            "description",
            "components",
            "additional_fields",
        ),
        57,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_batch_create_issues": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("issues", "validate_only"),
        57,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_update_issue": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        (
            "issue_key",
            "fields",
            "additional_fields",
            "components",
            "attachments",
            "transition",
            "comment",
            "comment_visibility",
            "worklog",
            "worklog_started",
        ),
        58,
        True,
        status=ParityStatus.VERIFIED,
        additional_implementation_issues=(56,),
    ),
    "jira_assign_issue": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("issue_key", "assignee"),
        58,
        True,
        status=ParityStatus.VERIFIED,
    ),
    # The fixed Jira 7.11 target stores role restrictions. Its deployment-level
    # group visibility setting is disabled, so live coverage records Jira's
    # structured commentLevel rejection while provider tests own the group payload.
    "jira_add_comment": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("issue_key", "body", "visibility"),
        62,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_edit_comment": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("issue_key", "comment_id", "body", "visibility"),
        62,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "jira_transition_issue": ParityEvidence(
        Product.JIRA,
        GapKind.DRIFTED,
        ("issue_key", "transition_id", "fields", "comment"),
        58,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_get_page": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        ("page_id", "title", "space_key"),
        61,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_get_page_children": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        ("parent_id", "expand", "limit", "start"),
        61,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_get_space_page_tree": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        ("space_key", "limit"),
        61,
        False,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_create_page": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        (
            "space_key",
            "title",
            "content",
            "parent_id",
            "content_format",
            "enable_heading_anchors",
            "content_file",
        ),
        50,
        True,
        status=ParityStatus.VERIFIED,
        additional_implementation_issues=(51,),
    ),
    # Confluence 6.12.4 accepts version.minorEdit=true but its update, page, and
    # history resources all report false; provider coverage owns the outgoing
    # boolean contract while live coverage records that fixed-version limit.
    "confluence_update_page": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        (
            "page_id",
            "title",
            "content",
            "is_minor_edit",
            "version_comment",
            "parent_id",
            "content_format",
            "enable_heading_anchors",
            "content_file",
        ),
        50,
        True,
        status=ParityStatus.VERIFIED,
        additional_implementation_issues=(51,),
    ),
    "confluence_add_comment": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        ("page_id", "body"),
        50,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_reply_to_comment": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        ("comment_id", "body"),
        50,
        True,
        status=ParityStatus.VERIFIED,
    ),
    "confluence_upload_attachment": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.DRIFTED,
        ("content_id", "file_path", "content_base64", "filename", "comment", "minor_edit"),
        52,
        True,
        status=ParityStatus.VERIFIED,
    ),
}


NEGATIVE_PARITY_EVIDENCE = {
    "jira_issue_date_status_history_summary": NegativeParityEvidence(
        NegativeDisposition.FOLLOW_ON,
        "Jira 7.11 exposes source fields and changelog, not a summary operation.",
        forbidden_commands=("jira issue history-summary",),
    ),
    "jira_all_attachment_download": NegativeParityEvidence(
        NegativeDisposition.FOLLOW_ON,
        "Jira 7.11 exposes individual attachment downloads, not download-all.",
        forbidden_commands=("jira issue attachment download-all",),
    ),
    "confluence_page_section_replacement": NegativeParityEvidence(
        NegativeDisposition.FOLLOW_ON,
        "Confluence 6.12.4 requires client-side full-page parsing and update.",
        forbidden_commands=("confluence page section replace",),
    ),
    "confluence_server_user_search": NegativeParityEvidence(
        NegativeDisposition.FOLLOW_ON,
        "Confluence 6.12.4 only exposes group-member reads requiring client filtering.",
        forbidden_commands=("confluence user search",),
    ),
    "confluence_page_wide_attachment_download": NegativeParityEvidence(
        NegativeDisposition.FOLLOW_ON,
        "Confluence 6.12.4 exposes individual attachment downloads, not page-wide download.",
        forbidden_commands=("confluence page attachment download-all",),
    ),
    "confluence_server_page_copy": NegativeParityEvidence(
        NegativeDisposition.FOLLOW_ON,
        "Confluence 6.12.4 has no Server page-copy REST operation.",
        forbidden_commands=("confluence page copy",),
    ),
    "confluence_bulk_restriction_mutation": NegativeParityEvidence(
        NegativeDisposition.EXCLUDED,
        "Confluence 6.12.4 does not document bulk restriction mutation.",
        forbidden_commands=("confluence page restriction set",),
        contract_test=(
            "tests/products/confluence/test_restriction_command.py::"
            "test_confluence_page_restriction_help_is_read_only"
        ),
    ),
    "jira_cloud_watcher_account_id": NegativeParityEvidence(
        NegativeDisposition.EXCLUDED,
        "Jira 7.11 Server watcher operations use usernames, not Cloud account IDs.",
        forbidden_options=(
            ("jira issue watcher add", "--account-id"),
            ("jira issue watcher remove", "--account-id"),
        ),
        required_options=(
            ("jira issue watcher add", "--user-identifier"),
            ("jira issue watcher remove", "--username"),
        ),
        contract_test=(
            "tests/products/jira/test_issue_command.py::"
            "test_jira_issue_watcher_add_routes_server_user_identifier"
        ),
    ),
}


PARITY_REFERENCES = {
    "jira_get_issue_watchers": EvidenceReference(
        "jira issue watcher list",
        "tests/products/jira/test_issue_command.py::test_jira_issue_watcher_list_routes_issue_key",
        "tests/e2e/test_jira_live.py::test_jira_watcher_and_worklog_contracts_live",
        "GET /rest/api/2/issue/{issueKey}/watchers (Jira 7.11)",
    ),
    "jira_add_watcher": EvidenceReference(
        "jira issue watcher add",
        "tests/products/jira/test_issue_command.py::test_jira_issue_watcher_add_routes_server_user_identifier",
        "tests/e2e/test_jira_live.py::test_jira_watcher_and_worklog_contracts_live",
        "POST /rest/api/2/issue/{issueKey}/watchers (Jira 7.11)",
    ),
    "jira_remove_watcher": EvidenceReference(
        "jira issue watcher remove",
        "tests/products/jira/test_issue_command.py::test_jira_issue_watcher_remove_routes_server_username",
        "tests/e2e/test_jira_live.py::test_jira_watcher_and_worklog_contracts_live",
        "DELETE /rest/api/2/issue/{issueKey}/watchers (Jira 7.11)",
    ),
    "jira_get_worklog": EvidenceReference(
        "jira issue worklog list",
        "tests/products/jira/test_issue_command.py::test_jira_issue_worklog_list_routes_issue_key",
        "tests/e2e/test_jira_live.py::test_jira_watcher_and_worklog_contracts_live",
        "GET /rest/api/2/issue/{issueKey}/worklog (Jira 7.11)",
    ),
    "jira_add_worklog": EvidenceReference(
        "jira issue worklog add",
        "tests/products/jira/test_issue_command.py::test_jira_issue_worklog_add_routes_all_semantic_inputs",
        "tests/e2e/test_jira_live.py::test_jira_watcher_and_worklog_contracts_live",
        "PUT /rest/api/2/issue/{issueKey} for originalEstimate; POST /rest/api/2/issue/{issueKey}/worklog with remaining-estimate adjustment query (Jira 7.11)",
    ),
    "jira_create_remote_issue_link": EvidenceReference(
        "jira issue remote-link create",
        "tests/products/jira/test_remote_link_command.py::test_jira_remote_link_create_maps_all_semantic_inputs",
        "tests/e2e/test_jira_live.py::test_jira_remote_issue_link_live",
        "POST /rest/api/2/issue/{issueKey}/remotelink (Jira 7.11)",
    ),
    "confluence_get_labels": EvidenceReference(
        "confluence page label list",
        "tests/products/confluence/test_label_command.py::test_confluence_page_label_list_outputs_json",
        "tests/e2e/test_confluence_live.py::test_confluence_label_and_restriction_contracts_live",
        "GET /rest/api/content/{id}/label (Confluence 6.12.4)",
    ),
    "confluence_add_label": EvidenceReference(
        "confluence page label add",
        "tests/products/confluence/test_label_command.py::test_confluence_page_label_add_maps_name_and_outputs_json",
        "tests/e2e/test_confluence_live.py::test_confluence_label_and_restriction_contracts_live",
        "POST /rest/api/content/{id}/label (Confluence 6.12.4)",
    ),
    "confluence_upload_attachments": EvidenceReference(
        "confluence attachment upload-many",
        "tests/products/confluence/test_attachment_command.py::test_confluence_attachment_upload_many_forwards_all_files",
        "tests/e2e/test_confluence_live.py::test_confluence_attachment_multi_upload_delete_live",
        "POST /rest/api/content/{id}/child/attachment (Confluence 6.12.4)",
    ),
    "confluence_delete_attachment": EvidenceReference(
        "confluence attachment delete",
        "tests/products/confluence/test_attachment_command.py::test_confluence_attachment_delete_requires_confirmation_and_deletes",
        "tests/e2e/test_confluence_live.py::test_confluence_attachment_multi_upload_delete_live",
        "DELETE /rest/api/content/{attachmentId} (Confluence 6.12.4)",
    ),
    "confluence_get_page_restrictions": EvidenceReference(
        "confluence page restriction get",
        "tests/products/confluence/test_restriction_command.py::test_confluence_page_restriction_get_outputs_json",
        "tests/e2e/test_confluence_live.py::test_confluence_label_and_restriction_contracts_live",
        "GET /rest/api/content/{id}/restriction/byOperation (Confluence 6.12.4)",
    ),
    "jira_search_assignable_users": EvidenceReference(
        "jira user search",
        "tests/products/jira/test_user_command.py::test_jira_user_search_maps_project_and_issue_scopes",
        "tests/e2e/test_jira_live.py::test_jira_project_and_metadata_live",
        "GET /rest/api/2/user/assignable/search (Jira 7.11)",
        additional_contract_tests=(
            "tests/products/jira/test_user_service.py::"
            "test_user_service_search_covers_project_and_issue_scopes",
        ),
    ),
    "jira_get_issue": EvidenceReference(
        "jira issue get",
        "tests/products/jira/test_issue_command.py::test_jira_issue_get_passes_fields_expand_and_comment_limit",
        "tests/e2e/test_jira_live.py::test_jira_issue_read_and_attachment_update_live",
        "GET /rest/api/2/issue/{issueIdOrKey} and GET /rest/api/2/issue/{issueIdOrKey}/comment (Jira 7.11; updateHistory has no stable independent read-back resource)",
        additional_contract_tests=(
            "tests/products/jira/test_provider.py::"
            "test_get_issue_forwards_server_options_and_limits_newest_comments",
        ),
        fixed_version_limitations=(
            "Jira 7.11 accepts updateHistory=false, but exposes no stable independent read-back "
            "for the current user's browsing-history side effect.",
        ),
    ),
    "jira_search_fields": EvidenceReference(
        "jira field search",
        "tests/products/jira/test_field_command.py::test_jira_field_search_outputs_json",
        "tests/e2e/test_jira_live.py::test_jira_project_and_metadata_live",
        "GET /rest/api/2/field (Jira 7.11)",
    ),
    "jira_get_field_options": EvidenceReference(
        "jira field options",
        "tests/products/jira/test_field_command.py::test_jira_field_options_outputs_json",
        "tests/e2e/test_jira_live.py::test_jira_project_and_metadata_live",
        "GET /rest/api/2/issue/createmeta?expand=projects.issuetypes.fields (Jira 7.11)",
    ),
    "jira_create_issue": EvidenceReference(
        "jira issue create",
        "tests/products/jira/test_issue_command.py::test_jira_issue_create_maps_all_semantic_inputs",
        "tests/e2e/test_jira_live.py::test_jira_issue_create_and_batch_contracts_live",
        "POST /rest/api/2/issue (Jira 7.11)",
    ),
    "jira_batch_create_issues": EvidenceReference(
        "jira issue batch-create",
        "tests/products/jira/test_issue_command.py::test_jira_issue_batch_create_accepts_semantic_issues_and_validate_only",
        "tests/e2e/test_jira_live.py::test_jira_issue_create_and_batch_contracts_live",
        "POST /rest/api/2/issue/bulk (Jira 7.11)",
    ),
    "jira_update_issue": EvidenceReference(
        "jira issue update",
        "tests/products/jira/test_issue_command.py::test_jira_issue_update_maps_non_default_fields_and_operations",
        "tests/e2e/test_jira_live.py::test_jira_issue_update_assignment_transition_contracts_live",
        "PUT /rest/api/2/issue/{issueIdOrKey}; POST /rest/api/2/issue/{issueIdOrKey}/attachments; POST /rest/api/2/issue/{issueIdOrKey}/transitions; POST /rest/api/2/issue/{issueIdOrKey}/comment; POST /rest/api/2/issue/{issueIdOrKey}/worklog (Jira 7.11)",
    ),
    "jira_assign_issue": EvidenceReference(
        "jira issue assign",
        "tests/products/jira/test_issue_command.py::test_jira_issue_assign_supports_assignment_and_unassignment",
        "tests/e2e/test_jira_live.py::test_jira_issue_update_assignment_transition_contracts_live",
        "PUT /rest/api/2/issue/{issueIdOrKey}/assignee (Jira 7.11)",
    ),
    "jira_add_comment": EvidenceReference(
        "jira comment add",
        "tests/products/jira/test_comment_command.py::test_jira_comment_add_forwards_visibility_and_jira_markup",
        "tests/e2e/test_jira_comments_live.py::test_jira_comment_contracts_live",
        "POST /rest/api/2/issue/{issueIdOrKey}/comment (Jira 7.11)",
    ),
    "jira_edit_comment": EvidenceReference(
        "jira comment edit",
        "tests/products/jira/test_comment_command.py::test_jira_comment_edit_forwards_visibility_and_jira_markup",
        "tests/e2e/test_jira_comments_live.py::test_jira_comment_contracts_live",
        "PUT /rest/api/2/issue/{issueIdOrKey}/comment/{commentId} (Jira 7.11)",
    ),
    "jira_transition_issue": EvidenceReference(
        "jira issue transition",
        "tests/products/jira/test_issue_command.py::test_jira_issue_transition_accepts_fields_and_comment",
        "tests/e2e/test_jira_live.py::test_jira_issue_update_assignment_transition_contracts_live",
        "POST /rest/api/2/issue/{issueIdOrKey}/transitions (Jira 7.11)",
    ),
    "confluence_get_page": EvidenceReference(
        "confluence page get",
        "tests/products/confluence/test_page_command.py::test_confluence_page_get_maps_id_and_title_space_selectors",
        "tests/e2e/test_confluence_live.py::test_confluence_page_read_navigation_contracts_live",
        "GET /rest/api/content/{id} or /rest/api/content?spaceKey&title (Confluence 6.12.4)",
    ),
    "confluence_get_page_children": EvidenceReference(
        "confluence page children",
        "tests/products/confluence/test_page_command.py::test_confluence_page_children_outputs_json",
        "tests/e2e/test_confluence_live.py::test_confluence_page_read_navigation_contracts_live",
        "GET /rest/api/content/{id}/child/page (Confluence 6.12.4)",
    ),
    "confluence_get_space_page_tree": EvidenceReference(
        "confluence page tree",
        "tests/products/confluence/test_page_command.py::test_confluence_page_tree_outputs_json",
        "tests/e2e/test_confluence_live.py::test_confluence_page_read_navigation_contracts_live",
        "GET /rest/api/content?spaceKey={spaceKey} (Confluence 6.12.4)",
    ),
    "confluence_create_page": EvidenceReference(
        "confluence page create",
        "tests/products/confluence/test_page_command.py::test_confluence_page_create_maps_inline_file_parent_anchors_and_storage",
        "tests/e2e/test_confluence_live.py::test_confluence_page_round_trip_live",
        "POST /rest/api/content (Confluence 6.12.4)",
    ),
    "confluence_update_page": EvidenceReference(
        "confluence page update",
        "tests/products/confluence/test_page_command.py::test_confluence_page_update_maps_file_and_explicit_storage_inputs",
        "tests/e2e/test_confluence_live.py::test_confluence_page_round_trip_live",
        "PUT /rest/api/content/{id} (Confluence 6.12.4)",
    ),
    "confluence_add_comment": EvidenceReference(
        "confluence comment add",
        "tests/products/confluence/test_comment_command.py::test_confluence_comment_add_accepts_storage_escape_hatch",
        "tests/e2e/test_confluence_live.py::test_confluence_comment_round_trip_live",
        "POST /rest/api/content with page comment container (Confluence 6.12.4)",
    ),
    "confluence_reply_to_comment": EvidenceReference(
        "confluence comment reply",
        "tests/products/confluence/test_comment_command.py::test_confluence_comment_reply_accepts_storage_escape_hatch",
        "tests/e2e/test_confluence_live.py::test_confluence_comment_round_trip_live",
        "POST /rest/api/content with comment container (Confluence 6.12.4)",
    ),
    "confluence_upload_attachment": EvidenceReference(
        "confluence page attachment upload",
        "tests/products/confluence/test_page_command.py::test_confluence_page_attachment_upload_maps_file_and_base64_sources",
        "tests/e2e/test_confluence_live.py::test_confluence_attachment_upload_inputs_live",
        "POST /rest/api/content/{id}/child/attachment (Confluence 6.12.4)",
    ),
}

assert set(PARITY_REFERENCES) == set(PARITY_EVIDENCE)
PARITY_EVIDENCE = {
    operation: replace(
        evidence,
        cli_command=reference.cli_command,
        readme_anchor=f"atlassian {reference.cli_command}",
        contract_test=reference.contract_test,
        live_test=reference.live_test,
        upstream_operation=f"{operation}@{MCP_ATLASSIAN_REVISION}",
        official_api=reference.official_api,
        additional_contract_tests=reference.additional_contract_tests,
        fixed_version_limitations=reference.fixed_version_limitations,
    )
    for operation, evidence in PARITY_EVIDENCE.items()
    for reference in (PARITY_REFERENCES[operation],)
}
