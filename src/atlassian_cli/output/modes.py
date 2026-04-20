def is_raw_output(output: str) -> bool:
    return output in {"raw-json", "raw-yaml"}


def normalized_output(output: str) -> str:
    if output == "raw-json":
        return "json"
    if output == "raw-yaml":
        return "yaml"
    return output
