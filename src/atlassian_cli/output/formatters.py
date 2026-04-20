import json

import yaml


def to_json(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def to_yaml(value) -> str:
    return yaml.safe_dump(value, sort_keys=False)
