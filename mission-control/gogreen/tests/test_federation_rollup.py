"""Negative, dimensional and integrity controls for wide-to-deep federation roll-up."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "federation_rollup.py"
SPEC = importlib.util.spec_from_file_location("federation_rollup", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def sample_repo(label, sha, queue=4, discovered=("CENSUS",)):
    return {"repository": "GBOGEB/" + label, "sha": sha, "branch_protected": False,
            "queue": {"state": "OBSERVED", "observed_at_utc": "2026-10-15T09:00:00Z",
                      "queued": queue, "in_progress": 1},
            "surfaces": {name: {"state": "SOURCE_DISCOVERED", "path": "tools/receipt.py", "receipt": None}
                         if name in discovered else {"state": "UNKNOWN", "path": None, "receipt": None}
                         for name in module.SURFACES}}


def fixture(q=4):
    return {"schema": module.SCHEMA, "pulse_id": "GOGREEN-W2",
            "observed_at_utc": "2026-10-15T09:01:00Z",
            "repositories": [sample_repo("ABACUS", "a" * 40, q), sample_repo("CODEX", "b" * 40, 0)],
            "authority_transfer": False, "merge_authorized": False}


class FederationTests(unittest.TestCase):
    def test_wide_first_denominators_and_hold(self):
        x = module.build(fixture())
        d = x["breadth_depth"]
        self.assertEqual((22, 2, 20), (d["target_repo_surface_cells"], d["source_discovered_cells"], d["unknown_cells"]))
        self.assertEqual((0, 0), (d["native_status_verified_cells"], d["artifact_bytes_verified_cells"]))
        self.assertEqual((4, 2), (d["fleet_queued_observed_sum"], d["fleet_in_progress_observed_sum"]))
        self.assertEqual("HOLD", x["admission"])
        self.assertEqual(0, x["worker_dispatches"])

    def test_zero_is_not_missing(self):
        x = module.build(fixture(q=0))
        self.assertEqual(0, x["queue_by_repo"]["GBOGEB/ABACUS"]["queued"])

    def test_unknown_queue_is_not_zero(self):
        p = fixture()
        p["repositories"][0]["queue"] = {"state": "UNAVAILABLE", "queued": None, "in_progress": None}
        x = module.build(p)
        self.assertIsNone(x["breadth_depth"]["fleet_queued_observed_sum"])
        self.assertEqual("INCOMPLETE", x["breadth_depth"]["queue_measurement_state"])

    def test_unknown_queue_with_numeric_count_rejected(self):
        p = fixture()
        p["repositories"][0]["queue"] = {"state": "UNAVAILABLE", "queued": 0, "in_progress": 0}
        with self.assertRaises(ValueError):
            module.build(p)

    def test_duplicate_repo_rejected(self):
        p = fixture()
        p["repositories"].append(copy.deepcopy(p["repositories"][0]))
        with self.assertRaises(ValueError):
            module.build(p)

    def test_invalid_sha_rejected(self):
        p = fixture()
        p["repositories"][0]["sha"] = "short"
        with self.assertRaises(ValueError):
            module.build(p)

    def test_unknown_surface_with_path_rejected(self):
        p = fixture()
        p["repositories"][0]["surfaces"]["LLDB"]["path"] = "fake.py"
        with self.assertRaises(ValueError):
            module.build(p)

    def test_missing_surface_rejected(self):
        p = fixture()
        p["repositories"][0]["surfaces"].pop("REX")
        with self.assertRaises(ValueError):
            module.build(p)

    def test_forged_native_proof_rejected(self):
        p = fixture()
        s = p["repositories"][0]["surfaces"]["CENSUS"]
        s["state"] = "NATIVE_STATUS"
        s["receipt"] = {"repository": "GBOGEB/ABACUS", "sha": "b" * 40,
                        "surface": "CENSUS", "run_id": 1, "job_id": 2, "attempt": 1,
                        "status": "completed", "conclusion": "success"}
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            module.build(p)

    def test_good_native_receipt_does_not_approve(self):
        p = fixture()
        s = p["repositories"][0]["surfaces"]["CENSUS"]
        s["state"] = "NATIVE_STATUS"
        s["receipt"] = {"repository": "GBOGEB/ABACUS", "sha": "a" * 40,
                        "surface": "CENSUS", "run_id": 1, "job_id": 2, "attempt": 1,
                        "status": "completed", "conclusion": "success"}
        x = module.build(p)
        self.assertEqual(1, x["breadth_depth"]["native_status_verified_cells"])
        self.assertFalse(x["merge_authorized"])
        self.assertEqual("HOLD", x["methods"]["PCA"]["status"])

    def test_verified_bytes_require_real_digest(self):
        p = fixture()
        s = p["repositories"][0]["surfaces"]["CENSUS"]
        s["state"] = "VERIFIED_BYTES"
        s["receipt"] = {"repository": "GBOGEB/ABACUS", "sha": "a" * 40,
                        "surface": "CENSUS", "run_id": 1, "job_id": 2, "attempt": 1,
                        "status": "completed", "conclusion": "success",
                        "artifact_sha256": "bad", "independent_byte_verifier": True}
        with self.assertRaisesRegex(ValueError, "sha256"):
            module.build(p)
        s["receipt"]["artifact_sha256"] = "e" * 64
        s["receipt"]["independent_byte_verifier"] = False
        with self.assertRaisesRegex(ValueError, "independent verifier"):
            module.build(p)

    def test_coverage_delta_not_fabricated(self):
        old, new = fixture(10), fixture(8)
        old["pulse_id"] = "GOGREEN-W1"
        old["observed_at_utc"] = "2026-10-15T09:00:30Z"
        x = module.build(new, old)
        d = x["queue_transitions"][0]
        self.assertEqual(-2, d["queued_change"])
        self.assertEqual("DESCRIPTIVE_NOT_CAUSAL", d["queue_delta_state"])
        self.assertIsNone(d["matched_coverage_delta"])
        self.assertIsNone(d["root_closures_verified"])

    def test_changed_sha_suppresses_delta(self):
        a, b = fixture(8), fixture(9)
        a["pulse_id"] = "GOGREEN-W1"
        a["observed_at_utc"] = "2026-10-15T09:00:30Z"
        a["repositories"][0]["sha"] = "c" * 40
        x = module.build(b, a)
        self.assertIsNone(x["queue_transitions"][0]["queued_change"])
        self.assertEqual("UNKNOWN", x["queue_transitions"][0]["queue_delta_state"])

    def test_time_order_rejected(self):
        a, b = fixture(), fixture()
        a["pulse_id"] = "GOGREEN-W1"
        with self.assertRaises(ValueError):
            module.build(b, a)

    def test_non_utc_rejected(self):
        p = fixture()
        p["observed_at_utc"] = "2026-10-15T11:01:00+02:00"
        with self.assertRaises(ValueError):
            module.build(p)

    def test_future_queue_sample_rejected(self):
        p = fixture()
        p["repositories"][0]["queue"]["observed_at_utc"] = "2026-10-15T10:10:00Z"
        with self.assertRaises(ValueError):
            module.build(p)

    def test_boolean_count_rejected(self):
        p = fixture()
        p["repositories"][0]["queue"]["queued"] = True
        with self.assertRaises(ValueError):
            module.build(p)

    def test_denied_authority_rejected(self):
        p = fixture()
        p["merge_authorized"] = True
        with self.assertRaises(ValueError):
            module.build(p)

    def test_unpaired_pca_and_bt_hold(self):
        x = module.build(fixture())
        self.assertTrue(all(z["status"] == "HOLD" for z in x["methods"].values()))
        self.assertIsNone(x["breadth_depth"]["independent_cycles"])

    def test_manifest_and_determinism(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            x = module.emit(fixture(), None, a)
            module.emit(fixture(), None, b)
            target = Path(a)
            digest = hashlib.sha256((target / "rollup.json").read_bytes()).hexdigest()
            m = json.loads((target / "manifest.json").read_text())
            self.assertEqual(digest, m["sha256"]["rollup.json"])
            self.assertEqual((target / "rollup.json").read_bytes(), (Path(b) / "rollup.json").read_bytes())
            self.assertFalse(x["authority_transfer"])


    def test_malformed_roots_and_coordinates(self):
        for field, replacement in (("schema", "wrong"), ("pulse_id", None), ("repositories", [])):
            with self.subTest(field=field):
                p = fixture()
                p[field] = replacement
                with self.assertRaises(ValueError):
                    module.build(p)
        p = fixture()
        p["repositories"][0] = None
        with self.assertRaises(ValueError):
            module.build(p)

    def test_queue_surface_protection_rejection(self):
        def edit(field, value):
            p = fixture()
            p["repositories"][0][field] = value
            return p
        for field, val in (("branch_protected", 17), ("queue", []), ("surfaces", [])):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    module.build(edit(field, val))
        p = fixture()
        p["repositories"][0]["surfaces"]["CENSUS"]["path"] = "../private"
        with self.assertRaises(ValueError):
            module.build(p)
        p = fixture()
        p["repositories"][0]["surfaces"]["CENSUS"] = {"state": "BOGUS", "path": "x"}
        with self.assertRaises(ValueError):
            module.build(p)

    def test_discovery_cannot_carry_native_receipt(self):
        p = fixture()
        p["repositories"][0]["surfaces"]["CENSUS"]["receipt"] = {}
        with self.assertRaises(ValueError):
            module.build(p)

    def test_native_receipt_missing_malformed(self):
        p = fixture()
        s = p["repositories"][0]["surfaces"]["CENSUS"]
        s["state"] = "NATIVE_STATUS"
        with self.assertRaises(ValueError):
            module.build(p)
        s["receipt"] = {"repository": "GBOGEB/ABACUS", "sha": "a" * 40,
                        "surface": "CENSUS", "run_id": 0, "job_id": 2, "attempt": 1,
                        "status": "completed", "conclusion": "success"}
        with self.assertRaises(ValueError):
            module.build(p)
        s["receipt"]["run_id"] = 1
        s["receipt"]["conclusion"] = "failure"
        with self.assertRaises(ValueError):
            module.build(p)
        s["receipt"]["conclusion"] = "success"
        s["receipt"]["surface"] = "MIP"
        with self.assertRaises(ValueError):
            module.build(p)

    def test_valid_byte_proof_remains_unadmitted(self):
        p = fixture()
        s = p["repositories"][0]["surfaces"]["CENSUS"]
        s["state"] = "VERIFIED_BYTES"
        s["receipt"] = {"repository": "GBOGEB/ABACUS", "sha": "a" * 40,
                        "surface": "CENSUS", "run_id": 1, "job_id": 2, "attempt": 1,
                        "status": "completed", "conclusion": "success",
                        "artifact_sha256": "b" * 64, "independent_byte_verifier": True}
        result = module.build(p)
        self.assertEqual(result["breadth_depth"]["artifact_bytes_verified_cells"], 1)
        self.assertEqual(result["admission"], "HOLD")

    def test_changed_clock_and_id_fail_closed(self):
        a, b = fixture(4), fixture(8)
        a["pulse_id"] = b["pulse_id"]
        a["observed_at_utc"] = "2026-10-15T09:00:45Z"
        with self.assertRaises(ValueError):
            module.build(b, a)
        self.assertEqual(module.utc("2026-10-15T09:00:00Z").year, 2026)
        with self.assertRaises(ValueError):
            module.utc("2026-99-99T50:00:00Z")

    def test_queue_nonmatching_previous_source_suppresses_delta(self):
        old, new = fixture(4), fixture(8)
        old["pulse_id"] = "GOGREEN-W1"
        old["observed_at_utc"] = "2026-10-15T09:00:30Z"
        old["repositories"][0]["queue"] = {"state": "UNAVAILABLE", "queued": None, "in_progress": None}
        self.assertIsNone(module.build(new, old)["queue_transitions"][0]["queued_change"])

    def test_command_line_roundtrip(self):
        import sys
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "current.json"
            current.write_text(json.dumps(fixture()), encoding="utf8")
            with mock.patch.object(sys, "argv", ["federation_rollup.py", "--current", str(current), "--output", str(base / "out")]):
                module.main()
            self.assertTrue((base / "out" / "rollup.json").exists())


if __name__ == "__main__":
    unittest.main()
