"""Mocked GitHub API collection, fail-closed pagination and ancestry controls."""
from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("pr_run_history_collect",ROOT/"pr_run_history_collect.py")
COLLECT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(COLLECT)
SOURCE=json.loads((ROOT/"PR_MERGE_TEMPORAL_H1_20261016.json").read_text())
CLOCK=lambda:"2026-10-16T12:59:00Z"

def api_fake(repo,path):
    if path.startswith("/pulls/"):
        n=int(path.split("/")[-1])
        seeded=next((r for r in SOURCE["prs"] if r["repository"]==repo and r["pr"]==n),None)
        if seeded is None:
            return {"head":{"sha":"a"*40},"merge_commit_sha":None,
                    "base":{"ref":"main"},"merged_at":None}
        return {"head":{"sha":seeded["head_sha"]},
                "merge_commit_sha":seeded["merge_commit_sha"],
                "base":{"ref":seeded["base_branch"]},
                "merged_at":seeded["merged_at_utc"]}
    if path.startswith("/actions/runs?"):
        import urllib.parse
        query=urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        head=query["head_sha"][0]
        return {"total_count":1,"workflow_runs":[
            {"id":90001,"run_attempt":2,"head_sha":head,
             "name":"Governed CI","event":"pull_request",
             "created_at":"2026-10-16T11:00:00Z",
             "run_started_at":"2026-10-16T11:00:10Z",
             "updated_at":"2026-10-16T11:00:20Z",
             "status":"completed","conclusion":"success"}]}
    raise ValueError("unsupported test API path")

class RecensusTests(unittest.TestCase):
    def test_offline_never_calls_network(self):
        def denied(*_):raise AssertionError("network was used")
        out=COLLECT.recensus(SOURCE,denied,CLOCK,False)
        self.assertEqual([],out["rows"])
        self.assertEqual("NOT_REQUESTED_NOT_ZERO",out["qualification"])
        self.assertFalse(out["authority_transfer"])

    def test_real_run_attempt_metadata_shape_and_ancestry(self):
        out=COLLECT.recensus(SOURCE,api_fake,CLOCK,True)
        self.assertEqual(5,len(out["rows"]))
        self.assertEqual([0,0,0,1,1],[r["depth"] for r in out["rows"]])
        self.assertTrue(any(r["state"]=="OPEN_OR_NOT_MERGED" for r in out["rows"]))
        self.assertTrue(all(r["source_alignment"]=="PIN_MATCH" for r in out["rows"][:3]))
        run=out["rows"][0]["run_phases"][0]["runs"][0]
        self.assertEqual(2,run["run_attempt"])
        self.assertEqual("2026-10-16T11:00:00Z",run["created_at"])
        self.assertEqual("MATCH",run["sha_alignment"])

    def test_source_head_drift_denies_credit(self):
        def stale(repo,path):
            if path.endswith("/2060"):
                x=api_fake(repo,path)
                x["head"]["sha"]="b"*40
                return x
            return api_fake(repo,path)
        r=COLLECT.recensus(SOURCE,stale,CLOCK,True)
        row=next(x for x in r["rows"] if x["pr"]==2060)
        self.assertEqual("SOURCE_DRIFT_HOLD",row["state"])
        self.assertEqual([],row["run_phases"])

    def test_network_error_is_unknown_not_zero(self):
        def fail(repo,path):raise ValueError("429 rate limit")
        r=COLLECT.recensus(SOURCE,fail,CLOCK,True)
        self.assertEqual(5,len(r["rows"]))
        self.assertTrue(all(x["state"]=="UNKNOWN" for x in r["rows"]))
        self.assertTrue(all("429" in x["error"] for x in r["rows"]))

    def test_pagination_incomplete_is_explicit(self):
        def page(repo,path):
            return {"total_count":300,"workflow_runs":[{"id":int(path.rsplit("=",1)[-1]),
                    "run_attempt":1,"head_sha":"a"*40}]}
        p=COLLECT.get_runs("GBOGEB/ABACUS","a"*40,page,max_pages=2)
        self.assertIs(False,p["census_complete"])
        self.assertEqual(300,p["reported_count"])
        self.assertEqual(2,p["retrieved_count"])

    def test_refuse_duplicate_or_invalid_attempt(self):
        def duplicate(repo,path):
            return {"total_count":2,"workflow_runs":[
                 {"id":1,"run_attempt":1,"head_sha":"a"*40},
                 {"id":1,"run_attempt":1,"head_sha":"a"*40}]}
        with self.assertRaisesRegex(ValueError,"duplicate run/attempt"):
            COLLECT.get_runs("GBOGEB/ABACUS","a"*40,duplicate)
        def invalid(repo,path):
            return {"total_count":1,"workflow_runs":[
                {"id":1,"run_attempt":0,"head_sha":"a"*40}]}
        with self.assertRaisesRegex(ValueError,"invalid workflow/run/attempt"):
            COLLECT.get_runs("GBOGEB/ABACUS","a"*40,invalid)

    def test_sha_mismatch_never_silent(self):
        def other(repo,path):
            return {"total_count":1,"workflow_runs":[
                {"id":22,"run_attempt":1,"head_sha":"b"*40}]}
        d=COLLECT.get_runs("GBOGEB/ABACUS","a"*40,other)
        self.assertEqual("MISMATCH",d["runs"][0]["sha_alignment"])

    def test_cycle_guard_and_depth(self):
        src=copy.deepcopy(SOURCE)
        src["edges"].append({"from":"GBOGEB/ABACUS#2033",
            "to":"GBOGEB/ABACUS#2061","kind":"MERGED_INTO_FEATURE_PR",
            "proof":"MERGE_COMMIT_IDENTICAL_TO_TARGET_HEAD"})
        v=COLLECT.ancestry_nodes(src)
        self.assertEqual(len(v),len({(a,b) for a,b,_ in v}))
        self.assertLessEqual(len(v),12)

if __name__=="__main__":unittest.main()
