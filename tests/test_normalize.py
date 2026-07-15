import unittest

from rankguard.normalize import normalize_url, path_segments, section_key, tail_slug, url_tokens


class NormalizeTests(unittest.TestCase):
    def test_normalize_strips_tracking_and_default_port(self):
        self.assertEqual(
            normalize_url("HTTPS://Example.COM:443/Products/Red-Shoes/?utm_source=x&id=7", keep_query=True),
            "https://example.com/Products/Red-Shoes?id=7",
        )

    def test_path_helpers_ignore_locale(self):
        url = "https://example.com/en-us/products/red-running-shoes/"
        self.assertEqual(section_key(url), "products")
        self.assertEqual(tail_slug(url), "red-running-shoes")
        self.assertIn("running", url_tokens(url))

    def test_preserves_encoded_reserved_path_characters(self):
        self.assertEqual(
            normalize_url("https://Example.com/a%2fb/%7EUser/../Final"),
            "https://example.com/a%2Fb/Final",
        )

    def test_path_segments_do_not_split_encoded_slash(self):
        url = "https://example.com/docs/a%2Fb/"
        self.assertEqual(path_segments(url), ["docs", "a%2fb"])
        self.assertEqual(tail_slug(url), "a%2fb")

    def test_url_tokens_decode_percent_encoded_separators(self):
        tokens = url_tokens("https://example.com/products/red%20running%20shoes")
        self.assertIn("running", tokens)
        self.assertIn("shoe", tokens)
        self.assertNotIn("20running", tokens)

    def test_ipv6_host_keeps_brackets_and_drops_default_port(self):
        self.assertEqual(
            normalize_url("HTTP://[2001:DB8::1]:80/a"),
            "http://[2001:db8::1]/a",
        )

    def test_preserves_path_params(self):
        self.assertEqual(
            normalize_url("https://example.com/products;v=1/item;sku=ABC"),
            "https://example.com/products;v=1/item;sku=ABC",
        )

    def test_filters_tracking_query_case_insensitively(self):
        self.assertEqual(
            normalize_url(
                "https://example.com/path?B=2&utm_source=x&a=1&GCLID=abc&empty=",
                keep_query=True,
            ),
            "https://example.com/path?B=2&a=1&empty=",
        )

    def test_invalid_port_raises_value_error(self):
        with self.assertRaises(ValueError):
            normalize_url("https://example.com:not-a-port/path")

    def test_hostname_with_whitespace_raises_value_error(self):
        with self.assertRaises(ValueError):
            normalize_url("https:// example.com/path")


if __name__ == "__main__":
    unittest.main()
