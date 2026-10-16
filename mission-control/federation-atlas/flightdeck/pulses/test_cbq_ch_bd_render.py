"""Regression controls for supporting CBQ and CH-BD projections."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "CBQ_CH_BD_20261016.json"
SPEC = importlib.util.spec_from_file_location(
    "cbq_ch_bd_render", HERE / "cbq_ch_bd_render.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CausalQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_controlled_frozen_source(self):
        MODULE.validate(self.source)

    def test_sealed_projection_and_no_closure_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = MODULE.produce(SOURCE, Path(tmp))
            projection = json.loads(
                (Path(tmp) / "projection.json").read_text(encoding="utf-8")
            )
            self.assertEqual(0, projection["verified_root_closures"])
            self.assertEqual("DEFER", projection["authority"]["qps_decision"])
            self.assertEqual(2, projection["scale"]["candidate_disjoint_source_workers"])
            self.assertEqual(5, len(projection["snapshots"]))
            self.assertEqual(9, len(projection["cbq"]))
            for name, expected in manifest["artifacts"].items():
                self.assertEqual(
                    expected,
                    hashlib.sha256((Path(tmp) / name).read_bytes()).hexdigest(),
                )

    def test_refuse_forged_qps_owner_decision(self):
        data = copy.deepcopy(self.source)
        data["authority"]["qps_decision"] = "ACCEPT"
        with self.assertRaisesRegex(ValueError, "authority inversion"):
            MODULE.validate(data)

    def test_refuse_synthetic_promotion(self):
        data = copy.deepcopy(self.source)
        data["authority"]["synthetic_promotion"] = True
        with self.assertRaises(ValueError):
            MODULE.validate(data)

    def test_refuse_changed_product_denominator(self):
        data = copy.deepcopy(self.source)
        data["baseline"]["historical_QPS_product_closure"]["denominator"] = 89
        with self.assertRaises(ValueError):
            MODULE.validate(data)

    def test_refuse_fleet_breadth_forgery(self):
        data = copy.deepcopy(self.source)
        data["baseline"]["historical_GOGREEN_cells"]["numerator"] = 42
        with self.assertRaises(ValueError):
            MODULE.validate(data)

    def test_refuse_duplicate_source_head_row(self):
        data = copy.deepcopy(self.source)
        data["snapshots"].append(copy.deepcopy(data["snapshots"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate PR"):
            MODULE.validate(data)

    def test_refuse_missing_sha(self):
        data = copy.deepcopy(self.source)
        data["snapshots"][0]["head_sha"] = "short"
        with self.assertRaisesRegex(ValueError, "missing exact head"):
            MODULE.validate(data)

    def test_refuse_invented_close(self):
        data = copy.deepcopy(self.source)
        data["families"][0]["verified_closed"] = True
        with self.assertRaisesRegex(ValueError, "unqualified root closure"):
            MODULE.validate(data)

    def test_refuse_invented_worker_proof(self):
        data = copy.deepcopy(self.source)
        data["scale"]["actual_live_worker_count"] = 2
        with self.assertRaisesRegex(ValueError, "worker deployment inferred"):
            MODULE.validate(data)

    def test_refuse_chain_native_promotion(self):
        data = copy.deepcopy(self.source)
        data["chain"][0]["status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "unqualified federation"):
            MODULE.validate(data)

    def test_refuse_unsupported_taxonomy_expansion(self):
        data = copy.deepcopy(self.source)
        data["semantic_names"]["CBQ"] = "Invented Canonical Label"
        with self.assertRaisesRegex(ValueError, "invented taxonomy"):
            MODULE.validate(data)


if __name__ == "__main__":
    unittest.main()
