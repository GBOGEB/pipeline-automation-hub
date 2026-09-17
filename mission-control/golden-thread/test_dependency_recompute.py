#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = _load("dependency_recompute", HERE / "dependency_recompute.py")
ff = _load("federation_frontier_for_recompute_test", HERE / "federation_frontier.py")


class DependencyRecomputeTests(unittest.TestCase):
    def _manifest(self):
        return json.loads(
            (HERE / "fixtures" / "GT_BD_002_REAL_CONE_BATCH001_v1.json").read_text(encoding="utf-8")
        )

    def test_real_batch001_descendant_cone_recomputes_with_zero_stale_survivors(self):
        manifest = self._manifest()
        with tempfile.TemporaryDirectory() as td:
            result = runner.execute_cone(manifest, td)

        receipt = result["receipt"]
        closure = result["closure"]
        expected = manifest["expected"]

        self.assertEqual(receipt["scope"], expected["scope"])
        self.assertEqual(receipt["affected_nodes"], sorted(expected["affected_nodes"]))
        self.assertEqual(receipt["affected_renditions"], sorted(expected["affected_renditions"]))
        self.assertEqual(closure["stale_survivor_count"], expected["stale_survivor_count"])
        self.assertEqual(closure["stale_rendition_count"], expected["stale_rendition_count"])
        self.assertEqual(closure["status"], expected["status"])
        self.assertTrue(closure["non_compensating_gates_preserved"])
        self.assertFalse(closure["authority_transfer"])
        self.assertFalse(result["authority_transfer"])
        self.assertEqual(result["summary"]["repository_count"], 4)
        self.assertEqual(result["summary"]["occurrence_count"], 4)
        self.assertEqual(result["summary"]["lineage_coverage"], 1.0)

    def test_incomplete_recompute_is_withheld_and_reports_stale_survivor(self):
        manifest = self._manifest()
        node_ids = [node["id"] for node in manifest["nodes"]]
        receipt = ff.build_invalidation_receipt(
            node_ids,
            [tuple(edge) for edge in manifest["edges"]],
            manifest["root_nodes"],
            "DESCENDANT_CONE",
            renditions=manifest["renditions"],
            trigger=manifest["trigger"],
        )
        closure = ff.close_invalidation(
            receipt,
            recomputed_nodes=["BOOTSTRAP_FIXTURE", "NORMALIZED_OCCURRENCE_PROJECTION"],
            regenerated_renditions=["normalized-occurrence-projection.json"],
        )
        self.assertEqual(closure["status"], "WITHHELD")
        self.assertEqual(closure["stale_survivors"], ["BOOTSTRAP_SUMMARY"])
        self.assertEqual(closure["stale_renditions"], ["bootstrap-summary.json"])
        self.assertFalse(closure["authority_transfer"])


if __name__ == "__main__":
    unittest.main()
