"""W19 count/visual-source fail-closed tests; no external dependencies."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/mission-control/w19/observations.json"
VIEW=ROOT/"docs/mission-control/w19/burndown.html"
def validate(d):
    assert d["schema"]=="code-purple.w19.integer-burndown.v1"
    assert d["authority_transfer"] is False and d["merge_admission"]=="HOLD"
    assert d["engineering_root_closure_credit"]==0 and d["formal_root_closure_credit"]==0
    assert d["search"]["incomplete_results"] is False
    assert sum(d["search"]["pages"])==d["search"]["total"]==141
    assert d["counts"]==[153,149,144,142,141,141]
    assert all(type(n) is int for n in d["counts"])
    m=d["membership"]
    assert m["baseline"]==m["current"]==m["retained"]==141
    assert m["added"]==m["removed"]==0 and m["updated_metadata"]==10
    assert sum(v for k,v in d["historical_ticket_closures"].items() if k != "accepted_causal_roots_from_this_wave")==12
    a=d["triage"]
    assert len(a)==len({z["url"] for z in a})==20
    assert sum(z["cohort"]=="HOT" for z in a)==5
    assert sum(z["cohort"]=="COLD" for z in a)==5
    assert sum(z["cohort"]=="GATE" for z in a)==10
    assert all(z["url"]==f'https://github.com/GBOGEB/{z["repo"]}/issues/{z["number"]}' and z["state"]=="open" for z in a)
    assert d["native"]["b0"]["conclusion"]==d["native"]["matrix"]["conclusion"]=="success"
    assert d["scenario"]["type"]=="ILLUSTRATIVE_NOT_FORECAST"
    return True
class W19Evidence(unittest.TestCase):
    def setUp(self):
        self.d=json.loads(DATA.read_text(encoding="utf8"))
    def test_source_bound_positive(self):self.assertTrue(validate(self.d))
    def test_reject_fractional_ticket(self):
        self.d["counts"][1]=149.25
        with self.assertRaises(AssertionError):validate(self.d)
    def test_reject_duplicate(self):
        self.d["triage"][-1]=self.d["triage"][0]
        with self.assertRaises(AssertionError):validate(self.d)
    def test_reject_partial_census(self):
        self.d["search"]["incomplete_results"]=True
        with self.assertRaises(AssertionError):validate(self.d)
    def test_reject_bad_denominator(self):
        self.d["search"]["pages"]=[100,40]
        with self.assertRaises(AssertionError):validate(self.d)
    def test_reject_root_fabrication(self):
        self.d["engineering_root_closure_credit"]=12
        with self.assertRaises(AssertionError):validate(self.d)
    def test_axis_and_hover_integers(self):
        h=VIEW.read_text(encoding="utf8")
        for t in ("for(let n=min;n<=max;n+=2)","ticktext:ticks.map(String)","%{y:.0f}"):self.assertIn(t,h)
    def test_html_scenarios_guarded(self):
        h=VIEW.read_text(encoding="utf8")
        for t in ('No-unblock plateau','not a prediction','not-observed'):self.assertIn(t,h)
    def test_buttons_and_svg_fallback(self):
        h=VIEW.read_text(encoding="utf8")
        for t in ('id="csv"','id="reset"','id="show-scenario"','function drawSvg','function csv'):self.assertIn(t,h)
    def test_generated_projection_exactly_matches_source(self):
        import subprocess
        import sys
        import re
        rendered = VIEW.read_text(encoding="utf-8")
        self.assertNotIn("The requested file reference is not currently visible", rendered)
        payload = re.search(
            r'<script id="source-data" type="application/json">(.+?)</script>',
            rendered, re.DOTALL,
        )
        self.assertIsNotNone(payload, "missing offline source payload")
        self.assertEqual(self.d, json.loads(payload.group(1)))
        completed = subprocess.run(
            [sys.executable, str(ROOT / "docs/mission-control/w19/render.py"), "--check"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_tool_error_and_source_divergence_negative_canary(self):
        import importlib.util
        import hashlib
        script = ROOT / "docs/mission-control/w19/render.py"
        spec = importlib.util.spec_from_file_location("w19_render", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        raw = DATA.read_bytes()
        tpl = (script.parent / "burndown.template.html").read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            mod.render(raw, "The requested file reference is not currently visible __SOURCE_JSON__ __SOURCE_BLOB__")
        mutated = json.loads(raw)
        mutated["counts"][0] += 1
        altered = mod.render(json.dumps(mutated).encode("utf-8"), tpl)
        self.assertNotEqual(altered, VIEW.read_text(encoding="utf-8"))
        marker = b"blob " + str(len(raw)).encode("ascii") + b"\0"
        blob = hashlib.sha1(marker + raw).hexdigest()
        self.assertIn(blob, VIEW.read_text(encoding="utf-8"))

    def test_main_admission_unknown(self):
        self.assertEqual(self.d["native"]["later_main"],"UNQUALIFIED")
        self.assertEqual(self.d["native"]["b9"],"UNPROVEN")
if __name__=="__main__":unittest.main()
