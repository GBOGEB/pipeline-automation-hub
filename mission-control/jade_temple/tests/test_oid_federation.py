"""OID federation crosswalk and wishbone kernel: every handover folder maps to a real
owner, open PR or parked item; pruning keeps the schedule; A and B converge; DSM / CPM /
makespan stay with their gg_MATH owner."""
import copy
import importlib.util
import io
import json
import tempfile
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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

    def test_cycle_fails_closed(self):
        with self.assertRaises(ValueError):
            of.wishbone({"a": ["b"], "b": ["a"]})

    def test_wishbone_converges_on_committed_dag(self):
        w = of.wishbone(PREREQS)
        self.assertTrue(w["track_c"]["converged"])
        self.assertTrue(w["track_c"]["idempotent"])
        self.assertEqual(of.wishbone(w["track_c"]["dag"])["track_c"]["dag"], w["track_c"]["dag"])
        self.assertEqual(w["track_a"]["waves"], w["track_b"]["waves"])
        self.assertEqual(w["track_c"]["wave_count"], len(w["track_c"]["waves"]))
        self.assertEqual(w["track_a"]["critical"], w["track_b"]["critical"])
        self.assertEqual(w["track_a"]["critical"][0], "C1_methane")

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
        doc["folders"]["01_DROPBOX_IN"] = {"title": "bus", "status": "open_pr"}
        doc["unverified_claims"][1]["evidence"] = "trust me"
        errs, _ = of.check(doc, NODES, fake_oid)
        self.assertIn("01_DROPBOX_IN: open_pr needs a PR number", errs)
        self.assertTrue(any("evidence must be null or a link" in e for e in errs))

    def test_mip_is_modernize_innovate_perpetuate(self):
        self.assertEqual(set(DOC["mip"]), {"modernize", "innovate", "perpetuate"})
        mip = next(t for t in DOC["term_collisions"] if t["term"] == "MIP")
        self.assertIn("Perpetuate", mip["hub_meaning"])
        self.assertNotIn("Prune", mip["hub_meaning"])

    def test_perpetuate_needs_every_control(self):
        doc = copy.deepcopy(DOC)
        del doc["mip"]["perpetuate"]["properties"]["mycelium_golden_thread"]
        doc["mip"]["innovate"]["owners"] = []
        errs, _ = of.check(doc, NODES, fake_oid)
        self.assertIn("mip.perpetuate: property mycelium_golden_thread is not bound to a control", errs)
        self.assertIn("mip.innovate: names no owner", errs)

    def test_claims_stay_unverified(self):
        self.assertTrue(all(c["evidence"] is None for c in DOC["unverified_claims"]))

    def test_cli_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = of.main(["--json"])
        r = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(r["wishbone"]["track_c"]["wave_count"], 9)
        self.assertIn(r["gg_math_kernel"]["status"], ("OK", "UNKNOWN"))

    def test_dsm_and_cpm_are_not_reimplemented(self):
        # Owner decision 2026-11-12: gg_MATH kernels/dsm_makespan.py (GBOGEB/gg_MATH#128).
        for name in ("cpm", "dsm", "makespan_bounds"):
            self.assertFalse(hasattr(of, name), name)


def fake_gg_math(tmp, schema=of.GG_MATH_SCHEMA, length=9.0):
    kern = Path(tmp) / "kernels"
    kern.mkdir()
    (kern / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    (kern / "dsm_makespan.py").write_text(FAKE.format(schema=schema, length=length),
                                          encoding="utf-8", newline="\n")
    return Path(tmp)


FAKE = 'SCHEMA = "{schema}"\n\n\ndef evaluate(lanes, workers):\n    return {{"schema": SCHEMA, "critical_path": {{"length": {length}, "total_work": float(len(lanes))}},\n            "workers": list(workers), "first": lanes[0]["id"]}}\n'


class GgMathKernel(unittest.TestCase):
    def pinned(self, root):
        return of.gg_math_kernel(PREREQS, root, head=lambda r: of.GG_MATH_PIN)

    def test_no_checkout_is_unknown_not_pass(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GG_MATH_ROOT", None)
            g = of.gg_math_kernel(PREREQS)
        self.assertEqual((g["status"], g["result"]), ("UNKNOWN", None))
        self.assertIn("GG_MATH_ROOT", g["reason"])

    def test_missing_kernel_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.pinned(tmp)
        self.assertEqual(g["status"], "UNKNOWN")
        self.assertIsNone(g["result"])

    def test_wrong_commit_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = of.gg_math_kernel(PREREQS, fake_gg_math(tmp), head=lambda r: "0" * 40)
        self.assertEqual((g["status"], g["result"]), ("UNKNOWN", None))
        self.assertIn(of.GG_MATH_PIN, g["reason"])

    def test_wrong_schema_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.pinned(fake_gg_math(tmp, schema="gg-math-dsm-makespan/v0"))
        self.assertEqual((g["status"], g["result"]), ("UNKNOWN", None))

    def test_pinned_owner_runs_with_lane_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.pinned(fake_gg_math(tmp))
        self.assertEqual(g["status"], "OK")
        self.assertEqual(g["result"]["workers"], list(of.GG_MATH_WORKERS))
        self.assertEqual(g["result"]["first"], next(iter(PREREQS)))  # insertion order kept
        self.assertNotIn("kernels", __import__("sys").modules)     # no package leak

    def test_owner_disagreeing_with_hub_waves_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.pinned(fake_gg_math(tmp, length=8.0))
        self.assertEqual(g["status"], "FAIL")

    def test_real_pinned_checkout(self):
        root = os.environ.get("GG_MATH_ROOT")
        if not root:
            self.skipTest("gg_math_kernel UNKNOWN: GG_MATH_ROOT not set (no pinned gg_MATH checkout)")
        g = of.gg_math_kernel(PREREQS, root)
        self.assertEqual(g["status"], "OK", g["reason"])
        self.assertEqual(g["result"]["schema"], of.GG_MATH_SCHEMA)
        self.assertEqual(g["result"]["critical_path"]["length"], 9.0)
        self.assertEqual(g["result"]["n_lanes"], 14)


if __name__ == "__main__":
    unittest.main()
