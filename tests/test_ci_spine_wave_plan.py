"""Offline wave scheduler safety, precedence and disjointness tests."""
import contextlib
import importlib.util
import io
import json
import tempfile
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

    def test_malformed_nested_index_fails_closed_with_structured_receipt(self):
        for field, value in (("source", ["bad"]), ("source", "not-a-mapping"),
                             ("assurance", ["bad"]), ("assurance", "bad"),
                             ("errors", None)):
            with self.subTest(field=field, value=value):
                i, p = sample()
                i[field] = value
                result = M.build(i, p)
                self.assertEqual(result["verdict"], "WAVE_POLICY_FIRST_RED")
                self.assertEqual(result["candidate_workers"], [])
                self.assertTrue(result["errors"])
                self.assertEqual(result["authority"]["merge"], "HOLD")

    def test_unsupported_glob_cannot_hide_two_worker_ownership(self):
        for bad in ("src/*.py", "src/a?.py", "src/[ab].py",
                    "src/{a,b}.py", "src/**/a.py", "src/**/nested"):
            with self.subTest(bad=bad):
                self.assertFalse(M.valid_path(bad))
                i, p = sample()
                p["tasks"][0]["owns"] = [bad]
                result = M.build(i, p)
                self.assertEqual(result["candidate_workers"], [])
                self.assertIn("invalid ownership paths", " ".join(result["errors"]))
        self.assertTrue(M.valid_path("src/**"))
        i, p = sample()
        p["tasks"][0]["owns"] = ["src/**"]
        self.assertEqual({x["id"]: x["disposition"] for x in M.build(i, p)["rows"]}["CI-N-C"],
                         "DEFER_OWNERSHIP_COLLISION")

    def test_cli_malformed_nested_source_emits_first_red_receipt(self):
        index, policy = sample()
        index["source"] = ["invalid"]
        with tempfile.TemporaryDirectory() as td:
            src, pol, out = (Path(td) / name for name in ("index.json", "policy.json", "receipt.json"))
            src.write_text(json.dumps(index), encoding="utf-8")
            pol.write_text(json.dumps(policy), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = M.main(["--index", str(src), "--policy", str(pol),
                             "--out", str(out), "--check"])
            self.assertEqual(rc, 1)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["verdict"], "WAVE_POLICY_FIRST_RED")
            self.assertEqual(result["candidate_workers"], [])
            self.assertIn("malformed source object", result["errors"])

    def test_receipt_mapping_with_nonstring_keys_fails_closed(self):
        i, p = sample()
        out = M.build(i, p, {42: receipt()})
        self.assertEqual(out["candidate_workers"], [])
        self.assertIn("receipt keys must be strings", out["errors"])

    def test_windows_casefold_aliases_cannot_run_concurrently(self):
        self.assertTrue(M.collision("src/A.py", "src/a.py"))
        self.assertTrue(M.collision("SRC/**", "src/subdir/a.py"))
        self.assertFalse(M.collision("src/a.py", "src-extra/a.py"))
        i, p = sample()
        p["tasks"][2]["owns"] = ["SRC/A.py"]
        p["tasks"][0]["owns"] = ["src/a.py"]
        result = M.build(i, p)
        self.assertEqual({t["id"]: t["disposition"] for t in result["rows"]}["CI-N-C"],
                         "DEFER_OWNERSHIP_COLLISION")
        self.assertEqual(result["candidate_workers"], ["CI-N-A", "CI-N-B"])

    def test_thousand_task_chain_and_cycle_have_structured_outcomes(self):
        i, p = sample()
        p["tasks"] = [job("CI-L-" + str(n).zfill(4), "WORKER-A",
                          ["src/" + str(n).zfill(4) + ".py"],
                          ["CI-L-" + str(n - 1).zfill(4)] if n else [])
                      for n in range(1200)]
        good = M.build(i, p)
        self.assertEqual(good["errors"], [])
        self.assertEqual(good["candidate_workers"], ["CI-L-0000"])
        p["tasks"][0]["depends"] = ["CI-L-1199"]
        bad = M.build(i, p)
        self.assertEqual(bad["candidate_workers"], [])
        self.assertIn("cycle", " ".join(bad["errors"]))
        with tempfile.TemporaryDirectory() as td:
            src, pol, out = (Path(td) / name for name in ("index.json", "policy.json", "result.json"))
            src.write_text(json.dumps(i), encoding="utf-8")
            pol.write_text(json.dumps(p), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = M.main(["--index", str(src), "--policy", str(pol),
                             "--out", str(out), "--check"])
            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(out.read_text())["verdict"], "WAVE_POLICY_FIRST_RED")

    def test_win32_alias_component_rejected_before_worker_allocation(self):
        # Windows strips trailing dot/space, reserves devices, and uses colon for ADS.
        bad_paths = (
            "src/a.py.", "src/a.py ", "src/a.py. ",
            "src/subfolder./a.py", "src/subfolder /a.py",
            "SRC/CON", "src/con.txt", "src/PRN.log", "src/COM1.csv",
            "src/lpt9", "src/COM\u00b9.txt", "src/COM\u00b2.log",
            "src/CoM\u00b3", "src/LPT\u00b9.txt", "src/lpt\u00b2.log",
            "src/Lpt\u00b3", "src/CONIN$", "src/conout$.txt",
            "src/a.py:malicious", "src/a|b.py",
            "src/tab\\tname.py", "src/review\\nname.py",
        )
        for candidate in bad_paths:
            with self.subTest(candidate=candidate):
                self.assertFalse(M.valid_path(candidate))
                i, policy = sample()
                policy["tasks"][0]["owns"] = [candidate]
                outcome = M.build(i, policy)
                self.assertEqual(outcome["candidate_workers"], [])
                self.assertEqual(outcome["authority"]["merge"], "HOLD")
                self.assertIn("invalid ownership paths", " ".join(outcome["errors"]))
        for valid in ("src/a.py", "src/reports/R1.2.md",
                      ".github/workflows/**", "docs/Specification 1.txt"):
            with self.subTest(valid=valid):
                self.assertTrue(M.valid_path(valid))

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
