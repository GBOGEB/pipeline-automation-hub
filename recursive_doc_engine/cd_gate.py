from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gate(run_dir: Path) -> dict:
    required = ["candidate.md", "ke_blocks.json", "cd.json"]
    missing = [name for name in required if not (run_dir / name).is_file()]
    reasons: list[str] = []
    if missing:
        reasons.append("missing_required:" + ",".join(sorted(missing)))
        return {"schema": "recursive_doc_engine.cd_gate.v1", "passed": False, "reasons": reasons}

    cd = json.loads((run_dir / "cd.json").read_text(encoding="utf-8"))
    metrics = cd.get("metrics", {})
    candidate_sha = file_sha256(run_dir / "candidate.md")
    expected_candidate_sha = cd.get("candidate", {}).get("sha256")

    checks = {
        "roundtrip_exact": metrics.get("roundtrip_exact") is True,
        "sha256_equal": metrics.get("sha256_equal") is True,
        "candidate_hash_bound": candidate_sha == expected_candidate_sha,
        "traceability_ratio": float(metrics.get("traceability_ratio", 0.0)) >= 1.0,
    }
    for name, passed in checks.items():
        if not passed:
            reasons.append(name)

    return {
        "schema": "recursive_doc_engine.cd_gate.v1",
        "passed": not reasons,
        "checks": checks,
        "reasons": reasons,
        "candidate_sha256": candidate_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a recursive document round-trip run directory.")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    result = gate(args.run_dir)
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
