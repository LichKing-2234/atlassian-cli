import time
from pathlib import Path

import pytest

from tests.e2e.support import CleanupRegistry, run_json, unique_name

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
        title = unique_name("confluence-search")
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            title,
            "--body",
            "<p>search target</p>",
            "--output",
            "json",
        )
        page_id = created["id"]
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
        title = unique_name("confluence-page")
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            title,
            "--body",
            "<p>version one</p>",
            "--output",
            "json",
        )
        page_id = created["id"]
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
        assert fetched["id"] == page_id

        updated = run_json(
            live_env,
            "confluence",
            "page",
            "update",
            page_id,
            "--title",
            f"{title} updated",
            "--body",
            "<p>version two</p>",
            "--output",
            "json",
        )
        assert updated["id"] == page_id
        assert updated["version"] >= created["version"]

        history = run_json(
            live_env,
            "confluence",
            "page",
            "history",
            page_id,
            "--version",
            str(updated["version"]),
            "--output",
            "json",
        )
        assert history["id"] == page_id

        diff = run_json(
            live_env,
            "confluence",
            "page",
            "diff",
            page_id,
            "--from-version",
            str(created["version"]),
            "--to-version",
            str(updated["version"]),
            "--output",
            "json",
        )
        assert diff["page_id"] == page_id
        assert diff["from_version"] == created["version"]
        assert diff["to_version"] == updated["version"]
        assert "version two" in diff["diff"] or "+<p>version two</p>" in diff["diff"]
    finally:
        registry.run()


def test_confluence_page_move_and_children_live(live_env) -> None:
    registry = CleanupRegistry()
    parent_id = None
    child_id = None
    try:
        parent = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-parent"),
            "--body",
            "<p>parent</p>",
            "--output",
            "json",
        )
        parent_id = parent["id"]
        registry.add(f"confluence page delete {parent_id}", lambda: _delete_page(live_env, parent_id))

        child = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-child"),
            "--body",
            "<p>child</p>",
            "--output",
            "json",
        )
        child_id = child["id"]
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
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-comment"),
            "--body",
            "<p>comment page</p>",
            "--output",
            "json",
        )
        page_id = page["id"]
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
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-attachment"),
            "--body",
            "<p>attachment page</p>",
            "--output",
            "json",
        )
        page_id = page["id"]
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
