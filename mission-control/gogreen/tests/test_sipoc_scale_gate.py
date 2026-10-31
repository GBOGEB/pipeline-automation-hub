"""Adversarial unit tests for read-only two-pulse crew-scaling gate."""
import copy
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "sipoc_scale_gate.py"
spec = importlib.util.spec_from_file_location("sipoc_scale_gate", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = "a" * 40
DIGEST = "b" * 64
HEADS = {"GBOGEB/pipeline-automation-hub": SHA}


def digest(n):
    return format(n, "064x")


def pair(i, pulse=0):
    base = 1000 * pulse + i
    proof = dict(run_id=base, attempt=1, job_id=base+10, source_sha=SHA,
                 receipt_sha256=digest(base), status="completed", conclusion="success")
    check = dict(proof, run_id=base+100, job_id=base+110, receipt_sha256=digest(base+100))
    return dict(id=f"PAIR-{i}", repo="GBOGEB/pipeline-automation-hub",
                source_sha=SHA, root_id=None, first_red_roots=[],
                lease_collision=False,
                worker=dict(actor=f"worker-{i}", mode="MUTATION_PROPOSAL",
                            mutation_paths=[f"features/{i}.py"], native=proof),
                verifier=dict(actor=f"verifier-{i}", mode="NATIVE_PROVE", native=check))


def sample():
    return dict(schema=m.SCHEMA, authority_transfer=False,
                merge_authorized=False, dispatch_authorized=False,
                target_mutators=4, source_heads=dict(HEADS),
                pulses=[dict(pulse_id=n, pairs=[pair(1, n),pair(2, n)],
                             first_red_recurrences=0, security_findings=0,
                             independent_review=True) for n in (7,8)],
                metrics=dict(owner=m.METRIC_OWNER,
                             before=dict(scope="JADE", denominator="executed-jobs",
                                         time_unit="seconds",repo_population="focus5",
                                         metric_key="queue_p95_seconds",count=10,value=240,
                                         pulse_id=7, source_heads=HEADS),
                             after=dict(scope="JADE", denominator="executed-jobs",
                                        time_unit="seconds",repo_population="focus5",
                                        metric_key="queue_p95_seconds",count=10,value=210,
                                        pulse_id=8, source_heads=HEADS)))


class ScaleGateTest(unittest.TestCase):
    def test_advisory_only_even_on_synthetic_candidate(self):
        out = m.assess(sample())
        self.assertEqual(out["classification"], "SCALE_CANDIDATE_EXTERNAL_GATE")
        self.assertFalse(out["dispatch_authorized"])
        self.assertFalse(out["merge_authorized"])
        self.assertTrue(out["native_revalidation_required"])
        self.assertEqual(out["engineering_credit_delta"], 0)

    def test_missing_native_proof_blocks(self):
        for key, value in (("run_id",0),("receipt_sha256","bad"),
                           ("conclusion","skipped"),("source_sha","c"*40)):
            record = sample()
            record["pulses"][0]["pairs"][0]["worker"]["native"][key] = value
            with self.subTest(key=key):
                self.assertEqual(m.assess(record)["classification"], "HOLD")

    def test_verifier_actor_and_receipt_separation(self):
        record = sample()
        record["pulses"][0]["pairs"][0]["verifier"]["actor"] = "worker-1"
        self.assertIn("INDEPENDENT_VERIFIER_MISSING", m.assess(record)["reasons"])
        record = sample()
        record["pulses"][0]["pairs"][0]["verifier"]["native"] = record["pulses"][0]["pairs"][0]["worker"]["native"]
        self.assertIn("VERIFIER_REUSES_WORKER_EVIDENCE", m.assess(record)["reasons"])

    def test_native_identity_reuse_across_records_blocks(self):
        # Same run/attempt/job with an irrelevant field changed: wp != vp.
        record = sample()
        p = record["pulses"][0]["pairs"][0]
        p["verifier"]["native"] = dict(p["worker"]["native"], receipt_sha256=digest(999))
        self.assertIn("NATIVE_EVIDENCE_REUSED", m.assess(record)["reasons"])
        # Pulse 8 replays pulse 7's native executions.
        record = sample()
        record["pulses"][1]["pairs"] = copy.deepcopy(record["pulses"][0]["pairs"])
        out = m.assess(record)
        self.assertEqual(out["classification"], "HOLD")
        self.assertIn("NATIVE_EVIDENCE_REUSED", out["reasons"])
        self.assertIn("NATIVE_RECEIPT_REUSED", out["reasons"])
        # Another pair reuses only a receipt digest.
        record = sample()
        pulse = record["pulses"][1]["pairs"]
        pulse[1]["worker"]["native"]["receipt_sha256"] = pulse[0]["worker"]["native"]["receipt_sha256"]
        self.assertIn("NATIVE_RECEIPT_REUSED", m.assess(record)["reasons"])

    def test_metric_windows_bound_to_pulse_source_census(self):
        stale = {"GBOGEB/pipeline-automation-hub": "c" * 40}
        for window, key, value in (("after", "source_heads", stale),
                                   ("before", "source_heads", None),
                                   ("after", "pulse_id", 7),
                                   ("before", "pulse_id", 8),
                                   ("before", "pulse_id", 3)):
            record = sample()
            record["metrics"][window][key] = value
            with self.subTest(window=window, key=key, value=value):
                self.assertIn("METRIC_WINDOW_NOT_SOURCE_BOUND", m.assess(record)["reasons"])
        # A historical baseline pulse with its own census binds to that census.
        record = sample()
        record["pulses"].insert(0, dict(pulse_id=6, source_heads=stale, pairs=[],
                                        first_red_recurrences=0, security_findings=0,
                                        independent_review=True))
        record["metrics"]["before"].update(pulse_id=6, source_heads=stale)
        self.assertEqual(m.assess(record)["classification"], "SCALE_CANDIDATE_EXTERNAL_GATE")
        record["metrics"]["before"]["source_heads"] = dict(HEADS)
        self.assertIn("METRIC_WINDOW_NOT_SOURCE_BOUND", m.assess(record)["reasons"])

    def test_overlap_or_causal_root_collision_blocks(self):
        record = sample()
        record["pulses"][0]["pairs"][1]["worker"]["mutation_paths"] = ["features"]
        self.assertIn("OVERLAPPING_DISJOINT_WORKER_LEASES", m.assess(record)["reasons"])
        record = sample()
        for pair in record["pulses"][0]["pairs"]:
            pair["root_id"] = "SHARED-ROOT"
        self.assertIn("OVERLAPPING_DISJOINT_WORKER_LEASES", m.assess(record)["reasons"])

    def test_path_traversal_and_unsafe_lease_rejected(self):
        for path in ("../secret","a/../b","/absolute","a\\b","a//b"):
            record = sample()
            record["pulses"][0]["pairs"][0]["worker"]["mutation_paths"] = [path]
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.assess(record)

    def test_pulse_lineage_and_gaps(self):
        for first, last in ((1,1),(2,1),(0,1),(True,2)):
            record = sample()
            record["pulses"][0]["pulse_id"] = first
            record["pulses"][1]["pulse_id"] = last
            with self.subTest(first=first,last=last), self.assertRaises(ValueError):
                m.assess(record)
        record = sample()
        record["pulses"][1]["pulse_id"] = 10
        self.assertIn("PULSE_SEQUENCE_GAP", m.assess(record)["reasons"])

    def test_first_red_security_review_hold(self):
        for name,value in (("first_red_recurrences",1),("security_findings",1),
                           ("independent_review",False)):
            record = sample()
            record["pulses"][1][name] = value
            with self.subTest(name=name):
                self.assertEqual(m.assess(record)["classification"], "HOLD")

    def test_metric_owner_and_denominator_protection(self):
        record = sample()
        record["metrics"]["owner"] = "shadow_metrics.py"
        self.assertEqual(m.assess(record)["classification"], "HOLD")
        for name,value in (("denominator","PRs"),("repo_population","other"),
                           ("metric_key","mean_queue")):
            record = sample()
            record["metrics"]["after"][name] = value
            with self.subTest(name=name):
                self.assertIn("METRIC_COHORT_NOT_COMPARABLE", m.assess(record)["reasons"])

    def test_queue_regression_and_withheld_denominators(self):
        record = sample()
        record["metrics"]["after"]["value"] = 241
        self.assertIn("QUEUE_P95_REGRESSION", m.assess(record)["reasons"])
        record = sample()
        record["metrics"]["after"]["count"] = 2
        self.assertIn("QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED", m.assess(record)["reasons"])

    def test_authority_missing_source_and_single_pulse(self):
        record = sample()
        record["merge_authorized"] = True
        with self.assertRaises(ValueError):
            m.assess(record)
        record = sample()
        record["source_heads"]["GBOGEB/pipeline-automation-hub"] = "main"
        with self.assertRaises(ValueError):
            m.assess(record)
        record = sample()
        record["pulses"] = record["pulses"][:1]
        self.assertIn("TWO_CONSECUTIVE_PULSES_REQUIRED", m.assess(record)["reasons"])


if __name__ == "__main__":
    unittest.main()
