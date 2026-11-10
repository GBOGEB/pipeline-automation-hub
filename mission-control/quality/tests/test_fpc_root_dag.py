"""Offline tests for the FPC root-red DAG (no network)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "fpc_root_dag.py"
spec = importlib.util.spec_from_file_location("fpc_root_dag", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

NOW = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)


def ev(pr, head, hours_ago, status, reason=None, run=0):
    t = (NOW - dt.timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {"run_id": run or hash((pr, head, hours_ago)) & 0xFFFFFF, "created_at": t, "pr": pr, "head_sha": head,
            "status": status, "reason": reason}


class Model(unittest.TestCase):
    def test_kahn_waves_go_source_reason_outcome(self):
        waves = m.kahn_waves()
        self.assertEqual(len(waves), 4)
        self.assertTrue(all(m.NODES[n][0] == "SOURCE" for n in waves[0]))
        self.assertTrue(all(m.NODES[n][0] == "REASON" for n in waves[1]))
        self.assertEqual(waves[2:], [["FPC_RED"], ["MERGE_BLOCKED"]])

    def test_every_source_has_a_class(self):
        for n, (kind, klass, _) in m.NODES.items():
            if kind == "SOURCE":
                self.assertIn(klass, ("INHERITED", "TRANSIENT", "PR_CAUSED", "PROCESS", "UNKNOWN"), n)

    def test_reason_codes_map(self):
        self.assertEqual(m.reason_node("CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD"), "R_CODEX_REVIEW_NOT_COMPLETED")
        self.assertEqual(m.reason_node("MISSING_REQUIRED_PROOF_PURPOSE: canonical_self_test"), "R_MISSING_PROOF")
        self.assertEqual(m.reason_node("CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP: x"), "R_CONTROL_PLANE_BOOTSTRAP")
        self.assertEqual(m.reason_node("STALE_HEAD: receipt=a current=b"), "R_STALE_HEAD")
        self.assertEqual(m.reason_node("CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: 1 open P0/P1"), "R_CODEX_FINDINGS")
        self.assertEqual(m.reason_node("MISSING_RECEIPT"), "R_RECEIPT_MISSING")
        self.assertEqual(m.reason_node("INVALID_RECEIPT_HEAD_SHA"), "R_STALE_HEAD")
        self.assertEqual(m.reason_node("NO_RECEIPT_ARTIFACT"), "R_GATE_ERROR")
        self.assertEqual(m.reason_node("PRE_EVALUATOR_FAILURE"), "R_GATE_ERROR")
        self.assertEqual(m.reason_node("GitHub API 502 for /repos/x/pulls/1"), "R_GATE_ERROR")
        self.assertEqual(m.reason_node("NO_ALLOWLISTED_PROOF_RUN_ON_EXACT_HEAD"), "R_MISSING_PROOF")
        self.assertEqual(m.reason_node("SOMETHING_NEW"), "R_OTHER")
        self.assertEqual(m.reason_node(None), "R_OTHER")


class Attribution(unittest.TestCase):
    def test_quota_is_inherited_even_if_later_evals_exist(self):
        rows = m.attribute_all([ev(1, "a", 3, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1)], {"1": {"codex_quota": True}})
        self.assertEqual((rows[0]["source"], rows[0]["klass"]), ("SRC_CODEX_QUOTA", "INHERITED"))

    def test_review_race_is_transient_when_a_later_eval_got_past(self):
        evals = [ev(2, "b", 5, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1), ev(2, "b", 4, "PASS", run=2)]
        rows = m.attribute_all(evals, {})
        self.assertEqual(rows[0]["source"], "SRC_CODEX_REVIEW_PENDING")
        self.assertEqual(rows[1]["klass"], "PASS")

    def test_review_never_completed_without_quota_is_unknown(self):
        rows = m.attribute_all([ev(3, "c", 5, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1)], {})
        self.assertEqual(rows[0]["klass"], "UNKNOWN")

    def test_proof_failed_vs_pending(self):
        evals = [ev(4, "d", 9, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 1),
                 ev(4, "d", 8, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 2),
                 ev(5, "e", 9, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 3)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, {})}
        self.assertEqual(rows[1]["source"], "SRC_PROOF_PENDING")
        self.assertEqual(rows[3]["source"], "SRC_PROOF_FAILED")
        self.assertEqual(rows[3]["klass"], "PR_CAUSED")

    def test_quota_notice_matches_rest_and_graphql_logins(self):
        body = "You have reached your Codex usage limits for code reviews."
        self.assertTrue(m.quota_notice([{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": body}]))
        self.assertTrue(m.quota_notice([{"author": {"login": "chatgpt-codex-connector"}, "body": body}]))
        self.assertFalse(m.quota_notice([{"user": {"login": "someone"}, "body": body}]))
        self.assertFalse(m.quota_notice([{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": "Review done"}]))

    def test_head_map_fills_the_pr_and_finds_the_quota(self):
        e = ev(None, "h1", 3, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1)
        rows = m.attribute_all([e], {"1171": {"codex_quota": True}}, {"h1": 1171})
        self.assertEqual((rows[0]["pr"], rows[0]["source"]), (1171, "SRC_CODEX_QUOTA"))

    def test_a_new_head_does_not_rescue_an_old_one(self):
        evals = [ev(6, "old", 9, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 1), ev(6, "new", 8, "PASS", run=2)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, {})}
        self.assertEqual(rows[1]["source"], "SRC_PROOF_FAILED")


class Metrics(unittest.TestCase):
    def setUp(self):
        self.evals = [ev(1, "a", 2, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1),
                      ev(2, "b", 30, "FAIL", "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP: x", 2),
                      ev(3, "c", 100, "PASS", run=3),
                      ev(4, "d", 400, "FAIL", "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: 1", 4)]
        self.rows = m.attribute_all(self.evals, {"1": {"codex_quota": True}})

    def test_windows_are_cumulative_back_from_now(self):
        w = {x["window"]: x for x in m.windows(self.rows, NOW)}
        self.assertEqual([w[k]["evaluations"] for k in ("4h", "24h", "2d", "5d", "21d", "total")], [1, 1, 2, 3, 4, 4])
        self.assertEqual(w["2d"]["inherited_share_of_red"], 1.0)
        self.assertEqual(w["total"]["pr_caused_share_of_red"], round(1 / 3, 4))
        self.assertEqual(w["total"]["first_pass_rate"], 0.25)
        self.assertEqual(list(x["window"] for x in m.windows(self.rows, NOW)), [n for n, _ in m.WINDOWS])

    def test_iterations_label_newest_block_n(self):
        it = m.iterations(self.rows, block=2)
        self.assertEqual([x["label"] for x in it], ["N-2", "N"])
        self.assertEqual(sum(x["evaluations"] for x in it), 4)

    def test_ledger_marks_what_the_pr_cannot_fix(self):
        led = {x["source"]: x for x in m.ledger(self.rows)}
        self.assertFalse(led["SRC_CODEX_QUOTA"]["pr_can_fix"])
        self.assertFalse(led["SRC_CONTROLLER_PATH"]["pr_can_fix"])
        self.assertTrue(led["SRC_CODE_FINDINGS"]["pr_can_fix"])

    def test_project_writes_all_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            cache, out = Path(d) / "c", Path(d) / "o"
            cache.mkdir()
            (cache / "evaluations.jsonl").write_text("\n".join(json.dumps(e) for e in self.evals), encoding="utf-8")
            (cache / "prs.json").write_text(json.dumps({"1": {"codex_quota": True}}), encoding="utf-8")
            doc = m.project(cache, out, NOW)
            names = sorted(p.name for p in out.iterdir())
            md = (out / "fpc_root_dag.md").read_text(encoding="utf-8")
            svg = (out / "fpc_dag.svg").read_text(encoding="utf-8")
        self.assertEqual(names, ["fpc_dag.svg", "fpc_iterations.svg", "fpc_root_dag.json", "fpc_root_dag.md", "fpc_windows.svg"])
        self.assertEqual(doc["node_counts"]["MERGE_BLOCKED"], 3)
        self.assertIn("FPC-CODEX_QUOTA", md)
        self.assertTrue(svg.startswith("<svg"))


if __name__ == "__main__":
    unittest.main()
