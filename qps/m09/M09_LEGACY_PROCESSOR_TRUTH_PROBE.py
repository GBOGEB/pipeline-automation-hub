#!/usr/bin/env python3
"""Truth probe for the legacy Pipeline Automation Hub PPT processor.

This does not modify the legacy processor. It measures what the current code
actually does so QPS can distinguish reusable metadata/orchestration patterns
from claims of PPTX content extraction.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
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


def run_probe() -> dict[str, object]:
    module = load_processor_module()
    with tempfile.TemporaryDirectory(prefix="qps-m09-") as tmp:
        root = Path(tmp)
        input_dir = root / "input"
        output_dir = root / "output"
        input_dir.mkdir()

        # Deliberately not a valid PPTX/ZIP package. A real PPT content parser
        # should reject this as content input; the current legacy implementation
        # only hashes and classifies the filename.
        fake = input_dir / "QPLANT_Status.pptx"
        fake.write_bytes(b"THIS IS NOT A PPTX FILE\n")

        processor = module.PPTProcessor(str(input_dir), str(output_dir))
        result = processor.process_file(fake.name)

        metadata_path = output_dir / "metadata" / "QPLANT_Status_metadata.json"
        refs_path = output_dir / "cross_references" / "QPLANT_Status_cross_refs.json"
        twin_path = output_dir / "digital_twins" / "QPLANT_Status.md"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
        twin = twin_path.read_text(encoding="utf-8")

        findings = {
            "invalid_pptx_accepted_as_completed": result["processing_status"] == "COMPLETED",
            "digital_twin_claimed_for_invalid_pptx": result["digital_twin_generated"] is True,
            "filename_drives_category": metadata.get("category") == "PROJECT_STATUS",
            "filename_drives_qplant_reference": any(r.get("reference") == "SCK CEN/0789" for r in refs),
            "twin_contains_placeholder_content_analysis": "Detection pending" in twin and "Scanning scheduled" in twin,
            "legacy_main_hardcodes_home_ubuntu": "/home/ubuntu/pipeline_automation_app" in PROCESSOR_PATH.read_text(encoding="utf-8"),
        }
        assert all(findings.values()), findings

        return {
            "schema": "qps.m09.legacy_processor_truth_probe.v1",
            "status": "PASS_PROBE_CONFIRMS_METADATA_HEURISTIC_ONLY_BOUNDARY",
            "processor": str(PROCESSOR_PATH.relative_to(REPO_ROOT)),
            "synthetic_fixture": "invalid_non_zip_bytes_with_pptx_extension",
            "findings": findings,
            "classification": "LEGACY_FILENAME_METADATA_AND_TEMPLATE_TWIN_GENERATOR",
            "not_proven": [
                "PPTX_slide_content_parsing",
                "content_derived_cross_reference_extraction",
                "visual_artifact_detection",
                "PDF_engine_execution",
                "Markdown_engine_content_fidelity",
            ],
            "reusable_candidates": [
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
