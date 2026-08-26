from dataclasses import dataclass
from enum import StrEnum

from atlassian_cli.config.models import Product


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

    @property
    def implementation_issues(self) -> tuple[int, ...]:
        return (self.implementation_issue, *self.additional_implementation_issues)


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
        Product.CONFLUENCE, GapKind.MISSING, ("page_id",), 59, False
    ),
    "confluence_add_label": ParityEvidence(
        Product.CONFLUENCE, GapKind.MISSING, ("page_id", "name"), 59, True
    ),
    "confluence_upload_attachments": ParityEvidence(
        Product.CONFLUENCE,
        GapKind.MISSING,
        ("content_id", "file_paths", "comment", "minor_edit"),
        53,
        True,
    ),
    "confluence_delete_attachment": ParityEvidence(
        Product.CONFLUENCE, GapKind.MISSING, ("attachment_id",), 53, True
    ),
    "confluence_get_page_restrictions": ParityEvidence(
        Product.CONFLUENCE, GapKind.MISSING, ("page_id",), 59, False
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
