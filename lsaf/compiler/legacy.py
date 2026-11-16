"""Lossless import of the earlier four-artifact handover shape.

The importer deliberately preserves the complete legacy payload. Normalized fields
are additive views; callers can round-trip the original data at the Python value
level without trusting the normalized projection.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def import_v1(*, state: dict[str, Any], manifest: dict[str, Any], handover: str, dropin: str) -> dict[str, Any]:
    payload = {
        "state": deepcopy(state),
        "manifest": deepcopy(manifest),
        "handover": handover,
        "dropin": dropin,
    }
    return {
        "schema": "lsaf/legacy-import/v0.1",
        "source_schema": "lossless-handover/v1",
        "evidence_class": "SOURCE",
        "authority_transfer": False,
        "legacy_payload": payload,
        "source_hashes": {k: _digest(v) for k, v in payload.items()},
        "normalized": {
            "state": deepcopy(state),
            "manifest": deepcopy(manifest),
            "handover_present": bool(handover),
            "dropin_present": bool(dropin),
        },
    }


def roundtrip_v1(imported: dict[str, Any]) -> dict[str, Any]:
    payload = imported.get("legacy_payload")
    if not isinstance(payload, dict):
        raise ValueError("legacy_payload missing")
    return deepcopy(payload)
