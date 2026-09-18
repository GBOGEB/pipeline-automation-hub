import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"first_pass_closure_gate.py"
spec=importlib.util.spec_from_file_location("fpc", SCRIPT)
fpc=importlib.util.module_from_spec(spec); spec.loader.exec_module(fpc)

HEAD="a"*40
REPO="GBOGEB/example"
PR=7
RUN=12345

class FakeClient:
    def __init__(self, mapping): self.mapping=mapping
    def get(self,path):
        if path not in self.mapping: raise AssertionError(path)
        return self.mapping[path]

def body(head=HEAD, purposes=None):
    purposes=purposes or ["canonical_self_test","mutation_test","exact_head_ci"]
    obj={"schema":"first_pass_closure/v1","head_sha":head,"required_runs":[{"repo":REPO,"run_id":RUN,"purposes":purposes}]}
    return "<!-- FPC_RECEIPT_V1 "+json.dumps(obj)+" -->"

def mapping(pr_body=None, review_body=None, review_state=None, run_head=HEAD, run_conclusion="success", completed=True):
    summary=f"""<!-- codex-pull-request-review-summary -->
| Review | Status | Commit |
| --- | --- | --- |
| Code Review | {'**Completed**' if completed else '**Running**'} | `{HEAD[:7]}` |
"""
    reviews=[]
    if review_body is not None:
        reviews=[{"state":review_state or "COMMENTED","body":review_body,"user":{"login":"chatgpt-codex-connector"}}]
    return {
      f"/repos/{REPO}/pulls/{PR}":{"head":{"sha":HEAD},"body":pr_body if pr_body is not None else body()},
      f"/repos/{REPO}/actions/runs/{RUN}":{"status":"completed","conclusion":run_conclusion,"head_sha":run_head},
      f"/repos/{REPO}/issues/{PR}/comments?per_page=100":[{"id":99,"body":summary}],
      f"/repos/{REPO}/pulls/{PR}/reviews?per_page=100":reviews,
    }

class TestFirstPassClosureGate(unittest.TestCase):
    def test_clean_exact_head_passes(self):
        r=fpc.evaluate(FakeClient(mapping()),REPO,PR)
        self.assertEqual(r["status"],"PASS_FIRST_PASS_CLOSURE_GATE")
        self.assertIs(r["merge_allowed"],True)

    def test_missing_receipt_rejected(self):
        with self.assertRaisesRegex(fpc.GateError,"MISSING_RECEIPT"):
            fpc.evaluate(FakeClient(mapping(pr_body="")),REPO,PR)

    def test_stale_head_rejected(self):
        with self.assertRaisesRegex(fpc.GateError,"STALE_HEAD"):
            fpc.evaluate(FakeClient(mapping(pr_body=body("b"*40))),REPO,PR)

    def test_missing_purpose_rejected(self):
        with self.assertRaisesRegex(fpc.GateError,"MISSING_REQUIRED_PROOF_PURPOSE"):
            fpc.evaluate(FakeClient(mapping(pr_body=body(purposes=["canonical_self_test","exact_head_ci"]))),REPO,PR)

    def test_failed_run_rejected(self):
        with self.assertRaisesRegex(fpc.GateError,"RUN_NOT_SUCCESS"):
            fpc.evaluate(FakeClient(mapping(run_conclusion="failure")),REPO,PR)

    def test_wrong_run_head_rejected(self):
        with self.assertRaisesRegex(fpc.GateError,"RUN_HEAD_MISMATCH"):
            fpc.evaluate(FakeClient(mapping(run_head="b"*40)),REPO,PR)

    def test_review_not_completed_rejected(self):
        with self.assertRaisesRegex(fpc.GateError,"CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(FakeClient(mapping(completed=False)),REPO,PR)

    def test_exact_head_codex_finding_rejected(self):
        review=f"### Codex Review\n**Reviewed commit:** `{HEAD[:10]}`"
        with self.assertRaisesRegex(fpc.GateError,"CODEX_MATERIAL_FINDINGS"):
            fpc.evaluate(FakeClient(mapping(review_body=review)),REPO,PR)

    def test_old_head_codex_finding_does_not_block(self):
        review="### Codex Review\n**Reviewed commit:** `bbbbbbbbbb`"
        r=fpc.evaluate(FakeClient(mapping(review_body=review)),REPO,PR)
        self.assertIs(r["merge_allowed"],True)

if __name__=="__main__":
    unittest.main()
