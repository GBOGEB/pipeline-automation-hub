#!/usr/bin/env python3
"""Execute one candidate notebook twice without mutating the candidate repository."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor


def canonical_outputs(nb: dict) -> dict:
    cells = []
    executed = 0
    for index, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("execution_count") is not None:
            executed += 1
        outputs = []
        for output in cell.get("outputs", []):
            item = {"output_type": output.get("output_type")}
            if output.get("output_type") == "stream":
                item.update({"name": output.get("name"), "text": output.get("text", "")})
            elif output.get("output_type") in {"display_data", "execute_result"}:
                item["data"] = output.get("data", {})
            elif output.get("output_type") == "error":
                item.update({
                    "ename": output.get("ename"),
                    "evalue": output.get("evalue"),
                    "traceback": output.get("traceback", []),
                })
            outputs.append(item)
        cells.append({"index": index, "source": cell.get("source", ""), "outputs": outputs})
    payload = {"executed_code_cells": executed, "cells": cells}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload["digest_sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def execute(source: Path) -> dict:
    nb = nbformat.read(source, as_version=4)
    ep = ExecutePreprocessor(timeout=240, kernel_name="python3", allow_errors=False)
    # Preserve the notebook's own relative-path semantics. For notebooks/foo.ipynb,
    # '../data/...' is intentionally resolved from notebooks/, not the repo root.
    ep.preprocess(nb, {"metadata": {"path": str(source.parent)}})
    return canonical_outputs(nb)


def version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    missioncontrol_sha = os.environ.get("MISSIONCONTROL_SHA", "")
    if len(missioncontrol_sha) != 40:
        raise SystemExit("FAIL: exact 40-char MISSIONCONTROL_SHA required")

    repo = args.repo.resolve()
    notebook = repo / args.notebook
    actual_sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    assert actual_sha == args.expected_sha, (actual_sha, args.expected_sha)
    assert notebook.is_file(), notebook
    before = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True)
    assert before == "", "candidate checkout must start clean"

    run1 = execute(notebook)
    run2 = execute(notebook)
    after = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True)
    assert after == "", "candidate checkout must remain clean"
    assert run1["executed_code_cells"] > 0, "scout requires >0 executed notebook cells"
    assert run2["executed_code_cells"] == run1["executed_code_cells"]
    assert run1["digest_sha256"] == run2["digest_sha256"], "notebook output digest must repeat"

    receipt = {
        "schema": "qps.gm_iv_ring2_jupyter_scout.v1",
        "missioncontrol_source_sha": missioncontrol_sha,
        "candidate_repository": "GBOGEB/codespaces-jupyter",
        "candidate_sha": actual_sha,
        "notebook": args.notebook,
        "notebook_working_directory": str(Path(args.notebook).parent),
        "source_file_sha256": hashlib.sha256(notebook.read_bytes()).hexdigest(),
        "run_1": run1,
        "run_2_digest_sha256": run2["digest_sha256"],
        "deterministic_repeat": True,
        "target_dirty_file_count": 0,
        "candidate_slot_bound": False,
        "canonical_child_bound": False,
        "domain_authority": False,
        "disposition": "SCOUT_RUNTIME_PASS_CANDIDATE_ONLY",
        "environment": {
            "python": platform.python_version(),
            "nbformat": version("nbformat"),
            "nbconvert": version("nbconvert"),
            "ipykernel": version("ipykernel"),
            "pandas": version("pandas"),
            "matplotlib": version("matplotlib"),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS_GM_IV_RING2_SCOUT_A",
        "missioncontrol_source_sha": missioncontrol_sha,
        "candidate": receipt["candidate_repository"],
        "candidate_sha": actual_sha,
        "executed_code_cells": run1["executed_code_cells"],
        "digest_sha256": run1["digest_sha256"],
        "slot_bound": False,
        "child_bound": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
