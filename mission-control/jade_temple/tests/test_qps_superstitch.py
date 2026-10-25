"""QPS Superstitch page: DOM-built panels, https-only links (CodeQL js/xss-through-dom, alerts 48 and 49).

The page renders data from its embedded JSON model. Every panel must be built with
createElement/textContent, never by parsing an HTML string, and every link must be https.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "qps_superstitch.html"
SINKS = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")
SVG_NS = "http://www.w3.org/2000/svg"


def findings(html):
    """Return a list of problems; empty means the page passes the guard."""
    bad = [f"HTML string sink: {s}" for s in SINKS if s in html]
    for href in re.findall(r'href="([^"]*)"', html):
        if not href.startswith("https://"):
            bad.append(f"non-https literal href: {href}")
    for url in re.findall(r"http://[^\s'\"<>)]+", html):
        if url != SVG_NS:
            bad.append(f"plain-http URL: {url}")
    if "x.protocol==='https:'" not in html:
        bad.append("no https guard on built links")
    for assign in re.findall(r"\.href=([^;]+);", html):
        if assign.strip() != "href":
            bad.append(f"link href not taken from safeUrl(): {assign}")
    if "a.rel='noopener noreferrer'" not in html:
        bad.append("built links lack rel=noopener noreferrer")
    return bad


class QpsSuperstitchPage(unittest.TestCase):
    def setUp(self):
        self.html = PAGE.read_text(encoding="utf-8")

    def test_no_html_string_sinks_and_https_only_links(self):
        self.assertEqual(findings(self.html), [])

    def test_repo_links_pass_the_https_guard(self):
        self.assertIn("let href=safeUrl('https://github.com/'+encodeURI(repo))", self.html)

    def test_page_is_offline(self):
        self.assertNotRegex(self.html, r"<script[^>]+src=")
        self.assertNotRegex(self.html, r"<link[^>]+href=")


if __name__ == "__main__":
    unittest.main()
