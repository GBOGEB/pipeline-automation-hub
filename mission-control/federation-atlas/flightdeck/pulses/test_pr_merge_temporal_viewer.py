"""Source-bound recursive PR and CI timeline replay/negative tests."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
INPUT=HERE/"PR_MERGE_TEMPORAL_H1_20261016.json"
SPEC=importlib.util.spec_from_file_location("pr_merge_temporal_viewer",HERE/"pr_merge_temporal_viewer.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class TemporalLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads(INPUT.read_text(encoding="utf-8"))

    def test_exact_source_schema_and_merge_boundaries(self):
        d=MODULE.validate(self.snapshot)
        self.assertEqual(3,len(d["prs"]))
        self.assertEqual([6,14,13],[len(p["phases"][0]["workflows"]) for p in d["prs"]])
        self.assertEqual([0,25,21],[len(p["phases"][1]["workflows"]) for p in d["prs"]])
        self.assertEqual(79,sum(MODULE.summary(d).values()))

    def test_mobile_refresh_line_must_wrap_without_clipping(self):
        page=MODULE.render(self.snapshot,"f"*64)
        self.assertIn("white-space:pre-wrap;overflow-wrap:anywhere",page)
        self.assertIn('name="viewport"',page)

    def test_utc_job_log_before_after(self):
        p=self.snapshot["prs"]
        self.assertEqual("POST_MERGE_JOB",MODULE.classify(
            p[0]["job_log_clocks"][0]["first_utc"],
            p[0]["job_log_clocks"][0]["last_utc"],p[0]["merged_at_utc"]))
        self.assertEqual("PRE_MERGE_JOB",MODULE.classify(
            p[1]["job_log_clocks"][0]["first_utc"],
            p[1]["job_log_clocks"][0]["last_utc"],p[1]["merged_at_utc"]))
        self.assertEqual("POST_MERGE_JOB",MODULE.classify(
            p[2]["job_log_clocks"][1]["first_utc"],
            p[2]["job_log_clocks"][1]["last_utc"],p[2]["merged_at_utc"]))

    def test_recursive_graph_reaches_parent_without_loops(self):
        graph=self.snapshot["edges"]
        seen=MODULE.traversal("GBOGEB/ABACUS#2060",graph,5)
        self.assertEqual([("GBOGEB/ABACUS#2060",0),
                          ("GBOGEB/ABACUS#2057",1)],seen)
        extra=graph+[{"from":"GBOGEB/ABACUS#2057","to":"GBOGEB/ABACUS#2060"}]
        self.assertEqual(seen,MODULE.traversal("GBOGEB/ABACUS#2060",extra,5))

    def test_deterministic_projection_and_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            receipt=MODULE.produce(INPUT,folder)
            html=(folder/"index.html").read_bytes()
            self.assertEqual(receipt,MODULE.produce(INPUT,folder))
            self.assertEqual(html,(folder/"index.html").read_bytes())
            self.assertIn(b"POST MERGE JOB",html)
            self.assertIn(b"PRE MERGE JOB",html)
            for name,sha in receipt["artifact_sha256"].items():
                self.assertEqual(sha,hashlib.sha256((folder/name).read_bytes()).hexdigest())

    def test_refuse_authority_promotion(self):
        for k,v in [("merge_admission","PASS"),("security_waiver",True),
                    ("authority_transfer",True),("accepted_root_closures",0),
                    ("accepted_rex",{})]:
            with self.subTest(k=k):
                x=copy.deepcopy(self.snapshot)
                x["authority"][k]=v
                with self.assertRaisesRegex(ValueError,"authority inversion"):
                    MODULE.validate(x)

    def test_refuse_feature_branch_as_main(self):
        x=copy.deepcopy(self.snapshot)
        x["prs"][1]["admission"]="MERGED_TO_DEFAULT_BRANCH_NO_QPS_CREDIT"
        with self.assertRaises(ValueError):MODULE.validate(x)

    def test_refuse_mismatched_phase_and_duplicate_run(self):
        x=copy.deepcopy(self.snapshot)
        x["prs"][1]["phases"][1]["sha"]="f"*40
        with self.assertRaisesRegex(ValueError,"phase lineage mismatch"):
            MODULE.validate(x)
        x=copy.deepcopy(self.snapshot)
        x["prs"][1]["phases"][1]["workflows"].append(
            copy.deepcopy(x["prs"][1]["phases"][0]["workflows"][0]))
        with self.assertRaises(ValueError):MODULE.validate(x)

    def test_unknown_workflow_times_not_forged(self):
        x=copy.deepcopy(self.snapshot)
        x["prs"][1]["phases"][0]["workflows"][0]["attempt"]=1
        with self.assertRaises(ValueError):MODULE.validate(x)

    def test_refuse_reverse_time_and_fake_edge(self):
        x=copy.deepcopy(self.snapshot)
        c=x["prs"][1]["job_log_clocks"][0]
        c["first_utc"],c["last_utc"]=c["last_utc"],c["first_utc"]
        with self.assertRaisesRegex(ValueError,"negative job time"):
            MODULE.validate(x)
        x=copy.deepcopy(self.snapshot)
        x["edges"][0]["proof"]="AGENT_APPROVED"
        with self.assertRaisesRegex(ValueError,"unsupported recursive edge"):
            MODULE.validate(x)

    def test_refuse_unbounded_graph(self):
        x=copy.deepcopy(self.snapshot)
        x["recursive_contract"]["max_depth"]=500
        with self.assertRaisesRegex(ValueError,"unbounded recursion"):
            MODULE.validate(x)

if __name__=="__main__":unittest.main()
