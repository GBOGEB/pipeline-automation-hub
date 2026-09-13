#!/usr/bin/env python3
"""Execute the upstream YAML reference parser test contract twice at one exact fork SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def tracked_tree_digest(repo: Path) -> str:
    payload = git(repo, "ls-files", "-s").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_test(repo: Path, log_path: Path) -> dict:
    started = time.monotonic()
    proc = subprocess.run(
        ["make", "test"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=900,
    )
    elapsed = time.monotonic() - started
    log_path.write_text(proc.stdout, encoding="utf-8")
    return {
        "returncode": proc.returncode,
        "duration_s": round(elapsed, 3),
        "log_sha256": hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest(),
        "tracked_tree_sha256_after": tracked_tree_digest(repo),
        "tracked_dirty_after": bool(git(repo, "status", "--porcelain", "--untracked-files=no")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-a", type=Path, required=True)
    parser.add_argument("--repo-b", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--log-a", type=Path, required=True)
    parser.add_argument("--log-b", type=Path, required=True)
    args = parser.parse_args()

    repos = [args.repo_a.resolve(), args.repo_b.resolve()]
    for repo in repos:
        actual = git(repo, "rev-parse", "HEAD")
        assert actual == args.expected_sha, (actual, args.expected_sha)
        assert git(repo, "status", "--porcelain", "--untracked-files=no") == ""
        assert (repo / "ReadMe.md").is_file()
        assert (repo / "Makefile").is_file()
        assert (repo / ".github/workflows/test.yml").is_file()
        readme = (repo / "ReadMe.md").read_text(encoding="utf-8")
        workflow = (repo / ".github/workflows/test.yml").read_text(encoding="utf-8")
        assert "YAML 1.2 Reference Parsers" in readme
        assert "github.com/yaml/yaml-reference-parser" in readme
        assert "make test" in workflow

    tree_before = [tracked_tree_digest(repo) for repo in repos]
    assert tree_before[0] == tree_before[1]

    run_a = run_test(repos[0], args.log_a)
    run_b = run_test(repos[1], args.log_b)

    assert run_a["returncode"] == 0, "first upstream make test execution failed"
    assert run_b["returncode"] == 0, "second upstream make test execution failed"
    assert run_a["tracked_tree_sha256_after"] == tree_before[0]
    assert run_b["tracked_tree_sha256_after"] == tree_before[1]
    assert run_a["tracked_dirty_after"] is False
    assert run_b["tracked_dirty_after"] is False

    receipt = {
        "schema": "qps.gm_iv_ring2_yaml_reference_scout.v1",
        "candidate_repository": "GBOGEB/yaml-reference-parser",
        "candidate_sha": args.expected_sha,
        "provenance": {
            "is_fork": True,
            "parent_repository": "yaml/yaml-reference-parser",
            "source_repository": "yaml/yaml-reference-parser",
            "upstream_contract": "make test",
            "provenance_class": "UPSTREAM_FORK_REFERENCE_CANDIDATE",
        },
        "run_a": run_a,
        "run_b": run_b,
        "semantic_repeat": True,
        "candidate_slot_bound": False,
        "canonical_child_bound": False,
        "domain_authority": False,
        "engineering_authority": False,
        "disposition": "SCOUT_RUNTIME_PASS_REFERENCE_OR_EXTRACT_CANDIDATE_ONLY",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS_GM_IV_RING2_SCOUT_B",
        "candidate": receipt["candidate_repository"],
        "candidate_sha": args.expected_sha,
        "provenance_class": receipt["provenance"]["provenance_class"],
        "semantic_repeat": True,
        "slot_bound": False,
        "child_bound": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
