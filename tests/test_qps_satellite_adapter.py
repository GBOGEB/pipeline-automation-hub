import json
import tempfile
import unittest
from pathlib import Path

from scripts import qps_satellite_adapter as adapter


class AdapterTests(unittest.TestCase):
    def test_export_is_deterministic_and_filters_unhashed_records(self):
        manifest = {
            "processing_summary": {
                "files_processed": [
                    {
                        "filename": "b.pptx",
                        "metadata": {
                            "original_filename": "b.pptx",
                            "file_hash": "b" * 64,
                            "file_type": "PPTX",
                            "category": "SYSTEMS",
                            "priority": "HIGH",
                        },
                        "cross_references": [],
                    },
                    {
                        "filename": "bad.pptx",
                        "metadata": {
                            "original_filename": "bad.pptx",
                            "file_hash": "not-a-hash",
                        },
                    },
                    {
                        "filename": "a.pptx",
                        "metadata": {
                            "original_filename": "a.pptx",
                            "file_hash": "a" * 64,
                            "file_type": "PPTX",
                            "category": "COMPLIANCE",
                            "priority": "CRITICAL",
                        },
                        "cross_references": [
                            {
                                "reference": "SCK CEN/1",
                                "context": "x",
                                "type": "primary",
                            }
                        ],
                    },
                ]
            }
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "PROCESSING_MANIFEST.json"
            out1 = root / "one.json"
            out2 = root / "two.json"
            source.write_text(json.dumps(manifest), encoding="utf-8")
            first = adapter.export_manifest(source, out1, "master", "abc123")
            second = adapter.export_manifest(source, out2, "master", "abc123")

            self.assertEqual(first["bridge_id"], second["bridge_id"])
            self.assertEqual(
                [item["source_path"] for item in first["artifact_records"]],
                ["a.pptx", "b.pptx"],
            )
            self.assertFalse(first["routing"]["direct_parent_dispatch_allowed"])
            self.assertFalse(first["governance"]["engineering_ssot_mutation_allowed"])

    def test_feedback_accepts_only_sanitized_reusable_accepts(self):
        payload = {
            "schema": adapter.FEEDBACK_SCHEMA,
            "source": {"repository": adapter.QPS_REPOSITORY, "sha": "qpssha"},
            "target_repository": adapter.SATELLITE_REPOSITORY,
            "correlation_id": "x",
            "findings": [
                {
                    "finding_id": "F1",
                    "disposition": "ACCEPT",
                    "reusable_learning": True,
                    "confidential": False,
                    "summary": "dedupe regression",
                    "source_reference": "qps/path",
                },
                {
                    "finding_id": "F2",
                    "disposition": "DEFER",
                    "reusable_learning": True,
                    "confidential": False,
                    "summary": "later",
                },
                {
                    "finding_id": "F3",
                    "disposition": "ACCEPT",
                    "reusable_learning": False,
                    "confidential": False,
                    "summary": "project only",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "feedback.json"
            output = root / "learning.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            result = adapter.import_feedback(source, output)

            self.assertEqual([item["finding_id"] for item in result["learnings"]], ["F1"])
            self.assertFalse(result["engineering_ssot_mutation_allowed"])

    def test_feedback_rejects_noncanonical_disposition(self):
        payload = {
            "schema": adapter.FEEDBACK_SCHEMA,
            "source": {"repository": adapter.QPS_REPOSITORY},
            "target_repository": adapter.SATELLITE_REPOSITORY,
            "findings": [
                {
                    "finding_id": "F1",
                    "disposition": "ACCEPT_AS_DERIVED_EVIDENCE",
                    "reusable_learning": True,
                    "confidential": False,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "feedback.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(adapter.AdapterError):
                adapter.import_feedback(source, root / "learning.json")


if __name__ == "__main__":
    unittest.main()
