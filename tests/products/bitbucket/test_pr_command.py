from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.output.interactive import CollectionPage

runner = CliRunner()


def test_bitbucket_pr_list_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [{"id": 42, "title": "Example pull request", "state": "OPEN"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout


def test_bitbucket_pr_list_json_keeps_full_payload(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"description": "Long body"' in result.stdout


def test_bitbucket_pr_list_markdown_non_tty_uses_summary_payload(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
            "--output",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert "Example pull request" in result.stdout
    assert "Long body" not in result.stdout


def test_bitbucket_pr_list_uses_interactive_browser_for_markdown_tty(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module, "browse_collection", lambda source: calls.setdefault("source", source)
    )
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [{"id": 42, "title": "Example pull request"}],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: (
                    CollectionPage(
                        items=[{"id": 42, "title": "Example pull request"}],
                        start=start,
                        limit=limit,
                        total=1,
                    )
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert calls["source"].title == "Bitbucket pull requests"


def test_bitbucket_pr_list_interactive_source_uses_compact_preview_renderers(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    sample_item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "Example Author"},
        "title": "[FEAT] DEMO-1234 example preview change",
        "reviewers": [
            {"display_name": "reviewer-one"},
            {"display_name": "reviewer-two"},
            {"display_name": "reviewer-three"},
            {"display_name": "reviewer-four"},
        ],
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2026-04-27T13:19:55+00:00",
        "description": "Line one\nLine two\nLine three\nLine four",
        "diff": "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n",
    }
    captured: dict[str, str] = {}

    class FakeService:
        def list_page(self, project_key, repo_slug, state, start, limit):
            return CollectionPage(items=[sample_item], start=start, limit=limit, total=1)

        def get(self, project_key, repo_slug, pr_id):
            return sample_item

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "browse_collection",
        lambda source: captured.update(
            {
                "item": source.render_item(1, sample_item),
                "preview": source.render_preview(sample_item),
                "detail": source.render_detail(sample_item),
            }
        ),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert (
        captured["item"] == "24990  OPEN  Example Author  [FEAT] DEMO-1234 example preview change"
    )
    assert "Reviewers: reviewer-one, reviewer-two, reviewer-three, +1 more" in captured["preview"]
    assert captured["detail"].startswith("# 24990 - [FEAT] DEMO-1234 example preview change")
    assert "\x1b[" in captured["detail"]


def test_bitbucket_pr_list_interactive_source_fetches_detail_with_diff(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls: dict[str, object] = {}
    captured: dict[str, object] = {}

    class FakeService:
        def list_page(self, project_key, repo_slug, state, start, limit):
            return CollectionPage(
                items=[{"id": 42, "title": "Example pull request"}], start=0, limit=25, total=1
            )

        def get_detail(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"id": pr_id, "title": "Example pull request", "diff": "+example change\n"}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "browse_collection",
        lambda source: captured.setdefault("detail", source.fetch_detail({"id": 42})),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert captured["detail"]["diff"] == "+example change\n"


def test_bitbucket_pr_diff_outputs_markdown_diff_detail(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get_detail": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                    "state": "OPEN",
                    "diff": "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n",
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("# 42 - Example pull request")
    assert "## Diff" in result.stdout
    assert "+example change" in result.stdout
    assert "\x1b[" not in result.stdout


def test_bitbucket_pr_diff_outputs_colored_diff_for_tty(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_color_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get_detail": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                    "state": "OPEN",
                    "diff": "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n",
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
        ],
        color=True,
    )

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout
    assert "+example change" in result.stdout


def test_bitbucket_pr_list_falls_back_to_markdown_when_interactive_import_fails(
    monkeypatch,
) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module, "browse_collection", lambda source: (_ for _ in ()).throw(ImportError("boom"))
    )
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: (
                    CollectionPage(
                        items=[{"id": 42, "title": "Example pull request"}],
                        start=start,
                        limit=limit,
                        total=1,
                    )
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert "Example pull request" in result.stdout


def test_bitbucket_pr_list_falls_back_to_markdown_when_interactive_runtime_fails(
    monkeypatch,
) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module, "browse_collection", lambda source: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: (
                    CollectionPage(
                        items=[{"id": 42, "title": "Example pull request"}],
                        start=start,
                        limit=limit,
                        total=1,
                    )
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert "Example pull request" in result.stdout
