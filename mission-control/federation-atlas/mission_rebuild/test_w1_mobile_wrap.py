"""Static mobile-wrap contract for the W1 page (offline; no browser).

Regression: native W1 Playwright DoV failed 'document horizontal overflow at 390'.
The footer renders the full 40-hex source SHA (~380 px at 16 px) into ~310 px of
usable width with no wrap rule. 2ad4e2d fixed the same class of bug for node
details only. These checks pin every region that receives unbroken identifiers.
"""
import re
import tempfile
import unittest
from pathlib import Path

import build

SAMPLE = build.ATLAS.parent / "gogreen/samples/sipoc_instance_wave_20261016.json"


def css_rules(html):
    css = "".join(re.findall(r"<style>(.*?)</style>", html, flags=re.S))
    css = re.sub(r"@media[^{]*\{((?:[^{}]*\{[^{}]*\})*)\s*\}", r"\1", css)  # flatten media blocks
    rules = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        for sel in selectors.split(","):
            rules.setdefault(sel.strip(), []).append(body)
    return rules


def wraps(rules, selector):
    return any("overflow-wrap:anywhere" in body.replace(" ", "") for body in rules.get(selector, []))


class W1MobileWrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            build.build(build.ATLAS, Path(d), "a" * 40, SAMPLE)
            cls.html = (Path(d) / "index.html").read_text(encoding="utf-8")
        cls.rules = css_rules(cls.html)

    def test_footer_with_full_source_sha_wraps(self):
        self.assertIn('$("footer").textContent="Read-only snapshot at "+d.source_sha', self.html)
        self.assertTrue(wraps(self.rules, "footer"), "footer renders 40-hex SHA without overflow-wrap")

    def test_card_captions_with_repo_and_lease_paths_wrap(self):
        for sel in (".repo small", ".node small"):
            with self.subTest(selector=sel):
                self.assertTrue(wraps(self.rules, sel))

    def test_prior_details_fix_retained(self):
        for sel in (".details", ".details pre", ".details a", "code"):
            with self.subTest(selector=sel):
                self.assertTrue(wraps(self.rules, sel))

    def test_wide_svg_stays_inside_its_scroll_container(self):
        self.assertTrue(any("overflow-x:auto" in b for b in self.rules.get(".beam-wrap", [])))
        self.assertTrue(any("max-width:100%" in b for b in self.rules.get(".beam-wrap", [])))

    def test_helper_detects_missing_rule(self):
        broken = self.html.replace("color:#aac2d1;overflow-wrap:anywhere}", "color:#aac2d1}", 1)
        self.assertNotEqual(broken, self.html)
        self.assertFalse(wraps(css_rules(broken), "footer"))


if __name__ == "__main__":
    unittest.main()
