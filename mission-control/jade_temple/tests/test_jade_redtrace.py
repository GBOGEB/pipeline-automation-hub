"""JADE N+8 red-trace federation ledger: source, determinism and presentation contracts (offline)."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_mod(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


B = load_mod("site/build_redtrace.py", "build_redtrace")
D = load_mod("tools/build_redtrace_data.py", "build_redtrace_data")
FED = json.loads((ROOT / "data/RED_TRACE_FEDERATION_N8.json").read_text(encoding='utf-8'))
GAP = json.loads((ROOT / "data/GAP_ANALYSIS_N8.json").read_text(encoding='utf-8'))


class Sources(unittest.TestCase):
    def test_five_core_repos_in_fixed_order(self):
        self.assertEqual([r["short"] for r in FED["repositories"]], D.CORE)

    def test_totals_reconcile_with_repositories(self):
        t = FED["totals"]
        self.assertEqual(t["red"], sum(r["currently_red"] for r in FED["repositories"]))
        self.assertEqual(t["red_fresh"] + t["red_stale"], t["red"])
        self.assertEqual(t["workflows"], sum(r["workflows_traced"] for r in FED["repositories"]))
        for r in FED["repositories"]:
            self.assertEqual(sum(r["counts"].values()), r["workflows_traced"], r["short"])
            reds = [w for w in r["non_green"] if w["current"] == "RED"]
            self.assertEqual(len(reds), r["currently_red"], r["short"])

    def test_no_authority_anywhere(self):
        for d in (FED, GAP):
            self.assertIs(d["authority"]["merge_authorized"], False)
        self.assertIsNone(FED["authority"]["root_closure_credit"])

    def test_gap_rows_complete_and_actor_typed(self):
        ids = [g["id"] for g in GAP["gaps"]]
        self.assertEqual(len(ids), len(set(ids)))
        for g in GAP["gaps"]:
            self.assertIn(g["actor"], B.ACTOR)
            self.assertIn(g["state"], B.GAPSTATE)
            for k in ("finding", "fill", "next"):
                self.assertTrue(g[k])
        self.assertTrue({a["actor"] for a in GAP["agent_actions"]} >= {"AGENT", "OWNER", "CI"})

    def test_assembler_rejects_authority_bearing_report(self):
        rep = {"schema": "gogreen.red_trace.v1", "authority": {"merge_authorized": True}}
        with self.assertRaises(ValueError):
            D.assemble({n: rep for n in D.CORE})


class Outputs(unittest.TestCase):
    def test_generated_files_match_sources(self):
        for name, data in B.build().items():
            with self.subTest(name=name):
                self.assertEqual((ROOT / "site" / name).read_bytes(), data,
                                 "run: python mission-control/jade_temple/site/build_redtrace.py")

    def test_deterministic(self):
        self.assertEqual(B.build(), B.build())

    def test_every_red_row_has_text_status_not_colour_only(self):
        html = (ROOT / "site/redtrace.html").read_text(encoding='utf-8')
        self.assertEqual(html.count('data-red="1"'), FED["totals"]["red"])
        self.assertEqual(html.count("RED NOW"), FED["totals"]["red"])

    def test_explicit_actor_badges_and_links(self):
        html = (ROOT / "site/redtrace.html").read_text(encoding='utf-8')
        for a in ("agent", "owner", "ci"):
            self.assertIn(f"rt-actor-{a}", html)
        for link in ("redtrace-slides.html", "redtrace-slides.pdf", "jade.css"):
            self.assertIn(link, html)

    def test_slide_outline_matches_deck(self):
        m = json.loads((ROOT / "site/redtrace-manifest.json").read_text(encoding='utf-8'))
        deck = (ROOT / "site/redtrace-slides.html").read_text(encoding='utf-8')
        self.assertEqual(deck.count('class="slide"'), len(m["slide_outline"]))
        for s in m["slide_outline"]:
            self.assertIn(f'id="{s["id"]}"', deck)
        self.assertFalse(m["pdf"]["deterministic"])
        self.assertIs(m["merge_authorized"], False)

    def test_source_tamper_detected(self):
        bad = copy.deepcopy(FED)
        bad["authority"]["merge_authorized"] = True
        orig = B.load
        B.load = lambda rel: bad if rel == B.FED else orig(rel)
        try:
            with self.assertRaises(SystemExit):
                B.build()
        finally:
            B.load = orig


if __name__ == "__main__":
    unittest.main()
