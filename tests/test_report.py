import unittest

from rankguard.models import (
    AuditIssue,
    MappingResult,
    ProbeHop,
    RedirectCandidate,
    RedirectValidation,
    URLRecord,
)
from rankguard.report import mapping_issues, render_mapping_html, render_validation_html


class ReportTests(unittest.TestCase):
    def test_report_contains_unmatched_issue(self):
        result = MappingResult(
            candidates=[],
            unmatched_old=[URLRecord("https://old.test/legacy-only-page")],
            orphan_new=[URLRecord("https://new.test/shop/red-running-shoes")],
            conflicts={},
            min_score=0.8,
        )
        issues = mapping_issues(result)
        self.assertEqual(issues[0].code, "unmatched_old_url")
        html = render_mapping_html(result, old_source="old", new_source="new")
        self.assertIn("unmatched_old_url", html)

    def test_mapping_issues_include_low_confidence_and_conflicts(self):
        result = MappingResult(
            candidates=[
                RedirectCandidate(
                    old_url="https://old.test/a",
                    new_url="https://new.test/a",
                    score=0.61,
                    confidence="low",
                    reason="shared slug",
                )
            ],
            unmatched_old=[],
            orphan_new=[],
            conflicts={"https://new.test/a": ["https://old.test/a", "https://old.test/b"]},
            min_score=0.58,
        )
        self.assertEqual(
            [issue.code for issue in mapping_issues(result)],
            ["low_confidence_mapping", "many_to_one_redirect"],
        )

    def test_validation_report_includes_issue_codes_and_chain_details(self):
        html = render_validation_html(
            [
                RedirectValidation(
                    source_url="https://old.test/a",
                    expected_url="https://new.test/a?keep=1",
                    final_url="https://new.test/a?keep=2",
                    final_status=200,
                    ok=False,
                    issues=[
                        AuditIssue(
                            severity="critical",
                            code="target_mismatch",
                            url="https://old.test/a",
                            message="Final URL does not match <planned> target.",
                            detail="Expected https://new.test/a?keep=1",
                        )
                    ],
                    hops=[
                        ProbeHop(url="https://old.test/a", status=301, location="/a?keep=2"),
                        ProbeHop(url="https://new.test/a?keep=2", status=200),
                    ],
                )
            ]
        )
        self.assertIn("target_mismatch", html)
        self.assertIn("Final URL does not match &lt;planned&gt; target.", html)
        self.assertIn("Location:", html)
        self.assertIn("Critical issues", html)

    def test_validation_report_empty_state(self):
        html = render_validation_html([])
        self.assertIn("No redirects validated.", html)
        self.assertIn("0 passed, 0 failed, 0 issues", html)


if __name__ == "__main__":
    unittest.main()
