"""H2 source-bound live selector integration: offline positive and tamper negatives."""
import hashlib
import importlib.util
import io
import json
import unittest
import zipfile
from pathlib import Path

PATH = Path(__file__).with_name("gate.py")
SPEC = importlib.util.spec_from_file_location("h2_gate", PATH)
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)
SHA = "a" * 40
REPO = "GBOGEB/pipeline-automation-hub"
WORKFLOW = ".github/workflows/first-pass-closure.yml"
PR = 19
AGG = 37
TRIGGER = 43


def fixture(state=g.PASS):
    report = {"schema": "gogreen.required_gate.v2", "head_sha": SHA, "pr": PR,
              "verdict": g.FAIL, "merge_authorized": False,
              "gates": [{"workflow": WORKFLOW, "state": state}]}
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("required-gate.json", json.dumps(report))
    archive = raw.getvalue()
    metadata = {"id": 13, "name": f"gogreen-required-gate-{PR}-1",
                "url": f"https://api.github.com/repos/{REPO}/actions/artifacts/13",
                "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
                "expired": False, "workflow_run": {"id": AGG, "head_sha": SHA}}
    return metadata, archive


class Reader:
    def __init__(self, state=g.PASS):
        self.repo = REPO
        self.posts = []
        self.metadata, self.archive = fixture(state)
        self.trigger = {"id": TRIGGER, "head_sha": SHA,
                        "status": "completed", "conclusion": "success", "event": "pull_request",
                        "path": WORKFLOW + "@refs/pull/19/merge",
                        "repository": {"full_name": REPO},
                        "pull_requests": [{"number": PR}]}
        self.aggregator = {"id": AGG, "run_attempt": 1, "status": "completed",
                           "conclusion": "failure", "head_sha": SHA,
                           "pull_requests": [{"number": PR}]}

    def get(self, path):
        if "/actions/workflows/" in path:
            return {"workflow_runs": [self.aggregator]}
        if path.endswith(f"/runs/{TRIGGER}"):
            return self.trigger
        if path.endswith(f"/runs/{AGG}/artifacts?per_page=100"):
            return {"total_count": 1, "artifacts": [self.metadata]}
        raise AssertionError("unapproved route " + path)

    def artifact_zip(self, artifact_id):
        assert artifact_id == 13
        return self.archive

    def rerun(self, run_id):
        self.posts.append(run_id)


class LiveSelectorTests(unittest.TestCase):
    def test_verified_pass_suppresses_only_its_recheck(self):
        r = Reader(g.PASS)
        out = g.recheck(r, SHA, trigger_run_id=TRIGGER)
        self.assertEqual(out["action"], "none")
        self.assertEqual(out["receipt_relevance"], g.RECHECK_ALREADY_SATISFIED)
        self.assertEqual(r.posts, [])

    def test_verified_not_applicable_suppresses(self):
        r = Reader(g.NA)
        self.assertEqual(g.recheck(r, SHA, trigger_run_id=TRIGGER)["action"], "none")

    def test_fail_and_wait_preserve_recovery(self):
        for state in (g.FAIL, g.WAIT):
            with self.subTest(state=state):
                r = Reader(state)
                out = g.recheck(r, SHA, trigger_run_id=TRIGGER)
                self.assertEqual(out["action"], "rerun")
                self.assertEqual(r.posts, [AGG])

    def test_digest_mismatch_never_suppresses(self):
        r = Reader(g.PASS)
        r.metadata["digest"] = "sha256:" + "0" * 64
        out = g.recheck(r, SHA, trigger_run_id=TRIGGER)
        self.assertEqual(out["receipt_relevance"], g.RECHECK_UNKNOWN)
        self.assertEqual(r.posts, [AGG])

    def test_wrong_head_or_pr_never_suppresses(self):
        for key, value in (("head_sha", "b" * 40), ("pull_requests", [{"number": 20}])):
            with self.subTest(key=key):
                r = Reader(g.PASS)
                r.trigger[key] = value
                self.assertEqual(g.recheck(r, SHA, trigger_run_id=TRIGGER)["action"], "rerun")

    def test_malformed_trigger_identity_remains_unknown_and_recoverable(self):
        r = Reader(g.PASS)
        r.trigger["pull_requests"] = [None]
        out = g.recheck(r, SHA, trigger_run_id=TRIGGER)
        self.assertEqual(out["receipt_relevance"], g.RECHECK_UNKNOWN)
        self.assertEqual(r.posts, [AGG])

    def test_wrong_attempt_artifact_never_suppresses(self):
        r = Reader(g.PASS)
        r.metadata["name"] = f"gogreen-required-gate-{PR}-2"
        self.assertEqual(g.recheck(r, SHA, trigger_run_id=TRIGGER)["action"], "rerun")

    def test_unavailable_receipt_preserves_recovery(self):
        r = Reader(g.PASS)
        r.archive = b"not a valid zip"
        self.assertEqual(g.recheck(r, SHA, trigger_run_id=TRIGGER)["action"], "rerun")

    def test_missing_trigger_identity_preserves_legacy_contract(self):
        r = Reader(g.PASS)
        self.assertEqual(g.recheck(r, SHA)["action"], "rerun")
        self.assertEqual(r.posts, [AGG])

    def test_failed_trigger_does_not_read_or_rerun(self):
        r = Reader(g.PASS)
        out = g.recheck(r, SHA, conclusion="failure", trigger_run_id=TRIGGER)
        self.assertEqual(out["action"], "none")
        self.assertEqual(r.posts, [])

    def test_dry_run_cannot_post(self):
        r = Reader(g.FAIL)
        out = g.recheck(r, SHA, dry_run=True, trigger_run_id=TRIGGER)
        self.assertEqual(out["action"], "dry-run")
        self.assertEqual(r.posts, [])


if __name__ == "__main__":
    unittest.main()
