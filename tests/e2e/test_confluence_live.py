import time
from pathlib import Path

import pytest

from tests.e2e.support import (
    CleanupRegistry,
    resolve_confluence_write_target,
    run_json,
    unique_name,
)

pytestmark = pytest.mark.e2e


def _delete_page(live_env, page_id: str) -> None:
    run_json(
        live_env,
        "confluence",
        "page",
        "delete",
        page_id,
        "--yes",
        "--output",
        "json",
    )


def test_confluence_space_and_search_live(live_env) -> None:
    spaces = run_json(live_env, "confluence", "space", "list", "--output", "json")
    assert spaces["results"]

    space = run_json(
        live_env,
        "confluence",
        "space",
        "get",
        live_env.confluence_space,
        "--output",
        "json",
    )
    assert space["key"] == live_env.confluence_space

    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        title = unique_name("confluence-search")
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            title,
            "--content",
            "<p>search target</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        page_id = created["page"]["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        search = None
        for _ in range(5):
            search = run_json(
                live_env,
                "confluence",
                "page",
                "search",
                "--query",
                title,
                "--output",
                "json",
            )
            if any(item["id"] == page_id for item in search["results"]):
                break
            time.sleep(1)
        assert search is not None
        assert any(item["id"] == page_id for item in search["results"])

        tree = run_json(
            live_env,
            "confluence",
            "page",
            "tree",
            live_env.confluence_space,
            "--output",
            "json",
        )
        assert tree["results"]
    finally:
        registry.run()


def test_confluence_page_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        title = unique_name("confluence-page")
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            title,
            "--content",
            "<p>version one</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        page_id = created["page"]["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        fetched = run_json(
            live_env,
            "confluence",
            "page",
            "get",
            page_id,
            "--output",
            "json",
        )
        assert fetched["metadata"]["id"] == page_id

        updated = run_json(
            live_env,
            "confluence",
            "page",
            "update",
            page_id,
            "--title",
            f"{title} updated",
            "--content",
            "<p>version two</p>",
            "--output",
            "json",
        )
        assert updated["page"]["id"] == page_id
        assert updated["page"]["version"] >= created["page"]["version"]

        history = run_json(
            live_env,
            "confluence",
            "page",
            "history",
            page_id,
            "--version",
            str(updated["page"]["version"]),
            "--output",
            "json",
        )
        assert history["metadata"]["id"] == page_id

        diff = run_json(
            live_env,
            "confluence",
            "page",
            "diff",
            page_id,
            "--from-version",
            str(created["page"]["version"]),
            "--to-version",
            str(updated["page"]["version"]),
            "--output",
            "json",
        )
        assert diff["page_id"] == page_id
        assert diff["from_version"] == created["page"]["version"]
        assert diff["to_version"] == updated["page"]["version"]
        assert "version two" in diff["diff"] or "+<p>version two</p>" in diff["diff"]
    finally:
        registry.run()


def test_confluence_page_move_and_children_live(live_env) -> None:
    registry = CleanupRegistry()
    parent_id = None
    child_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        parent = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("confluence-parent"),
            "--content",
            "<p>parent</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        parent_id = parent["page"]["id"]
        registry.add(
            f"confluence page delete {parent_id}", lambda: _delete_page(live_env, parent_id)
        )

        child = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("confluence-child"),
            "--content",
            "<p>child</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        child_id = child["page"]["id"]
        registry.add(f"confluence page delete {child_id}", lambda: _delete_page(live_env, child_id))

        moved = run_json(
            live_env,
            "confluence",
            "page",
            "move",
            child_id,
            "--parent",
            parent_id,
            "--output",
            "json",
        )
        assert moved["id"] == child_id

        children = run_json(
            live_env,
            "confluence",
            "page",
            "children",
            parent_id,
            "--output",
            "json",
        )
        assert any(item["id"] == child_id for item in children["results"])
    finally:
        registry.run()


def test_confluence_comment_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("confluence-comment"),
            "--content",
            "<p>comment page</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        page_id = page["page"]["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        comment = run_json(
            live_env,
            "confluence",
            "comment",
            "add",
            page_id,
            "--body",
            "example comment",
            "--output",
            "json",
        )
        assert comment["id"]

        reply = run_json(
            live_env,
            "confluence",
            "comment",
            "reply",
            comment["id"],
            "--body",
            "example response",
            "--output",
            "json",
        )
        assert reply["id"]

        comments = run_json(
            live_env,
            "confluence",
            "comment",
            "list",
            page_id,
            "--output",
            "json",
        )
        comment_ids = [item.get("id") for item in comments["results"]]
        assert comment["id"] in comment_ids
    finally:
        registry.run()


def test_confluence_attachment_round_trip_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("confluence-attachment"),
            "--content",
            "<p>attachment page</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        page_id = page["page"]["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        upload_file = tmp_path / "deploy.log"
        upload_file.write_text("release=42\nstatus=ok\n")

        uploaded = run_json(
            live_env,
            "confluence",
            "attachment",
            "upload",
            page_id,
            "--file",
            str(upload_file),
            "--output",
            "json",
        )
        assert uploaded["id"]

        listed = run_json(
            live_env,
            "confluence",
            "attachment",
            "list",
            page_id,
            "--output",
            "json",
        )
        attachment = next(item for item in listed["results"] if item["id"] == uploaded["id"])

        download_target = tmp_path / "downloaded.log"
        downloaded = run_json(
            live_env,
            "confluence",
            "attachment",
            "download",
            attachment["id"],
            "--destination",
            str(download_target),
            "--output",
            "json",
        )
        assert Path(downloaded["path"]).read_text() == "release=42\nstatus=ok\n"
    finally:
        registry.run()
