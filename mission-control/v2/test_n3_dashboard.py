"""Visual structure and static HTML security tests; not Playwright receipts."""
import copy
import json
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
from n3_dashboard import render
from n3_metrics import collect

LEDGER=HERE.parent/'federation-atlas'/'CBD_GOLDEN_GRAPH_N3_20261017.json'


class TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append((tag,dict(attrs)))


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=collect(json.loads(LEDGER.read_text(encoding='utf-8')))

    def test_deterministic(self):
        self.assertEqual(render(self.data),render(self.data))

    def test_html_svg_table_built(self):
        p=TagCollector();p.feed(render(self.data))
        self.assertIn('svg',[x[0] for x in p.tags]);self.assertIn('table',[x[0] for x in p.tags])
        self.assertEqual(sum(x[0]=='circle' for x in p.tags),3)

    def test_missing_values_visible(self):
        h=render(self.data)
        self.assertIn('UNKNOWN',h);self.assertIn('HOLD',h)
        self.assertIn('0/9',h);self.assertIn('LOCAL',h)

    def test_no_remote_dependencies(self):
        p=TagCollector();p.feed(render(self.data))
        self.assertFalse(any(tag in ('script','iframe','img') for tag,_ in p.tags))
        self.assertFalse(any(tag=='link' and 'href' in attrs for tag,attrs in p.tags))

    def test_action_html_escaped(self):
        d=copy.deepcopy(self.data)
        d['pulses'][0]['action_description']='<script>alert("x")</script>'
        h=render(d)
        self.assertNotIn('<script>',h)
        self.assertIn('&lt;script&gt;',h)

    def test_auth_escalation_rejected(self):
        d=copy.deepcopy(self.data);d['merge_admission']='PASS'
        with self.assertRaises(ValueError):render(d)
        d['merge_admission']='HOLD';d['authority_transfer']=True
        with self.assertRaises(ValueError):render(d)

    def test_bad_schema_rejected(self):
        d=copy.deepcopy(self.data);d['schema']='whatever'
        with self.assertRaises(ValueError):render(d)

    def test_all_ids_linked(self):
        h=render(self.data)
        for i in range(1,4):
            self.assertIn(f'id="pulse-{i}"',h)
            self.assertIn(f'href="#pulse-{i}"',h)


if __name__=='__main__':unittest.main()
