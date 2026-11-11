"""OID federation crosswalk and wishbone kernel: every handover folder maps to a real
owner, open PR or parked item; pruning keeps the schedule; A and B converge; CPM slack,
weighted makespan and the DSM are exact on small DAGs."""
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("oid_federation_under_test", ROOT / "tools" / "oid_federation.py")
of = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(of)
DOC = of.load()
NODES = of.AD.load()["nodes"]
PREREQS = {k: list(n.get("depends_on") or []) for k, n in NODES.items()}

# a->b->c plus the shortcut a->c, and an independent d
DIAMOND = {"a": [], "b": ["a"], "c": ["a", "b"], "d": []}


def fake_oid(rel):
    return "0" * 40


class Kernel(unittest.TestCase):
    def test_reduction_drops_only_the_shortcut(self):
        reduced, dropped = of.transitive_reduction(DIAMOND)
        self.assertEqual(dropped, [("a", "c")])
        self.assertEqual(reduced, {"a": [], "b": ["a"], "c": ["b"], "d": []})

    def test_reduction_keeps_reachability_and_waves(self):
        reduced, _ = of.transitive_reduction(PREREQS)
        anc, anc_r = of.AD.ancestors(PREREQS), of.AD.ancestors(reduced)
        self.assertEqual(anc, anc_r)
        self.assertEqual(of.AD.waves(PREREQS), of.AD.waves(reduced))

    def test_cpm_unit_weights_count_waves(self):
        c = of.cpm(DIAMOND)
        self.assertEqual((c["unit"], c["makespan"]), ("waves", 3.0))
        self.assertEqual(c["zero_slack"], ["a", "b", "c"])
        self.assertEqual(c["slack"]["d"], 2.0)

    def test_cpm_weighted(self):
        c = of.cpm(DIAMOND, {"a": 2, "b": 5, "c": 1, "d": 7.5})
        self.assertEqual((c["unit"], c["makespan"]), ("seconds", 8.0))
        self.assertEqual(c["earliest_start"]["c"], 7.0)
        self.assertEqual(c["slack"]["d"], 0.5)

    def test_cpm_missing_duration_fails_closed(self):
        with self.assertRaises(ValueError):
            of.cpm(DIAMOND, {"a": 1})

    def test_cycle_fails_closed(self):
        with self.assertRaises(ValueError):
            of.wishbone({"a": ["b"], "b": ["a"]})

    def test_wishbone_converges_on_committed_dag(self):
        w = of.wishbone(PREREQS)
        self.assertTrue(w["track_c"]["converged"])
        self.assertEqual(w["track_a"]["waves"], w["track_b"]["waves"])
        self.assertEqual(w["track_c"]["makespan"], len(w["track_c"]["waves"]))
        self.assertEqual(w["track_a"]["critical"][0], "C1_methane")

    def test_dsm_is_lower_triangular_in_wave_order(self):
        d = of.dsm(DIAMOND)
        self.assertEqual(d["above"], 0)
        self.assertEqual(sum(map(sum, d["matrix"])), 3)
        self.assertEqual(of.dsm(PREREQS)["above"], 0)


class Crosswalk(unittest.TestCase):
    def test_committed_crosswalk_is_clean(self):
        errs, bound = of.check(DOC, NODES)
        self.assertEqual(errs, [])
        self.assertTrue(all(len(v) == 40 for v in bound.values()))

    def test_anchor_is_c2(self):
        self.assertEqual(DOC["anchor"]["node"], "C2_ethane")

    def test_missing_folder_and_bad_status(self):
        doc = copy.deepcopy(DOC)
        del doc["folders"]["00_CONTROL"]
        doc["folders"]["04_SLICES_OUT"]["status"] = "done"
        errs, _ = of.check(doc, NODES, fake_oid)
        self.assertIn("00_CONTROL: missing", errs)
        self.assertTrue(any("04_SLICES_OUT: status" in e for e in errs))

    def test_owner_that_does_not_exist(self):
        doc = copy.deepcopy(DOC)
        doc["folders"]["00_CONTROL"]["owners"] = ["no/such/file.py"]
        errs, _ = of.check(doc, NODES, lambda rel: None)
        self.assertIn("00_CONTROL: owner no/such/file.py does not exist at HEAD", errs)

    def test_open_pr_needs_number_and_claims_need_link(self):
        doc = copy.deepcopy(DOC)
        doc["folders"]["01_DROPBOX_IN"].pop("pr")
        doc["unverified_claims"][1]["evidence"] = "trust me"
        errs, _ = of.check(doc, NODES, fake_oid)
        self.assertIn("01_DROPBOX_IN: open_pr needs a PR number", errs)
        self.assertTrue(any("evidence must be null or a link" in e for e in errs))

    def test_claims_stay_unverified(self):
        self.assertTrue(all(c["evidence"] is None for c in DOC["unverified_claims"]))

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            dur = Path(tmp) / "d.json"
            dur.write_text(json.dumps({k: 1 for k in NODES}), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = of.main(["--json", "--durations", str(dur)])
        r = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(r["wishbone"]["track_c"]["unit"], "seconds")


if __name__ == "__main__":
    unittest.main()
