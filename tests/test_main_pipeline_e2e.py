from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_processing.py"
AUTHORITY = "METADATA_ONLY_NOT_DOCUMENT_TRUTH"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_minimal_pptx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '</Types>',
        )
        archive.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )


def write_schedule_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan"
    ws.append(["Task", "Start Date", "Status"])
    ws.append(["Build", "2026-09-18", "Open"])
    wb.save(path)


class MainPipelineEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="main-pipeline-e2e-")
        self.root = Path(self.tmp.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()
        self.env = os.environ.copy()
        self.env["SOURCE_DATE_EPOCH"] = "1790262000"

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--input-dir",
                str(self.input_dir),
                "--output-dir",
                str(self.output_dir),
                *extra_args,
            ],
            cwd=REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_valid_pptx_runs_real_two_phase_pipeline_and_hash_binds_receipts(self):
        write_minimal_pptx(self.input_dir / "QPLANT_Status_Valid.pptx")

        result = self.run_main()
        self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

        summary_path = self.output_dir / "processing_summary.json"
        recursive_path = self.output_dir / "recursive_build" / "build_receipt.json"
        pipeline_path = self.output_dir / "pipeline_run_receipt.json"

        self.assertTrue(summary_path.exists())
        self.assertTrue(recursive_path.exists())
        self.assertTrue(pipeline_path.exists())

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        recursive = json.loads(recursive_path.read_text(encoding="utf-8"))
        pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["successful"], 1)
        self.assertTrue(recursive["status"].startswith("PASS"))
        self.assertEqual(recursive["record_count"], 1)

        self.assertEqual(pipeline["schema"], "pipeline_automation_hub.pipeline_run_receipt.v3")
        self.assertEqual(pipeline["status"], "PASS")
        self.assertEqual(pipeline["authority"], AUTHORITY)
        self.assertEqual(pipeline["phases"]["metadata"]["sha256"], sha256_file(summary_path))
        self.assertEqual(pipeline["phases"]["recursive_build"]["sha256"], sha256_file(recursive_path))
        self.assertEqual(pipeline["phases"]["excel_schedule"]["status"], "NOT_REQUESTED")
        self.assertIn("do not create", pipeline["authority_guardrail"])

    def test_invalid_renamed_pptx_fails_before_recursive_or_joined_receipt(self):
        (self.input_dir / "QPLANT_Status_Invalid.pptx").write_bytes(
            b"THIS IS NOT A PPTX FILE\n"
        )

        result = self.run_main()
        self.assertEqual(result.returncode, 2, msg=result.stdout + "\n" + result.stderr)

        summary_path = self.output_dir / "processing_summary.json"
        self.assertTrue(summary_path.exists())
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["successful"], 0)

        self.assertFalse((self.output_dir / "recursive_build" / "build_receipt.json").exists())
        self.assertFalse((self.output_dir / "pipeline_run_receipt.json").exists())

    def test_valid_pptx_plus_excel_runs_real_three_phase_pipeline(self):
        write_minimal_pptx(self.input_dir / "Architecture_MINERVA.pptx")
        workbook = self.root / "MASTER.xlsx"
        excel_root = self.root / "excel_root"
        write_schedule_workbook(workbook)

        result = self.run_main(
            "--excel-input",
            str(workbook),
            "--excel-output-root",
            str(excel_root),
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

        pipeline_path = self.output_dir / "pipeline_run_receipt.json"
        manifest_path = excel_root / "Outputs" / "excel" / "table_manifest.json"
        schedule_manifest_path = (
            excel_root / "Outputs" / "excel" / "schedule" / "schedule_manifest.json"
        )
        self.assertTrue(pipeline_path.exists())
        self.assertTrue(manifest_path.exists())
        self.assertTrue(schedule_manifest_path.exists())

        pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        excel_phase = pipeline["phases"]["excel_schedule"]

        self.assertEqual(pipeline["status"], "PASS")
        self.assertEqual(excel_phase["status"], "PASS")
        self.assertTrue(excel_phase["requested"])
        self.assertEqual(excel_phase["sha256"], sha256_file(manifest_path))
        projection = excel_phase["schedule_projection"]
        self.assertEqual(projection["status"], "PASS")
        self.assertEqual(
            projection["sha256"],
            sha256_file(schedule_manifest_path),
        )
        self.assertFalse(projection["authority_transfer"])
        self.assertEqual(manifest["summary"]["errors"], 0)
        self.assertGreaterEqual(manifest["summary"]["tables_exported"], 1)
        self.assertGreaterEqual(manifest["summary"]["schedule_candidates"], 1)
        self.assertFalse(manifest["authority"]["authority_transfer"])

        csv_dir = excel_root / "Outputs" / "excel" / "tables_csv"
        xlsx_dir = excel_root / "Outputs" / "excel" / "tables_xlsx"
        self.assertTrue(any(csv_dir.glob("*.csv")))
        self.assertTrue(any(xlsx_dir.glob("*.xlsx")))


if __name__ == "__main__":
    unittest.main()
