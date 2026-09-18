import importlib.util
import json
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

def test_clean_exact_head_passes():
    r=fpc.evaluate(FakeClient(mapping()),REPO,PR)
    assert r["status"]=="PASS_FIRST_PASS_CLOSURE_GATE"
    assert r["merge_allowed"] is True

def test_missing_receipt_rejected():
    m=mapping(pr_body="")
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "MISSING_RECEIPT" in str(e)
    else: raise AssertionError

def test_stale_head_rejected():
    m=mapping(pr_body=body("b"*40))
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "STALE_HEAD" in str(e)
    else: raise AssertionError

def test_missing_purpose_rejected():
    m=mapping(pr_body=body(purposes=["canonical_self_test","exact_head_ci"]))
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "MISSING_REQUIRED_PROOF_PURPOSE" in str(e)
    else: raise AssertionError

def test_failed_run_rejected():
    m=mapping(run_conclusion="failure")
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "RUN_NOT_SUCCESS" in str(e)
    else: raise AssertionError

def test_wrong_run_head_rejected():
    m=mapping(run_head="b"*40)
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "RUN_HEAD_MISMATCH" in str(e)
    else: raise AssertionError

def test_review_not_completed_rejected():
    m=mapping(completed=False)
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "CODEX_REVIEW_NOT_COMPLETED" in str(e)
    else: raise AssertionError

def test_exact_head_codex_finding_rejected():
    review=f"### Codex Review\n**Reviewed commit:** `{HEAD[:10]}`"
    m=mapping(review_body=review)
    try: fpc.evaluate(FakeClient(m),REPO,PR)
    except fpc.GateError as e: assert "CODEX_MATERIAL_FINDINGS" in str(e)
    else: raise AssertionError

def test_old_head_codex_finding_does_not_block():
    review="### Codex Review\n**Reviewed commit:** `bbbbbbbbbb`"
    r=fpc.evaluate(FakeClient(mapping(review_body=review)),REPO,PR)
    assert r["merge_allowed"] is True
