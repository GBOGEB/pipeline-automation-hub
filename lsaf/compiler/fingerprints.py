"""Semantic fingerprint helpers for LSAF recurrence experiments."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_FIELDS = (
    "repo_class",
    "workflow",
    "job",
    "failure_signature",
    "changed_component",
    "topic",
    "predicate",
)


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text.strip().lower())


def fingerprint_components(record: dict[str, Any]) -> dict[str, str]:
    return {key: normalize_text(record.get(key)) for key in _FIELDS}


def semantic_fingerprint(record: dict[str, Any]) -> str:
    components = fingerprint_components(record)
    raw = json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def occurrence_ledger(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[str]] = {}
    for index, record in enumerate(records):
        fp = semantic_fingerprint(record)
        occurrence_id = str(record.get("occurrence_id") or f"occurrence-{index + 1:04d}")
        buckets.setdefault(fp, []).append(occurrence_id)
    return [
        {
            "fingerprint": fp,
            "occurrence_count": len(sorted(ids)),
            "occurrences": sorted(ids),
            "maturity": "RECURRING" if len(ids) >= 2 else "OBSERVED",
        }
        for fp, ids in sorted(buckets.items())
    ]
