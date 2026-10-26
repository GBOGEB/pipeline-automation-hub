#!/usr/bin/env python3
"""Keep the committed W3 receipts equal to what the engines produce from the committed inputs.

Root cause this guards (found N+12): both receipts were persisted on 2026-09-12 from the
first 3 telemetry rows / 0 BT pairs; the inputs were extended minutes later (5 rows, 2
measured pairs) and nothing regenerated or compared the committed files. CI kept producing
fresh receipts as artifacts while the repository, burndown and registry quoted the old ones.

  --check  (CI): regenerate in memory with the owner engines and fail with a field diff when
           a committed receipt is stale. `ci_proof` is provenance, not engine output, and is
           excluded from the comparison.
  --write  : rewrite the committed receipts from the engines, keeping or replacing ci_proof.

Engines are imported, never copied: w3_analytics.analyze() and w3_bt_gate.build_receipt().
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w3_analytics  # noqa: E402
import w3_bt_gate  # noqa: E402

PAIRS = {
    "w3_measured_analytics_receipt.json": ("w3_fleet_telemetry.json", lambda doc: w3_analytics.analyze(doc)),
    "w3_observed_bt_receipt.json": ("w3_bt_observations.json", lambda doc: w3_bt_gate.build_receipt(doc)[0]),
}
PROVENANCE = ("ci_proof",)
SIG = 10  # significant digits: platform libm may differ in the last ulp


def canon(x):
    if isinstance(x, float):
        return float(f"{x:.{SIG}g}")
    if isinstance(x, dict):
        return {k: canon(v) for k, v in x.items()}
    if isinstance(x, list):
        return [canon(v) for v in x]
    return x


def diff(a, b, path="$", out=None, limit=20):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: missing in committed")
            elif k not in b:
                out.append(f"{path}.{k}: not produced by engine")
            else:
                diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: committed={json.dumps(a)[:80]} engine={json.dumps(b)[:80]}")
    return out


def fresh(root: Path, receipt: str) -> dict:
    src, fn = PAIRS[receipt]
    return fn(json.loads((root / src).read_text(encoding="utf-8")))


def check(root: Path) -> dict:
    report = {}
    for receipt in PAIRS:
        committed = json.loads((root / receipt).read_text(encoding="utf-8"))
        body = {k: v for k, v in committed.items() if k not in PROVENANCE}
        d = diff(canon(body), canon(fresh(root, receipt)))
        report[receipt] = {"state": "CURRENT" if not d else "STALE", "diff": d,
                           "has_ci_proof": "ci_proof" in committed}
    return report


def write(root: Path, ci_proof: dict | None) -> list:
    written = []
    for receipt in PAIRS:
        path = root / receipt
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        new = fresh(root, receipt)
        proof = ci_proof if ci_proof is not None else old.get("ci_proof")
        if proof is not None:
            new["ci_proof"] = proof
        path.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(receipt)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=HERE)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--ci-proof", help="JSON object to bind as ci_proof when writing")
    a = ap.parse_args(argv)
    if a.write:
        print(json.dumps({"written": write(a.root, json.loads(a.ci_proof) if a.ci_proof else None)}))
        return 0
    rep = check(a.root)
    for name, r in rep.items():
        print(f"{name}: {r['state']}")
        for line in r["diff"]:
            print(f"  {line}")
        if r["state"] == "STALE":
            print(f"::error title=W3 receipt stale::{name} differs from engine output on committed inputs; "
                  f"run: python mission-control/qps-triage-ultra/w3_receipt_sync.py --write")
    return 0 if all(r["state"] == "CURRENT" for r in rep.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
