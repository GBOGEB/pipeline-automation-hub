#!/usr/bin/env python3
"""Regression probe for the bounded M09 legacy PPTX metadata processor.

The original truth probe proved that invalid bytes with a .pptx suffix were
accepted and that filename heuristics were presented too strongly. This repair
probe preserves that historical finding while asserting the improved boundary:
invalid packages are rejected, minimally valid OpenXML packages are accepted,
and output remains explicitly metadata-only rather than document truth.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSOR_PATH = REPO_ROOT / "scripts" / "ppt_processor.py"


def load_processor_module():
    spec = importlib.util.spec_from_file_location("legacy_ppt_processor", PROCESSOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load legacy PPT processor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def run_probe() -> dict[str, object]:
    module = load_processor_module()
    with tempfile.TemporaryDirectory(prefix="qps-m09-repair-") as tmp:
        root = Path(tmp)
        input_dir = root / "input"
        output_dir = root / "output"
        input_dir.mkdir()
        processor = module.PPTProcessor(str(input_dir), str(output_dir))

        invalid = input_dir / "QPLANT_Status.pptx"
        invalid.write_bytes(b"THIS IS NOT A PPTX FILE\n")
        invalid_rejected = False
        invalid_error = None
        try:
            processor.process_file(invalid.name)
        except Exception as exc:
            invalid_rejected = True
            invalid_error = str(exc)

        valid = input_dir / "QPLANT_Status_Valid.pptx"
        write_minimal_pptx(valid)
        result = processor.process_file(valid.name)

        metadata_path = output_dir / "metadata" / "QPLANT_Status_Valid_metadata.json"
        refs_path = output_dir / "cross_references" / "QPLANT_Status_Valid_cross_refs.json"
        twin_path = output_dir / "digital_twins" / "QPLANT_Status_Valid.md"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
        twin = twin_path.read_text(encoding="utf-8")
        source_text = PROCESSOR_PATH.read_text(encoding="utf-8")

        findings = {
            "invalid_pptx_rejected_fail_closed": invalid_rejected,
            "valid_openxml_package_accepted": result["processing_status"] == "METADATA_ONLY_COMPLETED",
            "valid_package_marked_content_not_parsed": result["content_parsed"] is False and metadata.get("content_parsed") is False,
            "filename_reference_is_unverified_candidate": any(
                r.get("reference") == "SCK CEN/0789"
                and r.get("type") == "heuristic_candidate"
                and r.get("authority") == "UNVERIFIED_CANDIDATE"
                for r in refs
            ),
            "twin_declares_metadata_only_boundary": "METADATA_ONLY_NOT_DOCUMENT_TRUTH" in twin and "NOT PARSED" in twin,
            "legacy_home_ubuntu_path_removed": "/home/ubuntu/pipeline_automation_app" not in source_text,
            "pptx_package_validation_recorded": metadata.get("pptx_package_validated") is True,
        }
        assert all(findings.values()), {"findings": findings, "invalid_error": invalid_error}

        return {
            "schema": "qps.m09.legacy_processor_repair_probe.v2",
            "status": "PASS_FAIL_CLOSED_METADATA_ONLY_REPAIR",
            "processor": str(PROCESSOR_PATH.relative_to(REPO_ROOT)),
            "historical_first_red": "INVALID_NON_ZIP_PPTX_WAS_ACCEPTED_AND_FILENAME_HEURISTICS_OVERCLAIMED",
            "invalid_fixture_error": invalid_error,
            "findings": findings,
            "classification": "BOUNDED_PPTX_PACKAGE_METADATA_AND_TEMPLATE_TWIN_GENERATOR",
            "still_not_proven": [
                "PPTX_slide_content_parsing",
                "content_derived_cross_reference_extraction",
                "visual_artifact_detection",
                "PDF_engine_execution",
                "Markdown_engine_content_fidelity",
            ],
            "reusable_candidates": [
                "fail_closed_package_intake",
                "file_hashing",
                "output_directory_partitioning",
                "manifest_metadata_shape",
                "pipeline_stage_orchestration_pattern",
            ],
            "authority": "OBSERVATION_ONLY_NO_ENGINEERING_OR_DOCUMENT_TRUTH_TRANSFER",
        }


def main() -> None:
    print(json.dumps(run_probe(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
