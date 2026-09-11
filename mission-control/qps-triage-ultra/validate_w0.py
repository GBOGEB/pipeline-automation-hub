#!/usr/bin/env python3
"""Dependency-free QPS TRIAGE ULTRA W0 structural validator."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "mission-control" / "qps-triage-ultra"
REQUIRED = [
    "README.md", "architecture.yaml", "mission_registry.yaml",
    "resource_policy.yaml", "metric_registry.yaml", "pulse_ledger.yaml",
]

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

def main() -> int:
    missing = [name for name in REQUIRED if not (BASE / name).is_file()]
    text = "\n".join((BASE / name).read_text(encoding="utf-8") for name in REQUIRED if (BASE / name).is_file())
    invariants = {
        "authority_transfer_false": "authority_transfer: false" in text or "authority_transfer=false" in text,
        "coverage_floor_present": "coverage_floor" in text,
        "pca_measured_only": "MEASURED_NUMERIC_ONLY" in text,
        "bt_pairwise_only": "EXPLICIT_PAIRWISE_OUTCOMES_ONLY" in text,
        "active_M01": "M01:" in text,
        "active_M02A": "M02A:" in text,
        "active_M02B": "M02B:" in text,
    }
    ok = not missing and all(invariants.values())
    receipt = {
        "schema": "qps-triage-ultra-w0-receipt/v1",
        "status": "PASS" if ok else "FAIL",
        "head_sha": head(),
        "required_files": len(REQUIRED),
        "missing": missing,
        "invariants": invariants,
        "digests": {name: sha256(BASE / name) for name in REQUIRED if (BASE / name).is_file()},
        "authority_transfer": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
