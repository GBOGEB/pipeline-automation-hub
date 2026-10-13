import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_code_purple as bcp
import code_purple_series as cps

ROOT = HERE.parents[1]


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = cps.load_json(cps.QUEUE)

    def test_queue_validates_against_its_schema(self):
        self.assertEqual(cps.check_queue(self.queue), [])

    def test_schema_rejects_unknown_state_and_bad_key(self):
        bad = copy.deepcopy(self.queue)
        bad["items"][0]["history"][0]["state"] = "GREEN"
        bad["items"][1]["history"][0]["at"] = "2026-10-13"
        errs = cps.check_queue(bad)
        self.assertTrue(any("GREEN" in e for e in errs))
        self.assertTrue(any("2026-10-13" in e for e in errs))

    def test_history_must_increase(self):
        bad = copy.deepcopy(self.queue)
        h = bad["items"][0]["history"]
        h.reverse()
        self.assertTrue(any("strictly increasing" in e for e in cps.check_queue(bad)))

    def test_item_state_is_replayed_by_ordinal(self):
        item = next(i for i in self.queue["items"] if i["id"] == "CPQ-001")
        self.assertEqual(cps.item_at(item, "W1.C1.I0.S0")["state"], "TODO")
        self.assertEqual(cps.item_at(item, "W1.C1.I1.S0")["state"], "DONE")
        new = next(i for i in self.queue["items"] if i["id"] == "CPQ-010")
        self.assertIsNone(cps.item_at(new, "W1.C1.I1.S1"))

    def test_critical_path_items_exist_and_are_marked(self):
        beams = cps.load_json(cps.BEAMS)
        ids = {i["id"]: i for i in self.queue["items"]}
        for cid in beams["critical_path"]["items"]:
            self.assertTrue(ids[cid]["critical_path"])

    def test_no_authority_or_credit(self):
        self.assertIs(self.queue["authority_transfer"], False)
        self.assertEqual(self.queue["formal_credit_delta"], 0)


class SeriesTests(unittest.TestCase):
    def test_series_matches_tree(self):
        code, errs = cps.run_check()
        self.assertEqual((code, errs), (0, []))

    def test_tampered_entry_breaks_hash_chain(self):
        series = cps.load_json(cps.SERIES)
        series["entries"][0]["metrics"]["bd_open"] += 1
        self.assertTrue(any("prev_digest" in e or "delta" in e for e in cps.check_series(series)))

    def test_metric_drift_without_entry_fails(self):
        series = cps.load_json(cps.SERIES)
        last, prev = series["entries"][-1], series["entries"][-2]
        last["metrics"]["bd_open"] += 1
        last["delta"] = cps.delta(prev["metrics"], last["metrics"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text(json.dumps(series), encoding="utf-8")
            old = cps.SERIES
            cps.SERIES = p
            try:
                code, errs = cps.run_check()
            finally:
                cps.SERIES = old
        self.assertEqual(code, 1)
        self.assertTrue(any("metrics changed without a series entry" in e for e in errs))

    def test_keys_are_ordinal_not_time(self):
        for e in cps.load_json(cps.SERIES)["entries"]:
            self.assertRegex(e["key"], r"^W\d+\.C\d+\.I\d+\.S\d+$")
        with self.assertRaises(cps.SeriesError):
            cps.key_tuple("2026-10-13T10:00:00Z")

    def test_only_latest_entry_may_be_provisional(self):
        entries = cps.load_json(cps.SERIES)["entries"]
        self.assertTrue(all(e["tree"] != "PR_HEAD" for e in entries[:-1]))


class GateParityTests(unittest.TestCase):
    def test_page_ledger_agrees_with_repo_evaluator(self):
        contract = cps.load_json(ROOT / cps.CONTRACT)
        spec = importlib.util.spec_from_file_location(
            "gm_eval_test", ROOT / "mission-control/grand-missions/gm_dmaic_evolution_metrics.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ledger = cps.gate_ledger(contract)
        repo = mod.evaluate(contract)
        self.assertEqual(all(r["state"] == "PASS" for r in ledger["top7_to_top14"]), repo["top14_promotion_ready"])
        self.assertEqual(all(r["state"] == "PASS" for r in ledger["top14_to_top21"]), repo["top21_promotion_ready"])

    def test_null_observation_is_unknown_not_pass(self):
        contract = cps.load_json(ROOT / cps.CONTRACT)
        contract["current"]["max_unchanged_root_auto_repeat_after_control"] = None
        rows = cps.gate_ledger(contract)["top7_to_top14"]
        self.assertEqual(next(r for r in rows if r["label"] == "Unchanged-root auto-repeat")["state"], "UNKNOWN")


class PageTests(unittest.TestCase):
    def test_dag_lanes_are_acyclic_and_feedback_is_separate(self):
        beams = cps.load_json(cps.BEAMS)
        lanes = bcp.lanes(beams)
        for e in beams["edges"]:
            if e["type"] == "FEEDFORWARD":
                self.assertLess(lanes[e["from"]], lanes[e["to"]])
        bad = copy.deepcopy(beams)
        bad["edges"].append({"from": "B5", "to": "B3", "type": "FEEDFORWARD", "carries": "x"})
        with self.assertRaises(ValueError):
            bcp.lanes(bad)

    def test_page_builds_from_repo_files(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(bcp.main(["--out", d]), 0)
            html = (Path(d) / "code-purple.html").read_text(encoding="utf-8")
            payload = json.loads((Path(d) / "code-purple.json").read_text(encoding="utf-8"))
        self.assertTrue(html.startswith("<!doctype html>"))
        for anchor in ('id="dag"', 'id="beams"', 'id="queue"', 'id="mults"', 'id="gates"', 'id="cands"', 'data-c=', "Copy drop-in for chat"):
            self.assertIn(anchor, html)
        self.assertEqual(len(payload["repos"]), 21)
        self.assertEqual(payload["series_key"], cps.load_json(cps.SERIES)["entries"][-1]["key"])
        self.assertIs(payload["authority_transfer"], False)

    def test_fragment_has_no_document_skeleton(self):
        with tempfile.TemporaryDirectory() as d:
            bcp.main(["--out", d, "--fragment"])
            html = (Path(d) / "code-purple.html").read_text(encoding="utf-8")
        self.assertTrue(html.startswith("<title>"))
        self.assertNotIn("<body>", html)

    def test_graph_edges_all_bound(self):
        import yaml
        graph = yaml.safe_load((HERE / "ATLAS_GRAPH_v1.yaml").read_text(encoding="utf-8"))
        self.assertTrue(all(e.get("binding") in ("RECEIPT", "DECLARED") for e in graph["edges"]))
        self.assertTrue(all("source" in e for e in graph["edges"] if e["binding"] == "RECEIPT"))


if __name__ == "__main__":
    unittest.main()
