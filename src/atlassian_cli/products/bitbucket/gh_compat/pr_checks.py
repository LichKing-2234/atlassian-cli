from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from atlassian_cli.products.bitbucket.gh_compat.pr_output import (
    MISSING_JSON_VALUE,
    GhPreflightError,
    _format_tty_table,
    _style,
)

CHECK_FIELDS = (
    "bucket",
    "completedAt",
    "description",
    "event",
    "link",
    "name",
    "startedAt",
    "state",
    "workflow",
)
ZERO_TIME = "0001-01-01T00:00:00Z"

_STATE_MAP = {
    "SUCCESSFUL": ("SUCCESS", "pass"),
    "FAILED": ("FAILURE", "fail"),
    "INPROGRESS": ("PENDING", "pending"),
}
_BUCKET_ORDER = {"fail": 0, "pending": 1, "pass": 2}


@dataclass(frozen=True)
class CheckCounts:
    canceled: int = 0
    failed: int = 0
    passed: int = 0
    skipped: int = 0
    pending: int = 0

    @classmethod
    def from_checks(cls, checks: Sequence[Mapping[str, object]]) -> CheckCounts:
        failed = passed = pending = 0
        for check in checks:
            match str(check.get("bucket") or ""):
                case "fail":
                    failed += 1
                case "pass":
                    passed += 1
                case "pending":
                    pending += 1
        return cls(failed=failed, passed=passed, pending=pending)


def _project_check(build: Mapping[str, object]) -> dict[str, object]:
    state, bucket = _STATE_MAP.get(
        str(build.get("state") or "").upper(),
        ("PENDING", "pending"),
    )
    return {
        "bucket": bucket,
        "completedAt": ZERO_TIME,
        "description": str(build.get("description") or ""),
        "event": "",
        "link": str(build.get("url") or ""),
        "name": str(build.get("name") or build.get("key") or ""),
        "startedAt": ZERO_TIME,
        "state": state,
        "workflow": "",
    }


def project_checks(builds: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    checks = [_project_check(build) for build in builds]
    return sorted(
        checks,
        key=lambda check: (
            _BUCKET_ORDER.get(str(check["bucket"]), 3),
            str(check["name"]),
            str(check["link"]),
        ),
    )


def select_check_fields(
    checks: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> list[dict[str, object]]:
    return [{field: check[field] for field in fields} for check in checks]


def validate_check_fields(
    value: str | Sequence[str] | None,
    *,
    web: bool,
) -> tuple[str, ...] | None:
    if value is None or (not isinstance(value, str) and not value):
        return None

    values = [value] if isinstance(value, str) else value
    requested = [field.strip() for item in values for field in item.split(",")]
    available = "\n".join(f"  {field}" for field in sorted(CHECK_FIELDS))
    if MISSING_JSON_VALUE in requested:
        raise GhPreflightError(
            f"Specify one or more comma-separated fields for `--json`:\n{available}"
        )
    if web:
        raise GhPreflightError("cannot use `--web` with `--json`")

    unknown = next((field for field in requested if field not in CHECK_FIELDS), None)
    if unknown is not None:
        raise GhPreflightError(f'Unknown JSON field: "{unknown}"\nAvailable fields:\n{available}')
    return tuple(dict.fromkeys(requested))


def checks_exit_code(checks: Sequence[Mapping[str, object]]) -> int:
    counts = CheckCounts.from_checks(checks)
    if counts.failed:
        return 1
    if counts.pending:
        return 8
    return 0


def _summary(counts: CheckCounts, *, color: bool) -> str:
    if counts.failed:
        headline = "Some checks were not successful"
    elif counts.pending:
        headline = "Some checks are still pending"
    else:
        headline = "All checks were successful"
    tallies = (
        f"{counts.canceled} cancelled, {counts.failed} failing, "
        f"{counts.passed} successful, {counts.skipped} skipped, and "
        f"{counts.pending} pending checks"
    )
    return f"{_style(headline, '1', color=color)}\n{tallies}"


def _tabular_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def render_checks(
    checks: Sequence[Mapping[str, object]],
    *,
    tty: bool,
    color: bool,
    width: int,
) -> str:
    if not tty:
        rows = [
            "\t".join(
                (
                    _tabular_cell(check.get("name")),
                    str(check.get("bucket") or ""),
                    "0",
                    _tabular_cell(check.get("link")),
                    _tabular_cell(check.get("description")),
                )
            )
            for check in checks
        ]
        return "\n".join(rows) + ("\n" if rows else "")

    rows = [["", "NAME", "DESCRIPTION", "ELAPSED", "URL"]]
    colors: list[list[str | None]] = [[None, None, None, None, None]]
    for check in checks:
        bucket = str(check.get("bucket") or "")
        symbol, code = {
            "fail": ("X", "31"),
            "pending": ("*", "33"),
            "pass": ("✓", "32"),
        }.get(bucket, ("-", "2"))
        rows.append(
            [
                symbol,
                _tabular_cell(check.get("name")),
                _tabular_cell(check.get("description")),
                "",
                _tabular_cell(check.get("link")),
            ]
        )
        colors.append([code if color else None, None, None, None, None])

    counts = CheckCounts.from_checks(checks)
    table = _format_tty_table(rows, colors, max_width=width)
    return f"{_summary(counts, color=color)}\n\n{table}\n"
