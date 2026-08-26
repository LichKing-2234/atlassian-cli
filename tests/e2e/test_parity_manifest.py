import ast
from collections import Counter
from pathlib import Path

from typer.main import get_command

from atlassian_cli.cli import app
from atlassian_cli.config.models import Product
from tests.e2e.coverage_manifest import COVERAGE_MANIFEST
from tests.e2e.parity_manifest import (
    MCP_ATLASSIAN_REVISION,
    NEGATIVE_PARITY_EVIDENCE,
    PARITY_EVIDENCE,
    GapKind,
    NegativeDisposition,
    ParityStatus,
)
from tests.e2e.test_coverage_manifest import discover_leaf_commands

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


def test_confluence_attachment_upload_has_verified_alignment_evidence() -> None:
    assert PARITY_EVIDENCE["confluence_upload_attachment"].status is ParityStatus.VERIFIED


def test_issue_58_jira_update_rows_are_verified() -> None:
    for operation in ("jira_update_issue", "jira_assign_issue", "jira_transition_issue"):
        assert PARITY_EVIDENCE[operation].status is ParityStatus.VERIFIED


def test_issue_61_confluence_read_rows_are_verified() -> None:
    for operation in (
        "confluence_get_page",
        "confluence_get_page_children",
        "confluence_get_space_page_tree",
    ):
        assert PARITY_EVIDENCE[operation].status is ParityStatus.VERIFIED


def test_issue_49_jira_discovery_rows_are_verified() -> None:
    for operation in (
        "jira_search_assignable_users",
        "jira_search_fields",
        "jira_get_field_options",
    ):
        assert PARITY_EVIDENCE[operation].status is ParityStatus.VERIFIED


def test_issue_48_jira_remote_link_row_is_verified() -> None:
    assert PARITY_EVIDENCE["jira_create_remote_issue_link"].status is ParityStatus.VERIFIED


def test_issue_59_confluence_label_and_restriction_rows_are_verified() -> None:
    for operation in (
        "confluence_get_labels",
        "confluence_add_label",
        "confluence_get_page_restrictions",
    ):
        assert PARITY_EVIDENCE[operation].status is ParityStatus.VERIFIED


def test_issue_53_confluence_attachment_rows_are_verified() -> None:
    for operation in ("confluence_upload_attachments", "confluence_delete_attachment"):
        assert PARITY_EVIDENCE[operation].status is ParityStatus.VERIFIED


def _test_node_exists(node_id: str) -> bool:
    path_value, separator, function_name = node_id.partition("::")
    if not separator or not function_name:
        return False
    path = Path(path_value)
    if not path.is_file():
        return False
    tree = ast.parse(path.read_text())
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        for node in tree.body
    )


def test_complete_parity_evidence_map_is_executable() -> None:
    readme = Path("README.md").read_text()
    leaf_commands = discover_leaf_commands()

    assert len(PARITY_EVIDENCE) == 30
    for operation, evidence in PARITY_EVIDENCE.items():
        assert evidence.status is ParityStatus.VERIFIED, operation
        assert evidence.upstream_operation == f"{operation}@{MCP_ATLASSIAN_REVISION}"
        assert evidence.official_api
        assert evidence.cli_command in leaf_commands
        assert COVERAGE_MANIFEST[evidence.cli_command] == evidence.live_test.rsplit("::", 1)[-1]
        assert evidence.readme_anchor in readme
        assert _test_node_exists(evidence.contract_test)
        assert all(_test_node_exists(node_id) for node_id in evidence.additional_contract_tests)
        assert _test_node_exists(evidence.live_test)
    assert PARITY_EVIDENCE["jira_get_issue"].fixed_version_limitations


def _command_options(command_path: str) -> set[str]:
    command = get_command(app)
    for part in command_path.split():
        command = command.commands[part]
    return {option for parameter in command.params for option in getattr(parameter, "opts", ())}


def test_negative_parity_inventory_is_enforced() -> None:
    leaf_commands = discover_leaf_commands()

    assert len(NEGATIVE_PARITY_EVIDENCE) == 8
    assert Counter(item.disposition for item in NEGATIVE_PARITY_EVIDENCE.values()) == {
        NegativeDisposition.FOLLOW_ON: 6,
        NegativeDisposition.EXCLUDED: 2,
    }
    for evidence in NEGATIVE_PARITY_EVIDENCE.values():
        assert evidence.reason
        for command in evidence.forbidden_commands:
            assert command not in leaf_commands
        for command, option in evidence.forbidden_options:
            assert option not in _command_options(command)
        for command, option in evidence.required_options:
            assert option in _command_options(command)
        if evidence.contract_test:
            assert _test_node_exists(evidence.contract_test)
