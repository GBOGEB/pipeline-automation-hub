"""Native negative and positive controls for bounded G4 disjoint census packets."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import census_packets as cp
from pulse_rollup import rollup

HEAD="a"*40


class W32CensusPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sample=HERE/"samples"
        cls.g0=json.loads((sample/"fleet_g0.json").read_text())
        cls.g1=json.loads((sample/"fleet_g1.json").read_text())

    def r(self):
        return rollup(copy.deepcopy(self.g0),copy.deepcopy(self.g1),source_sha=HEAD,
                      workers=2,per_repo=1,packet_budget=12)

    def test_native_source_owned_six_disjoint_packets(self):
        p=cp.make_plan(self.r(),exact_head=HEAD)
        self.assertEqual(p["canonical_six_repo_producer_pr"],531)
        self.assertEqual(p["frozen_historical_breadth"],
                         {"observed":6,"eligible":42,"unobserved":36})
        self.assertEqual(p["packet_count"],6)
        self.assertEqual(len({x["repo"] for x in p["packets"]}),6)
        self.assertEqual(len({x["identity_sha256"] for x in p["packets"]}),6)
        self.assertEqual(p["conservative_new_lane_cap"],1)

    def test_empty_push_does_not_claim_completion(self):
        p=cp.make_plan(self.r(),exact_head=HEAD)
        x=cp.empty_push(p)
        self.assertEqual(x["emissions"],[])
        self.assertEqual(x["packets_executed"],0)
        self.assertEqual(x["unknown_tail"],36)
        self.assertIsNone(x["native_receipts_accepted"])
        self.assertEqual(x["status"],"EMPTY_NOT_EXECUTED")

    def test_exact_head_required(self):
        with self.assertRaisesRegex(ValueError,"UNPINNED_PRODUCER_HEAD"):
            cp.make_plan(self.r(),exact_head="b"*40)

    def test_bad_42_cell_denominator_rejected(self):
        r=self.r()
        r["waves"][1]["unobserved_cells"]=0
        with self.assertRaisesRegex(ValueError,"CANONICAL_42_CELL_BREADTH_DRIFT"):
            cp.make_plan(r,exact_head=HEAD)

    def test_emitting_dispatch_claim_rejected(self):
        r=self.r()
        r["scale_plan"]["dispatch_authorized"]=True
        with self.assertRaisesRegex(ValueError,"NONCANONICAL_DISPATCH_OR_CAPACITY"):
            cp.make_plan(r,exact_head=HEAD)

    def test_true_capacity_not_inferred(self):
        r=self.r()
        r["scale_plan"]["real_worker_capacity"]=2
        with self.assertRaisesRegex(ValueError,"NONCANONICAL_DISPATCH_OR_CAPACITY"):
            cp.make_plan(r,exact_head=HEAD)

    def test_worker_cap_greater_than_one_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNMEASURED_CAPACITY_EXPANSION"):
            cp.make_plan(self.r(),exact_head=HEAD,new_lane_cap=2)

    def test_packet_cap_is_bounded(self):
        p=cp.make_plan(self.r(),exact_head=HEAD,packet_cap=3)
        self.assertEqual(p["packet_count"],3)
        with self.assertRaisesRegex(ValueError,"UNBOUNDED_PACKET_CAP"):
            cp.make_plan(self.r(),exact_head=HEAD,packet_cap=7)

    def test_packet_repeated_repo_rejected(self):
        r=self.r()
        r["scale_plan"]["packets"][1]["repository"]=r["scale_plan"]["packets"][0]["repository"]
        with self.assertRaisesRegex(ValueError,"NONDISJOINT_REPOSITORY_PACKET"):
            cp.make_plan(r,exact_head=HEAD)

    def test_mutation_path_packet_rejected(self):
        r=self.r()
        r["scale_plan"]["packets"][0]["mutation_paths"]=[".github/workflows/evil.yml"]
        with self.assertRaisesRegex(ValueError,"UNSAFE_SOURCE_PACKET"):
            cp.make_plan(r,exact_head=HEAD)

    def test_historic_baseline_not_rewritten(self):
        r=self.r()
        r["waves"][0]["wave"]="G2"
        with self.assertRaisesRegex(ValueError,"HISTORICAL_WAVE_DRIFT"):
            cp.make_plan(r,exact_head=HEAD)

    def test_qps_owner_never_promoted(self):
        r=self.r()
        r["qps_disposition"]="ACCEPT"
        with self.assertRaisesRegex(ValueError,"AUTHORITY_PROMOTION"):
            cp.make_plan(r,exact_head=HEAD)

    def test_manifest_member_bytes_verified_after_emit(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            report=self.r()
            m=cp.emit(report,out,exact_head=HEAD)
            self.assertEqual(cp.verify(out,exact_head=HEAD),m)
            x=json.loads((out/"empty-push.json").read_text())
            self.assertEqual(x["merge_admission"],"HOLD")
            self.assertIsNone(x["cross_repo_coverage_gain"])

    def test_tampered_manifest_hash_fails(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            cp.emit(self.r(),out,exact_head=HEAD)
            (out/"pull-plan.json").write_text("not JSON")
            with self.assertRaisesRegex(ValueError,"PACKET_MEMBER_SHA256_MISMATCH"):
                cp.verify(out,exact_head=HEAD)

    def test_fake_push_fails_even_with_recomputed_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            cp.emit(self.r(),out,exact_head=HEAD)
            forged=json.loads((out/"empty-push.json").read_text())
            forged["emissions"]=[{"fake":True}]
            raw=cp.serialize(forged)
            (out/"empty-push.json").write_bytes(raw)
            m=json.loads((out/"manifest.json").read_text())
            m["files_sha256"]["empty-push.json"]=cp.sha(raw)
            (out/"manifest.json").write_bytes(cp.serialize(m))
            with self.assertRaisesRegex(ValueError,"FABRICATED_PUSH_EMISSION"):
                cp.verify(out,exact_head=HEAD)

    def test_replay_deterministic(self):
        self.assertEqual(cp.serialize(cp.make_plan(self.r(),exact_head=HEAD)),
                         cp.serialize(cp.make_plan(self.r(),exact_head=HEAD)))


if __name__=="__main__":
    unittest.main()
