#!/usr/bin/env python3
"""Inject governed build identity into the QPS Jekyll publication surface."""
from __future__ import annotations

import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_data" / "qps_build.yml"


def git_sha() -> str:
    env_sha = os.getenv("GITHUB_SHA") or os.getenv("QPS_SOURCE_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "UNBOUND"


def main() -> int:
    source_sha = git_sha()
    release_id = os.getenv("QPS_RELEASE_ID", f"qps-web-{source_sha[:12] if source_sha != 'UNBOUND' else 'unbound'}")
    evidence_state = os.getenv("QPS_EVIDENCE_STATE", "OBSERVED" if source_sha != "UNBOUND" else "DRAFT")
    schema_version = "qps.web.publication.v1"
    OUT.write_text(
        "\n".join(
            [
                f"release_id: {release_id}",
                f"source_sha: {source_sha}",
                f"schema_version: {schema_version}",
                f"evidence_state: {evidence_state}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"prepared {OUT}: release_id={release_id} source_sha={source_sha}")
    return 0 if source_sha != "UNBOUND" else 2


if __name__ == "__main__":
    raise SystemExit(main())
