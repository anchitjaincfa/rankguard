from __future__ import annotations

import posixpath
import re
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "gbraid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "wbraid",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)
HEX_PAIR_RE = re.compile(r"^[0-9A-Fa-f]{2}$")
UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
PATH_SAFE = "/-._~!$&'()*+,;=:@%"


def normalize_url(url: str, *, keep_query: bool = False) -> str:
    """Normalize a URL for matching and comparison.

    This is deliberately conservative: it normalizes casing and common tracking
    params, but does not invent business-specific rewrites.
    """
    raw = url.strip()
    if not raw:
        raise ValueError("URL cannot be empty")

    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    try:
        hostname = _normalize_hostname(parsed.hostname or "")
    except ValueError as exc:
        raise ValueError(f"URL has an invalid hostname: {url!r}") from exc
    if not hostname:
        raise ValueError(f"URL is missing a hostname: {url!r}")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"URL has an invalid port: {url!r}") from exc

    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{netloc}:{port}"

    raw_path = parsed.path or "/"
    if parsed.params:
        raw_path = f"{raw_path};{parsed.params}"
    path = _normalize_path(raw_path)

    query = ""
    if keep_query and parsed.query:
        pairs = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            lower_key = key.lower()
            if lower_key.startswith("utm_") or lower_key in TRACKING_QUERY_KEYS:
                continue
            pairs.append((key, value))
        query = urlencode(pairs, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def normalized_path(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return (parsed.path or "/").lower().rstrip("/") or "/"


def path_segments(url: str) -> list[str]:
    path = normalized_path(url)
    return [segment for segment in path.split("/") if segment]


def content_segments(url: str) -> list[str]:
    segments = path_segments(url)
    if segments and LOCALE_RE.match(segments[0]):
        return segments[1:]
    return segments


def section_key(url: str) -> str:
    segments = content_segments(url)
    return segments[0] if segments else ""


def tail_slug(url: str) -> str:
    segments = content_segments(url)
    return segments[-1] if segments else ""


def url_tokens(url: str) -> set[str]:
    tokens: set[str] = set()
    for segment in content_segments(url):
        tokens.update(segment_tokens(segment))
    return tokens


def segment_tokens(segment: str) -> set[str]:
    token_text = unquote(segment).lower()
    return {_stem_lightly(token) for token in TOKEN_RE.findall(token_text) if len(token) > 1}


def title_tokens(title: str) -> set[str]:
    return {_stem_lightly(token) for token in TOKEN_RE.findall(title.lower()) if len(token) > 2}


def _stem_lightly(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _normalize_hostname(hostname: str) -> str:
    host = hostname.lower()
    if not host or host != host.strip() or any(char.isspace() for char in host):
        raise ValueError("hostname cannot be empty or contain whitespace")

    if ":" in host:
        return host

    host = host.rstrip(".")
    if not host:
        raise ValueError("hostname cannot be empty")
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("hostname cannot be IDNA encoded") from exc


def _normalize_path(path: str) -> str:
    path = _decode_unreserved_percent_escapes(path.replace("\\", "/"))
    path = re.sub(r"/+", "/", path)

    trailing_slash = path.endswith("/")
    path = posixpath.normpath(path)
    if path == ".":
        path = "/"
    if not path.startswith("/"):
        path = "/" + path
    if trailing_slash and path != "/":
        path += "/"
    if path != "/":
        path = path.rstrip("/")
    return quote(path, safe=PATH_SAFE)


def _decode_unreserved_percent_escapes(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "%" and index + 2 < len(value):
            pair = value[index + 1 : index + 3]
            if HEX_PAIR_RE.match(pair):
                decoded = chr(int(pair, 16))
                if decoded in UNRESERVED:
                    result.append(decoded)
                else:
                    result.append("%" + pair.upper())
                index += 3
                continue
        if char == "%":
            result.append("%25")
        else:
            result.append(char)
        index += 1
    return "".join(result)
