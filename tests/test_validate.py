import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from rankguard.models import RedirectCandidate
from rankguard.validate import _request_once, validate_redirect, validate_redirects


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or {}
        self.closed = False

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.methods = []

    def open(self, request, timeout):
        self.methods.append(request.get_method())
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class ValidateTests(unittest.TestCase):
    def test_validate_redirect_success(self):
        with patch("rankguard.validate._request_once", side_effect=self._fake_request({
            "https://old.test/old": (301, "https://old.test/new"),
            "https://old.test/new": (200, ""),
        })):
            result = validate_redirect(self._candidate("/old"))

        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.final_status, 200)
        self.assertEqual([hop.status for hop in result.hops], [301, 200])

    def test_validate_redirect_flags_temporary_redirect(self):
        with patch("rankguard.validate._request_once", side_effect=self._fake_request({
            "https://old.test/temporary": (302, "https://old.test/new"),
            "https://old.test/new": (200, ""),
        })):
            result = validate_redirect(self._candidate("/temporary"))

        self.assertFalse(result.ok)
        self.assertIn("temporary_redirect", self._codes(result))
        self.assertEqual(result.final_status, 200)

    def test_validate_redirect_flags_redirect_chain(self):
        with patch("rankguard.validate._request_once", side_effect=self._fake_request({
            "https://old.test/chain": (301, "https://old.test/middle"),
            "https://old.test/middle": (308, "https://old.test/new"),
            "https://old.test/new": (200, ""),
        })):
            result = validate_redirect(self._candidate("/chain"))

        self.assertFalse(result.ok)
        self.assertIn("redirect_chain", self._codes(result))
        self.assertEqual([hop.status for hop in result.hops], [301, 308, 200])

    def test_validate_redirect_flags_loop(self):
        with patch("rankguard.validate._request_once", side_effect=self._fake_request({
            "https://old.test/loop-a": (301, "https://old.test/loop-b"),
            "https://old.test/loop-b": (301, "https://old.test/loop-a"),
        })):
            result = validate_redirect(self._candidate("/loop-a"))

        self.assertFalse(result.ok)
        self.assertIn("redirect_loop", self._codes(result))
        self.assertEqual(result.final_status, 301)

    def test_validate_redirect_flags_missing_location(self):
        with patch("rankguard.validate._request_once", return_value=(301, "")):
            result = validate_redirect(self._candidate("/missing-location"))

        self.assertFalse(result.ok)
        self.assertEqual(self._codes(result), ["missing_redirect_location"])
        self.assertEqual(result.final_status, 301)

    def test_validate_redirect_compares_meaningful_query_params(self):
        with patch("rankguard.validate._request_once", side_effect=self._fake_request({
            "https://old.test/query-old": (301, "https://old.test/new?keep=2"),
            "https://old.test/new?keep=2": (200, ""),
        })):
            result = validate_redirect(self._candidate("/query-old", "/new?keep=1"))

        self.assertFalse(result.ok)
        self.assertIn("target_mismatch", self._codes(result))
        self.assertEqual(result.final_url, "https://old.test/new?keep=2")

    def test_request_once_falls_back_to_get_when_head_is_not_allowed(self):
        opener = FakeOpener(
            [
                HTTPError("https://old.test/head", 405, "Method Not Allowed", {}, None),
                FakeResponse(301, {"Location": "/new"}),
            ]
        )
        status, location = _request_once(opener, "https://old.test/head", timeout=1)
        self.assertEqual((status, location), (301, "/new"))
        self.assertEqual(opener.methods, ["HEAD", "GET"])

    def test_request_once_reports_get_error_after_head_fallback(self):
        opener = FakeOpener(
            [
                HTTPError("https://old.test/head", 405, "Method Not Allowed", {}, None),
                HTTPError("https://old.test/head", 404, "Not Found", {}, None),
            ]
        )
        status, location = _request_once(opener, "https://old.test/head", timeout=1)
        self.assertEqual((status, location), (404, ""))
        self.assertEqual(opener.methods, ["HEAD", "GET"])

    def test_validate_redirects_respects_zero_limit(self):
        candidates = [self._candidate("/old"), self._candidate("/temporary")]
        self.assertEqual(validate_redirects(candidates, limit=0), [])

    def test_validate_redirects_rejects_negative_limit(self):
        with self.assertRaises(ValueError):
            validate_redirects([self._candidate("/old")], limit=-1)

    def _candidate(self, old_path, new_path="/new"):
        return RedirectCandidate(
            old_url=f"https://old.test{old_path}",
            new_url=f"https://old.test{new_path}",
            score=1.0,
            confidence="high",
            reason="test",
        )

    def _codes(self, result):
        return [issue.code for issue in result.issues]

    def _fake_request(self, routes):
        def fake_request(_opener, url, *, timeout):
            return routes[url]

        return fake_request


if __name__ == "__main__":
    unittest.main()
