"""B42: source-pinned CODEX alias and Hub title advisory, never a router."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODEX_MERGE = "c7535442cd325d2b7602fcadf7677aa235ecdafd"
TITLE_BLOB = "1f7bebe94a0fe114b604bb6bf5ecd4a6e2e1d92d"
OWNER_MODULE = "federation/mesh/prompt_alias_shadow.py"
TITLE_MODULE = "mission-control/issue_rank/title_taxonomy.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("MISSING_OWNER_MODULE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def _blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def observe(codex_root: Path, phrase: str, title: str) -> dict:
    """Read two distinct owners, return inert side-by-side candidates."""
    codex_root = codex_root.resolve()
    if _sha(codex_root) != CODEX_MERGE:
        raise ValueError("CODEX_EXACT_SOURCE_MISMATCH")
    title_path = ROOT / TITLE_MODULE
    if _blob(title_path) != TITLE_BLOB:
        raise ValueError("HUB_TITLE_OWNER_DRIFT")
    owner = _load(codex_root / OWNER_MODULE, "b42_codex_owner")
    parser = _load(title_path, "b42_hub_title_owner")
    profile = json.loads((codex_root / "federation/mesh/PROMPT_ALIAS_SHADOW_PROFILE_v1.json").read_text(encoding="utf-8"))
    validated = owner.validate_profile(
        profile,
        action_bytes=(codex_root / "federation/mesh/GLOBAL_ACTION_TAXONOMY_v1.yaml").read_bytes(),
        status_bytes=(codex_root / "governance/mesh/MESH_STATUS_CONTRACT_v1.yaml").read_bytes(),
    )
    candidate = None
    refusal = None
    try:
        result = owner.resolve_phrase(phrase, profile, validated=validated)
        candidate = result["route"]
        if candidate["dispatch_authorized"] or candidate["authority_transfer"] or candidate["formal_credit_delta"]:
            raise ValueError("UNEXPECTED_OWNER_AUTHORITY")
    except owner.AliasPolicyError as exc:
        refusal = str(exc)
    taxonomy = parser.parse_title(title, item_type="PullRequest")
    return {
        "schema": "jade.b42.source-shadow.v1",
        "codex_source_sha": CODEX_MERGE,
        "hub_title_blob": TITLE_BLOB,
        "action_candidate": candidate,
        "action_refusal": refusal,
        "title_classification": taxonomy,
        "source_roles": {"action": "GBOGEB/CODEX", "title": "GBOGEB/pipeline-automation-hub"},
        "changed_title": False,
        "dispatch_authorized": False,
        "merge_authorized": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only B42 shadow pilot; never dispatches.")
    ap.add_argument("--codex-root", type=Path, required=True)
    ap.add_argument("--phrase", required=True)
    ap.add_argument("--title", required=True)
    args = ap.parse_args()
    print(json.dumps(observe(args.codex_root, args.phrase, args.title), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
