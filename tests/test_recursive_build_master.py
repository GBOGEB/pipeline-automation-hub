from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "Recursive_Build_Master.py"
SPEC = importlib.util.spec_from_file_location("recursive_build_master", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


class RecursiveBuildMasterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.outputs = Path(self.tmp.name)
        (self.outputs / "metadata").mkdir()
        (self.outputs / "cross_references").mkdir()
        (self.outputs / "digital_twins").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write_metadata(self, name, priority, refs=0, file_hash="abc123"):
        normalized = name.replace(" ", "_")
        payload = {
            "original_filename": name,
            "normalized_name": normalized,
            "category": "TEST",
            "priority": priority,
            "processing_timestamp": "2026-09-18T00:00:00Z",
            "file_hash": file_hash,
            "cross_references": [f"REF-{i}" for i in range(refs)],
        }
        path = self.outputs / "metadata" / f"{Path(normalized).stem}_metadata.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_deterministic_outputs_with_explicit_time(self):
        self.write_metadata("A.pptx", "HIGH", refs=2)
        builder = MOD.RecursiveBuildMaster(self.outputs, "2026-09-18T15:00:00Z")
        receipt1 = builder.build().read_text(encoding="utf-8")
        index1 = (self.outputs / "recursive_build" / "index.json").read_text(encoding="utf-8")
        receipt2 = builder.build().read_text(encoding="utf-8")
        index2 = (self.outputs / "recursive_build" / "index.json").read_text(encoding="utf-8")
        self.assertEqual(receipt1, receipt2)
        self.assertEqual(index1, index2)

    def test_priority_dominates_ranking(self):
        self.write_metadata("critical.pptx", "CRITICAL", refs=0)
        self.write_metadata("low.pptx", "LOW", refs=10)
        MOD.RecursiveBuildMaster(self.outputs, "2026-09-18T15:00:00Z").build()
        index = json.loads((self.outputs / "recursive_build" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["records"][0]["original_filename"], "critical.pptx")
        self.assertEqual(index["records"][0]["rank"], 1)

    def test_buildlog_and_authority_guardrail(self):
        self.write_metadata("System Overview.pptx", "MEDIUM", refs=1)
        MOD.RecursiveBuildMaster(self.outputs, "2026-09-18T15:00:00Z").build()
        log = self.outputs / "recursive_build" / ".buildlog" / "system_overview_pptx" / "artefact_id.yaml"
        self.assertTrue(log.exists())
        self.assertIn("METADATA_ONLY_NOT_DOCUMENT_TRUTH", log.read_text(encoding="utf-8"))
        top = (self.outputs / "recursive_build" / "index_top30.md").read_text(encoding="utf-8")
        self.assertIn("grants no engineering", top)


if __name__ == "__main__":
    unittest.main()
