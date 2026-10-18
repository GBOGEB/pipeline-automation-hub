"""Fail-closed native controls for the additive Global DoV convergence hub."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convergence_hub as hub

HEAD = "a" * 40


class GlobalDOVHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = HERE / hub.SOURCE_NAME
        cls.baseline = json.loads(cls.source.read_text(encoding="utf-8"))

    def d(self):
        return copy.deepcopy(self.baseline)

    def test_six_repo_historical_denominator_is_not_run_identity(self):
        d = hub.validate(self.d())
        self.assertEqual(d["populations"]["canonical_federation"]["observed"], 6)
        self.assertEqual(d["populations"]["canonical_federation"]["eligible"], 42)
        self.assertEqual(d["populations"]["w31_run_identity"]["observed"], 124)
        self.assertEqual(d["populations"]["w31_run_identity"]["reported"], 157)
        self.assertFalse(d["populations"]["canonical_federation"]["fresh_readback_qualified"])

    def test_readiness_and_worker_time_unknown(self):
        d = hub.validate(self.d())
        self.assertEqual([d["readiness"][x] for x in ("M1","M2","M3")],
                         ["PARTIAL","HOLD","HOLD"])
        self.assertIsNone(d["readiness"]["worker_hours"])
        self.assertIsNone(hub.summary(d)["actual_worker_hours"])
        self.assertIsNone(hub.summary(d)["coverage_rollup_global"])

    def test_mixed_test_cohorts_are_labeled_overlapping(self):
        s = hub.summary(hub.validate(self.d()))
        self.assertGreater(s["curated_executed"], 600)
        self.assertEqual(s["curated_scope"], "OVERLAPPING_EXECUTION_INSTANCES_NOT_DISTINCT_TESTS")

    def test_three_fingerprints_nine_occurrences_no_root_closure(self):
        s = hub.summary(hub.validate(self.d()))
        self.assertEqual((s["root_manifestations"],s["first_red_signatures"]), (9,3))
        self.assertIsNone(s["formal_causal_root_closures"])

    def test_w29_regional_gain_is_descriptive_not_admitted(self):
        d=hub.validate(self.d())
        e=next(x for x in d["events"] if x["id"]=="ABACUS-W29-W75-W64")
        c=e["coverage"]
        self.assertEqual((c["statements"]["covered"], c["statements"]["total"]), (268,270))
        self.assertEqual((c["branches"]["covered"], c["branches"]["total"]), (74,76))
        pair=c["historical_comparison"]
        self.assertEqual(pair["contemporary_covered"]-pair["observed_covered"],256)
        self.assertFalse(pair["admission_qualified"])
        self.assertIsNone(hub.summary(d)["coverage_rollup_global"])

    def test_w29_baseline_coverage_forgery_rejected(self):
        d=self.d()
        e=next(x for x in d["events"] if x["id"]=="ABACUS-W29-W75-W64")
        e["coverage"]["historical_comparison"]["admission_qualified"]=True
        with self.assertRaisesRegex(ValueError,"UNQUALIFIED_HISTORICAL_COMPARISON"):
            hub.validate(d)

    def test_authentication_cannot_be_promoted_by_reader(self):
        d = self.d()
        d["populations"]["native_federation_authenticated_edges"]["observed"] = 1
        with self.assertRaisesRegex(ValueError, "FALSE_FEDERATION_PROOF"):
            hub.validate(d)

    def test_security_waiver_never_promoted(self):
        d = self.d()
        d["authority"]["security_waiver"] = True
        with self.assertRaisesRegex(ValueError, "AUTHORITY_PROMOTION"):
            hub.validate(d)

    def test_formal_root_closure_requires_owner(self):
        d = self.d()
        d["roots"][0]["root_id"] = "invented-root"
        with self.assertRaisesRegex(ValueError, "UNACCEPTED_ROOT_PROMOTION"):
            hub.validate(d)

    def test_native_status_and_test_denominator_fail_closed(self):
        d = self.d()
        d["events"][0]["tests"]["passed"] += 1
        with self.assertRaisesRegex(ValueError, "TEST_DENOMINATOR_DRIFT"):
            hub.validate(d)

    def test_nonterminal_is_never_fabricated_green(self):
        d = self.d()
        e = next(x for x in d["events"] if x["status"] == "NONTERMINAL")
        e["tests"]["passed"] = 7
        with self.assertRaisesRegex(ValueError, "FAKE_NONTERMINAL_TESTS"):
            hub.validate(d)

    def test_distinct_job_identity(self):
        d = self.d()
        d["events"][1]["jobs"].append(d["events"][0]["jobs"][0])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JOB_ID"):
            hub.validate(d)

    def test_scoped_coverage_denominator_fails_closed(self):
        d = self.d()
        e = next(x for x in d["events"] if "coverage" in x)
        e["coverage"]["branches"]["covered"] = 999
        with self.assertRaisesRegex(ValueError, "COVERAGE_DENOMINATOR_INVALID"):
            hub.validate(d)

    def test_generated_files_member_hash_and_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            m=hub.build(self.source,root,HEAD)
            self.assertEqual(hub.verify(root,HEAD),m)
            self.assertEqual(m["source_sha256"],hashlib.sha256(self.source.read_bytes()).hexdigest())
            self.assertEqual(set(m["member_sha256"]),
                             {"index.html","ledger.json","lineage.mmd"})
            page=(root/"index.html").read_text(encoding="utf-8")
            self.assertIn("Global DoV",page)
            self.assertIn('id="github-refresh"',page)
            self.assertIn('id="family-filter"',page)
            self.assertIn('id="lineage-grid"',page)
            self.assertIn("LIVE UNVERIFIED",page)
            self.assertIn("EXISTING_METHOD_ATLAS_PAGES_ONLY",
                          (root/"ledger.json").read_text(encoding="utf-8"))

    def test_tampered_generated_member_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            hub.build(self.source,root,HEAD)
            (root/"lineage.mmd").write_text("tamper",encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MANIFEST_HASH_MISMATCH"):
                hub.verify(root,HEAD)

    def test_no_new_publisher_or_runtime_dispatch(self):
        d=hub.validate(self.d())
        self.assertEqual(d["authority"]["publisher"],
                         "EXISTING_METHOD_ATLAS_PAGES_ONLY")
        self.assertFalse(d["authority"]["authority_transfer"])
        for link in d["links"]:
            if link["kind"]=="AUTHENTICATED_CONSUMPTION":
                self.assertEqual(link["status"],"NOT_PROVEN")

    def test_unsafe_lineage_and_malformed_presentation_head(self):
        d = self.d()
        d["lineage"][0]["path"]="../secret/private.json"
        with self.assertRaisesRegex(ValueError,"UNSAFE_GOLDEN_THREAD"):
            hub.validate(d)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"EXACT_PRESENTATION_HEAD_REQUIRED"):
                hub.build(self.source,temp,"main")


if __name__ == "__main__":
    unittest.main()
