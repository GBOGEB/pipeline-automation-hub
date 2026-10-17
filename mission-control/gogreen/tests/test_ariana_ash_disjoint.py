"""ASH tests: real CBD planning surfaces survive failure without false-green."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ash_survival", ROOT / "ash_survival.py"
)
assert SPEC is not None and SPEC.loader is not None
ASH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASH)
INPUT = ROOT / "samples" / "ariana_ash_disjoint_20261017.json"


def data() -> dict:
    return json.loads(INPUT.read_text(encoding="utf-8"))


class ASHDisjointRecoveryTests(unittest.TestCase):
    def test_native_source_bound_seed_and_two_scout_waves(self):
        receipt = ASH.analyze(data())
        self.assertEqual(receipt["survival"]["ready_scouts_remaining"], 3)
        self.assertEqual(receipt["survival"]["waves_planned"], 2)
        self.assertEqual(receipt["survival"]["planned_max_parallel"], 2)
        self.assertEqual(receipt["survival"]["native_proof_packets_still_present"], 1)
        self.assertEqual(receipt["survival"]["native_bytes_verified_packets"], 0)
        self.assertEqual(receipt["survival"]["independently_accepted_root_closures"], 0)

    def test_survival_keeps_known_local_proof_but_no_remote_acceptance(self):
        receipt = ASH.analyze(data())
        refs = receipt["recovery"]["retained_native_run_job_refs"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["run_id"], 39046986905)
        self.assertEqual(refs[0]["run_attempt"], 1)
        self.assertEqual(refs[0]["job_id"], 117437850200)
        self.assertFalse(refs[0]["archive_bytes_verified"])
        self.assertIsNone(receipt["survival"]["remote_keb_qps_acceptance"])
        self.assertIsNone(receipt["boundary"]["qps_engineering_acceptance"])

    def test_unknown_occurrences_are_not_declared_complete_denominator(self):
        receipt = ASH.analyze(data())
        self.assertEqual(receipt["survival"]["occurrence_counts_unknown_packets"], 9)
        self.assertEqual(receipt["survival"]["fingerprint_counts_unknown_packets"], 9)
        self.assertEqual(
            receipt["survival"]["total_observed_occurrences_known_scope"], 0
        )
        self.assertIsNone(receipt["survival"]["worker_launches_observed"])
        self.assertIsNone(receipt["survival"]["runner_minutes_observed"])
        self.assertIsNone(receipt["survival"]["matched_coverage_uplift_pp"])

    def test_one_scout_loss_degrades_gracefully_with_partial_results(self):
        receipt = ASH.analyze(data(), "ASH-SEC-SCOUT")
        self.assertEqual(
            receipt["observation_kind"], "SIMULATED_FAILURE_NOT_NATIVE_EXECUTION"
        )
        self.assertEqual(receipt["recovery"]["original_ready_scouts"], 3)
        self.assertEqual(receipt["recovery"]["postfailure_ready_scouts"], 2)
        self.assertEqual(receipt["survival"]["waves_planned"], 1)
        self.assertEqual(receipt["survival"]["native_proof_packets_still_present"], 1)
        self.assertTrue(
            receipt["recovery"]["read_only_scouts_remain_plan_eligible"]
        )
        self.assertFalse(receipt["recovery"]["mutation_fanout_admitted"])
        self.assertFalse(
            receipt["recovery"]["fleet_or_crew_dispatched_by_this_adapter"]
        )

    def test_all_read_only_scouts_lost_keeps_evidence_and_owner_blockers(self):
        payload = data()
        for row in payload["packets"]:
            if row["state"] == "READY":
                row["state"] = "BLOCKED"
                row["blockers"] = ["ASH_SIMULATED_WORKER_LOSS"]
        receipt = ASH.analyze(payload)
        self.assertEqual(receipt["survival"]["ready_scouts_remaining"], 0)
        self.assertEqual(receipt["survival"]["waves_planned"], 0)
        self.assertEqual(receipt["survival"]["native_proof_packets_still_present"], 1)
        self.assertFalse(
            receipt["recovery"]["read_only_scouts_remain_plan_eligible"]
        )
        self.assertEqual(receipt["boundary"]["merge_admission"], "HOLD")

    def test_simulation_cannot_erase_nonready_owner_blocker(self):
        with self.assertRaisesRegex(ValueError, "exactly one READY"):
            ASH.analyze(data(), "ASH-GOV-OWNER")
        with self.assertRaisesRegex(ValueError, "exactly one READY"):
            ASH.analyze(data(), "UNKNOWN_WORKER")

    def test_forecasted_crew_seat_does_not_make_an_active_runner(self):
        receipt = ASH.analyze(data())
        self.assertEqual(receipt["survival"]["state"],
                         "PARTIAL_READ_ONLY_WITH_OWNER_HOLDS")
        self.assertFalse(
            receipt["boundary"]["crew_competence_from_packet_count"]
        )
        self.assertTrue(
            receipt["boundary"][
                "proposed_worker_schedule_is_not_actual_worker_execution"
            ]
        )
        self.assertFalse(receipt["boundary"]["authority_transfer"])
        self.assertFalse(receipt["boundary"]["security_waiver"])

    def test_source_sha_spoofing_fails_closed(self):
        payload = data()
        native = next(p for p in payload["packets"] if p["id"] == "ASH-LOCAL-JOIN")
        native["proof"]["source_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "proof source mismatch"):
            ASH.analyze(payload)

    def test_ash_acceptance_cannot_self_promote_root(self):
        payload = data()
        native = next(p for p in payload["packets"] if p["id"] == "ASH-LOCAL-JOIN")
        native["accepted_root_ids"] = ["ROOT_WAS_NOT_APPROVED"]
        with self.assertRaisesRegex(ValueError, "accepted roots"):
            ASH.analyze(payload)

    def test_disjoint_repair_leases_do_not_overlap_in_one_wave(self):
        payload = data()
        sample = next(p for p in payload["packets"] if p["id"] == "ASH-SEC-SCOUT")
        for i, path in enumerate((
            "scripts/ci", "scripts/ci/ariana_dow_evidence.py"
        )):
            worker = copy.deepcopy(sample)
            worker["id"] = f"ASH-FAULT-PATH-{i}"
            worker["mode"] = "MUTATING_REPAIR"
            worker["phase"] = "REPAIR"
            worker["mutation_paths"] = [path]
            payload["packets"].append(worker)
        result = ASH.analyze(payload)
        waves = result["cbd_schedule"]["waves"]
        placement = {}
        for idx, wave in enumerate(waves):
            for packet in wave:
                if packet["id"].startswith("ASH-FAULT-PATH"):
                    placement[packet["id"]] = idx
        self.assertNotEqual(
            placement["ASH-FAULT-PATH-0"], placement["ASH-FAULT-PATH-1"]
        )
        self.assertGreaterEqual(
            result["survival"]["disjoint_path_conflicts_prevented"], 1
        )
        self.assertFalse(result["recovery"]["mutation_fanout_admitted"])

    def test_missing_security_approval_does_not_turn_verified_into_accepted(self):
        payload = data()
        security = next(p for p in payload["packets"] if p["id"] == "ASH-SEC-OWNER")
        security["state"] = "READY"
        security["blockers"] = []
        security["mode"] = "READ_ONLY_ANALYZE"
        receipt = ASH.analyze(payload)
        self.assertEqual(
            receipt["survival"]["independently_accepted_root_closures"], 0
        )
        self.assertEqual(receipt["boundary"]["merge_admission"], "HOLD")

    def test_readonly_adapter_preserves_input_and_has_no_write_or_dispatch(self):
        payload = data()
        original = copy.deepcopy(payload)
        receipt = ASH.analyze(payload, "ASH-GOV-SCOUT")
        self.assertEqual(payload, original)
        self.assertFalse(
            receipt["recovery"]["fleet_or_crew_dispatched_by_this_adapter"]
        )
        self.assertFalse(receipt["recovery"]["mutation_fanout_admitted"])


if __name__ == "__main__":
    unittest.main()
