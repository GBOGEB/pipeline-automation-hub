"""Offline tests for the FPC root-red DAG (no network)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

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
        self.assertEqual(waves[2:], [["FPC_RED"], ["MERGE_ADMISSION_UNVERIFIED"]])

    def test_realistic_red_but_merged_witness_cannot_claim_enforced_denial(self):
        """A red receipt alone is not a GitHub-enforced block (Hub #1154/#1277)."""
        failed = ev(1154, "949dbd1b4b50dba14de146f087af8d3dc4c7d15d",
                    2, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 44458722990)
        # A later main merge is a separate event, not an FPC PASS or merge denial.
        failed["merged_at"] = "2026-11-19T12:42:53Z"
        rows = m.attribute_all([failed], {})
        counts = m.node_counts(rows)
        self.assertEqual(counts["FPC_RED"], 1)
        self.assertEqual(counts["MERGE_ADMISSION_UNVERIFIED"], 1)
        self.assertNotIn("MERGE_BLOCKED", counts)
        self.assertNotIn("MERGE_BLOCKED", m.NODES)
        self.assertEqual(rows[0]["status"], "FAIL")
        self.assertEqual(rows[0]["merged_at"], "2026-11-19T12:42:53Z")

    def test_malformed_receipt_is_process_debt_not_unknown_root(self):
        for reason in ("INVALID_RECEIPT_JSON", "INVALID_RECEIPT_FIELDS",
                       "INVALID_RECEIPT_SCHEMA", "MISSING_REQUIRED_RUNS"):
            with self.subTest(reason=reason):
                self.assertEqual(m.reason_node(reason), "R_RECEIPT_MISSING")
                rows = m.attribute_all([ev(33, "x" * 40, 1, "FAIL", reason, 300)], {})
                self.assertEqual((rows[0]["klass"], rows[0]["source"]),
                                 ("PROCESS", "SRC_RECEIPT_ABSENT"))
                self.assertTrue(m.ledger(rows)[0]["pr_can_fix"])
                self.assertEqual(m.summarize(rows)["red"], 1)

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
        self.assertTrue(m.quota_notice([{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": body, "created_at": "2026-11-10T10:00:00Z"}]))
        self.assertTrue(m.quota_notice([{"author": {"login": "chatgpt-codex-connector"}, "body": body, "createdAt": "2026-11-10T11:00:00+01:00"}]))
        self.assertFalse(m.quota_notice([{"user": {"login": "someone"}, "body": body, "created_at": "2026-11-10T10:00:00Z"}]))
        self.assertFalse(m.quota_notice([{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": body}]))
        self.assertFalse(m.quota_notice([{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": "Review done"}]))

    def test_head_map_fills_the_pr_and_finds_the_quota(self):
        e = ev(None, "h1", 3, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1)
        rows = m.attribute_all([e], {"1171": {"codex_quota": True}}, {"h1": 1171})
        self.assertEqual((rows[0]["pr"], rows[0]["source"]), (1171, "SRC_CODEX_QUOTA"))

    def test_an_earlier_stage_failure_does_not_prove_review_completed(self):
        evals = [ev(7, "f", 9, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1),
                 ev(7, "f", 8, "FAIL", "STALE_HEAD: receipt=a current=f", 2),
                 ev(7, "f", 7, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 3)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, {})}
        self.assertEqual(rows[1]["source"], "SRC_CODEX_REVIEW_ABSENT")

    def test_a_later_stage_failure_proves_the_earlier_stage_passed(self):
        evals = [ev(8, "g", 9, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1),
                 ev(8, "g", 8, "FAIL", "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: 1", 2)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, {})}
        self.assertEqual(rows[1]["source"], "SRC_CODEX_REVIEW_PENDING")

    def test_quota_notice_is_matched_in_time(self):
        notice = (NOW - dt.timedelta(hours=5)).isoformat().replace("+00:00", "Z")
        prs = {"9": {"codex_quota": True, "quota_at": [notice]}}
        evals = [ev(9, "h", 30, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 1),
                 ev(9, "h", 5.5, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 2),
                 ev(9, "h", 2, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 3)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, prs)}
        self.assertEqual(rows[1]["source"], "SRC_CODEX_REVIEW_ABSENT")
        self.assertEqual(rows[2]["source"], "SRC_CODEX_QUOTA")
        self.assertEqual(rows[3]["source"], "SRC_CODEX_QUOTA")

    def test_quota_notices_carry_timestamps(self):
        body = "You have reached your Codex usage limits for code reviews."
        got = m.quota_notices([{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": body, "created_at": "2026-11-10T22:36:02Z"},
                               {"user": {"login": "someone"}, "body": body, "created_at": "2026-11-10T22:00:00Z"}])
        self.assertEqual(got, ["2026-11-10T22:36:02Z"])

    def test_timezone_aware_timestamps_and_quota_sort(self):
        self.assertEqual(m.ts("2026-11-10T12:00:00Z"),
                         m.ts("2026-11-10T13:00:00+01:00"))
        self.assertEqual(m.ts("2026-11-10T12:00:00Z"),
                         m.ts("2026-11-10T07:00:00-05:00"))
        with self.assertRaises(ValueError):
            m.ts("2026-11-10T12:00:00")
        body = "You have reached your Codex usage limits for code reviews."
        notice = lambda when: {"user": {"login": "chatgpt-codex-connector[bot]"},
                               "body": body, "created_at": when}
        first = "2026-11-10T23:30:00-05:00"  # 11 Nov 04:30 UTC
        second = "2026-11-11T05:00:00Z"       # 11 Nov 05:00 UTC
        self.assertEqual(m.quota_notices([notice(second), notice(first)]),
                         [first, second])

    def test_evaluations_are_sorted_by_utc_instant_not_offset_text(self):
        later = ev(22, "head", 1, "PASS", run=2)
        later["created_at"] = "2026-11-11T05:00:00Z"
        earlier = ev(22, "head", 2, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE", run=1)
        earlier["created_at"] = "2026-11-10T23:30:00-05:00"
        rows = m.attribute_all([later, earlier], {})
        self.assertEqual([r["run_id"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["source"], "SRC_PROOF_PENDING")

    def test_lookup_refresh_uses_offset_aware_instant(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            fresh = (dt.datetime.now(dt.timezone.utc) - m.REFRESH_SPAN
                     + dt.timedelta(minutes=30)).astimezone(
                         dt.timezone(dt.timedelta(hours=-12))).isoformat()
            old = (dt.datetime.now(dt.timezone.utc) - m.REFRESH_SPAN
                   - dt.timedelta(minutes=30)).astimezone(
                       dt.timezone(dt.timedelta(hours=12))).isoformat()
            (cache / "heads.json").write_text(json.dumps({"fresh": 9, "old": 10}))
            (cache / "prs.json").write_text(json.dumps({
                "9": {"codex_quota": False, "quota_at": []},
                "10": {"codex_quota": False, "quota_at": []}}))
            path = cache / "evaluations.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in [
                {"pr": 9, "head_sha": "fresh", "created_at": fresh},
                {"pr": 10, "head_sha": "old", "created_at": old}]) + "\n")
            with mock.patch.object(m, "_get_comments", return_value=[]) as get_comments:
                m._lookups(path, cache, "unused-token")
            get_comments.assert_called_once_with(9, "unused-token")

    def test_failed_wrapper_with_positive_evaluator_receipt_is_not_pass(self):
        """Passing evaluator bytes do not override a terminal failed gate wrapper."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("r.json", json.dumps({"merge_allowed": True,
                                            "head_sha": "a" * 40,
                                            "pr_number": "1187"}))
        def fake(url, token, raw=False):
            return buf.getvalue() if raw else {"artifacts": [
                {"name": m.ARTIFACT, "expired": False, "archive_download_url": "u"}]}
        run = {"id": 446, "created_at": "2026-11-20T11:00:00Z",
               "event": "pull_request_target", "conclusion": "failure",
               "head_sha": "b" * 40, "pull_requests": []}
        with mock.patch.object(m, "_get", fake):
            row = m._reason(run, "unused")
        self.assertEqual((row["status"], row["reason"]),
                         ("UNKNOWN", "WRAPPER_NOT_SUCCESS"))
        summary = m.summarize(m.attribute_all([row], {}))
        self.assertEqual((summary["pass"], summary["red"], summary["unverified"]),
                         (0, 0, 1))

    def test_successful_wrapper_with_positive_evaluator_receipt_is_pass(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("r.json", json.dumps({"merge_allowed": True,
                                            "head_sha": "a" * 40,
                                            "pr_number": "1187"}))
        def fake(url, token, raw=False):
            return buf.getvalue() if raw else {"artifacts": [
                {"name": m.ARTIFACT, "expired": False, "archive_download_url": "u"}]}
        run = {"id": 447, "created_at": "2026-11-20T11:00:00Z",
               "event": "pull_request_target", "conclusion": "success",
               "head_sha": "b" * 40, "pull_requests": []}
        with mock.patch.object(m, "_get", fake):
            row = m._reason(run, "unused")
        self.assertEqual((row["status"], row["reason"]), ("PASS", None))

    def test_successful_wrapper_without_fpc_receipt_is_unverified(self):
        """A green Actions wrapper may not manufacture an evaluator PASS."""
        run = {"id": 444, "created_at": "2026-11-19T20:10:00Z",
               "event": "pull_request_target", "conclusion": "success",
               "head_sha": "b" * 40, "pull_requests": []}
        with mock.patch.object(m, "_get", return_value={"artifacts": []}):
            row = m._reason(run, "unused")
        self.assertEqual((row["status"], row["reason"], row["head_from"]),
                         ("UNKNOWN", "NO_RECEIPT_ARTIFACT", "run"))
        enriched = m.attribute_all([row], {})
        self.assertEqual((enriched[0]["klass"], enriched[0]["source"]),
                         ("UNKNOWN", None))
        summary = m.summarize(enriched)
        self.assertEqual((summary["pass"], summary["red"], summary["unverified"],
                          summary["verified_evaluations"]), (0, 0, 1, 0))
        self.assertIsNone(summary["red_rate"])
        self.assertEqual(m.node_counts(enriched), {})
        self.assertEqual(m.ledger(enriched), [])

    def test_receipt_without_boolean_decision_cannot_make_green_or_red(self):
        """Non-boolean/malformed decision is unverified even when wrapper succeeds."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("r.json", json.dumps({"merge_allowed": "true",
                                            "head_sha": "a" * 40,
                                            "pr_number": "1187"}))
        def fake(url, token, raw=False):
            return buf.getvalue() if raw else {"artifacts": [
                {"name": m.ARTIFACT, "expired": False, "archive_download_url": "u"}]}
        run = {"id": 445, "created_at": "2026-11-19T20:11:00Z",
               "event": "pull_request_target", "conclusion": "success",
               "head_sha": "b" * 40, "pull_requests": []}
        with mock.patch.object(m, "_get", fake):
            row = m._reason(run, "unused")
        self.assertEqual((row["status"], row["reason"], row["head_sha"]),
                         ("UNKNOWN", "NO_EVALUATOR_DECISION", "a" * 40))

    def test_missing_receipt_does_not_dilute_verified_red_rate(self):
        good = ev(1, "a", 3, "PASS", run=1)
        bad = ev(2, "b", 2, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 2)
        missing = ev(3, "c", 1, "UNKNOWN", "NO_RECEIPT_ARTIFACT", 3)
        rows = m.attribute_all([good, bad, missing], {})
        s = m.summarize(rows)
        self.assertEqual((s["evaluations"], s["verified_evaluations"], s["pass"],
                          s["red"], s["unverified"]), (3, 2, 1, 1, 1))
        self.assertEqual(s["red_rate"], 0.5)
        self.assertEqual(m.node_counts(rows)["FPC_RED"], 1)

    def test_receipt_head_and_pr_win_over_the_run(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("r.json", json.dumps({"head_sha": "a" * 40, "pr_number": "1187", "reason": "X", "merge_allowed": False}))

        def fake(url, token, raw=False):
            return buf.getvalue() if raw else {"artifacts": [{"name": m.ARTIFACT, "expired": False, "archive_download_url": "u"}]}

        run = {"id": 1, "created_at": "t", "event": "pull_request_target", "conclusion": "failure", "head_sha": "b" * 40,
               "pull_requests": []}
        with mock.patch.object(m, "_get", fake):
            r = m._reason(run, "tok")
        self.assertEqual((r["head_sha"], r["run_head_sha"], r["head_from"], r["pr"]), ("a" * 40, "b" * 40, "receipt", 1187))

    def test_a_new_head_does_not_rescue_an_old_one(self):
        evals = [ev(6, "old", 9, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 1), ev(6, "new", 8, "PASS", run=2)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, {})}
        self.assertEqual(rows[1]["source"], "SRC_PROOF_FAILED")

    def test_same_head_on_another_pr_does_not_lend_evidence(self):
        # Review finding 1 (#1187): history is keyed by (repo, PR, head), never by SHA alone.
        evals = [ev(11, "same", 9, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 1),
                 ev(12, "same", 8, "PASS", run=2),
                 ev(13, "same", 7, "FAIL", "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD", 3),
                 ev(14, "same", 6, "FAIL", "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: 1", 4)]
        rows = {r["run_id"]: r for r in m.attribute_all(evals, {})}
        self.assertEqual(rows[1]["source"], "SRC_PROOF_FAILED")
        self.assertEqual(rows[3]["source"], "SRC_CODEX_REVIEW_ABSENT")
        self.assertEqual(rows[1]["head_first_status"], "FAIL")
        self.assertEqual(rows[2]["head_first_status"], "PASS")
        self.assertEqual(m.summarize(list(rows.values()))["heads"], 4)

    def test_untrusted_or_mutated_proof_is_pr_fixable(self):
        # Review finding 2 (#1187): the candidate's own proof identity is not inherited infrastructure.
        for reason in ("UNTRUSTED_PROOF_WORKFLOW_IDENTITY: x/y.yml", "PROOF_WORKFLOW_MUTATED_FROM_TRUSTED_BASE: y.yml"):
            self.assertEqual(m.reason_node(reason), "R_PROOF_IDENTITY")
            rows = m.attribute_all([ev(15, "p", 3, "FAIL", reason, 1)], {})
            self.assertEqual((rows[0]["source"], rows[0]["klass"]), ("SRC_PROOF_UNTRUSTED", "PR_CAUSED"))
            self.assertTrue(m.ledger(rows)[0]["pr_can_fix"])
            self.assertEqual(m.summarize(rows)["inherited_share_of_red"], 0.0)


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

    def test_a_retry_inside_a_window_is_not_a_first_pass(self):
        rows = m.attribute_all([ev(10, "k", 50, "FAIL", "MISSING_REQUIRED_PROOF_PURPOSE: x", 1),
                                ev(10, "k", 3, "PASS", run=2)], {})
        w = {x["window"]: x for x in m.windows(rows, NOW)}
        self.assertEqual(w["4h"]["evaluations"], 1)
        self.assertEqual(w["4h"]["first_pass_rate"], 0.0)
        self.assertEqual(w["4h"]["head_closure_rate"], 1.0)

    def test_unresolved_pr_is_not_counted_as_a_pr(self):
        # Review finding 3 (#1187): None is an unresolved identity, reported apart from the PR count.
        s = m.summarize(m.attribute_all([ev(None, "u1", 3, "FAIL", "MISSING_RECEIPT", 1)], {}))
        self.assertEqual((s["prs"], s["unresolved_pr_evaluations"]), (0, 1))
        mixed = m.attribute_all(self.evals + [ev(None, "u1", 3, "FAIL", "MISSING_RECEIPT", 5),
                                              ev(None, "u2", 2, "FAIL", "MISSING_RECEIPT", 6)], {})
        s = m.summarize(mixed)
        self.assertEqual((s["prs"], s["unresolved_pr_evaluations"]), (4, 2))

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
        self.assertEqual(doc["node_counts"]["MERGE_ADMISSION_UNVERIFIED"], 3)
        self.assertIn("FPC-CODEX_QUOTA", md)
        self.assertTrue(svg.startswith("<svg"))


if __name__ == "__main__":
    unittest.main()
