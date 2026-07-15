import tempfile
import unittest
from pathlib import Path

from rankguard.io import load_redirect_csv, load_url_records, write_redirect_csv
from rankguard.models import RedirectCandidate


class IOTests(unittest.TestCase):
    def test_load_sitemap(self):
        records = load_url_records("examples/old_sitemap.xml")
        self.assertEqual(len(records), 5)
        self.assertEqual(records[0].url, "https://example.com/products/red-running-shoes")

    def test_load_csv_and_redirect_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawl.csv"
            path.write_text(
                "Address,Title,Status Code,Canonical URL\n"
                "https://a.test/page,Page,200.0,https://a.test/canonical\n",
                encoding="utf-8",
            )
            records = load_url_records(str(path))
            self.assertEqual(records[0].title, "Page")
            self.assertEqual(records[0].status, 200)
            self.assertEqual(records[0].canonical, "https://a.test/canonical")

            redirects = Path(tmp) / "redirects.csv"
            write_redirect_csv(
                [
                    RedirectCandidate(
                        old_url="https://a.test/page",
                        new_url="https://b.test/page",
                        score=1.0,
                        confidence="high",
                        reason="test",
                        alternatives=[("https://b.test/alternate", 0.8)],
                    )
                ],
                redirects,
            )
            loaded = load_redirect_csv(redirects)
            self.assertEqual(loaded[0].new_url, "https://b.test/page")
            self.assertEqual(loaded[0].alternatives, [("https://b.test/alternate", 0.8)])

    def test_load_tsv_with_normalized_headers_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawl.tsv"
            path.write_text(
                "\ufeffSource URL\tPage Title\tHTTP Status\n"
                "https://a.test/one\tOne\t301 Moved\n"
                "https://a.test/one\tDuplicate\t200\n"
                "https://a.test/two\tTwo\t200.0\n",
                encoding="utf-8",
            )

            records = load_url_records(str(path))

        self.assertEqual([record.url for record in records], ["https://a.test/one", "https://a.test/two"])
        self.assertEqual(records[0].title, "One")
        self.assertEqual(records[0].status, 301)
        self.assertEqual(records[1].status, 200)

    def test_load_semicolon_csv_from_url_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "urls.txt"
            path.write_text(
                "URL;Name\nhttps://a.test/one;One\nhttps://a.test/two;Two\n",
                encoding="utf-8",
            )

            records = load_url_records(str(path))

        self.assertEqual([record.title for record in records], ["One", "Two"])

    def test_load_plaintext_skips_header_comments_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "urls.txt"
            path.write_text(
                "\ufeffurl\n# ignored\nhttps://a.test/one\n\nhttps://a.test/one\nhttps://a.test/two\n",
                encoding="utf-8",
            )

            records = load_url_records(str(path))

        self.assertEqual([record.url for record in records], ["https://a.test/one", "https://a.test/two"])

    def test_load_sitemap_index_with_relative_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "nested.xml"
            nested.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://a.test/one</loc></url>
</urlset>
""",
                encoding="utf-8",
            )
            index = Path(tmp) / "index.xml"
            index.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>nested.xml</loc></sitemap>
</sitemapindex>
""",
                encoding="utf-8",
            )

            records = load_url_records(str(index))

        self.assertEqual([record.url for record in records], ["https://a.test/one"])

    def test_csv_without_url_column_raises_for_csv_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawl.csv"
            path.write_text("Title,Status\nPage,200\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Could not find a URL column"):
                load_url_records(str(path))

    def test_redirect_csv_missing_url_values_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "redirects.csv"
            path.write_text("old_url,new_url,score\nhttps://a.test/old,,1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "row 2 must include old_url and new_url"):
                load_redirect_csv(path)


if __name__ == "__main__":
    unittest.main()
