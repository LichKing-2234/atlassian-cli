from collections import Counter

from atlassian_cli.config.models import Product
from tests.e2e.parity_manifest import (
    PARITY_EVIDENCE,
    GapKind,
    ParityStatus,
)

EXPECTED_OPERATIONS = {
    "jira_get_issue_watchers",
    "jira_add_watcher",
    "jira_remove_watcher",
    "jira_get_worklog",
    "jira_add_worklog",
    "jira_create_remote_issue_link",
    "confluence_get_labels",
    "confluence_add_label",
    "confluence_upload_attachments",
    "confluence_delete_attachment",
    "confluence_get_page_restrictions",
    "jira_search_assignable_users",
    "jira_get_issue",
    "jira_search_fields",
    "jira_get_field_options",
    "jira_create_issue",
    "jira_batch_create_issues",
    "jira_update_issue",
    "jira_assign_issue",
    "jira_add_comment",
    "jira_edit_comment",
    "jira_transition_issue",
    "confluence_get_page",
    "confluence_get_page_children",
    "confluence_get_space_page_tree",
    "confluence_create_page",
    "confluence_update_page",
    "confluence_add_comment",
    "confluence_reply_to_comment",
    "confluence_upload_attachment",
}


def test_parity_manifest_matches_accepted_boundary() -> None:
    assert set(PARITY_EVIDENCE) == EXPECTED_OPERATIONS
    assert Counter((row.product, row.gap) for row in PARITY_EVIDENCE.values()) == {
        (Product.JIRA, GapKind.MISSING): 6,
        (Product.CONFLUENCE, GapKind.MISSING): 5,
        (Product.JIRA, GapKind.DRIFTED): 11,
        (Product.CONFLUENCE, GapKind.DRIFTED): 8,
    }


def test_parity_manifest_has_explicit_inputs_and_issue_owner() -> None:
    for row in PARITY_EVIDENCE.values():
        assert row.semantic_inputs
        assert len(row.semantic_inputs) == len(set(row.semantic_inputs))
        assert all(issue > 0 for issue in row.implementation_issues)
        assert isinstance(row.status, ParityStatus)


def test_parity_manifest_tracks_operation_families_split_across_issues() -> None:
    assert PARITY_EVIDENCE["jira_update_issue"].implementation_issues == (58, 56)
    assert PARITY_EVIDENCE["confluence_create_page"].implementation_issues == (50, 51)
    assert PARITY_EVIDENCE["confluence_update_page"].implementation_issues == (50, 51)


def test_parity_statuses_keep_evidence_states_distinct() -> None:
    assert {status.value for status in ParityStatus} == {
        "unimplemented",
        "implemented-but-unverified",
        "verified",
        "excluded",
        "unsupported",
    }


def test_issue_50_confluence_write_rows_are_verified() -> None:
    for operation in (
        "confluence_create_page",
        "confluence_update_page",
        "confluence_add_comment",
        "confluence_reply_to_comment",
    ):
        assert PARITY_EVIDENCE[operation].status is ParityStatus.VERIFIED
