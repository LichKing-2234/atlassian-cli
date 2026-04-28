from atlassian_cli.output.formatters import to_json, to_yaml
from atlassian_cli.output.markdown import render_markdown
from atlassian_cli.output.modes import normalized_output


def render_output(value, *, output: str) -> str:
    output = normalized_output(output)
    if output == "markdown":
        return render_markdown(value)
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)
    raise ValueError(f"unsupported output mode: {output}")
