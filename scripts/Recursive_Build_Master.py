#!/usr/bin/env python3
"""Deterministic recursive-build master for the Pipeline Automation Hub.

This module indexes bounded metadata outputs. It does not promote metadata,
filename-derived references, or rankings into engineering/document truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

PRIORITY_SCORE = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.2}
AUTHORITY = "METADATA_ONLY_NOT_DOCUMENT_TRUTH"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_date_epoch() -> int | None:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer Unix timestamp") from exc


def deterministic_timestamp(explicit: str | None = None) -> str:
    if explicit:
        parsed = datetime.fromisoformat(explicit.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    epoch = source_date_epoch()
    if epoch is None:
        epoch = int(time.time())
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def write_simple_yaml(path: Path, mapping: Mapping[str, Any]) -> None:
    lines = [f"{key}: {yaml_scalar(value)}" for key, value in mapping.items()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ArtefactRecord:
    original_filename: str
    normalized_name: str
    category: str
    priority: str
    processing_timestamp: str
    source_metadata_path: str
    source_metadata_sha256: str
    file_hash: str
    reference_count: int
    relevance_score: float
    rank: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "original_filename": self.original_filename,
            "normalized_name": self.normalized_name,
            "category": self.category,
            "priority": self.priority,
            "processing_timestamp": self.processing_timestamp,
            "source_metadata_path": self.source_metadata_path,
            "source_metadata_sha256": self.source_metadata_sha256,
            "file_hash": self.file_hash,
            "reference_count": self.reference_count,
            "relevance_score": self.relevance_score,
            "rank": self.rank,
            "authority": AUTHORITY,
        }


class RecursiveBuildMaster:
    def __init__(self, outputs_dir: Path, generated_at: str | None = None, top_n: int = 30):
        self.outputs_dir = outputs_dir.resolve()
        self.metadata_dir = self.outputs_dir / "metadata"
        self.cross_refs_dir = self.outputs_dir / "cross_references"
        self.twins_dir = self.outputs_dir / "digital_twins"
        self.build_dir = self.outputs_dir / "recursive_build"
        self.lineage_dir = self.build_dir / ".buildlog"
        self.generated_at = deterministic_timestamp(generated_at)
        self.top_n = max(1, top_n)

    def load_metadata(self) -> List[tuple[Path, Dict[str, Any]]]:
        records: List[tuple[Path, Dict[str, Any]]] = []
        for path in sorted(self.metadata_dir.glob("*_metadata.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append((path, data))
        return records

    def reference_count(self, metadata: Mapping[str, Any]) -> int:
        refs = metadata.get("cross_references")
        if isinstance(refs, list):
            return len(refs)
        base = Path(str(metadata.get("normalized_name") or metadata.get("original_filename") or "")).stem
        candidate = self.cross_refs_dir / f"{base}_cross_refs.json"
        if not candidate.exists():
            return 0
        data = json.loads(candidate.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else 0

    def score(self, metadata: Mapping[str, Any], refs: int) -> float:
        priority = PRIORITY_SCORE.get(str(metadata.get("priority", "MEDIUM")).upper(), 0.5)
        ref_signal = min(refs, 10) / 10.0
        hash_signal = 1.0 if metadata.get("file_hash") else 0.0
        # Static, explainable score: priority dominates; linkage and identity are secondary.
        return round((0.70 * priority) + (0.20 * ref_signal) + (0.10 * hash_signal), 6)

    def make_records(self) -> List[ArtefactRecord]:
        provisional: List[ArtefactRecord] = []
        for path, metadata in self.load_metadata():
            original = str(metadata.get("original_filename") or path.stem)
            normalized = str(metadata.get("normalized_name") or original)
            refs = self.reference_count(metadata)
            provisional.append(
                ArtefactRecord(
                    original_filename=original,
                    normalized_name=normalized,
                    category=str(metadata.get("category", "UNKNOWN")),
                    priority=str(metadata.get("priority", "MEDIUM")).upper(),
                    processing_timestamp=str(metadata.get("processing_timestamp", "")),
                    source_metadata_path=str(path.relative_to(self.outputs_dir)),
                    source_metadata_sha256=sha256_file(path),
                    file_hash=str(metadata.get("file_hash", "")),
                    reference_count=refs,
                    relevance_score=self.score(metadata, refs),
                )
            )
        provisional.sort(key=lambda item: (-item.relevance_score, item.original_filename.lower()))
        return [
            ArtefactRecord(**{**record.__dict__, "rank": rank})
            for rank, record in enumerate(provisional, start=1)
        ]

    def write_artefact_logs(self, records: Sequence[ArtefactRecord]) -> None:
        for record in records:
            target = self.lineage_dir / slug(record.original_filename) / "artefact_id.yaml"
            write_simple_yaml(
                target,
                {
                    "schema": "recursive_build.artefact_id.v1",
                    "artefact": record.original_filename,
                    "normalized_name": record.normalized_name,
                    "category": record.category,
                    "priority": record.priority,
                    "rank": record.rank,
                    "relevance_score": record.relevance_score,
                    "source_metadata_path": record.source_metadata_path,
                    "source_metadata_sha256": record.source_metadata_sha256,
                    "source_file_hash": record.file_hash,
                    "reference_count": record.reference_count,
                    "generated_at": self.generated_at,
                    "authority": AUTHORITY,
                },
            )

    def write_index_json(self, records: Sequence[ArtefactRecord]) -> Path:
        target = self.build_dir / "index.json"
        payload = {
            "schema": "recursive_build.index.v1",
            "generated_at": self.generated_at,
            "authority": AUTHORITY,
            "ranking_method": "0.70*priority + 0.20*bounded_reference_density + 0.10*hash_presence",
            "total": len(records),
            "records": [record.as_dict() for record in records],
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def write_top_index(self, records: Sequence[ArtefactRecord]) -> Path:
        target = self.build_dir / "index_top30.md"
        lines = [
            "# Recursive Build — Top Artefacts",
            "",
            f"Generated: {self.generated_at}",
            f"Authority: `{AUTHORITY}`",
            "",
            "| Rank | Score | Priority | Category | Artefact |",
            "|---:|---:|---|---|---|",
        ]
        for record in records[: self.top_n]:
            lines.append(
                f"| {record.rank} | {record.relevance_score:.3f} | {record.priority} | "
                f"{record.category} | {record.original_filename} |"
            )
        lines.extend(
            [
                "",
                "> Ranking is a workflow relevance heuristic only. It grants no engineering, compliance, procurement, or acceptance credit.",
                "",
            ]
        )
        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def write_master_index(self, records: Sequence[ArtefactRecord]) -> Path:
        target = self.build_dir / "master_index.md"
        categories: Dict[str, int] = {}
        for record in records:
            categories[record.category] = categories.get(record.category, 0) + 1
        lines = [
            "# Master Index — Recursive Build Ecosystem",
            "",
            f"Generated: {self.generated_at}",
            f"Total artefacts: {len(records)}",
            f"Authority: `{AUTHORITY}`",
            "",
            "## Categories",
        ]
        for category, count in sorted(categories.items()):
            lines.append(f"- **{category}**: {count}")
        lines.extend(["", "## Ranked artefacts", ""])
        for record in records:
            twin = Path(record.normalized_name).with_suffix(".md").name
            lines.append(
                f"{record.rank}. **{record.original_filename}** — score {record.relevance_score:.3f}; "
                f"priority {record.priority}; [digital twin](../digital_twins/{twin})"
            )
        lines.extend(["", "---", "*Generated by Recursive_Build_Master.py*", ""])
        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def write_receipt(self, records: Sequence[ArtefactRecord], outputs: Iterable[Path]) -> Path:
        target = self.build_dir / "build_receipt.json"
        output_map = {}
        for path in outputs:
            output_map[str(path.relative_to(self.outputs_dir))] = sha256_file(path)
        payload = {
            "schema": "recursive_build.receipt.v1",
            "generated_at": self.generated_at,
            "authority": AUTHORITY,
            "record_count": len(records),
            "top_n": self.top_n,
            "outputs": output_map,
            "status": "PASS" if records else "PASS_EMPTY_INPUT",
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def build(self) -> Path:
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.lineage_dir.mkdir(parents=True, exist_ok=True)
        records = self.make_records()
        self.write_artefact_logs(records)
        outputs = [
            self.write_index_json(records),
            self.write_top_index(records),
            self.write_master_index(records),
        ]
        return self.write_receipt(records, outputs)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    default_outputs = repo_root / "app" / "public" / "outputs"
    parser = argparse.ArgumentParser(description="Deterministic recursive-build index and lineage generator")
    parser.add_argument(
        "--outputs-dir",
        default=os.environ.get("PIPELINE_OUTPUT_DIR", str(default_outputs)),
        help="Pipeline outputs directory",
    )
    parser.add_argument("--generated-at", help="Explicit ISO-8601 timestamp; otherwise SOURCE_DATE_EPOCH/current time")
    parser.add_argument("--top-n", type=int, default=30, help="Human ranked-index depth")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = RecursiveBuildMaster(Path(args.outputs_dir), args.generated_at, args.top_n).build()
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
