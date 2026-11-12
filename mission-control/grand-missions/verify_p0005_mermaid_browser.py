"""Bind current P0005 diagrams to the immutable renderer owned by PR #1175.

The consumer selects its three inputs and verifies source roles; all extraction,
browser execution, geometry checks and evidence production remain in that owner.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METHOD_SHA = "10c93e2268e62ab8584f8e915d60c3707116f81d"
METHOD_PATH = "tools/workstation/build_mermaid_check.py"
INPUTS = (
    "GM_I_C_R2_EXECUTION_LANES_P0005.mmd",
    "GM_I_C_R2_PROMOTION_DEPENDENCIES_P0005.mmd",
    "GM_I_C_R2_SIPOC_P0005.mmd",
)


def head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    verdict = {"schema": "gmic.p0005.mermaid_render.v1", "ok": False,
               "merge_admission": "HOLD", "closure_credit": 0}
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha) or head(ROOT) != args.source_sha:
            raise ValueError("diagram checkout SHA mismatch")
        method_root = args.method_root.resolve()
        if head(method_root) != METHOD_SHA:
            raise ValueError("method checkout SHA mismatch")
        method_file = method_root / METHOD_PATH
        committed = subprocess.check_output(["git", "-C", str(method_root), "show", f"{METHOD_SHA}:{METHOD_PATH}"])
        if method_file.read_bytes() != committed:
            raise ValueError("method file differs from qualified commit")
        spec = importlib.util.spec_from_file_location("p0005_mermaid_owner", method_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        diagrams = module.collect([ROOT / "mission-control/grand-missions/diagrams" / name for name in INPUTS])
        verdict = module.render_headless(diagrams, args.out, source_root=ROOT)
        if (len(diagrams) != 3 or verdict.get("owner_head_sha") != METHOD_SHA
                or verdict.get("owner_matches_commit") is not True
                or verdict.get("source_binding", {}).get("head_sha") != args.source_sha):
            raise ValueError("render receipt source binding mismatch")
    except Exception as exc:
        verdict["ok"] = False
        verdict["error"] = f"{type(exc).__name__}: {exc}"
    (args.out / "receipt.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
