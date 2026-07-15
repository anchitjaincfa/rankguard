from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import AuditIssue, ProbeHop, RedirectCandidate, RedirectValidation
from .normalize import normalize_url

REDIRECT_STATUSES = {300, 301, 302, 303, 305, 307, 308}
TEMPORARY_REDIRECT_STATUSES = {302, 303, 307}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def validate_redirect(candidate: RedirectCandidate, *, timeout: int = 15, max_hops: int = 8) -> RedirectValidation:
    if max_hops < 0:
        raise ValueError("max_hops cannot be negative")

    hops: list[ProbeHop] = []
    issues: list[AuditIssue] = []
    current = candidate.old_url
    opener = build_opener(_NoRedirect)

    try:
        for _ in range(max_hops + 1):
            status, location = _request_once(opener, current, timeout=timeout)
            hops.append(ProbeHop(url=current, status=status, location=location))

            if _is_redirect(status):
                if not location:
                    issues.append(
                        AuditIssue(
                            severity="critical",
                            code="missing_redirect_location",
                            url=candidate.old_url,
                            message="Redirect response did not include a Location header.",
                            detail=f"HTTP {status} at {current}",
                        )
                    )
                    return _validation(candidate, current, status, False, issues, hops)

                next_url = urljoin(current, location)
                if any(
                    normalize_url(hop.url, keep_query=True) == normalize_url(next_url, keep_query=True)
                    for hop in hops
                ):
                    issues.append(
                        AuditIssue(
                            severity="critical",
                            code="redirect_loop",
                            url=candidate.old_url,
                            message="Redirect chain loops back to a previously seen URL.",
                            detail=f"{current} -> {next_url}",
                        )
                    )
                    return _validation(candidate, next_url, status, False, issues, hops)
                current = next_url
                continue

            final_url = current
            _add_status_issues(candidate, status, final_url, issues)
            _add_target_issues(candidate, final_url, issues)
            _add_chain_issues(candidate, hops, issues)
            return _validation(candidate, final_url, status, not issues, issues, hops)

        issues.append(
            AuditIssue(
                severity="critical",
                code="too_many_redirects",
                url=candidate.old_url,
                message=f"Redirect chain exceeded {max_hops} hops.",
                detail=f"Last checked URL: {current}",
            )
        )
        _add_chain_issues(candidate, hops, issues)
        return _validation(candidate, current, hops[-1].status if hops else None, False, issues, hops)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        issues.append(
            AuditIssue(
                severity="critical",
                code="request_failed",
                url=candidate.old_url,
                message="Could not validate redirect.",
                detail=str(exc),
            )
        )
        return RedirectValidation(
            source_url=candidate.old_url,
            expected_url=candidate.new_url,
            final_url=current,
            final_status=hops[-1].status if hops else None,
            ok=False,
            issues=issues,
            hops=hops,
            error=str(exc),
        )


def validate_redirects(
    candidates: list[RedirectCandidate],
    *,
    timeout: int = 15,
    max_hops: int = 8,
    limit: int | None = None,
) -> list[RedirectValidation]:
    if limit is not None and limit < 0:
        raise ValueError("limit cannot be negative")
    selected = candidates if limit is None else candidates[:limit]
    return [validate_redirect(candidate, timeout=timeout, max_hops=max_hops) for candidate in selected]


def _request_once(opener, url: str, *, timeout: int) -> tuple[int, str]:
    try:
        return _open_once(opener, url, method="HEAD", timeout=timeout)
    except HTTPError as exc:
        if exc.code in {405, 501}:
            _close_error(exc)
            try:
                return _open_once(opener, url, method="GET", timeout=timeout)
            except HTTPError as get_exc:
                return _error_status(get_exc)
        return _error_status(exc)


def _open_once(opener, url: str, *, method: str, timeout: int) -> tuple[int, str]:
    request = Request(url, method=method, headers={"User-Agent": "RankGuard/0.1"})
    response = opener.open(request, timeout=timeout)
    try:
        return int(response.status), response.headers.get("Location", "")
    finally:
        response.close()


def _error_status(exc: HTTPError) -> tuple[int, str]:
    try:
        return int(exc.code), exc.headers.get("Location", "")
    finally:
        _close_error(exc)


def _close_error(exc: HTTPError) -> None:
    try:
        exc.close()
    except Exception:
        pass


def _add_status_issues(candidate: RedirectCandidate, status: int, final_url: str, issues: list[AuditIssue]) -> None:
    if not (200 <= status < 300):
        issues.append(
            AuditIssue(
                severity="critical",
                code="bad_final_status",
                url=candidate.old_url,
                message=f"Final URL returned HTTP {status}.",
                detail=final_url,
            )
        )


def _add_target_issues(candidate: RedirectCandidate, final_url: str, issues: list[AuditIssue]) -> None:
    try:
        final_normalized = normalize_url(final_url, keep_query=True)
        expected_normalized = normalize_url(candidate.new_url, keep_query=True)
    except ValueError as exc:
        issues.append(
            AuditIssue(
                severity="critical",
                code="invalid_target_url",
                url=candidate.old_url,
                message="Could not normalize the planned or final redirect target.",
                detail=str(exc),
            )
        )
        return

    if final_normalized != expected_normalized:
        issues.append(
            AuditIssue(
                severity="critical",
                code="target_mismatch",
                url=candidate.old_url,
                message="Final URL does not match the planned redirect target.",
                detail=f"Expected {candidate.new_url}, got {final_url}",
            )
        )


def _add_chain_issues(candidate: RedirectCandidate, hops: list[ProbeHop], issues: list[AuditIssue]) -> None:
    redirect_hops = [hop for hop in hops if _is_redirect(hop.status)]
    if len(redirect_hops) == 0:
        issues.append(
            AuditIssue(
                severity="critical",
                code="missing_redirect",
                url=candidate.old_url,
                message="Old URL did not redirect.",
            )
        )
    temporary_hops = [hop for hop in redirect_hops if hop.status in TEMPORARY_REDIRECT_STATUSES]
    if temporary_hops:
        issues.append(
            AuditIssue(
                severity="warning",
                code="temporary_redirect",
                url=candidate.old_url,
                message="Redirect chain uses a temporary status; use 301 or 308 for permanent migrations.",
                detail=_format_hops(temporary_hops),
            )
        )
    if len(redirect_hops) > 1:
        issues.append(
            AuditIssue(
                severity="warning",
                code="redirect_chain",
                url=candidate.old_url,
                message=f"Redirect chain has {len(redirect_hops)} hops.",
                detail=_format_hops(redirect_hops),
            )
        )


def _is_redirect(status: int) -> bool:
    return status in REDIRECT_STATUSES


def _format_hops(hops: list[ProbeHop]) -> str:
    shown = "; ".join(f"HTTP {hop.status} at {hop.url}" for hop in hops[:5])
    if len(hops) > 5:
        shown = f"{shown}; +{len(hops) - 5} more"
    return shown


def _validation(
    candidate: RedirectCandidate,
    final_url: str,
    final_status: int | None,
    ok: bool,
    issues: list[AuditIssue],
    hops: list[ProbeHop],
) -> RedirectValidation:
    return RedirectValidation(
        source_url=candidate.old_url,
        expected_url=candidate.new_url,
        final_url=final_url,
        final_status=final_status,
        ok=ok,
        issues=issues,
        hops=hops,
    )
