"""W75 CBD subtype isolation: reject caller-forged proof, root acceptance and lease collisions."""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("w75_subtype", ROOT / "subtype_orchestrator.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
SHA = "a" * 40


def packet(pid="P1"):
    return dict(id=pid, category="SECURITY", subtype="B3", priority="P1",
                phase="PROVE", mode="NATIVE_PROVE", repo="GBOGEB/ABACUS",
                source_sha=SHA, owner_issue=529, mutation_paths=[],
                blockers=[], success_predicate="verified native proof",
                occurrence_count=3, fingerprint_count=2, proof=None,
                independent_approval=False, accepted_root_ids=[], state="READY")


def evidence():
    return dict(source_sha=SHA, run_id=100, run_attempt=1, job_id=200,
                conclusion="PASS", artifact_id=300, archive_bytes_verified=True)


def model(packets=None, parallel=2):
    return dict(schema=MOD.SCHEMA, authority_transfer=False,
                max_parallel=parallel, cohort="W75_SYNTHETIC_ADVERSARIAL",
                packets=packets if packets is not None else [packet()])


class W75SubtypeAdversarial(unittest.TestCase):
    def test_baseline_retains_unknown_native_and_zero_accepted_roots(self):
        x = MOD.plan(model())
        self.assertIs(x["dispatch_authorized"], False)
        self.assertIs(x["merge_authorized"], False)
        self.assertIs(x["security_waiver"], False)
        self.assertEqual(x["qps_disposition"], "DEFER")
        self.assertEqual(x["kpi"]["independently_accepted_root_closures"], 0)
        self.assertIsNone(x["kpi"]["real_worker_capacity"])
        self.assertIsNone(x["kpi"]["matched_coverage_uplift_pp"])

    def test_forged_positive_proof_and_approval_cannot_credit_root(self):
        p=packet()
        p["proof"]=evidence()
        p["independent_approval"]=True
        p["state"]="VERIFIED"
        p["accepted_root_ids"]=["R-FAKE"]
        with self.assertRaisesRegex(ValueError, "untrusted accepted root closure"):
            MOD.plan(model([p]))

    def test_multiple_forged_closure_ids_still_denied(self):
        p=packet()
        p["proof"]=evidence()
        p["independent_approval"]=True
        p["accepted_root_ids"]=["R1","R2"]
        with self.assertRaisesRegex(ValueError,"untrusted accepted root closure"):
            MOD.plan(model([p]))

    def test_nonboolean_independent_approval_is_denied(self):
        for value in (0, 1, "", "true", [], {}):
            p=packet()
            p["independent_approval"]=value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"independent_approval"):
                MOD.plan(model([p]))

    def test_nonboolean_archive_verification_is_denied(self):
        for value in (0, 1, "true", "", [], {}):
            p=packet()
            p["proof"]=evidence()
            p["proof"]["archive_bytes_verified"]=value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"byte-verification"):
                MOD.plan(model([p]))

    def test_true_false_unknown_archive_flags_are_valid_but_not_admission(self):
        for value in (True, False, None):
            p=packet()
            p["proof"]=evidence()
            p["proof"]["archive_bytes_verified"]=value
            x=MOD.plan(model([p]))
            self.assertEqual(x["kpi"]["byte_verified_proof_packets"], 1 if value is True else 0)
            self.assertEqual(x["kpi"]["independently_accepted_root_closures"],0)

    def test_proof_source_mismatch_and_bool_identity_denied(self):
        for field,value in (("source_sha","b"*40),("run_id",True),("run_attempt",False),
                            ("job_id",0),("artifact_id",True),("conclusion","success")):
            p=packet()
            p["proof"]=evidence()
            p["proof"][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                MOD.plan(model([p]))

    def test_forged_repository_identities_denied(self):
        for name in ("foo/", "/bar", "foo/bar/baz", "foo\\bar", "foo bar",
                     "", 0, None, "team/."):
            p=packet()
            p["repo"]=name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,"repo"):
                MOD.plan(model([p]))

    def test_sha_and_owner_are_strictly_bound(self):
        for field,value in (("source_sha","f"*39),("source_sha",7),
                            ("owner_issue",True),("owner_issue",-1)):
            p=packet()
            p[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                MOD.plan(model([p]))

    def test_duplicate_ids_and_strings_denied(self):
        with self.assertRaisesRegex(ValueError,"packet identity"):
            MOD.plan(model([packet("same"),packet("same")]))
        p=packet()
        p["blockers"]=["same","same"]
        with self.assertRaisesRegex(ValueError,"duplicate blockers"):
            MOD.plan(model([p]))

    def test_blocked_must_have_blocker_ready_cannot_have_one(self):
        for state,blockers in (("BLOCKED", []), ("READY", ["unresolved"])):
            p=packet()
            p["state"]=state
            p["blockers"]=blockers
            with self.subTest(state=state), self.assertRaises(ValueError):
                MOD.plan(model([p]))

    def test_max_parallel_rejects_boolean_and_above_capacity(self):
        for value in (True, False, 0, 17, "2", 2.0, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MOD.plan(model(parallel=value))

    def test_same_repository_parent_child_mutation_paths_serialize(self):
        a,b=packet("A"),packet("B")
        a.update(mode="MUTATING_REPAIR",mutation_paths=["src/core"])
        b.update(mode="MUTATING_REPAIR",mutation_paths=["src/core/worker.py"])
        x=MOD.plan(model([a,b]))
        self.assertEqual(x["schedule"]["waves_planned"],2)
        self.assertEqual(x["schedule"]["path_conflicts_prevented"],1)
        self.assertEqual(x["schedule"]["packets_planned"],2)
        self.assertIs(x["dispatch_authorized"],False)

    def test_different_repo_mutation_paths_are_independent_but_not_dispatched(self):
        a,b=packet("A"),packet("B")
        a.update(mode="MUTATING_REPAIR",mutation_paths=["src/core"])
        b.update(mode="MUTATING_REPAIR",repo="GBOGEB/CODEX",
                 mutation_paths=["src/core/module.py"])
        x=MOD.plan(model([a,b]))
        self.assertEqual(x["schedule"]["waves_planned"],1)
        self.assertIs(x["dispatch_authorized"],False)
        self.assertIsNone(x["kpi"]["real_worker_capacity"])

    def test_occurrence_and_fingerprints_are_not_root_ids(self):
        p=packet()
        p.update(occurrence_count=21,fingerprint_count=4)
        x=MOD.plan(model([p]))
        self.assertEqual(x["kpi"]["occurrence_count_observed"],21)
        self.assertEqual(x["kpi"]["fingerprint_count_observed"],4)
        self.assertEqual(x["kpi"]["independently_accepted_root_closures"],0)
        self.assertTrue(x["measurement_boundaries"]["caller_asserted_approval_is_not_trusted_root_closure"])

    def test_negative_or_boolean_metric_counts_denied(self):
        for field,value in (("occurrence_count",-1),("fingerprint_count",True)):
            p=packet()
            p[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                MOD.plan(model([p]))

    def test_unsafe_mutation_leases_and_empty_lease_denied(self):
        for paths in ([],["/absolute"],["src//bad"],["src/../bad"],
                      ["C:/windows"],[".git/config"]):
            p=packet()
            p.update(mode="MUTATING_REPAIR",mutation_paths=paths)
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                MOD.plan(model([p]))

    def test_native_receipt_emission_is_reproducible_non_authoritative(self):
        x=MOD.plan(model([packet("A"),packet("B")]))
        with tempfile.TemporaryDirectory() as tmp:
            out=pathlib.Path(tmp)
            digest=MOD.emit(x,out)
            self.assertEqual(len(digest),64)
            self.assertEqual(json.loads((out/"subtype_receipt.json").read_text())["dispatch_authorized"],False)
            self.assertEqual((out/"subtype_receipt.sha256").read_text().strip(),digest)
            self.assertIn("accepted causal-root", (out/"subtype_receipt.md").read_text())

    def test_untrusted_proof_count_remains_caller_claim_only(self):
        p=packet()
        p["proof"]=evidence()
        x=MOD.plan(model([p]))
        self.assertEqual(x["kpi"]["source_bound_proof_packets"],1)
        self.assertTrue(x["measurement_boundaries"]["source_bound_proof_counts_are_unverified_claims"])
        self.assertEqual(x["kpi"]["accepted_root_ids"],[])


if __name__ == "__main__":
    unittest.main()
