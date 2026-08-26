import re


def markdown_to_jira(text: str) -> str:
    protected: list[str] = []

    def protect(pattern: str, replacement, value: str) -> str:
        def store(match: re.Match[str]) -> str:
            marker = f"\x00JIRAMARKUP{len(protected)}\x00"
            protected.append(replacement(match))
            return marker

        return re.sub(pattern, store, value, flags=re.MULTILINE)

    valid_code_languages = {
        "bash",
        "c",
        "c#",
        "c++",
        "css",
        "diff",
        "go",
        "groovy",
        "html",
        "java",
        "javascript",
        "json",
        "perl",
        "php",
        "powershell",
        "python",
        "ruby",
        "sql",
        "swift",
        "xml",
        "yaml",
    }
    language_aliases = {
        "cpp": "c++",
        "cs": "c#",
        "js": "javascript",
        "py": "python",
        "sh": "bash",
        "ts": "javascript",
        "typescript": "javascript",
        "yml": "yaml",
    }

    def code_block(match: re.Match[str]) -> str:
        language = match.group(1).lower()
        language = language_aliases.get(language, language)
        opening = f"{{code:{language}}}" if language in valid_code_languages else "{code}"
        return f"{opening}{match.group(2)}{{code}}"

    output = protect(r"```([\w#+.-]*)\n([\s\S]+?)```", code_block, text)
    output = protect(r"`([^`]+)`", lambda match: "{{" + match.group(1) + "}}", output)
    output = protect(
        r"!\[([^\]\n]*)\]\(([^)\n\s]+)\)",
        lambda match: (
            f"!{match.group(2)}|alt={match.group(1)}!" if match.group(1) else f"!{match.group(2)}!"
        ),
        output,
    )
    output = protect(
        r"\[([^\]\n]+)\]\(([^)]+)\)",
        lambda match: f"[{match.group(1)}|{match.group(2)}]",
        output,
    )
    output = re.sub(
        r"^(?=[^\n]*\S)(.*?)\n([=-])+$",
        lambda match: f"h{1 if match.group(2)[0] == '=' else 2}. {match.group(1)}",
        output,
        flags=re.MULTILINE,
    )
    output = re.sub(
        r"^([#]+) (.*)$",
        lambda match: f"h{len(match.group(1))}. {match.group(2)}",
        output,
        flags=re.MULTILINE,
    )

    def convert_emphasis(line: str) -> str:
        line = re.sub(
            r"(?<=[^\W_])_+(?=[^\W_])",
            lambda match: r"\_" * len(match.group(0)),
            line,
        )
        if re.match(r"^[*_]+\s", line):
            return line
        return re.sub(
            r"([*_]+)(.*?)\1",
            lambda match: (
                ("_" if len(match.group(1)) == 1 else "*")
                + match.group(2)
                + ("_" if len(match.group(1)) == 1 else "*")
            ),
            line,
        )

    output = "\n".join(convert_emphasis(line) for line in output.split("\n"))
    output = re.sub(
        r"^([ \t]*)[-+*] (.*)$",
        lambda match: f"{'*' * (len(match.group(1)) // 2 + 1)} {match.group(2)}",
        output,
        flags=re.MULTILINE,
    )
    output = re.sub(
        r"^([ \t]*)\d+\. (.*)$",
        lambda match: f"{'#' * (len(match.group(1)) // 2 + 1)} {match.group(2)}",
        output,
        flags=re.MULTILINE,
    )
    output = re.sub(r"~~(.*?)~~", r"-\1-", output)

    lines = output.split("\n")
    index = 0
    while index < len(lines) - 1:
        if re.match(r"^\|[-\s|:]+\|$", lines[index + 1]) and re.match(r"^\|.*\|$", lines[index]):
            header = [cell.strip() for cell in lines[index].split("|")[1:-1]]
            lines[index] = "||" + "||".join(header) + "||"
            lines.pop(index + 1)
            while index + 1 < len(lines) and re.match(r"^\|.*\|$", lines[index + 1]):
                cells = [cell.strip() for cell in lines[index + 1].split("|")[1:-1]]
                lines[index + 1] = "|" + "|".join(cells) + "|"
                index += 1
        index += 1
    output = "\n".join(lines)

    for index, value in enumerate(protected):
        output = output.replace(f"\x00JIRAMARKUP{index}\x00", value)
    return output
