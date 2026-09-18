from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_processing.py"
SPEC = importlib.util.spec_from_file_location("run_processing_recursive_integration", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class RunProcessingRecursiveIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tmp.name) / "outputs"
        self.input_dir = Path(self.tmp.name) / "input"
        self.output_dir.mkdir()
        self.input_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def make_phase_receipts(self):
        summary = {
            "processing_scope": "METADATA_ONLY",
            "total_files": 2,
            "successful": 2,
            "failed": 0,
            "cross_references_global": [],
        }
        summary_path = self.output_dir / "processing_summary.json"
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        recursive_dir = self.output_dir / "recursive_build"
        recursive_dir.mkdir()
        recursive = {
            "schema": "recursive_build.receipt.v1",
            "generated_at": "2026-09-18T16:00:00Z",
            "authority": MOD.AUTHORITY,
            "record_count": 2,
            "status": "PASS",
        }
        recursive_path = recursive_dir / "build_receipt.json"
        recursive_path.write_text(json.dumps(recursive), encoding="utf-8")
        return summary_path, recursive_path

    def test_pipeline_receipt_hash_binds_both_phases(self):
        summary_path, recursive_path = self.make_phase_receipts()
        target = MOD.write_pipeline_receipt(self.output_dir, recursive_path)
        self.assertIsNotNone(target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["authority"], MOD.AUTHORITY)
        self.assertEqual(payload["phases"]["metadata"]["sha256"], MOD.sha256_file(summary_path))
        self.assertEqual(
            payload["phases"]["recursive_build"]["sha256"],
            MOD.sha256_file(recursive_path),
        )
        self.assertIn("do not create", payload["authority_guardrail"])

    def test_recursive_build_invokes_canonical_master(self):
        _, recursive_path = self.make_phase_receipts()
        completed = SimpleNamespace(returncode=0, stdout=str(recursive_path), stderr="")
        with patch.object(MOD.subprocess, "run", return_value=completed) as run:
            result = MOD.run_recursive_build(self.output_dir)
        self.assertEqual(result, recursive_path)
        command = run.call_args.args[0]
        self.assertIn("Recursive_Build_Master.py", command[1])
        self.assertEqual(command[-1], str(self.output_dir))

    def test_main_runs_recursive_only_after_metadata_passes(self):
        _, recursive_path = self.make_phase_receipts()
        args = argparse.Namespace(input_dir=str(self.input_dir), output_dir=str(self.output_dir))
        pipeline_receipt = self.output_dir / "pipeline_run_receipt.json"
        pipeline_receipt.write_text("{}", encoding="utf-8")
        with (
            patch.object(MOD, "parse_args", return_value=args),
            patch.object(MOD, "run_ppt_processing", return_value=True) as ppt,
            patch.object(MOD, "summarize", return_value=True) as summary,
            patch.object(MOD, "run_recursive_build", return_value=recursive_path) as recursive,
            patch.object(MOD, "write_pipeline_receipt", return_value=pipeline_receipt) as receipt,
        ):
            rc = MOD.main()
        self.assertEqual(rc, 0)
        ppt.assert_called_once()
        summary.assert_called_once()
        recursive.assert_called_once_with(self.output_dir)
        receipt.assert_called_once_with(self.output_dir, recursive_path)

    def test_main_stops_before_recursive_when_metadata_summary_fails(self):
        args = argparse.Namespace(input_dir=str(self.input_dir), output_dir=str(self.output_dir))
        with (
            patch.object(MOD, "parse_args", return_value=args),
            patch.object(MOD, "run_ppt_processing", return_value=True),
            patch.object(MOD, "summarize", return_value=False),
            patch.object(MOD, "run_recursive_build") as recursive,
        ):
            rc = MOD.main()
        self.assertEqual(rc, 3)
        recursive.assert_not_called()


if __name__ == "__main__":
    unittest.main()
