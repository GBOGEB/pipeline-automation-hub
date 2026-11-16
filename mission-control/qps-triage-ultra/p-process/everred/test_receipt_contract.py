"""Fail-closed semantic-root receipt tests (offline fixtures are NOT native CI)."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import receipt_contract as r

A = "a" * 40
B = "b" * 40
REPO = "GBOGEB/ABACUS"
REF = REPO + "@pull/2746"
CATALOG = {"roots": [{"id": "ABACUS-RC-2026-0002", "match": [{"repo": REPO, "workflow": "CI Matrix", "job": "coverage", "step": "floor"}]}]}


def ev(run=1, conclusion="failure", sha=A, at="2026-11-15T12:00:00Z", predicate="changed-lines-below-80", scope="policy-v1"):
    return {"repo": REPO, "sha": sha, "target_ref": "pull/2746",
            "workflow": "CI Matrix", "job": "coverage", "step": "floor", "failure_predicate": predicate,
            "config_scope": scope, "run_id": run, "run_attempt": 1, "job_id": run * 10,
            "step_number": 8, "observed_at": at, "conclusion": conclusion,
            "executed_steps": 1, "url": f"https://github.com/GBOGEB/ABACUS/actions/runs/{run}",
            "source_grade": "PROVIDER_READBACK"}


def make(*events, head=A, catalog=CATALOG):
    return r.build(list(events), catalog, {REF: head})


class RootReceipts(unittest.TestCase):
    def test_repetition_one_root_two_occurrences(self):
        result = make(ev(1), ev(2))
        self.assertEqual(len(result["roots"]), 1)
        self.assertEqual(result["roots"][0]["occurrence_count"], 2)
        self.assertEqual(result["counts"]["unique"], 2)
        self.assertEqual(result["counts"]["verified_closed"], 0)
        self.assertEqual(result["roots"][0]["canonical_root_id"], "ABACUS-RC-2026-0002")
        self.assertEqual(result["roots"][0]["latest_badge"], "ROOT_RED")

    def test_repeated_delivery_is_not_repeated_occurrence(self):
        x = ev()
        result = make(x, copy.deepcopy(x))
        self.assertEqual(result["counts"]["duplicate_deliveries"], 1)
        self.assertEqual(result["counts"]["unique"], 1)

    def test_identity_mutation_fails_closed(self):
        x = ev()
        y = copy.deepcopy(x)
        y["sha"] = B
        with self.assertRaisesRegex(ValueError, "MUTATED_DELIVERY"):
            make(x, y)

    def test_different_predicate_is_different_candidate(self):
        self.assertEqual(len(make(ev(1), ev(2, predicate="scanner-auth-401"))["roots"]), 2)

    def test_different_configuration_is_different_candidate(self):
        self.assertEqual(len(make(ev(1), ev(2, scope="policy-v2"))["roots"]), 2)

    def test_cross_repo_cannot_alias_root(self):
        x = ev()
        y = ev(2)
        y["repo"] = "GBOGEB/CODEX"
        y["url"] = "https://github.com/GBOGEB/CODEX/actions/runs/2"
        self.assertEqual(len(r.build([x, y], CATALOG, {REF: A, "GBOGEB/CODEX@pull/2746": A})["roots"]), 2)

    def test_missing_or_ambiguous_root_remains_candidate(self):
        missing = make(ev(), catalog={"roots": []})
        self.assertIsNone(missing["roots"][0]["canonical_root_id"])
        amb = make(ev(), catalog={"roots": CATALOG["roots"] * 2 + [{"id": "OTHER", "match": CATALOG["roots"][0]["match"]}]})
        self.assertEqual(amb["roots"][0]["root_mapping"], "AMBIGUOUS")
        self.assertIsNone(amb["roots"][0]["canonical_root_id"])

    def test_stale_head_badge_not_green(self):
        res = make(ev(1, conclusion="success", sha=A), head=B)
        self.assertEqual(res["roots"][0]["latest_badge"], "STALE_HEAD")
        self.assertEqual(res["occurrences"][0]["admission"], "ADMISSION_HOLD")

    def test_missing_head_unknown_not_stale(self):
        res = r.build([ev()], CATALOG, {})
        self.assertEqual(res["roots"][0]["latest_badge"], "HEAD_UNKNOWN")

    def test_action_required_not_execution(self):
        x = ev(conclusion="action_required")
        x["executed_steps"] = 0
        res = make(x)
        self.assertEqual(res["roots"][0]["latest_badge"], "UNEXECUTED")
        with self.assertRaisesRegex(ValueError, "UNEXECUTED_WITH_STEPS"):
            make(ev(conclusion="action_required"))

    def test_zero_step_success_rejected(self):
        x = ev(conclusion="success")
        x["executed_steps"] = 0
        with self.assertRaisesRegex(ValueError, "ZERO_STEP_SUCCESS"):
            make(x)

    def test_out_of_order_invariant_and_regression(self):
        red = ev(1, at="2026-11-15T11:00:00Z")
        green = ev(2, conclusion="success", at="2026-11-15T12:00:00Z")
        relapse = ev(3, at="2026-11-15T13:00:00Z")
        p = make(red, green, relapse)
        q = make(relapse, red, green)
        self.assertEqual(p["sha256"], q["sha256"])
        self.assertTrue(p["roots"][0]["regression_after_success"])
        self.assertEqual(p["roots"][0]["latest_badge"], "ROOT_RED")

    def test_unproven_positive_no_verification_badge(self):
        x = ev(1, conclusion="success")
        self.assertEqual(make(x)["roots"][0]["latest_badge"], "PROOF_INCOMPLETE")

    def test_fake_proof_source_not_promoted(self):
        x = ev(1, conclusion="success")
        x["regression"] = {"negative": {"url": "https://fake.invalid/run", "head_sha": A,
                            "conclusion": "success", "source_grade": "PROVIDER_READBACK", "executed_steps": 1}}
        self.assertEqual(make(x)["roots"][0]["latest_badge"], "PROOF_INCOMPLETE")

    def test_proof_requires_distinct_run_and_independent_review(self):
        x = ev(1, conclusion="success")
        proof = {"url": "https://github.com/GBOGEB/ABACUS/actions/runs/11", "head_sha": A,
                 "conclusion": "success", "source_grade": "PROVIDER_READBACK", "executed_steps": 1}
        x["regression"] = {"negative": proof, "positive": dict(proof),
                           "independent_review": {"state": "APPROVED", "head_sha": A,
                            "source_grade": "PROVIDER_READBACK", "reviewer": "reviewer",
                            "url": "https://github.com/GBOGEB/ABACUS/pull/2746"}, "author": "worker"}
        self.assertEqual(make(x)["roots"][0]["latest_badge"], "PROOF_INCOMPLETE")
        x["regression"]["positive"]["url"] = "https://github.com/GBOGEB/ABACUS/actions/runs/12"
        self.assertEqual(make(x)["roots"][0]["latest_badge"], "REGRESSION_VERIFIED")
        x["regression"]["independent_review"]["reviewer"] = "worker"
        self.assertEqual(make(x)["roots"][0]["latest_badge"], "PROOF_INCOMPLETE")

    def test_proof_cannot_override_red_or_old_head(self):
        x = ev(1, conclusion="failure")
        x["regression"] = {"negative": {}, "positive": {}}
        self.assertEqual(make(x)["roots"][0]["latest_badge"], "ROOT_RED")

    def test_kahn_parallel_lanes_and_cycle(self):
        d = make(ev())["dag_layers"]
        self.assertEqual(d[0], ["badge", "negative", "normalize"])
        self.assertEqual(d[-1], ["admission"])
        with self.assertRaisesRegex(ValueError, "DAG_CYCLE"):
            r.kahn(["A", "B"], [("A", "B"), ("B", "A")])
        with self.assertRaisesRegex(ValueError, "DAG_UNKNOWN_NODE"):
            r.kahn(["A"], [("A", "B")])

    def test_disjoint_paths_or_collision(self):
        self.assertTrue(r.check_disjoint({"A": ["root.py"], "B": ["test.py"], "C": ["badges.py"]}))
        with self.assertRaisesRegex(ValueError, "WRITE_COLLISION"):
            r.check_disjoint({"A": ["root.py"], "B": ["root.py"]})

    def test_html_escapes_source_and_never_claims_admitted(self):
        h = r.render_html(make(ev()))
        self.assertIn("ADMISSION HOLD", h)
        self.assertNotIn("ADMITTED", h)

    def test_invalid_timestamp_sha_and_ids_rejected(self):
        cases = [("sha", "bad", "EVENT_SHA"), ("observed_at", "yesterday", "TIMESTAMP_INVALID"),
                 ("run_attempt", True, "RUN_IDENTITY"), ("step_number", -1, "JOB_STEP_IDENTITY")]
        for key, value, err in cases:
            with self.subTest(key=key):
                x = ev()
                x[key] = value
                with self.assertRaisesRegex(ValueError, err):
                    make(x)

    def test_cli_deterministic_and_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            files = {"events.json": [ev()], "catalog.json": CATALOG, "heads.json": {REF: A}}
            for name, data in files.items():
                (d/name).write_text(json.dumps(data), encoding="utf-8")
            before = {k: (d/k).read_bytes() for k in files}
            out = d/"out"
            self.assertEqual(r.main(["--events", str(d/"events.json"), "--catalog", str(d/"catalog.json"),
                                     "--heads", str(d/"heads.json"), "--out", str(out)]), 0)
            self.assertEqual(before, {k: (d/k).read_bytes() for k in files})
            self.assertEqual(json.loads((out/"root_receipt.json").read_text())["counts"]["unique"], 1)
            self.assertTrue((out/"root_receipt.html").exists())

if __name__ == "__main__":
    unittest.main()