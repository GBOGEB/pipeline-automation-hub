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


class GoldenThreadBootstrapBatchTests(unittest.TestCase):
    def test_batch001_replays_idempotently_with_full_repo_lineage(self):
        fixture = json.loads(
            (HERE / "fixtures" / "GT_BD_011_BOOTSTRAP_BATCH001_20260917.json").read_text(encoding="utf-8")
        )

        records = [
            adapter.normalize_connector_snapshot(
                item["repository"],
                item["object_type"],
                item["anchor_sha"],
                item["snapshot"],
            )
            for item in fixture["records"]
        ]

        repositories = {record["repository"] for record in records}
        self.assertEqual(len(repositories), fixture["expected"]["repository_count"])
        self.assertEqual(len(records), fixture["expected"]["occurrence_count"])
        self.assertEqual(len(repositories) / fixture["expected"]["repository_count"], fixture["expected"]["lineage_coverage"])

        first = ff.import_occurrences(records)
        self.assertEqual(first["occurrence_count"], fixture["expected"]["occurrence_count"])
        self.assertEqual(first["imported_count"], fixture["expected"]["occurrence_count"])
        self.assertFalse(first["authority_transfer"])

        second = ff.import_occurrences(records, first["occurrences"])
        self.assertEqual(second["imported_count"], fixture["expected"]["reimport_imported_count"])
        self.assertEqual(second["duplicate_count"], fixture["expected"]["reimport_duplicate_count"])
        self.assertEqual(second["projection_digest"], first["projection_digest"])
        self.assertFalse(second["authority_transfer"])

        for item in fixture["records"]:
            self.assertEqual(item["anchor_sha"], item["snapshot"]["head"]["sha"])

        self.assertFalse(fixture["nonclaims"]["fleet_M4"])
        self.assertFalse(fixture["nonclaims"]["qps_gt_bdq_credit"])
        self.assertFalse(fixture["nonclaims"]["engineering_credit"])
        self.assertFalse(fixture["nonclaims"]["source_authority_transfer"])


if __name__ == "__main__":
    unittest.main()
