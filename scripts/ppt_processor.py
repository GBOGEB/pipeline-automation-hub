#!/usr/bin/env python3
"""Legacy PowerPoint metadata/twin generator for Pipeline Automation Hub.

QPS M09 boundary:
- validates that input is at least a PPTX/ZIP package before reporting success;
- hashes files and derives *heuristic* metadata/cross-reference candidates from filenames;
- emits a Markdown metadata twin;
- does NOT parse slide text, tables, images, diagrams, or document semantics.

Use a real PPTX content parser/OCR/rendering pipeline for content-derived evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = REPO_ROOT / "app" / "public" / "master_input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "app" / "public" / "outputs"


def _timestamp_now() -> str:
    """Return a reproducible UTC timestamp when SOURCE_DATE_EPOCH is provided."""
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        try:
            return datetime.fromtimestamp(int(source_date_epoch), tz=timezone.utc).isoformat()
        except ValueError as exc:
            raise ValueError("SOURCE_DATE_EPOCH must be an integer Unix timestamp") from exc
    return datetime.now(timezone.utc).isoformat()


class PPTProcessor:
    """Filename-metadata/hash/template-twin generator with fail-closed PPTX intake."""

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.metadata_dir = self.output_dir / "metadata"
        self.twins_dir = self.output_dir / "digital_twins"
        self.cross_refs_dir = self.output_dir / "cross_references"

        for dir_path in [self.metadata_dir, self.twins_dir, self.cross_refs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def validate_pptx_package(self, filepath: Path) -> None:
        """Reject renamed/non-PPTX bytes before any COMPLETED result is emitted."""
        if filepath.suffix.lower() != ".pptx":
            raise ValueError(f"not a .pptx file: {filepath.name}")
        if not filepath.is_file():
            raise FileNotFoundError(filepath)
        if not zipfile.is_zipfile(filepath):
            raise ValueError(f"invalid PPTX package (not ZIP/OpenXML): {filepath.name}")
        with zipfile.ZipFile(filepath) as archive:
            names = set(archive.namelist())
        required = {"[Content_Types].xml", "ppt/presentation.xml"}
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"invalid PPTX package; missing required OpenXML members: {missing}")

    def extract_filename_metadata(self, filename: str, processing_timestamp: str | None = None) -> Dict[str, Any]:
        """Derive non-authoritative metadata from filename patterns only."""
        metadata: Dict[str, Any] = {
            "original_filename": filename,
            "normalized_name": re.sub(r"[^a-zA-Z0-9._-]", "_", filename),
            "file_type": "PPTX",
            "processing_timestamp": processing_timestamp or _timestamp_now(),
            "file_hash": None,
            "processing_scope": "FILENAME_METADATA_HASH_AND_TEMPLATE_TWIN",
            "content_parsed": False,
            "cross_reference_basis": "FILENAME_HEURISTIC_ONLY",
            "authority": "METADATA_ONLY_NOT_DOCUMENT_TRUTH",
        }

        filename_lower = filename.lower()
        if any(term in filename_lower for term in ["architecture", "minerva"]):
            metadata.update(category="SYSTEM_ARCHITECTURE", priority="HIGH", sub_category="CORE_SYSTEMS")
        elif any(term in filename_lower for term in ["values", "commitments"]):
            metadata.update(category="VALUES_POLICY", priority="HIGH", sub_category="GOVERNANCE")
        elif any(term in filename_lower for term in ["status", "granting", "phase"]):
            metadata.update(category="PROJECT_STATUS", priority="MEDIUM", sub_category="PROGRESS_TRACKING")
        elif any(term in filename_lower for term in ["naming", "conventions"]):
            metadata.update(category="STANDARDS", priority="HIGH", sub_category="DOCUMENTATION")
        elif any(term in filename_lower for term in ["ped", "compliance"]):
            metadata.update(category="COMPLIANCE", priority="CRITICAL", sub_category="REGULATORY")
        elif any(term in filename_lower for term in ["buildings", "qplant"]):
            metadata.update(category="INFRASTRUCTURE", priority="MEDIUM", sub_category="FACILITIES")
        elif any(term in filename_lower for term in ["recovery", "pressure", "he"]):
            metadata.update(category="SYSTEMS", priority="HIGH", sub_category="OPERATIONS")
        else:
            metadata.update(category="GENERAL", priority="MEDIUM", sub_category="MISC")
        return metadata

    def extract_cross_references(self, filename: str) -> List[Dict[str, str]]:
        """Return filename-derived *candidate* references; no file-content parsing occurs."""
        cross_refs: List[Dict[str, str]] = []
        filename_lower = filename.lower()

        def candidate(reference: str, context: str) -> Dict[str, str]:
            return {
                "reference": reference,
                "context": context,
                "type": "heuristic_candidate",
                "evidence_basis": "filename_only",
                "authority": "UNVERIFIED_CANDIDATE",
            }

        if "minerva" in filename_lower or "architecture" in filename_lower:
            cross_refs.append(candidate("SCK CEN/0245", "MINERVA Architecture"))
        if "values" in filename_lower or "commitments" in filename_lower:
            cross_refs.append(candidate("SCK CEN/0156", "Values & Commitments"))
        if "qplant" in filename_lower or "status" in filename_lower:
            cross_refs.append(candidate("SCK CEN/0789", "QPLANT Status"))
        if "naming" in filename_lower or "conventions" in filename_lower:
            cross_refs.append(candidate("SCK CEN/0334", "Naming Conventions"))
        if "ped" in filename_lower or "compliance" in filename_lower:
            cross_refs.append(candidate("SCK CEN/0567", "PED Compliance"))
        return cross_refs

    def generate_file_hash(self, filepath: Path) -> str:
        hash_sha256 = hashlib.sha256()
        with filepath.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def create_digital_twin(self, filename: str, metadata: Dict[str, Any], cross_refs: List[Dict[str, str]]) -> str:
        """Generate an explicitly metadata-only Markdown twin."""
        timestamp = metadata["processing_timestamp"]
        return f"""# {filename.replace('.pptx', '')}

> **Legacy M09 boundary:** this file is a metadata/template twin only. The legacy processor has not parsed slide text, tables, images, diagrams, or document semantics.

## Document Metadata
- **Original Filename**: {filename}
- **Category**: {metadata.get('category', 'UNKNOWN')} *(filename heuristic)*
- **Priority**: {metadata.get('priority', 'MEDIUM')} *(filename heuristic)*
- **Sub-category**: {metadata.get('sub_category', 'GENERAL')} *(filename heuristic)*
- **File Type**: {metadata.get('file_type', 'PPTX')}
- **Processing Date**: {timestamp}
- **File Hash**: {metadata.get('file_hash', 'N/A')}
- **Content Parsed**: false
- **Authority**: METADATA_ONLY_NOT_DOCUMENT_TRUTH

## Candidate Cross-References
{self._format_cross_references(cross_refs)}

## Content Analysis
- Slide text/content: **NOT PARSED by this legacy processor**
- Tables: **NOT PARSED**
- Images/diagrams: **NOT PARSED**
- Visual artifacts: **NOT PARSED**
- PDF conversion: **NOT EXECUTED by this processor**

## Processing Status
- **Status**: METADATA_ONLY_COMPLETED
- **Executed capability**: PPTX package validation → SHA256 → filename metadata → filename heuristic references → Markdown template twin

## KEB Frontend Integration
```json
{{
  "keb_id": "{metadata.get('normalized_name', filename)}",
  "digital_twin": true,
  "content_parsed": false,
  "cross_reference_basis": "filename_heuristic_only",
  "authority": "metadata_only_not_document_truth"
}}
```

## Change Log
- **Created**: {timestamp}
- **Last Modified**: {timestamp}
- **Version**: 1.1.0-m09
- **Generator**: PPT_Processor_legacy_metadata_guard

---
*Metadata-only twin generated by Pipeline Automation Hub legacy processor.*
"""

    def _format_cross_references(self, cross_refs: List[Dict[str, str]]) -> str:
        if not cross_refs:
            return "- No filename-derived candidate references"
        return "\n".join(
            f"- **{ref['reference']}**: {ref['context']} — {ref['type']}, {ref['evidence_basis']}, {ref['authority']}"
            for ref in cross_refs
        )

    def process_file(self, filename: str) -> Dict[str, Any]:
        filepath = self.input_dir / filename
        self.validate_pptx_package(filepath)

        timestamp = _timestamp_now()
        metadata = self.extract_filename_metadata(filename, timestamp)
        metadata["file_hash"] = self.generate_file_hash(filepath)
        metadata["file_size"] = filepath.stat().st_size
        metadata["pptx_package_validated"] = True

        cross_refs = self.extract_cross_references(filename)
        twin_content = self.create_digital_twin(filename, metadata, cross_refs)

        self._save_metadata(filename, metadata)
        self._save_cross_references(filename, cross_refs)
        self._save_digital_twin(filename, twin_content, metadata)

        return {
            "filename": filename,
            "metadata": metadata,
            "cross_references": cross_refs,
            "digital_twin_generated": True,
            "content_parsed": False,
            "processing_status": "METADATA_ONLY_COMPLETED",
        }

    def _save_metadata(self, filename: str, metadata: Dict[str, Any]) -> None:
        output_path = self.metadata_dir / filename.replace(".pptx", "_metadata.json")
        output_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _save_cross_references(self, filename: str, cross_refs: List[Dict[str, str]]) -> None:
        output_path = self.cross_refs_dir / filename.replace(".pptx", "_cross_refs.json")
        output_path.write_text(json.dumps(cross_refs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _save_digital_twin(self, filename: str, content: str, metadata: Dict[str, Any]) -> None:
        md_filename = metadata["normalized_name"].replace(".pptx", ".md")
        (self.twins_dir / md_filename).write_text(content, encoding="utf-8")

    def process_all_files(self) -> Dict[str, Any]:
        started = _timestamp_now()
        results: Dict[str, Any] = {
            "processing_started": started,
            "processing_scope": "LEGACY_METADATA_ONLY",
            "files_processed": [],
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "cross_references_global": [],
            "categories_summary": {},
        }

        pptx_files = list(self.input_dir.glob("*.pptx"))
        results["total_files"] = len(pptx_files)
        categories: Dict[str, int] = {}
        global_refs: set[str] = set()

        for filepath in pptx_files:
            try:
                result = self.process_file(filepath.name)
                results["files_processed"].append(result)
                results["successful"] += 1
                category = result["metadata"].get("category", "UNKNOWN")
                categories[category] = categories.get(category, 0) + 1
                for ref in result["cross_references"]:
                    global_refs.add(ref["reference"])
            except Exception as exc:
                results["failed"] += 1
                results["files_processed"].append(
                    {"filename": filepath.name, "error": str(exc), "processing_status": "REJECTED_OR_FAILED"}
                )

        results["categories_summary"] = categories
        results["cross_references_global"] = sorted(global_refs)
        results["processing_completed"] = _timestamp_now()
        (self.output_dir / "processing_summary.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Legacy metadata-only PPTX processing surface")
    parser.add_argument(
        "--input-dir",
        default=os.environ.get("PIPELINE_INPUT_DIR", str(DEFAULT_INPUT_DIR)),
        help="PPTX input directory (default: repo app/public/master_input or PIPELINE_INPUT_DIR)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("PIPELINE_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Output directory (default: repo app/public/outputs or PIPELINE_OUTPUT_DIR)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    processor = PPTProcessor(args.input_dir, args.output_dir)
    print("Starting legacy metadata-only PPTX processor...")
    results = processor.process_all_files()
    print(json.dumps({
        "scope": results["processing_scope"],
        "total_files": results["total_files"],
        "successful": results["successful"],
        "failed": results["failed"],
        "output_dir": str(Path(args.output_dir).resolve()),
    }, indent=2))
    return 0 if results["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
