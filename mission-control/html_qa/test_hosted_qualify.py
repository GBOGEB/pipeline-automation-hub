"""Mocked per-path hosted qualification: no network, UNKNOWN never becomes PASS."""
import hashlib, sys, unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hosted_pages_verify as hv  # noqa: E402

BASE = "https://gbogeb.github.io/pipeline-automation-hub/"
INDEX = (b'<html><head><link rel="stylesheet" href="a.css"></head><body>'
         b'<a href="page.html#x">p</a><a href="#top">t</a><a href="https://example.com/">e</a>'
         b'<a href="mailto:x@example.com">m</a><a href="missing.html">m</a>'
         b'<img src="img/x.png" alt="x"><a href="/pipeline-automation-hub/abs.html?q=1">a</a>'
         b'<a href="/other-repo/x.html">o</a></body></html>')


def h(b):
    return hashlib.sha256(b).hexdigest()


def site(pages):
    def fetch(url):
        rel = url[len(BASE):]
        if rel in pages:
            return 200, pages[rel], url
        return 404, None, url
    return fetch


class LinkTests(unittest.TestCase):
    def test_local_links_same_site_only(self):
        links = hv.local_links(INDEX, BASE, BASE)
        self.assertEqual(links, [BASE + p for p in ["a.css", "abs.html", "img/x.png", "missing.html", "page.html"]])

    def test_relative_from_subdir(self):
        links = hv.local_links(b'<a href="../up.html">u</a><a href="../../escape.html">x</a>',
                               BASE + "sub/index.html", BASE)
        self.assertEqual(links, [BASE + "up.html"])


class QualifyTests(unittest.TestCase):
    pages = {"": INDEX, "index.html": INDEX, "a.css": b"css", "page.html": b"<p>",
             "img/x.png": b"png", "abs.html": b"<p>"}

    def test_per_path_status_parity_and_links(self):
        r = hv.qualify(BASE, ["", "page.html", "gone.html"],
                       expected={"": h(INDEX), "page.html": h(b"other")}, fetch=site(self.pages))
        root, page, gone = r["results"]
        self.assertTrue(root["converged"])
        self.assertEqual(root["parity"], "MATCH")
        self.assertEqual([f["status"] for f in root["fetches"]], [200, 200])
        self.assertEqual(page["parity"], "MISMATCH")
        self.assertFalse(gone["converged"])
        self.assertIsNone(gone["parity"])
        self.assertIsNone(gone["served_sha256"])
        self.assertEqual([f["status"] for f in gone["fetches"]], [404, 404])
        s = r["summary"]
        self.assertEqual((s["paths"], s["http_200_converged"], s["non_200_or_unstable"]), (3, 2, 1))
        self.assertEqual((s["parity_match"], s["parity_mismatch"], s["parity_unknown"]), (1, 1, 1))
        self.assertEqual(s["links_broken"], ["missing.html"])
        self.assertEqual(s["links_checked"], 5)
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_no_expected_is_unknown_not_pass(self):
        r = hv.qualify(BASE, ["a.css"], fetch=site(self.pages))
        self.assertIsNone(r["results"][0]["parity"])
        self.assertIsNone(r["results"][0]["links"])

    def test_unstable_bytes_do_not_converge(self):
        calls = [0]

        def fetch(url):
            calls[0] += 1
            return 200, b"v%d" % calls[0], url
        r = hv.qualify(BASE, ["page.html"], expected={"page.html": h(b"v1")}, fetch=fetch)
        self.assertFalse(r["results"][0]["converged"])
        self.assertIsNone(r["results"][0]["parity"])

    def test_off_origin_redirect_is_unknown(self):
        r = hv.qualify(BASE, ["page.html"], fetch=lambda u: (200, b"x", "https://evil.test/x"))
        self.assertEqual([f["status"] for f in r["results"][0]["fetches"]], [None, None])

    def test_link_redirect_off_origin_is_broken(self):
        def fetch(url):
            if url.endswith("a.css"):
                return 200, b"", "https://evil.test/a.css"
            return site(self.pages)(url)
        r = hv.qualify(BASE, [""], fetch=fetch)
        self.assertIn("a.css", r["summary"]["links_broken"])

    def test_follow_links_off(self):
        r = hv.qualify(BASE, [""], follow_links=False, fetch=site(self.pages))
        self.assertIsNone(r["results"][0]["links"])

    def test_bounds_and_base(self):
        with self.assertRaises(ValueError):
            hv.qualify(BASE, [""], repeat=1, fetch=site(self.pages))
        with self.assertRaises(ValueError):
            hv.qualify("https://evil.test/pipeline-automation-hub/", [""], fetch=site(self.pages))


class FetchStatusTests(unittest.TestCase):
    class Response:
        status = 200

        def __init__(self, body):
            self.body = body
            self.url = BASE

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return self.body[:n]

    def test_ok(self):
        with patch.object(hv, "urlopen", lambda req, timeout: self.Response(b"ok")):
            self.assertEqual(hv.fetch_status(BASE), (200, b"ok", BASE))

    def test_http_error_reports_status(self):
        def boom(req, timeout):
            raise HTTPError(BASE, 404, "nf", {}, None)
        with patch.object(hv, "urlopen", boom):
            self.assertEqual(hv.fetch_status(BASE), (404, None, BASE))

    def test_network_error_is_unknown(self):
        def boom(req, timeout):
            raise OSError("down")
        with patch.object(hv, "urlopen", boom):
            self.assertEqual(hv.fetch_status(BASE), (None, None, BASE))

    def test_oversize_body_dropped(self):
        with patch.object(hv, "MAX_PROBE_BYTES", 3), \
             patch.object(hv, "urlopen", lambda req, timeout: self.Response(b"toolong")):
            self.assertEqual(hv.fetch_status(BASE), (200, None, BASE))


if __name__ == "__main__":
    unittest.main()
