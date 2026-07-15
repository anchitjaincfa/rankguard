from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class URLRecord:
    url: str
    title: str = ""
    status: int | None = None
    canonical: str = ""
    source: str = ""
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class RedirectCandidate:
    old_url: str
    new_url: str
    score: float
    confidence: str
    reason: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class MappingResult:
    candidates: list[RedirectCandidate]
    unmatched_old: list[URLRecord]
    orphan_new: list[URLRecord]
    conflicts: dict[str, list[str]]
    min_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditIssue:
    severity: str
    code: str
    url: str
    message: str
    detail: str = ""


@dataclass
class ProbeHop:
    url: str
    status: int
    location: str = ""


@dataclass
class RedirectValidation:
    source_url: str
    expected_url: str
    final_url: str
    final_status: int | None
    ok: bool
    issues: list[AuditIssue]
    hops: list[ProbeHop]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
