from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timezone

from .models import AuditIssue, MappingResult, RedirectValidation


def mapping_issues(result: MappingResult) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for record in result.unmatched_old:
        issues.append(
            AuditIssue(
                severity="critical",
                code="unmatched_old_url",
                url=record.url,
                message="Old URL has no redirect target above the confidence threshold.",
            )
        )
    for candidate in result.candidates:
        if candidate.confidence == "low":
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="low_confidence_mapping",
                    url=candidate.old_url,
                    message="Redirect target needs human review.",
                    detail=f"Candidate target: {candidate.new_url} ({candidate.score:.3f})",
                )
            )
    for target, sources in result.conflicts.items():
        issues.append(
            AuditIssue(
                severity="warning",
                code="many_to_one_redirect",
                url=target,
                message=f"{len(sources)} old URLs map to the same target.",
                detail=", ".join(sources[:8]),
            )
        )
    for record in result.orphan_new[:50]:
        issues.append(
            AuditIssue(
                severity="notice",
                code="orphan_new_url",
                url=record.url,
                message="New URL has no old URL mapped to it.",
            )
        )
    return issues


def mapping_summary(result: MappingResult) -> dict[str, int | float]:
    confidence = Counter(candidate.confidence for candidate in result.candidates)
    return {
        "mapped": len(result.candidates),
        "unmatched_old": len(result.unmatched_old),
        "orphan_new": len(result.orphan_new),
        "conflicts": len(result.conflicts),
        "high_confidence": confidence["high"],
        "medium_confidence": confidence["medium"],
        "low_confidence": confidence["low"],
        "min_score": result.min_score,
    }


def render_mapping_html(result: MappingResult, *, old_source: str, new_source: str) -> str:
    issues = mapping_issues(result)
    summary = mapping_summary(result)
    rows = "\n".join(
        _candidate_row(candidate.old_url, candidate.new_url, candidate.score, candidate.confidence, candidate.reason)
        for candidate in result.candidates[:500]
    )
    issue_rows = "\n".join(_issue_row(issue) for issue in issues[:500])
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RankGuard Migration Report</title>
  <style>
    :root {{ color-scheme: light; --ink:#1b1f23; --muted:#59636e; --line:#d8dee4; --critical:#b42318; --warning:#a15c07; --notice:#0969da; --ok:#1a7f37; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:#f6f8fa; }}
    header {{ padding:32px; background:#ffffff; border-bottom:1px solid var(--line); }}
    main {{ max-width:1180px; margin:0 auto; padding:24px; }}
    h1, h2 {{ margin:0 0 12px; letter-spacing:0; }}
    p {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
    .metric {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; }}
    .metric strong {{ display:block; font-size:28px; line-height:1.1; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    th, td {{ padding:10px 12px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; font-size:14px; }}
    th {{ background:#f6f8fa; color:#424a53; }}
    code {{ word-break:break-word; }}
    .critical {{ color:var(--critical); font-weight:700; }}
    .warning {{ color:var(--warning); font-weight:700; }}
    .notice {{ color:var(--notice); font-weight:700; }}
    .high {{ color:var(--ok); font-weight:700; }}
    .medium {{ color:var(--warning); font-weight:700; }}
    .low {{ color:var(--critical); font-weight:700; }}
    section {{ margin-top:28px; }}
  </style>
</head>
<body>
  <header>
    <h1>RankGuard Migration Report</h1>
    <p>Generated {html.escape(generated)} from <code>{html.escape(old_source)}</code> to <code>{html.escape(new_source)}</code>.</p>
  </header>
  <main>
    <section class="grid">
      {_metric("Mapped", summary["mapped"])}
      {_metric("Unmatched old", summary["unmatched_old"])}
      {_metric("Low confidence", summary["low_confidence"])}
      {_metric("Many-to-one targets", summary["conflicts"])}
      {_metric("Orphan new", summary["orphan_new"])}
    </section>
    <section>
      <h2>Priority Issues</h2>
      <table>
        <thead><tr><th>Severity</th><th>Code</th><th>URL</th><th>Message</th></tr></thead>
        <tbody>{issue_rows or '<tr><td colspan="4">No priority issues found.</td></tr>'}</tbody>
      </table>
    </section>
    <section>
      <h2>Redirect Candidates</h2>
      <table>
        <thead><tr><th>Old URL</th><th>New URL</th><th>Score</th><th>Confidence</th><th>Reason</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="5">No mappings generated.</td></tr>'}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def render_validation_html(results: list[RedirectValidation]) -> str:
    ok_count = sum(1 for result in results if result.ok)
    issue_count = sum(len(result.issues) for result in results)
    severity_counts = Counter(issue.severity for result in results for issue in result.issues)
    rows = "\n".join(_validation_row(result) for result in results)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RankGuard Launch Validation</title>
  <style>
    :root {{ color-scheme: light; --ink:#1b1f23; --muted:#59636e; --line:#d8dee4; --critical:#b42318; --warning:#a15c07; --notice:#0969da; --ok:#1a7f37; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:#f6f8fa; }}
    header, main {{ max-width:1180px; margin:0 auto; padding:24px; }}
    header {{ background:#fff; border-bottom:1px solid var(--line); max-width:none; }}
    h1, h2 {{ margin:0 0 12px; letter-spacing:0; }}
    p {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:14px; }}
    th {{ background:#f6f8fa; }}
    code {{ word-break:break-word; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:24px; }}
    .metric {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; }}
    .metric strong {{ display:block; font-size:28px; line-height:1.1; }}
    .metric span, .muted {{ color:var(--muted); }}
    .ok {{ color:var(--ok); font-weight:700; }}
    .fail, .critical {{ color:var(--critical); font-weight:700; }}
    .warning {{ color:var(--warning); font-weight:700; }}
    .notice {{ color:var(--notice); font-weight:700; }}
    .issues, .chain {{ margin:0; padding-left:18px; }}
    .issues li, .chain li {{ margin:0 0 6px; }}
    .issues li:last-child, .chain li:last-child {{ margin-bottom:0; }}
  </style>
</head>
<body>
  <header>
    <h1>RankGuard Launch Validation</h1>
    <p>Generated {html.escape(generated)}. {ok_count} passed, {len(results) - ok_count} failed, {issue_count} issues.</p>
  </header>
  <main>
    <section class="grid">
      {_metric("Passed", ok_count)}
      {_metric("Failed", len(results) - ok_count)}
      {_metric("Critical issues", severity_counts["critical"])}
      {_metric("Warnings", severity_counts["warning"])}
      {_metric("Total issues", issue_count)}
    </section>
    <table>
      <thead><tr><th>Status</th><th>Source</th><th>Expected</th><th>Final</th><th>Issues</th><th>Chain</th></tr></thead>
      <tbody>{rows or '<tr><td colspan="6">No redirects validated.</td></tr>'}</tbody>
    </table>
  </main>
</body>
</html>
"""


def _candidate_row(old_url: str, new_url: str, score: float, confidence: str, reason: str) -> str:
    return (
        "<tr>"
        f"<td><code>{html.escape(old_url)}</code></td>"
        f"<td><code>{html.escape(new_url)}</code></td>"
        f"<td>{score:.3f}</td>"
        f"<td class=\"{html.escape(confidence)}\">{html.escape(confidence)}</td>"
        f"<td>{html.escape(reason)}</td>"
        "</tr>"
    )


def _issue_row(issue: AuditIssue) -> str:
    detail = f" {html.escape(issue.detail)}" if issue.detail else ""
    return (
        "<tr>"
        f"<td class=\"{html.escape(issue.severity)}\">{html.escape(issue.severity)}</td>"
        f"<td>{html.escape(issue.code)}</td>"
        f"<td><code>{html.escape(issue.url)}</code></td>"
        f"<td>{html.escape(issue.message)}{detail}</td>"
        "</tr>"
    )


def _validation_row(result: RedirectValidation) -> str:
    status = "pass" if result.ok else "fail"
    status_class = "ok" if result.ok else "fail"
    return (
        "<tr>"
        f"<td class=\"{status_class}\">{status}</td>"
        f"<td><code>{html.escape(result.source_url)}</code></td>"
        f"<td><code>{html.escape(result.expected_url)}</code></td>"
        f"<td>{_final_cell(result)}</td>"
        f"<td>{_validation_issues(result)}</td>"
        f"<td>{_validation_chain(result)}</td>"
        "</tr>"
    )


def _final_cell(result: RedirectValidation) -> str:
    status = f"HTTP {result.final_status}" if result.final_status is not None else "No status"
    return f'<span class="muted">{html.escape(status)}</span><br><code>{html.escape(result.final_url)}</code>'


def _validation_issues(result: RedirectValidation) -> str:
    if result.issues:
        items = []
        for issue in result.issues:
            detail = f" {html.escape(issue.detail)}" if issue.detail else ""
            items.append(
                "<li>"
                f"<strong class=\"{html.escape(issue.severity)}\">{html.escape(issue.severity)}</strong> "
                f"<code>{html.escape(issue.code)}</code>: {html.escape(issue.message)}{detail}"
                "</li>"
            )
        return f'<ul class="issues">{"".join(items)}</ul>'
    if result.error:
        return html.escape(result.error)
    return '<span class="muted">No issues.</span>'


def _validation_chain(result: RedirectValidation) -> str:
    if not result.hops:
        return '<span class="muted">No response.</span>'
    items = []
    for hop in result.hops:
        location = ""
        if hop.location:
            location = f' <span class="muted">Location:</span> <code>{html.escape(hop.location)}</code>'
        items.append(f"<li>HTTP {hop.status} <code>{html.escape(hop.url)}</code>{location}</li>")
    return f'<ol class="chain">{"".join(items)}</ol>'


def _metric(label: str, value: int | float) -> str:
    return f'<div class="metric"><strong>{value}</strong><span>{html.escape(label)}</span></div>'
