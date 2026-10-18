"""G3C N16–N18 regression: paired coverage, source provenance and no false stability."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g3c_convergence import project, render, digest

SHA="a"*40

def fixture():
    pulses=[]
    for name,commit,n,s,b in (
        ("N+13",SHA,8,88,19),("N+14",SHA,18,89,20),
        ("N+15",None,24,99,20)):
        pulses.append({"pulse":name,"source_commit":commit,
                       "tests_passed_local":n,"tests_failed_local":0,
                       "statement_covered":s,"statement_total":100,
                       "branch_covered":b,"branch_total":22,
                       "combined_covered":s+b,"combined_total":122})
    p={"schema":"missioncontrol.g3a.n13_n15.source_and_local_proof.v1",
       "merge_admission":"HOLD","authority_transfer":False,"security_waiver":False,
       "native_exact_head_ci":None,"human_independent_approval":None,
       "accepted_n_delta":None,"source_denominator_same":True,
       "source_bridge_git_blob":SHA,"source_bridge_sha256":"b"*64,
       "cross_repository_candidate_edges":3,
       "cross_repo_native_authenticated_edges":None,"pulse_records":pulses}
    g={"schema":"code-purple.g3a.master-dags-projection.v1",
       "merge_admission":"HOLD","authority_transfer":False,"accepted_n_delta":None,
       "metrics":{"sources":4,"graph_families":8,"declared_cross_repository_edges":3,
                  "native_verified_edges":None,"formal_root_closures":None},
       "topological_order":[str(i) for i in range(8)],
       "edges":[{"binding":"DECLARED","receipt":None,"accepted":False}
                for _ in range(3)]}
    return p,g

class G3CConvergence(unittest.TestCase):
    def test_matched_local_increase_is_not_six_sigma(self):
        p,g=fixture();x=project(p,g);m=x["matched_local_metrics"]
        self.assertEqual((m["numerator_start"],m["numerator_end"],m["denominator"]),(107,119,122))
        self.assertEqual(m["successive_delta_covered"],[2,10])
        self.assertEqual(m["covered_delta"],12)
        self.assertEqual(m["trend"],"ACCELERATING_LOCAL_COVERAGE")
        self.assertEqual(x["stability"]["status"],"NOT_QUALIFIED")
        self.assertIsNone(x["stability"]["six_sigma"])
        self.assertEqual(x["merge_admission"],"HOLD")

    def test_missing_edge_and_duplicate_node_are_rejected(self):
        p,g=fixture();g["edges"].pop()
        with self.assertRaisesRegex(ValueError,"topology incomplete"):project(p,g)
        p,g=fixture();g["topological_order"][7]=g["topological_order"][0]
        with self.assertRaisesRegex(ValueError,"topology incomplete"):project(p,g)
        p,g=fixture();g["edges"]=[None]*3
        with self.assertRaisesRegex(ValueError,"topology incomplete"):project(p,g)

    def test_denominator_change_rejected(self):
        p,g=fixture()
        p["pulse_records"][2]["branch_total"]+=1
        p["pulse_records"][2]["combined_total"]+=1
        with self.assertRaisesRegex(ValueError,"non-comparable"):project(p,g)

    def test_combined_drift_rejected(self):
        p,g=fixture();p["pulse_records"][0]["combined_covered"]=108
        with self.assertRaisesRegex(ValueError,"combined coverage"):project(p,g)

    def test_source_promotion_rejected(self):
        for key,value in (("merge_admission","PASS"),("authority_transfer",True),
                          ("security_waiver",True),("native_exact_head_ci","PASS"),
                          ("accepted_n_delta",0),
                          ("human_independent_approval","APPROVED")):
            with self.subTest(key=key):
                p,g=fixture();p[key]=value
                with self.assertRaises(ValueError):project(p,g)

    def test_graph_admission_and_receipt_rejected(self):
        for mutation in (
            lambda g:g["metrics"].update(native_verified_edges=3),
            lambda g:g["edges"][1].update(binding="NATIVE"),
            lambda g:g.update(topological_order=["A"]),
            lambda g:g.update(merge_admission="PASS")):
            p,g=fixture();mutation(g)
            with self.assertRaises(ValueError):project(p,g)

    def test_zero_slope_is_local_plateau_not_stable(self):
        p,g=fixture()
        for row in p["pulse_records"]:
            row.update(statement_covered=88,branch_covered=19,combined_covered=107)
        x=project(p,g)
        self.assertEqual(x["matched_local_metrics"]["trend"],"LOCAL_PLATEAU_ONLY")
        self.assertEqual(x["stability"]["status"],"NOT_QUALIFIED")

    def test_missing_third_commit_stays_missing(self):
        p,g=fixture();x=project(p,g)
        self.assertTrue(x["source_gap"]["last_pulse_commit_missing"])
        self.assertIsNone(x["matched_local_metrics"]["pulses"][2]["source_commit"])

    def test_bad_historical_commit_rejected(self):
        p,g=fixture();p["pulse_records"][2]["source_commit"]="inferred"
        with self.assertRaisesRegex(ValueError,"commit identity"):project(p,g)

    def test_regressing_covered_count_rejected(self):
        p,g=fixture()
        p["pulse_records"][2].update(statement_covered=80,combined_covered=100)
        with self.assertRaisesRegex(ValueError,"negative matched"):project(p,g)

    def test_producer_admission_cannot_be_forged(self):
        p,g=fixture()
        producer={"sha":SHA,"artifact_id":12139440079,"workflow_run_id":39133186022,
                  "status":"ACCEPTED"}
        with self.assertRaisesRegex(ValueError,"producer promotion"):project(p,g,producer)
        producer["status"]="HISTORICAL_PRODUCER_GREEN"
        x=project(p,g,producer)
        self.assertIsNone(x["accepted_n_delta"])
        self.assertEqual(x["pulses"][-1]["state"],"CONSUMER_OWNER_PENDING")

    def test_html_reports_integer_counts(self):
        p,g=fixture();x=project(p,g);page=render(x)
        self.assertIn("107/122",page)
        self.assertIn("119/122",page)
        self.assertIn("Covered obligations (whole counts)",page)
        self.assertIn('aria-label="Exact covered-count table"',page)
        self.assertIn('aria-label="Whole covered obligations: 107, 109, 119 of matched denominator 122"',page)
        self.assertIn('x1="126"',page,"integer Y-axis leaves space beside the first data label")
        self.assertIn("NOT QUALIFIED",page)
        self.assertEqual(page,render(x))

    def test_fingerprint_order_independent(self):
        p,g=fixture()
        self.assertEqual(digest(g),digest(dict(reversed(list(g.items())))))

    def test_cli_outputs_hash_registry(self):
        import json
        import tempfile
        from unittest.mock import patch
        import g3c_convergence as m
        p,g=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            proof,graph,out=root/"proof.json",root/"graph.json",root/"out"
            proof.write_text(json.dumps(p));graph.write_text(json.dumps(g))
            with patch.object(sys,"argv",["g3c_convergence","--proof",str(proof),
                       "--graph",str(graph),"--out-dir",str(out)]):
                m.main()
            man=json.loads((out/"manifest.json").read_text())
            self.assertEqual(man["admission"],"HOLD")
            for f,d in man["files_sha256"].items():
                self.assertEqual(__import__("hashlib").sha256((out/f).read_bytes()).hexdigest(),d)
            self.assertEqual(len(man["files_sha256"]),2)

    def test_cli_invalid_source_fails_without_output(self):
        import json
        import tempfile
        from unittest.mock import patch
        import g3c_convergence as m
        p,g=fixture();p["schema"]="invented"
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            proof,graph,out=root/"proof.json",root/"graph.json",root/"out"
            proof.write_text(json.dumps(p));graph.write_text(json.dumps(g))
            with patch.object(sys,"argv",["g3c_convergence","--proof",str(proof),
                       "--graph",str(graph),"--out-dir",str(out)]):
                with self.assertRaisesRegex(ValueError,"invalid G3A proof"):m.main()
            self.assertFalse(out.exists())

    def test_deceleration_and_constant_rate_are_not_six_sigma(self):
        p,g=fixture()
        p["pulse_records"][1].update(statement_covered=98,branch_covered=20,combined_covered=118)
        self.assertEqual(project(p,g)["matched_local_metrics"]["trend"],"DECELERATING_LOCAL_COVERAGE")
        p,g=fixture()
        p["pulse_records"][1].update(statement_covered=93,branch_covered=20,combined_covered=113)
        self.assertEqual(project(p,g)["matched_local_metrics"]["trend"],"CONSTANT_RATE_LOCAL_COVERAGE")
        self.assertEqual(project(p,g)["stability"]["status"],"NOT_QUALIFIED")

    def test_bad_producer_scope_is_rejected(self):
        p,g=fixture()
        bad={"sha":SHA,"artifact_id":False,"workflow_run_id":2,"status":"UNVERIFIED"}
        with self.assertRaisesRegex(ValueError,"producer native identity"):project(p,g,bad)
        bad["artifact_id"]=1;bad["extra"]=True
        with self.assertRaisesRegex(ValueError,"producer contract"):project(p,g,bad)

if __name__=="__main__":unittest.main()
