from enum import StrEnum


class OutputMode(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    RAW_JSON = "raw-json"
    RAW_YAML = "raw-yaml"


def is_raw_output(output: str) -> bool:
    return output in {OutputMode.RAW_JSON, OutputMode.RAW_YAML}


def normalized_output(output: str) -> str:
    if output == OutputMode.RAW_JSON:
        return OutputMode.JSON
    if output == OutputMode.RAW_YAML:
        return OutputMode.YAML
    return output


def is_machine_output(output: str) -> bool:
    return normalized_output(output) in {OutputMode.JSON, OutputMode.YAML}
