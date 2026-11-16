#!/usr/bin/env python3
"""Adversarial tests for the namespaced read-only overlay."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nseries_overlay", HERE / "nseries_overlay.py")
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class OverlayChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(mod.INPUT.read_text(encoding="utf-8"))

    def test_registry_valid_and_not_admitted(self):
        summary = mod.validate(self.data)
        self.assertGreater(summary["nodes"], 0)
        self.assertEqual(summary["merge_admission"], "HOLD")
        self.assertIsNone(summary["native_execution_receipt"])
        self.assertIsNone(summary["independent_approval"])
        self.assertGreater(len(summary["layers"]), 0)

    def _reject(self, edit, term):
        data = copy.deepcopy(self.data)
        edit(data)
        with self.assertRaisesRegex(ValueError, term):
            mod.validate(data)

    def test_duplicate_node_rejected(self):
        self._reject(lambda d: d["nodes"].append(copy.deepcopy(d["nodes"][0])), "duplicate node")

    def test_unknown_endpoint_rejected(self):
        self._reject(lambda d: d["edges"].append({"from": "GLOBAL:N0",
                     "to": "GLOBAL:UNKNOWN", "kind": "HARD_DAG", "evidence": "NEGATIVE"}),
                     "unknown edge endpoint")

    def test_hard_cycle_rejected(self):
        self._reject(lambda d: d["edges"].append({"from": "GLOBAL:N7",
                     "to": "GLOBAL:N0", "kind": "HARD_DAG", "evidence": "NEGATIVE"}),
                     "cycle in feedforward graph")

    def test_feedback_does_not_create_hard_cycle(self):
        summary = mod.validate(self.data)
        feedback = [e for e in self.data["edges"] if e["kind"] == "NEXT_PULSE"]
        self.assertGreater(len(feedback), 0)
        self.assertEqual(summary["hard_edges"],
                         sum(e["kind"] == "HARD_DAG" for e in self.data["edges"]))

    def test_unverified_cross_owner_hard_dependency_rejected(self):
        self._reject(lambda d: d["edges"].append({"from": "QPS.TOPO:N4",
                     "to": "GLOBAL:N1", "kind": "HARD_DAG", "evidence": "NEGATIVE"}),
                     "unverified cross-namespace hard dependency")

    def test_missing_authority_and_false_green_rejected(self):
        self._reject(lambda d: d.update(merge_admission="ADMITTED"), "merge admission")
        self._reject(lambda d: d["nodes"][0].update(status="PASS"), "cannot assert success")
        self._reject(lambda d: d["nodes"][0].update(owner=""), "unowned")
        self._reject(lambda d: d.update(authority_transfer=True), "authority boundary")

    def test_alias_and_namespace_collision_rejected(self):
        self._reject(lambda d: d["nodes"][0].update(namespace="WATCH"), "namespace mismatch")
        self.assertIn("WATCH:N6", {n["id"] for n in self.data["nodes"]})
        self.assertIn("GLOBAL:N6", {n["id"] for n in self.data["nodes"]})

    def test_duplicate_edge_and_missing_provenance_rejected(self):
        self._reject(lambda d: d["edges"].append(copy.deepcopy(d["edges"][0])), "duplicate typed edge")
        self._reject(lambda d: d["edges"][0].update(evidence=""), "untyped or ungrounded")

    def test_mermaid_is_deterministic_and_escaped(self):
        text = mod.diagram(self.data, only_hard=True)
        self.assertEqual(text, mod.diagram(self.data, only_hard=True))
        self.assertIn("flowchart LR", text)
        self.assertNotIn("NEXT_PULSE", text)

    def test_offline_html_no_external_dependencies_or_private_data(self):
        body = mod.webpage(self.data, mod.validate(self.data))
        self.assertIn('id="search"', body)
        self.assertIn("<svg", body)
        self.assertNotIn("<script src=", body)
        self.assertNotIn("GITHUB_TOKEN", body)
        self.assertNotIn("ACCEPTED_BY_AUTHORITY", body)

    def test_generated_outputs_declared(self):
        files = {p.name for p in mod.outputs(self.data)}
        self.assertEqual(files, {"GLOBAL_N_SERIES.mmd", "N_SERIES_DEPENDENCIES.mmd",
                                 "nseries_atlas.html", "nseries_atlas.json"})


if __name__ == "__main__":
    unittest.main()
