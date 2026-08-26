import base64
import binascii
import re
from urllib.parse import parse_qs, urlsplit

_TINY_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,11}")
_PAGE_ID_PATH_PATTERN = re.compile(r"(?:^|/)pages/([0-9]+)(?:/|$)")
_TINY_LINK_PATH_PATTERN = re.compile(r"(?:^|/)x/([A-Za-z0-9_-]+)(?:/|$)")
_MAX_PAGE_ID = (1 << 63) - 1


def _encode_tiny_id(page_id: int) -> str:
    encoded = base64.b64encode(page_id.to_bytes(8, byteorder="little"))
    return encoded.decode("ascii").rstrip("=").rstrip("A").replace("/", "-").replace("+", "_")


def _decode_tiny_id(encoded: str) -> int | None:
    if _TINY_ID_PATTERN.fullmatch(encoded) is None:
        return None
    padded = encoded.replace("-", "/").replace("_", "+").ljust(11, "A") + "="
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(decoded) != 8:
        return None
    page_id = int.from_bytes(decoded, byteorder="little")
    if not 0 < page_id <= _MAX_PAGE_ID or _encode_tiny_id(page_id) != encoded:
        return None
    return page_id


def resolve_page_id(reference: str) -> str:
    if re.fullmatch(r"[0-9]+", reference):
        return reference
    parsed = urlsplit(reference)
    page_match = _PAGE_ID_PATH_PATTERN.search(parsed.path)
    if page_match:
        return page_match.group(1)
    query_page_ids = parse_qs(parsed.query).get("pageId", [])
    if len(query_page_ids) == 1 and re.fullmatch(r"[0-9]+", query_page_ids[0]):
        return query_page_ids[0]
    tiny_match = _TINY_LINK_PATH_PATTERN.search(parsed.path)
    if tiny_match:
        resolved = _decode_tiny_id(tiny_match.group(1))
        if resolved is not None:
            return str(resolved)
    return reference
