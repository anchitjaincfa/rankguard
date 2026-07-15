from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import RedirectCandidate, URLRecord

URL_COLUMNS = ("url", "address", "loc", "location", "old_url", "new_url", "source", "source_url")
TITLE_COLUMNS = ("title", "page_title", "h1", "name")
STATUS_COLUMNS = ("status", "status_code", "status code", "http_status", "response_code", "response code")
CANONICAL_COLUMNS = ("canonical", "canonical_url")
REDIRECT_OLD_COLUMNS = ("old_url", "source_url", "source", "from")
REDIRECT_NEW_COLUMNS = ("new_url", "target_url", "destination_url", "target", "to")
CSV_DELIMITERS = ",\t;"


def load_url_records(location: str, *, _seen: set[str] | None = None) -> list[URLRecord]:
    text = read_text(location)
    if not text.strip():
        return []

    sample = text.lstrip("\ufeff \t\r\n")[:500].lower()
    if _looks_like_sitemap(sample):
        records = _load_sitemap(location, text, _seen=_seen)
    else:
        delimiter = _detect_csv_delimiter(location, text)
        records = _load_csv(location, text, delimiter=delimiter) if delimiter else _load_plaintext(location, text)
    return _dedupe_records(records)


def read_text(location: str, *, timeout: int = 30) -> str:
    if location == "-":
        return sys.stdin.read()
    if _is_http(location):
        request = Request(location, headers={"User-Agent": "RankGuard/0.1"})
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            if charset.lower().replace("_", "-") == "utf-8":
                charset = "utf-8-sig"
            return response.read().decode(charset, errors="replace")
    return Path(location).expanduser().read_text(encoding="utf-8-sig")


def write_redirect_csv(candidates: Iterable[RedirectCandidate], path: str | Path) -> None:
    _ensure_parent(path)
    with Path(path).expanduser().open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["old_url", "new_url", "score", "confidence", "reason", "alternatives"],
        )
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "old_url": candidate.old_url,
                    "new_url": candidate.new_url,
                    "score": f"{candidate.score:.3f}",
                    "confidence": candidate.confidence,
                    "reason": candidate.reason,
                    "alternatives": json.dumps(candidate.alternatives),
                }
            )


def load_redirect_csv(path: str | Path) -> list[RedirectCandidate]:
    with Path(path).expanduser().open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        field_map = _field_map(reader.fieldnames or [])
        old_col = _first_existing(field_map, REDIRECT_OLD_COLUMNS)
        new_col = _first_existing(field_map, REDIRECT_NEW_COLUMNS)
        if not old_col or not new_col:
            raise ValueError("Redirect CSV must include old_url and new_url columns.")
        score_col = _first_existing(field_map, ("score", "match_score"))
        confidence_col = _first_existing(field_map, ("confidence",))
        reason_col = _first_existing(field_map, ("reason",))
        alternatives_col = _first_existing(field_map, ("alternatives",))
        candidates = []
        for line_number, row in enumerate(reader, start=2):
            if _row_is_blank(row):
                continue
            old_url = _cell(row, old_col)
            new_url = _cell(row, new_col)
            if not old_url or not new_url:
                raise ValueError(f"Redirect CSV row {line_number} must include old_url and new_url.")
            candidates.append(
                RedirectCandidate(
                    old_url=old_url,
                    new_url=new_url,
                    score=_parse_score(_cell(row, score_col), path, line_number),
                    confidence=_cell(row, confidence_col) or "planned",
                    reason=_cell(row, reason_col) or "imported",
                    alternatives=_parse_alternatives(_cell(row, alternatives_col), path, line_number),
                )
            )
        return candidates


def write_json(data: object, path: str | Path) -> None:
    _ensure_parent(path)
    Path(path).expanduser().write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _load_sitemap(location: str, text: str, *, _seen: set[str] | None = None) -> list[URLRecord]:
    seen = _seen if _seen is not None else set()
    if location in seen:
        return []
    seen.add(location)

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ValueError(f"Could not parse XML sitemap {location}: {exc}") from exc

    tag = _strip_namespace(root.tag)
    if tag == "sitemapindex":
        records: list[URLRecord] = []
        for loc in root.iter():
            if _strip_namespace(loc.tag) != "loc" or not loc.text:
                continue
            nested_location = _resolve_sitemap_location(location, loc.text.strip())
            records.extend(load_url_records(nested_location, _seen=seen))
        return records

    records = []
    for url_node in root.iter():
        if _strip_namespace(url_node.tag) != "url":
            continue
        loc = ""
        meta: dict[str, str] = {}
        for child in url_node:
            key = _strip_namespace(child.tag)
            value = (child.text or "").strip()
            if key == "loc":
                loc = value
            elif value:
                meta[key] = value
        if loc:
            records.append(URLRecord(url=loc, source=location, meta=meta))
    if tag == "urlset":
        return records
    raise ValueError(f"Unsupported sitemap XML root in {location}: {tag}")


def _load_csv(location: str, text: str, *, delimiter: str = ",") -> list[URLRecord]:
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return _load_plaintext(location, text)

    field_map = _field_map(reader.fieldnames)
    url_col = _first_existing(field_map, URL_COLUMNS)
    if not url_col:
        found = ", ".join(_clean_header(name) for name in reader.fieldnames if name) or "none"
        raise ValueError(
            f"Could not find a URL column in {location}. "
            f"Tried: {', '.join(URL_COLUMNS)}. Found: {found}."
        )

    title_col = _first_existing(field_map, TITLE_COLUMNS)
    status_col = _first_existing(field_map, STATUS_COLUMNS)
    canonical_col = _first_existing(field_map, CANONICAL_COLUMNS)

    records = []
    for row in reader:
        url = _cell(row, url_col)
        if not url or url.startswith("#"):
            continue
        records.append(
            URLRecord(
                url=url,
                title=_cell(row, title_col),
                status=_parse_status(_cell(row, status_col)),
                canonical=_cell(row, canonical_col),
                source=location,
                meta=_row_meta(row),
            )
        )
    return records


def _load_plaintext(location: str, text: str) -> list[URLRecord]:
    records = []
    for line in text.splitlines():
        value = line.strip().lstrip("\ufeff")
        if value and not value.startswith("#"):
            if not records and _normalize_column_name(value) in {_normalize_column_name(name) for name in URL_COLUMNS}:
                continue
            records.append(URLRecord(url=value, source=location))
    return records


def _first_existing(lower_to_actual: dict[str, str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        normalized = _normalize_column_name(candidate)
        if normalized in lower_to_actual:
            return lower_to_actual[normalized]
    return ""


def _looks_like_sitemap(sample: str) -> bool:
    return sample.startswith("<?xml") or "<urlset" in sample or "<sitemapindex" in sample


def _detect_csv_delimiter(location: str, text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return ""

    first_line = lines[0].lstrip("\ufeff")
    if not any(delimiter in first_line for delimiter in CSV_DELIMITERS):
        return ""

    sample = "\n".join(lines[:20])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=CSV_DELIMITERS).delimiter
    except csv.Error:
        delimiter = max(CSV_DELIMITERS, key=first_line.count)
        if first_line.count(delimiter) == 0:
            return ""

    try:
        first_row = next(csv.reader([first_line], delimiter=delimiter))
    except csv.Error:
        return ""

    if len(first_row) < 2:
        return ""
    if _first_existing(_field_map(first_row), URL_COLUMNS):
        return delimiter
    return delimiter if _looks_like_delimited_file(location) else ""


def _looks_like_delimited_file(location: str) -> bool:
    if location == "-":
        return False
    suffix = Path(urlparse(str(location)).path).suffix.lower()
    return suffix in {".csv", ".tsv"}


def _field_map(fieldnames: Iterable[str | None]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for name in fieldnames:
        if name is None:
            continue
        clean_name = _clean_header(name)
        normalized = _normalize_column_name(clean_name)
        if normalized and normalized not in fields:
            fields[normalized] = name
    return fields


def _clean_header(name: str) -> str:
    return name.lstrip("\ufeff").strip()


def _normalize_column_name(name: str) -> str:
    return "".join(char for char in name.lstrip("\ufeff").lower() if char.isalnum())


def _cell(row: dict[str | None, object], column: str) -> str:
    if not column:
        return ""
    value = row.get(column)
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _row_meta(row: dict[str | None, object]) -> dict[str, str]:
    meta: dict[str, str] = {}
    for key in row:
        if key is None:
            continue
        clean_value = _cell(row, key)
        if clean_value:
            meta[_clean_header(key)] = clean_value
    return meta


def _row_is_blank(row: dict[str | None, object]) -> bool:
    return not any(_cell(row, key or "") for key in row)


def _parse_status(value: str) -> int | None:
    if not value:
        return None
    token = value.split()[0]
    try:
        return int(float(token))
    except ValueError:
        return None


def _parse_score(value: str, path: str | Path, line_number: int) -> float:
    if not value:
        return 1.0
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Redirect CSV row {line_number} in {path} has invalid score: {value}") from None


def _parse_alternatives(value: str, path: str | Path, line_number: int) -> list[tuple[str, float]]:
    if not value:
        return []
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Redirect CSV row {line_number} in {path} has invalid alternatives JSON.") from exc

    if not isinstance(raw, list):
        raise ValueError(f"Redirect CSV row {line_number} in {path} alternatives must be a JSON list.")

    alternatives: list[tuple[str, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            raise ValueError(f"Redirect CSV row {line_number} in {path} has invalid alternative entry.")
        try:
            alternatives.append((str(item[0]), float(item[1])))
        except (TypeError, ValueError):
            raise ValueError(f"Redirect CSV row {line_number} in {path} has invalid alternative score.") from None
    return alternatives


def _dedupe_records(records: Iterable[URLRecord]) -> list[URLRecord]:
    unique: list[URLRecord] = []
    seen: set[str] = set()
    for record in records:
        if record.url in seen:
            continue
        seen.add(record.url)
        unique.append(record)
    return unique


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_http(location: str) -> bool:
    return urlparse(location).scheme in {"http", "https"}


def _resolve_sitemap_location(base: str, loc: str) -> str:
    if _is_http(loc):
        return loc
    if _is_http(base):
        return urljoin(base, loc)
    return str((Path(base).parent / loc).resolve())


def _ensure_parent(path: str | Path) -> None:
    parent = Path(path).expanduser().parent
    if parent != Path("."):
        parent.mkdir(parents=True, exist_ok=True)
