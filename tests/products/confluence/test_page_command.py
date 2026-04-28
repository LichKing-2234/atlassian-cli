from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_page_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, page_id: {"id": page_id, "title": "Runbook"}},
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
    assert '"id": "1234"' in result.stdout


def test_confluence_page_get_by_title_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get_by_title": lambda self, space_key, title: {"id": "1234", "title": title}},
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
            "Runbook",
            "--space",
            "OPS",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"title": "Runbook"' in result.stdout


def test_confluence_page_get_by_title_missing_page_exits_nonzero(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get_by_title": lambda self, space_key, title: None},
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
            "--space",
            "OPS",
        ],
    )

    assert result.exit_code != 0
    assert "page not found" in result.output.lower()


def test_confluence_page_search_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "search": lambda self, query, limit: {
                    "results": [{"id": "1234", "title": "Runbook"}]
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
    assert '"title": "Runbook"' in result.stdout


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
            "OPS",
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
            {"history": lambda self, page_id, version: {"id": page_id, "version": version}},
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
