"""Source-bound and adversarial N12 GM recovery tests; no GitHub API or runner dispatch."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lineage import build, digest, git_blob, is_dag, load_canonical, yaml_mission


class MissionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.data = load_canonical()

    def test_exact_blob_sources(self):
        self.assertEqual(len(self.spec["internal"]), 15)

    def test_git_blob_identity(self):
        self.assertEqual(git_blob(b"test\n"), "9daeafb9864cf43055ae93beb0afd6c7d144bfa4")

    def test_canonical_five_missions(self):
        z = build(self.spec, self.data)
        self.assertEqual([m["id"] for m in z["missions"] if m["type"]=="GRAND_MISSION"],
                         ["GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"])
        self.assertEqual(z["metrics"]["grand_frontier_ladder"], [1,2,4,8,16])

    def test_iv_activation_is_not_child_binding(self):
        z = build(self.spec, self.data)
        iv = next(x for x in z["missions"] if x["id"]=="GM-IV")
        self.assertEqual(iv["state"], "ACTIVE_8_OF_8")
        self.assertEqual(iv["children"], [])
        self.assertEqual(len(iv["candidate_frontiers"]), 8)

    def test_v_remains_held(self):
        z = build(self.spec, self.data)
        self.assertEqual(next(x["state"] for x in z["missions"] if x["id"]=="GM-V"), "HELD")

    def test_hm_lm_namespace(self):
        z = build(self.spec, self.data)
        self.assertEqual(len([x for x in z["missions"] if x["id"].startswith("HM-")]),1)
        self.assertEqual(len([x for x in z["missions"] if x["id"].startswith("LM-")]),2)
        self.assertEqual(z["metrics"]["registered_variants"],3)

    def test_crew_is_not_runtime_capacity(self):
        z = build(self.spec, self.data)
        self.assertEqual(z["metrics"]["crew_registered"], 23)
        self.assertEqual(z["metrics"]["crew_conceptual"], 8)
        self.assertIsNone(z["metrics"]["crew_runtime_proven_current"])
        self.assertTrue(all(x["live_worker_status"] is None for x in z["crew"]))

    def test_rex_original_timestamp_semantics(self):
        z = build(self.spec, self.data)
        self.assertEqual(z["metrics"]["rex_historical_events"],10)
        self.assertTrue(all(x["time_basis"]=="LEDGER_SEED_COMMIT_RECORDED_AT" for x in z["rex"]))

    def test_cohort_denominators_not_summed(self):
        z = build(self.spec, self.data)
        self.assertEqual(z["metrics"]["top7_repos_historical"],7)
        self.assertEqual(z["metrics"]["top21_file_repos"],21)
        self.assertEqual(z["metrics"]["historical_pr_fleet_repos"],90)
        self.assertTrue(z["metrics"]["cohort_denominators_not_additive"])

    def test_forged_frontier_count_rejected(self):
        d = copy.deepcopy(self.data)
        d["gm_registry"]["grand_missions"][3]["frontier_count"]=12
        with self.assertRaisesRegex(ValueError,"scaling ladder"):
            build(self.spec,d)

    def test_forged_held_mission_activation_rejected(self):
        d = copy.deepcopy(self.data)
        d["gm_registry"]["grand_missions"][4]["state"]="ACTIVE_16"
        with self.assertRaisesRegex(ValueError,"GM-V"):
            build(self.spec,d)

    def test_forged_gmiv_child_rejected(self):
        d = copy.deepcopy(self.data)
        d["gm_registry"]["grand_missions"][3]["children"]=["GBOGEB/imaginary"]
        with self.assertRaisesRegex(ValueError,"GM-IV"):
            build(self.spec,d)

    def test_orphan_rex_parent_rejected(self):
        d = copy.deepcopy(self.data)
        d["rex_ledger"]["events"][-1]["causal_parent"]="NONE"
        with self.assertRaisesRegex(ValueError,"dangling REX"):
            build(self.spec,d)

    def test_cycle_rejected(self):
        with self.assertRaisesRegex(ValueError,"CYCLIC_EXECUTION_OR_LINEAGE_DAG"):
            is_dag([{"from":"A","to":"B","kind":"LINEAGE_PARENT"},
                    {"from":"B","to":"A","kind":"LINEAGE_PARENT"}])

    def test_non_lineage_feedback_cycle_allowed(self):
        self.assertTrue(is_dag([{"from":"A","to":"B","kind":"SOURCE_REFERENCES"},
                                {"from":"B","to":"A","kind":"SOURCE_REFERENCES"}]))

    def test_forged_conceptual_promotion_rejected(self):
        d=copy.deepcopy(self.data)
        person=next(x for x in d["crew_roster"]["crew"] if x["maturity"]=="CONCEPTUAL")
        person["authority"]["promote"]="GATED"
        with self.assertRaisesRegex(ValueError,"conceptual crew"):
            build(self.spec,d)

    def test_current_vs_archival_state_preserved(self):
        z=build(self.spec,self.data)
        r=z["historical_conflicts"][0]
        self.assertEqual(r["archival_state"],"HELD")
        self.assertEqual(r["current_state"],"ACTIVE_8_OF_8")

    def test_hash_determinism(self):
        a,b=build(self.spec,self.data),build(self.spec,self.data)
        self.assertEqual(a["semantic_sha256"],b["semantic_sha256"])
        self.assertEqual(digest({"x":2,"y":3}),digest({"y":3,"x":2}))

    def test_no_unauthorized_promotion(self):
        z=build(self.spec,self.data)
        self.assertFalse(z["authority_transfer"])
        self.assertEqual(z["merge_admission"],"HOLD")
        self.assertTrue(z["no_auto_dispatch"])
        self.assertEqual(z["engineering_credit_delta"],0)


if __name__=="__main__":
    unittest.main()
