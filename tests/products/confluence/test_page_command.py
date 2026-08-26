import re

import pytest
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.mark.parametrize(
    ("command_args", "expected"),
    [
        (
            [
                "create",
                "--space-key",
                "DEMO",
                "--title",
                "Example Page",
                "--content",
                "<h1>Example Page</h1>",
                "--emoji",
                "example response",
            ],
            ("emoji is not supported on Confluence 6.12.4",),
        ),
        (
            [
                "create",
                "--space-key",
                "DEMO",
                "--title",
                "Example Page",
                "--content",
                "<h1>Example Page</h1>",
                "--content-format",
                "storage",
                "--enable-heading-anchors",
            ],
            ("enable-heading-anchors requires", "content-format=markdown"),
        ),
        (
            [
                "update",
                "1234",
                "--title",
                "Example Page",
                "--content",
                "<h1>Example Page</h1>",
                "--emoji",
                "example response",
            ],
            ("emoji is not supported on Confluence 6.12.4",),
        ),
        (
            [
                "update",
                "1234",
                "--title",
                "Example Page",
                "--content",
                "<h1>Example Page</h1>",
                "--content-format",
                "storage",
                "--enable-heading-anchors",
            ],
            ("enable-heading-anchors requires", "content-format=markdown"),
        ),
        (
            [
                "create",
                "--space-key",
                "DEMO",
                "--title",
                "Example Page",
                "--content",
                "# Example Page",
                "--page-width",
                "full-width",
            ],
            ("page-width", "not supported on Confluence 6.12.4"),
        ),
        (
            [
                "update",
                "1234",
                "--title",
                "Example Page",
                "--content",
                "# Example Page",
                "--table-layout",
                "wide",
            ],
            ("table-layout", "not supported on Confluence 6.12.4"),
        ),
        (
            [
                "create",
                "--space-key",
                "DEMO",
                "--title",
                "Example Page",
                "--content",
                "# Example Page",
                "--subtype",
                "live",
            ],
            ("subtype", "only supported on Confluence Cloud"),
        ),
        (
            [
                "update",
                "1234",
                "--title",
                "Example Page",
                "--content",
                "# Example Page",
                "--content-format",
                "wiki",
            ],
            ("content-format must be markdown", "storage on Confluence 6.12.4"),
        ),
    ],
)
def test_confluence_page_write_rejects_ignored_inputs_before_service(
    monkeypatch, command_args: list[str], expected: tuple[str, ...]
) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    def fail_build(*_args, **_kwargs):
        raise AssertionError("service must not be built for a rejected input")

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        fail_build,
    )

    result = runner.invoke(
        app,
        ["--url", "https://confluence.example.com", "confluence", "page", *command_args],
    )

    assert result.exit_code != 0
    plain_output = ANSI_ESCAPE_RE.sub("", result.output)
    plain_output = " ".join(plain_output.replace("│", " ").split())
    assert all(part in plain_output for part in expected)


@pytest.mark.parametrize("command", ["create", "update"])
def test_confluence_page_write_help_names_fixed_version_limits(command: str) -> None:
    result = runner.invoke(app, ["confluence", "page", command, "--help"])

    assert result.exit_code == 0
    plain_output = ANSI_ESCAPE_RE.sub("", result.output)
    compact_output = " ".join(plain_output.replace("│", " ").split())
    assert "Input format: markdown (default) or storage (raw escape hatch)." in compact_output
    assert "Read the UTF-8 page body from a file" in compact_output
    assert "Add Confluence anchor macros to Markdown headings." in compact_output
    assert "Unsupported on Confluence 6.12.4" in compact_output
    if command == "update":
        assert "Mark the new page version as a minor edit." in compact_output
        assert "Comment attached to the new page version." in compact_output


def test_confluence_page_create_reads_markdown_from_content_file(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    captured = {}

    class FakeService:
        def create(self, **kwargs):
            captured.update(kwargs)
            return {"message": "Page created successfully", "page": {"id": "1234"}}

    content_file = tmp_path / "page.md"
    content_file.write_text("# Example Page\n\nexample response\n", encoding="utf-8")
    monkeypatch.setattr(page_module, "build_page_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "create",
            "--space-key",
            "DEMO",
            "--title",
            "Example Page",
            "--content-file",
            str(content_file),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["content"] == "# Example Page\n\nexample response\n"
    assert captured["content_format"] == "markdown"


def test_confluence_page_update_maps_file_parent_and_version_inputs(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    captured = {}

    class FakeService:
        def update(self, page_id, **kwargs):
            captured["page_id"] = page_id
            captured.update(kwargs)
            return {"message": "Page updated successfully", "page": {"id": page_id}}

    content_file = tmp_path / "page.md"
    content_file.write_text("## Example Page\n", encoding="utf-8")
    monkeypatch.setattr(page_module, "build_page_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "update",
            "1234",
            "--title",
            "Example Page",
            "--content-file",
            str(content_file),
            "--parent-id",
            "5678",
            "--is-minor-edit",
            "--version-comment",
            "example comment",
            "--enable-heading-anchors",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "page_id": "1234",
        "title": "Example Page",
        "content": "## Example Page\n",
        "parent_id": "5678",
        "content_format": "markdown",
        "is_minor_edit": True,
        "version_comment": "example comment",
        "enable_heading_anchors": True,
        "include_content": False,
        "emoji": None,
    }


@pytest.mark.parametrize(
    "command_args",
    [
        ["create", "--space-key", "DEMO", "--title", "Example Page"],
        [
            "create",
            "--space-key",
            "DEMO",
            "--title",
            "Example Page",
            "--content",
            "# Example Page",
            "--content-file",
            "page.md",
        ],
        ["update", "1234", "--title", "Example Page"],
    ],
)
def test_confluence_page_write_requires_exactly_one_content_source(
    monkeypatch, command_args: list[str]
) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args: (_ for _ in ()).throw(AssertionError("service must not be built")),
    )

    result = runner.invoke(
        app,
        ["--url", "https://confluence.example.com", "confluence", "page", *command_args],
    )

    assert result.exit_code != 0
    assert "--content" in ANSI_ESCAPE_RE.sub("", result.output)


def test_confluence_page_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get": lambda self, page_id, **kwargs: {
                    "metadata": {"id": page_id, "title": "Example Page"},
                    "content": {"value": "Example body"},
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"metadata"' in result.stdout


def test_confluence_page_attachment_download_outputs_json(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.confluence.commands import page_attachment as attachment_module

    target = tmp_path / "diagram.png"
    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "download_from_content": lambda self, page_id, *, name, destination: {
                    "page_id": page_id,
                    "title": name,
                    "path": destination,
                    "bytes_written": 3,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "confluence",
            "page",
            "attachment",
            "download",
            "1234",
            "--name",
            "diagram.png",
            "--destination",
            str(target),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"page_id": "1234"' in result.stdout
    assert str(target) in result.stdout


def test_confluence_page_get_renders_storage_html_in_markdown_output(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get": lambda self, page_id, **kwargs: {
                    "metadata": {"id": page_id, "title": "Example Page"},
                    "content": {
                        "value": (
                            '<p>Intro <a href="https://example.com">example link</a></p>'
                            '<ac:structured-macro ac:name="info">'
                            "<ac:rich-text-body><p>Example note</p></ac:rich-text-body>"
                            "</ac:structured-macro>"
                        )
                    },
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "1234",
            "--output",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert "<p>" not in result.stdout
    assert "ac:structured-macro" not in result.stdout
    assert "[example link](https://example.com)" in result.stdout
    assert "Example note" in result.stdout


def test_confluence_page_get_by_title_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get_by_title": lambda self, space_key, title, **kwargs: {
                    "metadata": {"id": "1234", "title": title}
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "--title",
            "Example Page",
            "--space-key",
            "DEMO",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"title": "Example Page"' in result.stdout


def test_confluence_page_get_by_title_missing_page_exits_nonzero(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get_by_title": lambda self, space_key, title, **kwargs: None},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "--title",
            "Missing",
            "--space-key",
            "DEMO",
        ],
    )

    assert result.exit_code != 0
    assert "page not found" in result.output.lower()


def test_confluence_page_get_missing_space_key_mentions_new_flag() -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "--title",
            "Missing",
        ],
    )

    assert result.exit_code != 0
    stripped_output = ANSI_ESCAPE_RE.sub("", result.output)
    normalized_output = " ".join(
        token for token in stripped_output.split() if token.strip("│╭╮╰╯─")
    )
    assert "--space-key" in normalized_output


def test_confluence_page_search_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "search": lambda self, query, limit, spaces_filter=None: {
                    "results": [{"id": "1234", "title": "Example Page"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "search",
            "--query",
            "runbook",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"title": "Example Page"' in result.stdout


def test_confluence_page_search_accepts_spaces_filter(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    captured: dict[str, object] = {}

    class FakeService:
        def search(self, query, *, limit, spaces_filter=None):
            captured["query"] = query
            captured["limit"] = limit
            captured["spaces_filter"] = spaces_filter
            return {"results": [{"id": "1234", "title": "Example Page"}]}

    monkeypatch.setattr(page_module, "build_page_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "search",
            "--query",
            "label=documentation",
            "--spaces-filter",
            "DEMO,~example-user",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["spaces_filter"] == ["DEMO", "~example-user"]


def test_confluence_page_children_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "children": lambda self, page_id: {
                    "results": [{"id": "child-1", "title": "Child One"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "children",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "child-1"' in result.stdout


def test_confluence_page_tree_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"tree": lambda self, space_key: {"results": [{"id": "root", "depth": 0}]}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "tree",
            "DEMO",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"depth": 0' in result.stdout


def test_confluence_page_history_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "history": lambda self, page_id, version, **kwargs: {
                    "metadata": {"id": page_id, "version": version},
                    "content": {"value": "Example history body"},
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "history",
            "1234",
            "--version",
            "2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"version": 2' in result.stdout


def test_confluence_page_get_rejects_convert_to_markdown_until_supported() -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "1234",
            "--include-metadata",
            "--convert-to-markdown",
            "--output",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "convert-to-markdown" in result.output.lower()
    assert "not" in result.output.lower()
    assert "supported" in result.output.lower()


def test_confluence_page_diff_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "diff": lambda self, page_id, from_version, to_version: {
                    "diff": "--- version-1\\n+++ version-2"
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "diff",
            "1234",
            "--from-version",
            "1",
            "--to-version",
            "2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"diff": "--- version-1\\\\n+++ version-2"' in result.stdout


def test_confluence_page_move_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "move": lambda self, page_id, target_parent_id=None, target_space_key=None, position="append": {
                    "id": page_id,
                    "version": 8,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "move",
            "1234",
            "--parent",
            "5678",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"version": 8' in result.stdout
