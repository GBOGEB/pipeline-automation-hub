"""hints.py: identity, recurrence, signals and proposals over an operations ledger. Offline, fake gh only."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("maroon_hints", HERE / "hints.py")
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)

RULE = "## Semgrep Finding: yaml.github-actions.security.github-actions-mutable-action-tag"
HEAD = "a" * 40


def obs(oid, pr, title=RULE, path=".github/workflows/ci.yml", state="open", root=None, ref=None, **kw):
    row = {"id": oid, "repo": "o/r", "pr": pr, "comment_id": int(oid[1:]) if oid[1:].isdigit() else 1,
           "title": title, "path": path, "anchor": "uses: actions/checkout@v4 # pinned by tag",
           "reviewer": "semgrep-app[bot]", "head_ref": ref or f"feat/{pr}", "head_repo": "o/r",
           "head_sha": HEAD, "semantic_state": state, "provider_state": "open", "pr_state": "open",
           "root_id": root or f"mr-{oid}", "sighting_count": 1, "reopen_count": 0, "closure_receipts": [],
           "first_seen": "2026-11-10T00:00:00+00:00", "last_seen": "2026-11-11T00:00:00+00:00"}
    row.update(kw)
    return row


def ledger(*rows, pulses=2):
    return {"schema": H.LEDGER_SCHEMA, "revision": 3, "pulses": {f"p{i}": {} for i in range(pulses)},
            "observations": {r["id"]: r for r in rows}, "roots": {}}


class Identity(unittest.TestCase):
    def test_rule_is_identity_and_prose_code_is_not(self):
        self.assertEqual(H.rule_of(RULE), "yaml.github-actions.security.github-actions-mutable-action-tag")
        self.assertEqual(H.rule_of("Bandit B602 shell=True"), "B602")
        self.assertIsNone(H.rule_of("Use os.path.join here"))
        self.assertIsNone(H.rule_of("Pin the SHA256 digest"))
        self.assertEqual(H.finding_key("o/r", RULE + " at ci.yml:4"), H.finding_key("o/r", RULE + " elsewhere"))
        self.assertNotEqual(H.finding_key("o/r", RULE), H.finding_key("o/x", RULE))

    def test_near_duplicates_merge_rules_never(self):
        items = [{"key": k, "repo": "o/r", "title": t} for k, t in (
            ("a", "Silent failure: exit 0 swallows the error"), ("b", "exit 0 swallows the error silently: failure"),
            ("c", RULE), ("d", "## Semgrep Finding: python.lang.security.audit.other-rule"))]
        canon = H.merge_near_duplicates(items)
        self.assertEqual(canon["a"], canon["b"])
        self.assertNotEqual(canon["c"], canon["d"])


class Analyse(unittest.TestCase):
    def test_systemic_repeat_gives_group_one_method_and_fold_back(self):
        result = H.analyse(ledger(obs("o1", 1), obs("o2", 1), obs("o3", 2), obs("o4", 3)))
        (key, f), = result["findings"].items()
        self.assertEqual((f["recurrence"], len(f["prs"]), f["open"], f["frequency"]), ("SYSTEMIC", 3, 4, 2.0))
        kinds = sorted(p["kind"] for p in result["proposals"])
        self.assertEqual(kinds, ["FOLD_BACK", "GROUP_FINDINGS", "ONE_METHOD_MANY_PACKETS"])
        group = next(p for p in result["proposals"] if p["kind"] == "GROUP_FINDINGS")
        self.assertEqual(group["item_ids"], ["o1", "o2"])  # same PR and head only: operations' own rule
        self.assertEqual(result["authority"], "DIAGNOSIS_HINT_NOT_CLOSURE_PROOF")

    def test_history_and_false_positive_signals(self):
        fixed = obs("o1", 1, state="closed", closure_receipts=[{"receipt": {"classification": "fixed"}}])
        fp1 = obs("o2", 2, state="closed", closure_receipts=[{"receipt": {"classification": "false_positive"}}])
        fp2 = obs("o3", 3, state="closed", closure_receipts=[{"receipt": {"classification": "false_positive"}}])
        live = obs("o4", 4, reopen_count=1)
        hints = {h["code"] for h in H.analyse(ledger(fixed, fp1, fp2, live))["observations"]["o4"]["hints"]}
        self.assertEqual(hints, {"SEEN_FIXED", "FP_HISTORY", "REOPENED"})

    def test_closed_pr_history_counts_but_is_never_work(self):
        review = {"repos": {"o/r": {"alerts": [{"pr": 9, "number": 90, "title": RULE, "path": ".github/workflows/ci.yml",
                                                "state": "resolved", "pr_merged": True, "closed_at": "2026-11-01"}]}}}
        result = H.analyse(ledger(obs("o1", 1)), review)
        self.assertEqual(list(result["observations"]), ["o1"])
        self.assertIn("SEEN_FIXED", {h["code"] for h in result["observations"]["o1"]["hints"]})
        self.assertEqual(next(iter(result["findings"].values()))["recurrence"], "RECURRING")

    def test_bot_fork_generated_and_tags(self):
        rows = [obs("o1", 1, ref="dependabot/pip/x"), obs("o2", 2, title="Stale number", path="mission-control/x/data/y.json"),
                obs("o3", 3, title="Census drift in the scaling pilot", path="mission-control/gogreen/scale_dock.py",
                    head_repo="fork/r")]
        result = H.analyse(ledger(*rows))
        codes = {oid: {h["code"] for h in o["hints"]} for oid, o in result["observations"].items()}
        self.assertIn("NO_PUSH_BOT_BRANCH", codes["o1"])
        self.assertIn("GENERATED_PATH", codes["o2"])
        self.assertIn("NO_PUSH_FORK", codes["o3"])
        self.assertTrue({"PINNED_OID", "SCALING_PILOT"} <= set(result["observations"]["o3"]["tags"]))

    def test_head_signals_read_only(self):
        calls = []

        def gh(args):
            calls.append(args)
            if "pulls/comments/" in args[-1]:
                return 0, json.dumps({"body": "Pin it.\n```suggestion\nuses: actions/checkout@abc123 # v4\n```"}), ""
            return 0, "steps:\n  - uses: actions/checkout@abc123 # v4\n", ""
        row = obs("o5", 1)
        codes = {h["code"] for h in H.head_signals(row, gh)}
        self.assertEqual(codes, {"SUGGESTION_AT_HEAD", "ANCHOR_GONE_AT_HEAD"})
        self.assertTrue(all(a[0] == "api" and "-X" not in a for a in calls))

    def test_public_counts_hold_no_text_and_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "l.json").write_text(json.dumps(ledger(obs("o1", 1, title="Secret leak in src/app.py"))), encoding="utf-8")
            self.assertEqual(H.main(["--ledger", str(tmp / "l.json"), "--out", str(tmp / "out")]), 0)
            public = (tmp / "out" / "MAROON_HINTS_PUBLIC.json").read_text(encoding="utf-8")
            self.assertNotIn("app.py", public)
            self.assertNotIn("leak", public.lower())
            self.assertIn("none of them is closure proof", (tmp / "out" / "MAROON_HINTS.md").read_text(encoding="utf-8"))
            (tmp / "bad.json").write_text(json.dumps({"schema": "other"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                H.main(["--ledger", str(tmp / "bad.json"), "--out", str(tmp / "out")])


if __name__ == "__main__":
    unittest.main()
