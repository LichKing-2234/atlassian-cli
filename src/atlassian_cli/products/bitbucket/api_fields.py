from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

PlaceholderResolver = Callable[[str], str]

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-z]+)\}")
_SUPPORTED_PLACEHOLDERS = {"project", "repo", "branch"}
_FIELD_PATTERN = re.compile(
    r"^(?P<root>[^\[\]=]+)(?P<nested>(?:\[[^\[\]=]*\])*)(?:=(?P<value>.*))?$",
    re.DOTALL,
)


def validate_placeholders(value: str) -> None:
    for match in _PLACEHOLDER_PATTERN.finditer(value):
        name = match.group(1)
        if name not in _SUPPORTED_PLACEHOLDERS:
            raise ValueError(f"unknown placeholder: {name}")


def fill_placeholders(value: str, resolver: PlaceholderResolver) -> str:
    validate_placeholders(value)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return resolver(name)

    return _PLACEHOLDER_PATTERN.sub(replace, value)


def _typed_value(
    value: str,
    *,
    resolver: PlaceholderResolver,
    stdin: TextIO,
) -> object:
    if value.startswith("@"):
        source = value[1:]
        if source == "-":
            return stdin.read()
        return Path(source).read_text(encoding="utf-8")

    try:
        return int(value)
    except ValueError:
        pass

    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    return fill_placeholders(value, resolver)


def _field_parts(field: str) -> tuple[list[str], str | None]:
    match = _FIELD_PATTERN.fullmatch(field)
    if match is None:
        raise ValueError(f"invalid key: {field!r}")

    keys = [match.group("root"), *re.findall(r"\[([^\[\]=]*)\]", match.group("nested"))]
    value = match.group("value")
    if value is None:
        if len(keys) == 1:
            raise ValueError(f"invalid key: {field!r}")
        if keys[-1] != "":
            raise ValueError(f"field {field!r} requires a value separated by an '=' sign")
        return keys, None
    return keys, value


def _add_params_map(container: dict[str, object], key: str) -> dict[str, object]:
    if key in container:
        existing = container[key]
        if isinstance(existing, dict):
            return existing
        raise ValueError(f"expected map type under {key!r}, got {type(existing).__name__}")

    nested: dict[str, object] = {}
    container[key] = nested
    return nested


def _add_params_slice(
    container: dict[str, object],
    previous_key: str,
    new_key: str,
) -> dict[str, object]:
    if previous_key in container:
        existing = container[previous_key]
        if not isinstance(existing, list):
            raise ValueError(
                f"expected array type under {previous_key!r}, got {type(existing).__name__}"
            )
        if existing:
            last_item = existing[-1]
            if isinstance(last_item, dict) and (
                new_key not in last_item or isinstance(last_item[new_key], list)
            ):
                return last_item
        nested: dict[str, object] = {}
        existing.append(nested)
        return nested

    nested = {}
    container[previous_key] = [nested]
    return nested


def _apply_field_value(
    params: dict[str, object],
    field: str,
    *,
    keys: list[str],
    value: object,
    empty_array: bool,
) -> None:
    destination = params
    is_array = False
    subkey: str | None = None
    for key in keys:
        if key == "":
            is_array = True
            continue
        if subkey is not None:
            if is_array:
                destination = _add_params_slice(destination, subkey, key)
                is_array = False
            else:
                destination = _add_params_map(destination, subkey)
        subkey = key

    if subkey is None:
        raise ValueError(f"invalid key: {field!r}")

    if is_array:
        if empty_array:
            existing = destination.get(subkey)
            if existing is not None and not isinstance(existing, list):
                raise ValueError(
                    f"expected array type under {subkey!r}, got {type(existing).__name__}"
                )
            destination[subkey] = []
            return

        if subkey in destination:
            existing = destination[subkey]
            if not isinstance(existing, list):
                raise ValueError(
                    f"expected array type under {subkey!r}, got {type(existing).__name__}"
                )
            existing.append(value)
        else:
            destination[subkey] = [value]
        return

    if subkey in destination:
        raise ValueError(f"unexpected override existing field under {subkey!r}")
    destination[subkey] = value


def _apply_field(
    params: dict[str, object],
    field: str,
    *,
    typed: bool,
    resolver: PlaceholderResolver,
    stdin: TextIO,
) -> None:
    keys, raw_value = _field_parts(field)
    value = (
        _typed_value(raw_value, resolver=resolver, stdin=stdin)
        if typed and raw_value is not None
        else raw_value
    )
    _apply_field_value(
        params,
        field,
        keys=keys,
        value=value,
        empty_array=raw_value is None,
    )


def validate_api_fields(raw_fields: Sequence[str], typed_fields: Sequence[str]) -> None:
    params: dict[str, object] = {}
    marker = object()
    for field, typed in (
        *((field, False) for field in raw_fields),
        *((field, True) for field in typed_fields),
    ):
        keys, raw_value = _field_parts(field)
        if typed and raw_value is not None and not raw_value.startswith("@"):
            validate_placeholders(raw_value)
        value = None if raw_value is None else marker
        _apply_field_value(
            params,
            field,
            keys=keys,
            value=value,
            empty_array=raw_value is None,
        )


def parse_api_fields(
    raw_fields: Sequence[str],
    typed_fields: Sequence[str],
    *,
    resolver: PlaceholderResolver,
    stdin: TextIO,
) -> dict[str, object]:
    params: dict[str, object] = {}
    for field in raw_fields:
        _apply_field(
            params,
            field,
            typed=False,
            resolver=resolver,
            stdin=stdin,
        )
    for field in typed_fields:
        _apply_field(
            params,
            field,
            typed=True,
            resolver=resolver,
            stdin=stdin,
        )
    return params
