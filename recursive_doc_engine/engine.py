from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_line(line: str) -> str:
    stripped = line.lstrip()
    if not stripped.strip():
        return "blank"
    if stripped.startswith("#"):
        return "heading"
    if stripped.startswith(("- ", "* ", "+ ")):
        return "list_item"
    return "text"


def parse_master(text: str) -> list[dict]:
    """Preserve every source line as one traceable KE_BLOCK."""
    blocks = []
    for index, line in enumerate(text.splitlines(keepends=True), start=1):
        blocks.append(
            {
                "id": f"KE-{index:05d}",
                "sequence": index,
                "kind": classify_line(line),
                "content": line,
                "content_sha256": sha256_text(line),
            }
        )
    if text and not blocks:
        blocks.append(
            {
                "id": "KE-00001",
                "sequence": 1,
                "kind": "text",
                "content": text,
                "content_sha256": sha256_text(text),
            }
        )
    return blocks


def rebuild_master(blocks: Iterable[dict]) -> str:
    ordered = sorted(blocks, key=lambda item: int(item["sequence"]))
    return "".join(str(item["content"]) for item in ordered)


def build_candidate(master_text: str) -> tuple[list[dict], str, dict]:
    blocks = parse_master(master_text)
    candidate = rebuild_master(blocks)
    source_sha = sha256_text(master_text)
    candidate_sha = sha256_text(candidate)
    cd = {
        "schema": "recursive_doc_engine.cd.v1",
        "process": "MASTER_TO_KE_BLOCKS_TO_CANDIDATE_ROUNDTRIP",
        "source": {"kind": "MASTER", "sha256": source_sha},
        "candidate": {"kind": "CANDIDATE", "sha256": candidate_sha},
        "metrics": {
            "block_count": len(blocks),
            "roundtrip_exact": candidate == master_text,
            "sha256_equal": source_sha == candidate_sha,
            "traceability_ratio": 1.0 if blocks or not master_text else 0.0,
        },
        "feedback": {
            "mode": "nurturing_fidelity",
            "next_action": "CONTROL" if candidate == master_text else "IMPROVE",
        },
    }
    return blocks, candidate, cd


def write_run(master_path: Path, out_dir: Path) -> dict:
    master_text = master_path.read_text(encoding="utf-8")
    blocks, candidate, cd = build_candidate(master_text)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ke_blocks.json").write_text(json.dumps(blocks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "candidate.md").write_text(candidate, encoding="utf-8")
    (out_dir / "cd.json").write_text(json.dumps(cd, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cd


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic MASTER <-> KE_BLOCK round-trip.")
    parser.add_argument("master", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cd = write_run(args.master, args.out)
    print(json.dumps(cd, sort_keys=True))
    return 0 if cd["metrics"]["roundtrip_exact"] and cd["metrics"]["sha256_equal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
