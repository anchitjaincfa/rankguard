import unittest

from rankguard.matcher import generate_redirect_map, render_server_rules
from rankguard.models import RedirectCandidate, URLRecord


class MatcherTests(unittest.TestCase):
    def test_maps_slug_across_section_change(self):
        result = generate_redirect_map(
            [URLRecord("https://old.test/products/red-running-shoes")],
            [URLRecord("https://new.test/shop/red-running-shoes")],
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].confidence, "high")

    def test_unmatched_below_threshold(self):
        result = generate_redirect_map(
            [URLRecord("https://old.test/blog/returns-policy")],
            [URLRecord("https://new.test/shop/red-running-shoes")],
            min_score=0.7,
        )
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(len(result.unmatched_old), 1)

    def test_nginx_rules(self):
        result = generate_redirect_map(
            [URLRecord("https://old.test/products/red-running-shoes")],
            [URLRecord("https://new.test/shop/red-running-shoes")],
        )
        rules = render_server_rules(result.candidates, fmt="nginx")
        self.assertIn("return 301 https://new.test/shop/red-running-shoes", rules)

    def test_exact_path_candidate_not_missed_in_large_sparse_pool(self):
        new_records = [URLRecord(f"https://new.test/archive/page-{index}") for index in range(450)]
        new_records.append(URLRecord("https://new.test/"))

        result = generate_redirect_map([URLRecord("https://old.test/")], new_records, min_score=0.9)

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].new_url, "https://new.test/")

    def test_nginx_rules_preserve_encoded_source_path_and_normalize_target(self):
        candidate = RedirectCandidate(
            old_url="https://old.test/Docs/A%2fb",
            new_url="HTTPS://new.test:443/Docs/A%2fb?utm_source=x&id=7",
            score=1.0,
            confidence="high",
            reason="test",
        )

        rules = render_server_rules([candidate], fmt="nginx")

        self.assertIn("location = /Docs/A%2Fb", rules)
        self.assertIn("return 301 https://new.test/Docs/A%2Fb?id=7", rules)

    def test_apache_rules_escape_regex_metacharacters(self):
        candidate = RedirectCandidate(
            old_url="https://old.test/Docs/v1.0/a+b",
            new_url="https://new.test/Docs/v1.0/a+b",
            score=1.0,
            confidence="high",
            reason="test",
        )

        rules = render_server_rules([candidate], fmt="apache")

        self.assertIn(r"RewriteRule ^Docs/v1\.0/a\+b$ https://new.test/Docs/v1.0/a+b [R=301,L]", rules)


if __name__ == "__main__":
    unittest.main()
