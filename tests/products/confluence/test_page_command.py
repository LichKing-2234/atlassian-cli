import re

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


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
