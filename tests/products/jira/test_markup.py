from atlassian_cli.products.jira.markup import markdown_to_jira


def test_markdown_to_jira_converts_common_semantic_markup() -> None:
    assert (
        markdown_to_jira("# Example Page\n\n- **example response**\n- [Example Page](DEMO)")
        == "h1. Example Page\n\n* *example response*\n* [Example Page|DEMO]"
    )


def test_markdown_to_jira_protects_code_tables_and_literal_underscores() -> None:
    markdown = (
        "Use custom_field_name.\n\n"
        "1. Run `example response`\n"
        "  1. Inspect the result\n\n"
        "```python\nprint('example response')\n```\n\n"
        "| Name | Status |\n"
        "|------|--------|\n"
        "| DEMO | **Ready** |"
    )

    assert markdown_to_jira(markdown) == (
        "Use custom\\_field\\_name.\n\n"
        "# Run {{example response}}\n"
        "## Inspect the result\n\n"
        "{code:python}print('example response')\n{code}\n\n"
        "||Name||Status||\n"
        "|DEMO|*Ready*|"
    )
