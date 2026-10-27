"""GoGREEN comparative reporting regression, invariants and adverse inputs."""
import json
from pathlib import Path
import re
import unittest

HERE=Path(__file__).resolve().parent
DATA=HERE/"comparison.json"
HTML=HERE/"index.html"

def validate(d):
    p=d["portfolio"]; rows=p["repo_events"]
    assert len({r["repo"] for r in rows})==len(rows)
    for key in ("created","closed","merged"):
        assert type(p[key]) is int and p[key] == sum(r[key] for r in rows)
    assert p["closed_unmerged"]==p["closed"]-p["merged"]>=0
    for row in rows:
        assert all(type(row[k]) is int and row[k]>=0 for k in ("created","closed","merged"))
        assert row["merged"]<=row["closed"]
    b=d["bd"]
    assert sum(b[x] for x in ("done","active","todo","needs_reader"))==b["total"]
    assert b["active"]+b["todo"]+b["needs_reader"]==b["open"]
    go=d["go_green"]
    assert go["runs"]["total"] == go["runs"]["success"]+go["runs"]["failure"]
    assert go["coverage"]["matched_delta_pp"] is None
    assert go["coverage"]["native_current_head_percent"] is None
    assert d["authority"]["formal_closure_delta"]==0
    assert d["authority"]["security_waiver"] is False
    assert d["authority"]["merge_authorized"] is False
    assert d["top21"]["status"]=="CANDIDATE_EXPANSION_NOT_VERIFIED"
    assert d["top21"]["repo_count_eligible"]==21
    assert d["top21"]["repo_count_scanned"]==21
    assert d["top21"]["repo_count_source_heads_verified"]==21
    assert d["top21"]["effective_admission"] is None
    assert sum(d["top21"]["cohorts"].values())==21
    assert d["go_green"]["native_temporal"]["runner_executed_successful_jobs"]==9
    assert d["go_green"]["native_temporal"]["sampled_native_jobs"]==10
    assert d["go_green"]["native_temporal"]["skipped_jobs_excluded"]==1
    assert d["go_green"]["native_temporal"]["runner_busy_seconds"]==235
    assert d["go_green"]["native_temporal"]["matched_coverage_gain_pp"]==5.7522
    assert d["go_green"]["native_temporal"]["matched_branch_gain_pp"]==2.6316
    assert d["go_green"]["native_temporal"]["native_Nplus1_test_methods_passed"]==53
    assert d["go_green"]["native_temporal"]["production_source_modified_between_N_and_Nplus1"] is False
    assert d["go_green"]["native_temporal"]["native_Nplus1_statement_cov"]=={"covered":226,"eligible":226,"source_module_only":True}
    assert d["go_green"]["native_temporal"]["native_Nplus1_branch_cov"]=={"covered":38,"eligible":38,"source_module_only":True}
    assert d["go_green"]["native_temporal"]["whole_repo_pass_pct"] is None
    assert d["go_green"]["native_temporal"]["source_module_git_blob"]=="e7b54f64890489b495bfa43de7b1e5a43902f47a"
    assert d["go_green"]["native_temporal"]["coverage_tool_version"]=="7.13.3"
    assert d["go_green"]["native_temporal"]["independent_trial_count"] is None
    q=d["go_green"]["qps_threepulse"]
    assert q["schema"]=="gogreen.qps-threepulse.native.v1"
    q0=q["frozen_main_run_census"]
    assert (q0["runs"],q0["success"],q0["failure"],q0["cancelled"])==(33,22,11,0)
    assert sum(q0[x] for x in ("success","failure","cancelled"))==q0["runs"]
    assert q0["retrieved_page_complete"] is True
    assert sorted(x["n"] for x in q["failure_family_manifestations"])==[1,2,8]
    assert sum(x["n"] for x in q["failure_family_manifestations"])==q0["failure"]
    assert (q["first_red_exact_error_verified"],q["first_red_unknown"])==(10,1)
    assert q["first_red_exact_error_verified"]+q["first_red_unknown"]==q0["failure"]
    assert len(q["pulse_results"])==3
    assert q["pulse_results"][1]["python_tests_passed"]==21
    assert q["pulse_results"][1]["ts_tests_passed"]==41
    assert q["pulse_results"][2]["test_n2"]==21
    assert q["pulse_results"][2]["statement_n2"]==[30,30]
    assert q["pulse_results"][2]["branch_n2"]==[18,18]
    assert q["pulse_results"][2]["source_scope_comparable"] is False
    assert q["pulse_results"][2]["formal_closure_credit"]==0
    assert q["post_merge_controls"]["root_closure_credit"]==0
    assert q["post_merge_controls"]["independent_review_verified"] is False
    assert q["admission"]=="HOLD"
    assert d["rex"]["not_new_evidence"] is True
    ids={n["id"] for n in d["dag"]}
    assert len(ids)==len(d["dag"])
    for n in d["dag"]:
        assert set(n["deps"])<=ids
        assert n["id"] not in n["deps"]
    visited=set(); visiting=set(); graph={x["id"]:x["deps"] for x in d["dag"]}
    def walk(x):
        if x in visiting: raise AssertionError("cycle")
        if x in visited:return
        visiting.add(x)
        for parent in graph[x]:walk(parent)
        visiting.remove(x);visited.add(x)
    for x in ids:walk(x)
    assert len({t["id"] for t in d["todo"]}) == len(d["todo"])
    return True

class Compare(unittest.TestCase):
    def setUp(self): self.d=json.loads(DATA.read_text(encoding="utf-8"))
    def test_valid(self):self.assertTrue(validate(self.d))
    def test_markup(self):
        s=HTML.read_text(encoding="utf-8")
        self.assertIn('id="data"',s)
        self.assertIn("textContent",s)
        self.assertNotIn("innerHTML",s)
        self.assertIn("No automatic green",s)
    def test_merge_arithmetic_negative(self):
        self.d["portfolio"]["merged"]=67
        with self.assertRaises(AssertionError):validate(self.d)
    def test_missing_repo_negative(self):
        self.d["portfolio"]["repo_events"].pop()
        with self.assertRaises(AssertionError):validate(self.d)
    def test_duplicate_repo_negative(self):
        self.d["portfolio"]["repo_events"][1]["repo"]=self.d["portfolio"]["repo_events"][0]["repo"]
        with self.assertRaises(AssertionError):validate(self.d)
    def test_fake_native_coverage_negative(self):
        self.d["go_green"]["coverage"]["native_current_head_percent"]=99
        with self.assertRaises(AssertionError):validate(self.d)
    def test_unverified_top21_negative(self):
        self.d["top21"]["status"]="ACCEPTED"
        with self.assertRaises(AssertionError):validate(self.d)
    def test_root_credit_negative(self):
        self.d["authority"]["formal_closure_delta"]=1
        with self.assertRaises(AssertionError):validate(self.d)
    def test_security_waiver_negative(self):
        self.d["authority"]["security_waiver"]=True
        with self.assertRaises(AssertionError):validate(self.d)
    def test_cyclic_dag_negative(self):
        self.d["dag"][0]["deps"]=["C"]
        with self.assertRaises(AssertionError):validate(self.d)
    def test_unknown_parent_negative(self):
        self.d["dag"][0]["deps"]=["DOES-NOT-EXIST"]
        with self.assertRaises(AssertionError):validate(self.d)
    def test_inconsistent_bd_negative(self):
        self.d["bd"]["done"]+=1
        with self.assertRaises(AssertionError):validate(self.d)
    def test_workflow_double_count_negative(self):
        self.d["go_green"]["runs"]["failure"]+=1
        with self.assertRaises(AssertionError):validate(self.d)
    def test_no_fleet_physics_claim(self):
        self.assertIsNone(self.d["go_green"]["coverage"]["whole_repository_percent"])
        self.assertIsNone(self.d["top21"]["effective_admission"])

    def test_native_g7_top21_not_promotion(self):
        self.assertEqual(self.d["top21"]["repo_count_scanned"], 21)
        self.assertIsNone(self.d["top21"]["effective_admission"])
        self.assertEqual(self.d["top21"]["source_registry"],
                         "mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json")

    def test_false_22_of_21_fleet_negative(self):
        self.d["top21"]["repo_count_scanned"]=22
        with self.assertRaises(AssertionError):validate(self.d)

    def test_runner_skipped_as_success_negative(self):
        self.d["go_green"]["native_temporal"]["runner_executed_successful_jobs"]=10
        with self.assertRaises(AssertionError):validate(self.d)

    def test_runner_time_forgery_negative(self):
        self.d["go_green"]["native_temporal"]["runner_busy_seconds"]=236
        with self.assertRaises(AssertionError):validate(self.d)

    def test_fake_matched_coverage_promotion_negative(self):
        self.d["go_green"]["native_temporal"]["matched_coverage_gain_pp"]=100
        with self.assertRaises(AssertionError):validate(self.d)

    def test_portfolio_frozen_sequence(self):
        self.assertEqual(self.d["portfolio_previous_checkpoint"]["created"], 105)
        self.assertEqual((self.d["portfolio"]["created"],self.d["portfolio"]["merged"],
                          self.d["portfolio"]["closed"]), (111,71,72))
        self.assertEqual(self.d["portfolio"]["closed_unmerged"],1)

    def test_standalone_html_native_dashboard_and_denominators(self):
        s=HTML.read_text(encoding="utf-8")
        self.assertIn('id="k-runs"',s)
        self.assertIn('id="k-runner"',s)
        self.assertIn('id="k-top21"',s)
        self.assertIn('id="k-merged"',s)
        self.assertIn('G7 source PR',s)


    def test_exact_blob_and_cov_denominators(self):
        k=self.d["go_green"]["native_temporal"]
        self.assertEqual(k["source_module_git_blob"],"e7b54f64890489b495bfa43de7b1e5a43902f47a")
        self.assertEqual(k["statement_cov_n"]["eligible"],k["native_Nplus1_statement_cov"]["eligible"])
        self.assertEqual(k["branch_cov_n"]["eligible"],k["native_Nplus1_branch_cov"]["eligible"])
        self.assertFalse(k["production_source_modified_between_N_and_Nplus1"])

    def test_false_source_modification_negative(self):
        self.d["go_green"]["native_temporal"]["production_source_modified_between_N_and_Nplus1"]=True
        with self.assertRaises(AssertionError):validate(self.d)


    def test_qps_success_failure_partition(self):
        q=self.d["go_green"]["qps_threepulse"]
        self.assertEqual(q["frozen_main_run_census"]["success"],22)
        self.assertEqual(sum(x["n"] for x in q["failure_family_manifestations"]),11)

    def test_qps_missing_failed_family_negative(self):
        self.d["go_green"]["qps_threepulse"]["failure_family_manifestations"].pop()
        with self.assertRaises(AssertionError):validate(self.d)

    def test_qps_false_exact_root_attribution_negative(self):
        self.d["go_green"]["qps_threepulse"]["first_red_exact_error_verified"]=11
        with self.assertRaises(AssertionError):validate(self.d)

    def test_qps_stale_run_denominator_negative(self):
        self.d["go_green"]["qps_threepulse"]["frozen_main_run_census"]["runs"]=30
        with self.assertRaises(AssertionError):validate(self.d)

    def test_qps_fake_matched_source_uplift_negative(self):
        self.d["go_green"]["qps_threepulse"]["pulse_results"][2]["source_scope_comparable"]=True
        with self.assertRaises(AssertionError):validate(self.d)

    def test_qps_false_governance_closure_negative(self):
        self.d["go_green"]["qps_threepulse"]["post_merge_controls"]["root_closure_credit"]=1
        with self.assertRaises(AssertionError):validate(self.d)

    def test_qps_source_scope_coverage_denominator_negative(self):
        self.d["go_green"]["qps_threepulse"]["pulse_results"][2]["branch_n2"]=[18,17]
        with self.assertRaises(AssertionError):validate(self.d)

    def test_qps_html_root_surface_and_sipoc(self):
        h=HTML.read_text(encoding="utf-8")
        for marker in ('id="q-runs"','id="q-root-rows"','id="q-firstred"',
                       'id="q-coverage"','QPS first-red conversion'):
            self.assertIn(marker,h)
        ids={node["id"] for node in self.d["dag"]}
        self.assertIn("P5",ids)
        self.assertIn("O_QPS",ids)
        self.assertIn("GG-W8",{t["id"] for t in self.d["todo"]})

if __name__=="__main__":unittest.main()
