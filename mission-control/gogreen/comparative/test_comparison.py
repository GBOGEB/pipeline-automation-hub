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
    assert d["go_green"]["native_temporal"]["matched_coverage_gain_pp"] is None
    assert d["go_green"]["native_temporal"]["whole_repo_pass_pct"] is None
    assert d["go_green"]["native_temporal"]["independent_trial_count"] is None
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
    def setUp(self): self.d=json.loads(DATA.read_text())
    def test_valid(self):self.assertTrue(validate(self.d))
    def test_markup(self):
        s=HTML.read_text()
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
        self.d["go_green"]["native_temporal"]["matched_coverage_gain_pp"]=5.75
        with self.assertRaises(AssertionError):validate(self.d)

    def test_portfolio_frozen_sequence(self):
        self.assertEqual(self.d["portfolio_previous_checkpoint"]["created"], 105)
        self.assertEqual((self.d["portfolio"]["created"],self.d["portfolio"]["merged"],
                          self.d["portfolio"]["closed"]), (111,71,72))
        self.assertEqual(self.d["portfolio"]["closed_unmerged"],1)

    def test_standalone_html_native_dashboard_and_denominators(self):
        s=HTML.read_text()
        self.assertIn('id="k-runs"',s)
        self.assertIn('id="k-runner"',s)
        self.assertIn('id="k-top21"',s)
        self.assertIn('id="k-merged"',s)
        self.assertIn('G7 source PR',s)

if __name__=="__main__":unittest.main()
