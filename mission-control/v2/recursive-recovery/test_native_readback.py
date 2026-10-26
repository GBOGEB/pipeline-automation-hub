"""N12 read-only native telemetry negative/positive controls; no network calls."""
import copy
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_readback import Reader, attempt_get, classify_job, collect, source_sha, trim_checks, verify


S = "a"*40
T = "b"*40
RUN = 39010000001
JOB = 11740000001
CONFIG = {"authority_transfer":False,"execution_mode":"GET_ONLY_NO_RERUN",
          "max_runs_per_pr":2,"max_jobs_per_run":100,"targets":[
              {"repo":"GBOGEB/pipeline-automation-hub","branch":"master","class":"CONTROL",
               "issues":[604],"prs":[671]}]}


class Fake:
    def __init__(self, incomplete=False):
        self.paths=[]
        self.incomplete=incomplete
    def get(self, path):
        self.paths.append(path)
        if path.endswith("/branches/master"):
            return {"commit":{"sha":S}}
        if path.endswith("/issues/604"):
            return {"number":604,"state":"open"}
        if path.endswith("/pulls/671"):
            return {"state":"closed","merged":True,"head":{"sha":S},"base":{"sha":T,"ref":"master"}}
        if "/check-runs?" in path:
            return {"total_count":3,"check_runs":[{"status":"completed","conclusion":"success"},
                                                 {"status":"completed","conclusion":"failure"}]}
        if "/actions/runs?head_sha=" in path:
            return {"total_count":1,"workflow_runs":[{"id":RUN,"head_sha":S,"run_attempt":2,
                       "created_at":"2026-10-17T19:00:00Z","status":"completed","conclusion":"failure"}]}
        if path.endswith("/actions/runs/" + str(RUN) + "/jobs?per_page=100"):
            return {"total_count":1,"jobs":[{"id":JOB,"name":"native-fail",
                        "status":"completed","conclusion":"failure",
                        "steps":[{"name":"checkout","status":"completed","conclusion":"success"},
                                 {"name":"unit test","status":"completed","conclusion":"failure"}]}]}
        raise RuntimeError("unexpected route " + path)


class Denied(Fake):
    def get(self,path):
        raise HTTPError("https://api.github.com",404,"Not Found",None,None)


class NativeReadbackTests(unittest.TestCase):
    def test_source_sha_rejects_short(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_SHA"):
            source_sha("invalid")

    def test_native_readback_binds_run_attempt_job(self):
        d=collect(Fake(),CONFIG)
        p=d["targets"][0]["prs"][0]
        self.assertEqual(p["head_sha"],S)
        run=p["runs"][0]
        self.assertEqual(run["attempt"],2)
        self.assertEqual(run["job_receipt"]["jobs"][0]["attempt"],2)
        self.assertEqual(run["job_receipt"]["jobs"][0]["run"],RUN)
        self.assertEqual(run["job_receipt"]["jobs"][0]["first_red"]["step"],"unit test")
        self.assertTrue(verify(d))

    def test_sample_not_all_ci(self):
        d=collect(Fake(),CONFIG)
        self.assertFalse(d["sampling"]["is_complete_ci_population"])
        self.assertEqual(d["sampling"]["sampled_jobs"],1)
        self.assertEqual(d["sampling"]["sampled_failed_jobs"],1)
        self.assertEqual(d["targets"][0]["prs"][0]["check_runs"]["quality"],"TRUNCATED_MORE_PAGES")

    def test_all_calls_are_get_only(self):
        r=Fake()
        collect(r,CONFIG)
        self.assertTrue(all(p.startswith("/repos/") for p in r.paths))
        self.assertFalse(any(p.endswith("/rerun") or "/dispatch" in p for p in r.paths))

    def test_missing_cross_repo_access_does_not_become_zero(self):
        d=collect(Denied(),CONFIG)
        self.assertEqual(d["sampling"]["source_accessible_repos"],0)
        self.assertIsNone(d["targets"][0]["source_head_sha"])
        self.assertEqual(d["targets"][0]["prs"][0]["head_sha"],None)
        self.assertNotEqual(d["targets"][0]["source_quality"],"EXACT_DEFAULT_BRANCH_GITHUB_API")

    def test_failed_zero_step_is_habitat_not_application(self):
        x=classify_job({"conclusion":"failure","steps":None})
        self.assertEqual(x["kind"],"NO_EXECUTED_STEP_HABITAT_OR_UNKNOWN")

    def test_nonfailure_does_not_fabricate_first_red(self):
        x=classify_job({"conclusion":"success","steps":[{"name":"run","conclusion":"success"}]})
        self.assertIsNone(x["step"])

    def test_forged_promotion_rejected(self):
        d=collect(Fake(),CONFIG)
        d["targets"][0]["prs"][0]["native_acceptance"]="APPROVED"
        with self.assertRaisesRegex(ValueError,"FORGED_GATE"):
            verify(d)

    def test_forged_job_attempt_rejected(self):
        d=collect(Fake(),CONFIG)
        d["targets"][0]["prs"][0]["runs"][0]["job_receipt"]["jobs"][0]["attempt"]=1
        with self.assertRaisesRegex(ValueError,"JOB_RUN_ATTEMPT"):
            verify(d)

    def test_forged_dispatch_rejected(self):
        d=collect(Fake(),CONFIG)
        d["dispatch_count"]=1
        with self.assertRaisesRegex(ValueError,"FORGED_WORKER"):
            verify(d)

    def test_truncated_check_list_never_green(self):
        c=trim_checks({"total_count":1,"check_runs":[]})
        self.assertEqual(c["quality"],"TRUNCATED_MORE_PAGES")

    def test_unapproved_external_endpoint_blocked(self):
        with self.assertRaisesRegex(ValueError,"UNAPPROVED"):
            Reader("").get("/orgs/not-owner/actions/dispatch")


if __name__ == "__main__":
    unittest.main()
