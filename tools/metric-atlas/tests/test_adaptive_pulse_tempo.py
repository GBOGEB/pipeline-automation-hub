"""W381 deterministic and adversarial N-1/N-5/N-10 planning proof.

All source identities are synthetic fixture tokens, NOT observed queue telemetry.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from metric_atlas import adaptive_pulse_tempo as t

A = "a" * 40
H = "1" * 64


def scenario():
    rows = []
    for i in range(11):
        rows.append({
            "n": i, "observed_at": f"2026-10-{10+i:02d}T10:00:00Z",
            "cohort_sha256": H, "method_version": "1.0",
            "population_sha256": "2" * 64,
            "provenance": {name: {"source_head": A, "receipt_sha256": H}
                           for name in t.OWNERS},
            "evidence_class": "DECLARED_SCENARIO",
            "metrics": {"queue_p95_s": 210 - i*10, "queue_depth": 30,
                        "running_jobs": 10, "unique_roots": 1,
                        "source_collisions": 0, "controller_acks": 1,
                        "reused_packets": 3, "source_reads": 20 - i}})
    return {"schema": t.SCHEMA, "mode": "READ_ONLY_CANDIDATE",
            "current_budget": 3, "limits": {"max_queue_p95_s": 240,
                  "max_queue_depth": 60, "max_running_jobs": 20},
            "pulses": rows, "authority_transfer": False,
            "execution_authorized": False}


class AdaptiveTempoTests(unittest.TestCase):
    def setUp(self):
        self.doc = scenario()

    def reject(self, mutator, reason):
        x = copy.deepcopy(self.doc)
        mutator(x)
        with self.assertRaisesRegex(ValueError, reason):
            t.propose(x)

    def test_three_comparable_windows_and_one_step_proposal(self):
        o = t.propose(self.doc)
        self.assertEqual(o["proposed_state"], "ACCELERATE_CANDIDATE")
        self.assertEqual(o["topic_budget_candidate"], 6)
        self.assertEqual(o["window_references"]["N-10"]["n"], 0)
        self.assertEqual(o["window_references"]["N-5"]["n"], 5)
        self.assertEqual(o["window_references"]["N-1"]["n"], 9)
        self.assertEqual(o["delta_probe_interval_multiplier_candidate"], 0.5)

    def test_observed_receipt_name_never_authorizes_execution(self):
        for row in self.doc["pulses"]:
            row["evidence_class"] = "OWNER_RECEIPT_REFERENCED"
        o = t.propose(self.doc)
        self.assertFalse(o["execution_authorized"])
        self.assertEqual(o["merge_admission"], "HOLD")
        self.assertIsNone(o["verified_real_world_savings"])

    def test_missing_n10_blocks_acceleration(self):
        self.doc["pulses"] = self.doc["pulses"][-10:]
        self.assertEqual(t.propose(self.doc)["proposed_state"], "HOLD_N10_INCOMPLETE")

    def test_max_topic_budget_not_exceeded(self):
        self.doc["current_budget"] = 12
        o = t.propose(self.doc)
        self.assertEqual(o["proposed_state"], "STEADY_AT_CEILING")
        self.assertEqual(o["topic_budget_candidate"], 12)

    def test_queue_backpressure_slows_one_step(self):
        self.doc["current_budget"] = 12
        self.doc["pulses"][-1]["metrics"]["queue_depth"] = 65
        o = t.propose(self.doc)
        self.assertEqual(o["proposed_state"], "DECELERATE_CANDIDATE")
        self.assertEqual(o["topic_budget_candidate"], 6)
        self.assertEqual(o["delta_probe_interval_multiplier_candidate"], 2)

    def test_any_source_scope_collision_is_veto(self):
        self.doc["pulses"][-1]["metrics"]["source_collisions"] = 1
        self.assertEqual(t.propose(self.doc)["proposed_state"], "DECELERATE_CANDIDATE")

    def test_running_capacity_saturates(self):
        self.doc["pulses"][-1]["metrics"]["running_jobs"] = 20
        self.assertEqual(t.propose(self.doc)["proposed_state"], "DECELERATE_CANDIDATE")

    def test_missing_queue_does_not_equal_zero(self):
        self.doc["pulses"][-1]["metrics"]["queue_p95_s"] = None
        o = t.propose(self.doc)
        self.assertEqual(o["proposed_state"], "HOLD_MISSING_TELEMETRY")
        self.assertIn("queue_p95_s", o["missing_metrics"])

    def test_missing_reuse_or_ack_prevents_acceleration(self):
        self.doc["pulses"][-1]["metrics"]["controller_acks"] = 0
        self.assertEqual(t.propose(self.doc)["proposed_state"], "STEADY_NO_SCALE_EVIDENCE")
        self.doc["pulses"][-1]["metrics"]["controller_acks"] = 1
        self.doc["pulses"][-2]["metrics"]["reused_packets"] = 0
        self.assertEqual(t.propose(self.doc)["proposed_state"], "STEADY_NO_SCALE_EVIDENCE")

    def test_short_term_queue_regression_prevents_acceleration(self):
        self.doc["pulses"][-1]["metrics"]["queue_p95_s"] = 125
        self.assertEqual(t.propose(self.doc)["proposed_state"], "STEADY_NO_SCALE_EVIDENCE")

    def test_same_method_and_population_required(self):
        self.reject(lambda d: d["pulses"][3].update(method_version="2"), "INCOMPARABLE")
        self.reject(lambda d: d["pulses"][3].update(population_sha256="3"*64),
                    "INCOMPARABLE")

    def test_gapped_or_reordered_sequence_refused(self):
        self.reject(lambda d: d["pulses"][7].update(n=100), "GAPPED_OR_REORDERED")
        self.reject(lambda d: d["pulses"][5].update(observed_at="2026-10-01T00:00:00Z"),
                    "NONMONOTONE")

    def test_invalid_owner_identity_refused(self):
        self.reject(lambda d: d["pulses"][0]["provenance"]["everred"].update(
            source_head="deadbeef"), "INVALID_OWNER_BINDING")

    def test_boolean_negative_and_nan_not_measurements(self):
        self.reject(lambda d: d.update(current_budget=True), "BAD_TOPIC_BUDGET")
        self.reject(lambda d: d["pulses"][-1]["metrics"].update(source_reads=-1),
                    "INVALID_MEASUREMENT")
        self.reject(lambda d: d["pulses"][-1]["metrics"].update(queue_p95_s=float("nan")),
                    "INVALID_MEASUREMENT")

    def test_no_new_cron_and_deterministic_candidate(self):
        a=t.propose(self.doc)
        b=t.propose(copy.deepcopy(self.doc))
        self.assertEqual(a,b)
        self.assertEqual(a["new_cron_jobs"],0)
        self.assertEqual(a["native_workers_launched"],0)
        self.assertEqual(a["source_input_sha256"],t.exchange.digest(self.doc))

    def test_cli_receipt_no_authority(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"input.json"
            p.write_text(json.dumps(self.doc))
            out=Path(root)/"receipt.json"
            import subprocess
            import sys
            result=subprocess.run([sys.executable,"-m","metric_atlas.adaptive_pulse_tempo",
                                   "--input",str(p),"--out",str(out)],
                                  capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            r=json.loads(out.read_text())
            self.assertFalse(r["execution_authorized"])
            self.assertEqual(r["proposed_state"],"ACCELERATE_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
