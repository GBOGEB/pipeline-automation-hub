#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ff = _load("federation_frontier", HERE / "federation_frontier.py")
adapter = _load("occurrence_connector_adapter", HERE / "occurrence_connector_adapter.py")


class ConnectorOccurrenceAdapterTests(unittest.TestCase):
    def test_second_independent_family_is_idempotent_and_registry_bound(self):
        fixture = json.loads(
            (HERE / "fixtures" / "LIVE_GITHUB_OCCURRENCE_FAMILY_CODEX_20260917.json").read_text(encoding="utf-8")
        )
        records = [
            adapter.normalize_connector_snapshot(
                fixture["repository"],
                item["object_type"],
                item["anchor_sha"],
                item["snapshot"],
            )
            for item in fixture["connector_snapshots"]
        ]
        first = ff.import_occurrences(records)
        self.assertEqual(first["occurrence_count"], fixture["expected"]["occurrence_count"])
        self.assertEqual(first["projection_digest"], fixture["expected"]["first_projection_digest"])
        second = ff.import_occurrences(records, first["occurrences"])
        self.assertEqual(second["imported_count"], fixture["expected"]["reimport_imported_count"])
        self.assertEqual(second["duplicate_count"], fixture["expected"]["reimport_duplicate_count"])
        self.assertEqual(second["projection_digest"], fixture["expected"]["reimport_projection_digest"])
        self.assertFalse(second["authority_transfer"])

        registry = json.loads((HERE / "GOLDEN_THREAD_IMPORT_RECEIPT_REGISTRY_v1.json").read_text(encoding="utf-8"))
        family = next(x for x in registry["families"] if x["family_id"] == "CODEX_753_754")
        self.assertEqual(family["projection_digest"], first["projection_digest"])
        self.assertEqual(family["idempotency_keys"], sorted(first["occurrences"]))
        self.assertEqual(registry["controls"]["family_count"], 2)
        self.assertEqual(registry["controls"]["repository_count"], 2)
        self.assertFalse(registry["controls"]["authority_transfer"])
        self.assertFalse(registry["controls"]["qps_gt_bdq_credit"])
        self.assertFalse(registry["controls"]["fleet_m4_credit"])

    def test_adapter_fails_closed_on_missing_pr_sha(self):
        with self.assertRaises(adapter.ConnectorOccurrenceError):
            adapter.normalize_connector_snapshot(
                "GBOGEB/CODEX",
                "pull_request",
                "abc1234",
                {
                    "number": 1,
                    "title": "bad",
                    "state": "open",
                    "base": {"sha": "base123"},
                    "head": {},
                },
            )

    def test_adapter_rejects_unsupported_object_type(self):
        with self.assertRaises(adapter.ConnectorOccurrenceError):
            adapter.normalize_connector_snapshot(
                "GBOGEB/CODEX",
                "release",
                "abc1234",
                {"number": 1, "title": "bad", "state": "open"},
            )


if __name__ == "__main__":
    unittest.main()
