"""RankGuard: local-first SEO migration guardrails."""

from .matcher import generate_redirect_map
from .models import MappingResult, RedirectCandidate, URLRecord

__all__ = [
    "MappingResult",
    "RedirectCandidate",
    "URLRecord",
    "generate_redirect_map",
]

__version__ = "0.1.0"
