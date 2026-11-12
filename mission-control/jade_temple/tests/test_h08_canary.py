"""H08 rejected RED canary: receipts verify live, only a protection 405 counts, the merge attempt
refuses unless every precondition holds, and private repositories never enter the public file."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H8 = load("h08_canary")
FP = load("focus5_pulse")

HEAD = "a" * 40
CHECK = "Offline fixture integrity (211 productions) (3.12)"
RID = 26380979


def world(**over):
    w = {
        "rules": [{"type": "deletion", "ruleset_id": RID}, {"type": "pull_request", "ruleset_id": RID},
                  {"type": "required_status_checks", "ruleset_id": RID,
                   "parameters": {"required_status_checks": [{"context": CHECK}]}}],
        "ruleset": {"id": RID, "enforcement": "active", "target": "branch", "bypass_actors": [],
                    "current_user_can_bypass": "never",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}},
        "pr": {"number": 9, "state": "open", "draft": False, "merged_at": None, "html_url": "https://github.com/O/R/pull/9",
               "base": {"ref": "master"}, "head": {"sha": HEAD}},
        "runs": [{"name": CHECK, "status": "completed", "conclusion": "failure", "id": 5,
                  "completed_at": "2026-11-07T10:00:00Z", "html_url": "https://github.com/O/R/runs/5"}],
        "meta": {"default_branch": "master", "private": False},
    }
    w.update(over)
    calls = []

    def lookup(path):
        calls.append(path)
        if path == "repos/O/R":
            return w["meta"]
        if path == "repos/O/R/rules/branches/master":
            return w["rules"]
        if path == f"repos/O/R/rulesets/{RID}":
            return w["ruleset"]
        if path == "repos/O/R/pulls/9":
            return w["pr"]
        if path.startswith(f"repos/O/R/commits/{HEAD}/check-runs"):
            return {"check_runs": w["runs"]}
        raise AssertionError(path)

    lookup.calls = calls
    return lookup


RECEIPT = {"repo": "O/R", "pr_number": 9, "head_sha": HEAD, "base_branch": "master", "failing_check": CHECK,
           "ruleset_id": RID, "proof_class": "GITHUB_REJECTED_RED_MERGE",
           "attempt": {"at": "2026-11-07T10:05:00Z", "http_status": 405, "response_sha256": "b" * 64,
                       "message": "Repository rule violations found\n\nRequired status check is failing."}}


class EffectiveProtection(unittest.TestCase):
    def test_ok_only_with_pr_rule_required_checks_and_no_bypass(self):
        self.assertTrue(H8.effective_protection("O/R", "master", world())[0])
        no_checks = [r for r in world()("repos/O/R/rules/branches/master") if r["type"] != "required_status_checks"]
        self.assertFalse(H8.effective_protection("O/R", "master", world(rules=no_checks))[0])
        rs = world()(f"repos/O/R/rulesets/{RID}")
        for bad in ({"bypass_actors": [{"actor_type": "RepositoryRole"}]}, {"current_user_can_bypass": "always"},
                    {"enforcement": "evaluate"},
                    {"conditions": {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}}}):
            self.assertFalse(H8.effective_protection("O/R", "master", world(ruleset=dict(rs, **bad)))[0], bad)


class VerifyReceipt(unittest.TestCase):
    def status(self, **over):
        return H8.verify_receipt("O/R", "master", RECEIPT, world(**over))[0]

    def test_pass_on_the_live_configuration(self):
        status, url, why = H8.verify_receipt("O/R", "master", RECEIPT, world())
        self.assertEqual(status, "PASS")
        self.assertEqual(url, "https://github.com/O/R/pull/9")
        self.assertIn("405", why)

    def test_every_drift_is_unknown_never_pass(self):
        pr = world()("repos/O/R/pulls/9")
        self.assertEqual(self.status(pr=dict(pr, merged_at="2026-11-08T00:00:00Z")), "UNKNOWN")
        self.assertEqual(self.status(pr=dict(pr, head={"sha": "c" * 40})), "UNKNOWN")
        self.assertEqual(self.status(runs=[dict(world()(f"repos/O/R/commits/{HEAD}/check-runs")["check_runs"][0],
                                                conclusion="success", id=6, completed_at="2026-11-07T11:00:00Z")]
                                     + world()(f"repos/O/R/commits/{HEAD}/check-runs")["check_runs"]), "UNKNOWN")
        other = [dict(r, ruleset_id=RID) if r["type"] != "required_status_checks" else
                 dict(r, parameters={"required_status_checks": [{"context": "other"}]})
                 for r in world()("repos/O/R/rules/branches/master")]
        self.assertEqual(self.status(rules=other), "UNKNOWN")
        moved = copy.deepcopy(RECEIPT)
        moved["ruleset_id"] = 1
        self.assertEqual(H8.verify_receipt("O/R", "master", moved, world())[0], "UNKNOWN")


class Receipts(unittest.TestCase):
    def doc(self, **over):
        r = copy.deepcopy(RECEIPT)
        r.update(over)
        return {"schema": H8.SCHEMA, "receipts": [r]}

    def test_valid_receipt_loads(self):
        self.assertEqual(list(H8.validate_receipts(self.doc(), private=())), ["O/R"])

    def test_rejects_private_wrong_proof_non_405_and_non_protection_405(self):
        with self.assertRaises(ValueError):
            H8.validate_receipts(self.doc(), private=("O/R",))
        with self.assertRaises(ValueError):
            H8.validate_receipts(self.doc(proof_class="CALLER_SAID_SO"), private=())
        for attempt in ({"http_status": 200}, {"message": "Pull Request is still a draft"},
                        {"message": "Repository rule violations found. 5 of 5 required status checks are queued."},
                        {"message": "Pull Request is not mergeable"}, {"response_sha256": "x"}):
            bad = copy.deepcopy(RECEIPT)
            bad["attempt"].update(attempt)
            with self.assertRaises(ValueError, msg=attempt):
                H8.validate_receipts({"schema": H8.SCHEMA, "receipts": [bad]}, private=())

    def test_committed_receipts_file_is_valid(self):
        self.assertIsInstance(H8.load_receipts(ROOT), dict)


class Attempt(unittest.TestCase):
    def test_refuses_before_any_merge_call_when_a_precondition_fails(self):
        merged = []

        def merge(*a):
            merged.append(a)
            return 405, '{"message":"Required status check is failing"}'
        pr = world()("repos/O/R/pulls/9")
        rs = world()(f"repos/O/R/rulesets/{RID}")
        for over in ({"pr": dict(pr, draft=True)}, {"pr": dict(pr, state="closed")},
                     {"ruleset": dict(rs, current_user_can_bypass="pull_requests_only")},
                     {"runs": []}, {"meta": {"default_branch": "master", "private": True}}):
            with self.assertRaises(SystemExit, msg=over):
                H8.attempt("O/R", 9, CHECK, world(**over), merge)
        with self.assertRaises(SystemExit):
            H8.attempt("O/R", 9, "not-required", world(), merge)
        queued = world()(f"repos/O/R/commits/{HEAD}/check-runs")["check_runs"] + [{"name": CHECK, "status": "queued"}]
        with self.assertRaises(SystemExit):
            H8.attempt("O/R", 9, CHECK, world(runs=queued), merge)
        self.assertEqual(merged, [])

    def test_records_only_a_protection_405_and_alarms_on_success(self):
        rec = H8.attempt("O/R", 9, CHECK, world(),
                         lambda *a: (405, '{"message":"Repository rule violations found. Required status check is failing."}'))
        self.assertEqual((rec["attempt"]["http_status"], rec["head_sha"], rec["ruleset_id"]), (405, HEAD, RID))
        H8.validate_receipts({"schema": H8.SCHEMA, "receipts": [rec]}, private=())
        with self.assertRaises(SystemExit) as alarm:
            H8.attempt("O/R", 9, CHECK, world(), lambda *a: (200, '{"merged":true}'))
        self.assertIn("ALARM", str(alarm.exception))
        with self.assertRaises(SystemExit):
            H8.attempt("O/R", 9, CHECK, world(), lambda *a: (405, '{"message":"Pull Request is not mergeable"}'))
        with self.assertRaises(SystemExit):
            H8.attempt("O/R", 9, CHECK, world(),
                       lambda *a: (405, '{"message":"Repository rule violations found. 5 of 5 required status checks are queued."}'))


class PulseIntegration(unittest.TestCase):
    def test_h08_passes_only_with_a_verified_receipt(self):
        w = world()
        base = {"repos/O/R/branches/master": {"protected": False}}

        def lookup(path):
            if path in base:
                return base[path]
            if path == "repos/O/R":
                return {"default_branch": "master"}
            if path == "repos/O/R/commits/master":
                return {"sha": HEAD}
            if path.startswith("repos/O/R/contents"):
                return [{"name": "README.md", "type": "file"}]
            if path.startswith("repos/O/R/actions/runs?head_sha="):
                return {"workflow_runs": []}
            if path.startswith("repos/O/R/tags"):
                return []
            return w(path)
        g = {x["id"]: x for x in FP.observe_repo("O/R", None, lookup, None, [RECEIPT])["gates"]}
        self.assertEqual(g["H08"]["status"], "PASS")
        g = {x["id"]: x for x in FP.observe_repo("O/R", None, lookup, None, [])["gates"]}
        self.assertEqual(g["H08"]["status"], "UNKNOWN")
        self.assertIn("no rejected RED canary receipt", g["H08"]["reason"])


if __name__ == "__main__":
    unittest.main()
