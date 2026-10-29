"""Offline wave scheduler safety, precedence and disjointness tests."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_spine_wave_plan", ROOT / "scripts/ci_spine_wave_plan.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
SHA = "a" * 40


def job(id, lane, owns, deps=(), prio=1, stage="PREPARE"):
    return {"id": id, "lane": lane, "owns": owns, "depends": list(deps),
            "priority": prio, "stage": stage}


def sample():
    index = {"schema": M.INDEX_SCHEMA, "source": {"checkout_sha": SHA, "expected_sha": SHA},
             "verdict": "PASS_STATIC_BINDINGS_ONLY", "errors": [],
             "assurance": {"merge_admission": "HOLD"}}
    policy = {"schema": M.POLICY_SCHEMA, "max_workers": 3,
              "tasks": [job("CI-N-A", "WORKER-A", ["src/a.py"]),
                        job("CI-N-B", "WORKER-B", ["src/b.py"]),
                        job("CI-N-C", "WORKER-C", ["src/a.py"], prio=2),
                        job("CI-N-FANIN", "REVIEW", ["docs/review.md"],
                            ["CI-N-A", "CI-N-B"], stage="INTEGRATE")]}
    return index, policy


def receipt(sha=SHA, verdict="PASS"):
    return {"source_sha": sha, "run_id": 43, "tests_ran": 3, "verdict": verdict}


class WaveContract(unittest.TestCase):
    def test_disjoint_fanout_and_nonexecuted_fanin(self):
        index, policy = sample()
        doc = M.build(index, policy)
        self.assertEqual(doc["candidate_workers"], ["CI-N-A", "CI-N-B"])
        self.assertEqual(doc["authority"]["execution"], "NONE")
        rows = {r["id"]: r for r in doc["rows"]}
        self.assertEqual(rows["CI-N-C"]["disposition"], "DEFER_OWNERSHIP_COLLISION")
        self.assertEqual(rows["CI-N-FANIN"]["disposition"], "BLOCKED_DEPENDENCY")
        self.assertEqual(doc["authority"]["merge"], "HOLD")

    def test_exact_receipts_only_advance_deps_but_are_not_authority(self):
        i, p = sample()
        doc = M.build(i, p, {"CI-N-A": receipt(), "CI-N-B": receipt()})
        self.assertEqual(doc["candidate_workers"], ["CI-N-FANIN", "CI-N-C"])
        self.assertEqual(len(doc["declared_receipts_not_revalidated"]), 2)
        self.assertEqual(doc["authority"]["merge"], "HOLD")

    def test_stale_receipt_does_not_release_fanin(self):
        i, p = sample()
        doc = M.build(i, p, {"CI-N-A": receipt("b" * 40), "CI-N-B": receipt()})
        self.assertNotIn("CI-N-FANIN", doc["candidate_workers"])

    def test_invalid_input_never_selects_workers(self):
        i, p = sample()
        i["verdict"] = "CI_SPINE_CONTRACT_FIRST_RED"
        self.assertEqual(M.build(i, p)["candidate_workers"], [])
        i["verdict"] = "PASS_STATIC_BINDINGS_ONLY"
        i["source"]["expected_sha"] = "b" * 40
        self.assertEqual(M.build(i, p)["candidate_workers"], [])

    def test_cycles_fail_closed(self):
        i, p = sample()
        p["tasks"][0]["depends"] = ["CI-N-FANIN"]
        doc = M.build(i, p)
        self.assertIn("cycle", " ".join(doc["errors"]))
        self.assertEqual(doc["candidate_workers"], [])

    def test_missing_dependency_and_duplicate_id_fail(self):
        i, p = sample()
        p["tasks"][0]["depends"] = ["MISSING"]
        self.assertIn("dangling", " ".join(M.build(i, p)["errors"]))
        p["tasks"][0]["depends"] = []
        p["tasks"].append(dict(p["tasks"][0]))
        self.assertIn("duplicate", " ".join(M.build(i, p)["errors"]))

    def test_path_safety_and_parent_collision(self):
        for bad in ("../a", "/abs", "x/../../a", "x\\a", "./x"):
            self.assertFalse(M.valid_path(bad))
        self.assertTrue(M.collision("src/**", "src/a.py"))
        self.assertFalse(M.collision("src/a.py", "src2/a.py"))

    def test_same_lane_and_worker_capacity(self):
        i, p = sample()
        p["tasks"][2]["owns"] = ["src/c.py"]
        p["tasks"][2]["lane"] = "WORKER-B"
        self.assertEqual({r["id"]: r["disposition"] for r in M.build(i, p)["rows"]}["CI-N-C"], "DEFER_LANE_OCCUPIED")
        p["tasks"][2]["lane"] = "WORKER-C"
        p["max_workers"] = 2
        self.assertEqual({r["id"]: r["disposition"] for r in M.build(i, p)["rows"]}["CI-N-C"], "DEFER_WORKER_CAPACITY")

    def test_shipped_policy_is_complete_but_not_prequalified(self):
        contract = json.loads((ROOT / "governance/ci_spine/CI_SPINE_WAVE_POLICY_V1.json").read_text())
        self.assertEqual(contract["schema"], M.POLICY_SCHEMA)
        self.assertEqual(len(contract["tasks"]), 8)
        i, _ = sample()
        doc = M.build(i, contract)
        self.assertEqual(doc["candidate_workers"], ["CI-N6-SOURCE", "CI-N6-DELTA", "CI-N6-MATRIX"])
        self.assertEqual(doc["verdict"], "PROPOSED_ONLY_NOT_EXECUTED")
        self.assertTrue(any(x["disposition"] == "BLOCKED_DEPENDENCY" for x in doc["rows"]))


if __name__ == "__main__":
    unittest.main()
