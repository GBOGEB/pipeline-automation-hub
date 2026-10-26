"""JADE Colorway V1 — semantic UI guardrails, no authority mutation."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'site'

class ColorwayTests(unittest.TestCase):
    def test_n3_j8_naming_is_not_iteration_eight(self):
        template=(SITE/'eightpoint_template.html').read_text(encoding='utf-8')
        self.assertIn('>JT</span>',template)
        self.assertIn('N+3 DEVELOPMENT ITERATION',template)
        self.assertIn('J01–J08',template)
        self.assertIn('J08</strong> = bounded execution',template)
        self.assertNotIn('>J8</span>',template)
    def test_accessible_theme_switch_in_both_modes(self):
        html=(SITE/'eightpoint.html').read_text(encoding='utf-8');js=(SITE/'eightpoint.js').read_text(encoding='utf-8');css=(SITE/'eightpoint.css').read_text(encoding='utf-8')
        self.assertIn('id="theme-toggle"',html)
        self.assertIn('aria-pressed="false"',html)
        self.assertIn("themeSwitch.setAttribute('aria-pressed'",js)
        self.assertIn(':root[data-theme="light"]',css)
        self.assertIn('color-scheme:dark',css)
        self.assertIn('color-scheme:light',css)
    def test_eight_card_semantic_colours(self):
        css=(SITE/'eightpoint.css').read_text(encoding='utf-8')
        for i in range(1,9):
            self.assertIn('[data-axis="J%02d"]'%i,css)
        self.assertIn('.axis[data-axis="J08"]{--accent:var(--violet)',css)
        self.assertIn('.metrics>div:nth-child(3){--metric-accent:var(--red)',css)
        self.assertIn('.event.red{',css)
        self.assertIn('.gate.status-fail{',css)
        self.assertIn('.gate.status-unknown{',css)
    def test_source_and_authority_unchanged(self):
        p=json.loads((SITE/'eightpoint.json').read_text(encoding='utf-8'))
        self.assertEqual([x['id'] for x in p['sections']],[f'J{i:02d}' for i in range(1,9)])
        self.assertEqual(len(p['rows']),21)
        self.assertEqual(p['merge_admission'],'HOLD')
        self.assertIsNone(p['formal_point_release'])
        self.assertEqual(p['metrics']['action_owner_closed'],0)
        self.assertFalse(p['security_waiver'])
        self.assertFalse(p['authority_transfer'])
    def test_regenerated_hashes_match_presentation_only(self):
        spec=importlib.util.spec_from_file_location('colorway_builder',SITE/'build_eightpoint.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        expected=module.builds()
        for name,blob in expected.items():
            self.assertEqual((SITE/name).read_bytes(),blob,name)
        manifest=json.loads(expected['eightpoint-manifest.json'])
        self.assertEqual(manifest['repo_count'],21)
        self.assertEqual(manifest['static_population'],6)
        self.assertEqual(manifest['merge_admission'],'HOLD')
    def test_no_eval_or_dom_html_injection(self):
        js=(SITE/'eightpoint.js').read_text(encoding='utf-8')
        self.assertNotIn('.innerHTML=',js)
        self.assertNotIn('eval(',js)
        self.assertIn('document.createTextNode',js)

if __name__=='__main__':unittest.main()
