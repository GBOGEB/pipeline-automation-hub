"""Read-only pinned-main repeat proof for the Hub MAIN E2E contract.

This is an execution receipt, not a release, engineering or CONTROL approval.
The source is checked out by a detached Git worktree. The owner source is never
mutated and no outcome is inferred from a PR status.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

HEX40 = re.compile(r"^[0-9a-f]{40}$")
SUITE = "tests.test_main_pipeline_e2e"
EXPECTED_CASES = 3
RECEIPT_SCHEMA = "jade.main-pipeline-repeat.v1"


def command(args, cwd: Path):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def worktree_listed(repo: Path, work: Path) -> bool:
    """True when Git still has an administrative entry for ``work``.

    A failing checkout phase (e.g. a post-checkout hook) can make
    ``git worktree add`` exit nonzero after the entry was registered.
    """
    listing = command(["git", "worktree", "list", "--porcelain"], repo)
    if listing.returncode:
        return True  # unknown: attempt deregistration rather than leave a stale entry
    return any(line.startswith("worktree ") and _same_path(line[len("worktree "):], work)
               for line in listing.stdout.splitlines())


def execute(repo: Path, source_sha: str, out: Path):
    if not HEX40.fullmatch(source_sha):
        raise ValueError("exact 40-hex source commit required")
    if out.exists():
        raise ValueError("output receipt must not already exist")
    repo = repo.resolve()
    source = command(["git", "cat-file", "-t", source_sha], repo)
    if source.returncode != 0 or source.stdout.strip() != "commit":
        raise ValueError("pinned source commit missing from local Git objects")
    started = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    # Git Bash/Windows cannot reliably traverse owner-only TemporaryDirectory
    # parents. Build a named scratch folder beneath the system temp directory.
    scratch = Path(tempfile.gettempdir()) / ("jade-hub-main-proof-" + uuid.uuid4().hex)
    os.makedirs(scratch, mode=0o755, exist_ok=False)
    work = scratch / "source"
    worktree_registered = False
    try:
        checkout = command(["git", "worktree", "add", "--detach", str(work), source_sha], repo)
        if checkout.returncode:
            worktree_registered = worktree_listed(repo, work)
            raise RuntimeError("detached source worktree failed: " + checkout.stderr[-600:])
        worktree_registered = True
        sha = command(["git", "rev-parse", "HEAD"], work)
        if sha.returncode or sha.stdout.strip() != source_sha:
            raise RuntimeError("source worktree head mismatch")
        blob = command(["git", "rev-parse", "HEAD:README.md"], work)
        if blob.returncode or not HEX40.fullmatch(blob.stdout.strip()):
            raise RuntimeError("source root README blob missing")
        test_file = work / "tests" / "test_main_pipeline_e2e.py"
        if not test_file.is_file():
            raise RuntimeError("canonical real-subprocess MAIN test suite absent")
        test_sha256 = hashlib.sha256(test_file.read_bytes()).hexdigest()
        begin = time.monotonic()
        run = command([sys.executable, "-m", "unittest", "-v", SUITE], work)
        seconds = round(time.monotonic() - begin, 3)
        output = run.stdout + "\n" + run.stderr
        cases = re.search(r"Ran (\d+) tests? in ", output)
        count = int(cases.group(1)) if cases else None
        passed = (run.returncode == 0 and count == EXPECTED_CASES
                  and re.search(r"\nOK\s*$", output) is not None)
        receipt = {
            "schema": RECEIPT_SCHEMA, "source_repo": "GBOGEB/pipeline-automation-hub",
            "source_sha": source_sha, "root_readme_blob_sha": blob.stdout.strip(),
            "suite_path": "tests/test_main_pipeline_e2e.py",
            "suite_sha256": test_sha256, "test_count": count,
            "required_test_count": EXPECTED_CASES,
            "tests": ["valid_PPTX_real_subprocess", "invalid_renamed_PPTX_rejected",
                      "valid_PPTX_plus_Excel_real_subprocess"],
            "started_at_utc": started, "elapsed_seconds": seconds,
            "native_returncode": run.returncode,
            "status": "PASS_NATIVE_REPEAT" if passed else "FAIL_NATIVE_REPEAT",
            "authority": "METADATA_ONLY_NOT_DOCUMENT_TRUTH",
            "release_qualified": False, "control_qualified": False,
            "merge_admission": "WITHHELD",
            "log_tail": output[-5500:],
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        return passed, receipt
    finally:
        # Cleanup must attempt BOTH Git deregistration and scratch deletion;
        # neither failure may mask a primary checkout / suite failure.
        primary_error = sys.exc_info()[1]
        cleanup_errors = []
        if worktree_registered:
            try:
                cleanup = command(["git", "worktree", "remove", "--force", str(work)], repo)
                if cleanup.returncode:
                    cleanup_errors.append("git worktree remove failed: " + cleanup.stderr[-600:])
            except Exception as exc:
                cleanup_errors.append("git worktree remove exception: " + str(exc))
        try:
            shutil.rmtree(scratch)
        except OSError as exc:
            cleanup_errors.append("scratch removal failed: " + str(exc))
        if cleanup_errors:
            detail = "; ".join(cleanup_errors)
            if primary_error is not None:
                primary_error.add_note("Additional cleanup failure: " + detail)
            else:
                raise RuntimeError("detached source worktree cleanup failed: " + detail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    ok, receipt = execute(args.repo, args.source_sha, args.out)
    print("MAIN_REPEAT_" + receipt["status"] +
          f" source={receipt['source_sha']} tests={receipt['test_count']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
