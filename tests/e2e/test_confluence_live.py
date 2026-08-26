import base64
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urljoin

import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    build_live_context,
    resolve_confluence_write_target,
    run_failure,
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


def test_confluence_page_round_trip_live(live_env, confluence_fixed_version, tmp_path) -> None:
    registry = CleanupRegistry()
    first_parent_id = None
    second_parent_id = None
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        first_parent = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("confluence-parent-one"),
            "--content",
            "<p>example response</p>",
            "--content-format",
            "storage",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        first_parent_id = first_parent["page"]["id"]
        registry.add(
            f"confluence page delete {first_parent_id}",
            lambda: _delete_page(live_env, first_parent_id),
        )
        first_parent_read = confluence_fixed_version.get_page(first_parent_id)
        assert first_parent_read["body"]["storage"]["value"] == "<p>example response</p>"

        second_parent = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("confluence-parent-two"),
            "--content",
            "# Example Page",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        second_parent_id = second_parent["page"]["id"]
        registry.add(
            f"confluence page delete {second_parent_id}",
            lambda: _delete_page(live_env, second_parent_id),
        )

        title = unique_name("confluence-page")
        content_file = tmp_path / "page.md"
        content_file.write_text(
            "# Example Page\n\n**example comment**\n",
            encoding="utf-8",
        )
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            title,
            "--content-file",
            str(content_file),
            "--parent-id",
            first_parent_id,
            "--enable-heading-anchors",
            "--output",
            "json",
        )
        page_id = created["page"]["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        created_read = confluence_fixed_version.client.get_page_by_id(
            page_id,
            expand="ancestors,version,body.storage",
        )
        created_body = created_read["body"]["storage"]["value"]
        assert '<ac:structured-macro ac:name="anchor"' in created_body
        assert "<strong>example comment</strong>" in created_body
        assert created_read["ancestors"][-1]["id"] == first_parent_id

        updated = run_json(
            live_env,
            "confluence",
            "page",
            "update",
            page_id,
            "--title",
            title,
            "--content",
            "## Example Page\n\n*example response*",
            "--parent-id",
            second_parent_id,
            "--is-minor-edit",
            "--version-comment",
            "example comment",
            "--enable-heading-anchors",
            "--output",
            "json",
        )
        assert updated["page"]["id"] == page_id
        assert updated["page"]["version"] >= created["page"]["version"]

        updated_read = confluence_fixed_version.client.get_page_by_id(
            page_id,
            expand="ancestors,version,body.storage",
        )
        updated_body = updated_read["body"]["storage"]["value"]
        assert '<ac:structured-macro ac:name="anchor"' in updated_body
        assert "<em>example response</em>" in updated_body
        assert updated_read["ancestors"][-1]["id"] == second_parent_id
        # Confluence 6.12.4 accepts minorEdit=true but reports false in both the
        # PUT response and subsequent version read-back. The provider contract
        # test verifies the outgoing true value.
        assert updated_read["version"]["message"] == "example comment"
        history_read = confluence_fixed_version.client.history(page_id)["lastUpdated"]
        assert history_read["number"] == updated_read["version"]["number"]
        assert history_read["message"] == "example comment"
        assert history_read["minorEdit"] is False

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
        assert "example response" in diff["diff"]
    finally:
        registry.run()


def test_confluence_page_read_navigation_contracts_live(
    live_env, confluence_fixed_version, cleanup_registry
) -> None:
    target = resolve_confluence_write_target(live_env)
    if str(target["space_key"]).startswith("~"):
        context = build_live_context(Product.CONFLUENCE, live_env)
        assert context.auth.username is not None
        target["space_key"] = f"~{context.auth.username}"

    def create_page(title: str, *, parent_id: str | None = None) -> str:
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
            "example response",
            *(["--parent-id", parent_id] if parent_id else []),
            "--output",
            "json",
        )
        page_id = str(created["page"]["id"])
        cleanup_registry.add(
            f"confluence page delete {page_id}",
            lambda identifier=page_id: _delete_page(live_env, identifier),
        )
        return page_id

    base_parent_id = target["parent_page_id"]
    if base_parent_id is None:
        homepage = confluence_fixed_version.get_space_homepage(str(target["space_key"]))
        base_parent_id = str(homepage["id"])
    parent_id = create_page(
        unique_name("confluence-navigation-parent"), parent_id=str(base_parent_id)
    )
    child_ids = [
        create_page(unique_name("confluence-navigation-child"), parent_id=parent_id)
        for _ in range(3)
    ]

    base_url = str(confluence_fixed_version.client.url).rstrip("/")
    full_url = f"{base_url}/pages/viewpage.action?pageId={parent_id}"
    by_url = run_json(live_env, "confluence", "page", "get", full_url, "--output", "json")
    assert by_url["metadata"]["id"] == parent_id

    raw_parent = confluence_fixed_version.get_page(parent_id)
    tiny_path = raw_parent.get("_links", {}).get("tinyui")
    assert isinstance(tiny_path, str) and tiny_path
    tiny_url = urljoin(f"{base_url}/", tiny_path.lstrip("/"))
    by_tiny = run_json(live_env, "confluence", "page", "get", tiny_url, "--output", "json")
    assert by_tiny["metadata"]["id"] == parent_id

    all_children = confluence_fixed_version.get_page_children(
        parent_id, expand="body.storage,version", limit=3, start=0
    )
    assert [str(item["id"]) for item in all_children] == child_ids
    paged = run_json(
        live_env,
        "confluence",
        "page",
        "children",
        parent_id,
        "--expand",
        "body.storage,version",
        "--limit",
        "1",
        "--start",
        "1",
        "--output",
        "raw-json",
    )
    assert len(paged) == 1
    assert str(paged[0]["id"]) == child_ids[1]
    assert "body" in paged[0] and "version" in paged[0]

    tree = run_json(
        live_env,
        "confluence",
        "page",
        "tree",
        str(target["space_key"]),
        "--limit",
        "2",
        "--output",
        "json",
    )
    assert len(tree["results"]) == 2


def test_confluence_label_and_restriction_contracts_live(
    live_env, confluence_fixed_version, cleanup_registry
) -> None:
    target = resolve_confluence_write_target(live_env)
    if str(target["space_key"]).startswith("~"):
        context = build_live_context(Product.CONFLUENCE, live_env)
        assert context.auth.username is not None
        target["space_key"] = f"~{context.auth.username}"

    parent_id = target["parent_page_id"]
    if parent_id is None:
        homepage = confluence_fixed_version.get_space_homepage(str(target["space_key"]))
        parent_id = str(homepage["id"])
    created = run_json(
        live_env,
        "confluence",
        "page",
        "create",
        "--space-key",
        str(target["space_key"]),
        "--title",
        unique_name("confluence-label-restriction"),
        "--content",
        "# Example Page",
        "--parent-id",
        str(parent_id),
        "--output",
        "json",
    )
    page_id = str(created["page"]["id"])
    cleanup_registry.add(
        f"confluence page delete {page_id}",
        lambda: _delete_page(live_env, page_id),
    )

    label_name = "example-repo"
    label_present = {"value": False}

    def remove_label() -> None:
        if label_present["value"]:
            confluence_fixed_version.client.remove_page_label(page_id, label_name)

    cleanup_registry.add(
        f"confluence page label remove {page_id}",
        remove_label,
    )

    listed = run_json(
        live_env,
        "confluence",
        "page",
        "label",
        "list",
        page_id,
        "--output",
        "json",
    )
    assert not any(item.get("name") == label_name for item in listed["results"])

    added = run_json(
        live_env,
        "confluence",
        "page",
        "label",
        "add",
        page_id,
        "--name",
        label_name,
        "--output",
        "json",
    )
    label_present["value"] = True
    assert any(item.get("name") == label_name for item in added["results"])

    labels_read_back = confluence_fixed_version.client.get_page_labels(page_id)
    assert any(item.get("name") == label_name for item in labels_read_back.get("results", []))

    restrictions_before = confluence_fixed_version.client.get_all_restrictions_for_content(page_id)
    before_digest = hashlib.sha256(
        json.dumps(restrictions_before, sort_keys=True).encode()
    ).hexdigest()
    restrictions = run_json(
        live_env,
        "confluence",
        "page",
        "restriction",
        "get",
        page_id,
        "--output",
        "json",
    )
    assert set(restrictions) == {"read", "update"}
    for operation in ("read", "update"):
        assert set(restrictions[operation]) == {"users", "groups"}

    restrictions_after = confluence_fixed_version.client.get_all_restrictions_for_content(page_id)
    after_digest = hashlib.sha256(
        json.dumps(restrictions_after, sort_keys=True).encode()
    ).hexdigest()
    assert after_digest == before_digest

    confluence_fixed_version.client.remove_page_label(page_id, label_name)
    label_present["value"] = False
    labels_after_cleanup = confluence_fixed_version.client.get_page_labels(page_id)
    assert not any(
        item.get("name") == label_name for item in labels_after_cleanup.get("results", [])
    )


def test_confluence_page_write_rejections_do_not_mutate_live(
    live_env, confluence_fixed_version, cleanup_registry
) -> None:
    target = resolve_confluence_write_target(live_env)
    rejected_title = unique_name("confluence-rejected-create")
    run_failure(
        live_env,
        "confluence",
        "page",
        "create",
        "--space-key",
        str(target["space_key"]),
        "--title",
        rejected_title,
        "--content",
        "<h1>Example Page</h1>",
        "--emoji",
        "example response",
        expected="emoji is not supported on Confluence 6.12.4",
    )
    assert (
        confluence_fixed_version.get_page_by_title(str(target["space_key"]), rejected_title) is None
    )

    title = unique_name("confluence-rejected-update")
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
        "<h1>Example Page</h1>",
        *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
        "--output",
        "json",
    )
    page_id = created["page"]["id"]
    cleanup_registry.add(
        f"confluence page delete {page_id}",
        lambda: _delete_page(live_env, page_id),
    )
    before = confluence_fixed_version.get_page(page_id)

    run_failure(
        live_env,
        "confluence",
        "page",
        "update",
        page_id,
        "--title",
        title,
        "--content",
        "<h1>Example Page</h1>",
        "--content-format",
        "storage",
        "--enable-heading-anchors",
        expected="enable-heading-anchors requires",
    )

    run_failure(
        live_env,
        "confluence",
        "page",
        "update",
        page_id,
        "--title",
        title,
        "--content",
        "# Example Page",
        "--table-layout",
        "wide",
        expected="table-layout",
    )

    run_failure(
        live_env,
        "confluence",
        "page",
        "update",
        page_id,
        "--title",
        title,
        "--content",
        "# Example Page",
        "--content-format",
        "wiki",
        expected="content-format must be markdown",
    )

    after = confluence_fixed_version.get_page(page_id)
    assert after["version"]["number"] == before["version"]["number"]
    assert after["body"]["storage"]["value"] == before["body"]["storage"]["value"]


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


def test_confluence_comment_round_trip_live(live_env, confluence_fixed_version) -> None:
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
            "# Example Page",
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
            "**example comment**",
            "--output",
            "json",
        )
        assert comment["id"]
        comment_read = confluence_fixed_version.client.get_page_by_id(
            comment["id"],
            expand="body.storage",
        )
        assert comment_read["body"]["storage"]["value"] == "<p><strong>example comment</strong></p>"

        reply = run_json(
            live_env,
            "confluence",
            "comment",
            "reply",
            comment["id"],
            "--body",
            "*example response*",
            "--output",
            "json",
        )
        assert reply["id"]
        reply_read = confluence_fixed_version.client.get_page_by_id(
            reply["id"],
            expand="body.storage",
        )
        assert reply_read["body"]["storage"]["value"] == "<p><em>example response</em></p>"

        storage_comment = run_json(
            live_env,
            "confluence",
            "comment",
            "add",
            page_id,
            "--body",
            "<p>example comment</p>",
            "--content-format",
            "storage",
            "--output",
            "json",
        )
        storage_comment_read = confluence_fixed_version.client.get_page_by_id(
            storage_comment["id"],
            expand="body.storage",
        )
        assert storage_comment_read["body"]["storage"]["value"] == "<p>example comment</p>"

        storage_reply = run_json(
            live_env,
            "confluence",
            "comment",
            "reply",
            storage_comment["id"],
            "--body",
            "<p>example response</p>",
            "--content-format",
            "storage",
            "--output",
            "json",
        )
        storage_reply_read = confluence_fixed_version.client.get_page_by_id(
            storage_reply["id"],
            expand="body.storage",
        )
        assert storage_reply_read["body"]["storage"]["value"] == "<p>example response</p>"

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


def test_confluence_attachment_round_trip_live(
    live_env, confluence_fixed_version, tmp_path
) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        username = getattr(confluence_fixed_version.client, "username", None)
        if not username:
            raise RuntimeError("Confluence live attachment writes require a configured username")
        target["space_key"] = f"~{username}"
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
        uploaded_metadata = confluence_fixed_version.client.get(
            f"rest/api/content/{uploaded['id']}",
            params={"expand": "version"},
        )
        assert uploaded_metadata["version"]["minorEdit"] is False

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

        page_upload_file = tmp_path / "diagram.png"
        page_upload_file.write_text("example diagram\n")
        page_uploaded = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "upload",
            page_id,
            str(page_upload_file),
            "--output",
            "json",
        )
        assert page_uploaded["title"] == "diagram.png"

        page_listed = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "list",
            page_id,
            "--filename",
            "diagram.png",
            "--output",
            "json",
        )
        assert any(item["title"] == "diagram.png" for item in page_listed["results"])

        page_download_target = tmp_path / "downloaded-diagram.png"
        page_downloaded = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "download",
            page_id,
            "--name",
            "diagram.png",
            "--destination",
            str(page_download_target),
            "--output",
            "json",
        )
        assert Path(page_downloaded["path"]).read_text() == "example diagram\n"
    finally:
        registry.run()


def test_confluence_attachment_upload_inputs_live(live_env, confluence_fixed_version) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        username = getattr(confluence_fixed_version.client, "username", None)
        if not username:
            raise RuntimeError("Confluence live attachment writes require a configured username")
        target["space_key"] = f"~{username}"
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("Example Page"),
            "--content",
            "<p>example response</p>",
            *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
            "--output",
            "json",
        )
        page_id = page["page"]["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        filename = unique_name("example response")
        content = b"\x00\x01example response\xff"
        uploaded = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "upload",
            page_id,
            "--content-base64",
            base64.b64encode(content).decode("ascii"),
            "--filename",
            filename,
            "--comment",
            "example comment",
            "--minor-edit",
            "--output",
            "json",
        )

        attachment = confluence_fixed_version.client.get(
            f"rest/api/content/{uploaded['id']}",
            params={"expand": "version"},
        )
        assert attachment["title"] == filename
        assert attachment["version"]["message"] == "example comment"
        assert attachment["version"]["minorEdit"] is True

        download_url = confluence_fixed_version.client.url_joiner(
            confluence_fixed_version.client.url,
            attachment["_links"]["download"],
        )
        response = confluence_fixed_version.client._session.get(download_url)
        response.raise_for_status()
        assert response.content == content
    finally:
        registry.run()


def test_confluence_attachment_multi_upload_delete_live(
    live_env, confluence_fixed_version, tmp_path
) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        target = resolve_confluence_write_target(live_env)
        username = getattr(confluence_fixed_version.client, "username", None)
        if not username:
            raise RuntimeError("Confluence live attachment writes require a configured username")
        target["space_key"] = f"~{username}"
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space-key",
            str(target["space_key"]),
            "--title",
            unique_name("Example Page"),
            "--content",
            "example response",
            *("--parent-id", str(target["parent_page_id"])) if target["parent_page_id"] else (),
            "--output",
            "json",
        )
        page_id = str(page["page"]["id"])
        registry.add(
            f"confluence page delete {page_id}",
            lambda: _delete_page(live_env, page_id),
        )

        first = tmp_path / f"{unique_name('diagram')}.png"
        second = tmp_path / f"{unique_name('report')}.pdf"
        expected_content = {
            first.name: b"example diagram\n",
            second.name: b"example report\n",
        }
        first.write_bytes(expected_content[first.name])
        second.write_bytes(expected_content[second.name])
        uploaded = run_json(
            live_env,
            "confluence",
            "attachment",
            "upload-many",
            page_id,
            "--file",
            str(first),
            "--file",
            str(second),
            "--comment",
            "example comment",
            "--minor-edit",
            "--output",
            "json",
        )
        assert len(uploaded["attachments"]) == 2

        metadata_by_title = {}
        for item in uploaded["attachments"]:
            metadata = confluence_fixed_version.client.get(
                f"rest/api/content/{item['id']}", params={"expand": "version"}
            )
            metadata_by_title[metadata["title"]] = metadata
            assert metadata["version"]["message"] == "example comment"
            assert metadata["version"]["minorEdit"] is True
            download_url = confluence_fixed_version.client.url_joiner(
                confluence_fixed_version.client.url,
                metadata["_links"]["download"],
            )
            response = confluence_fixed_version.client._session.get(download_url)
            response.raise_for_status()
            assert response.content == expected_content[metadata["title"]]
        assert set(metadata_by_title) == set(expected_content)

        deleted = metadata_by_title[first.name]
        result = run_json(
            live_env,
            "confluence",
            "attachment",
            "delete",
            str(deleted["id"]),
            "--yes",
            "--output",
            "json",
        )
        assert result == {"attachment_id": str(deleted["id"]), "deleted": True}
        remaining = confluence_fixed_version.list_attachments(page_id, filename=first.name).get(
            "results", []
        )
        assert not any(str(item.get("id")) == str(deleted["id"]) for item in remaining)
    finally:
        registry.run()
