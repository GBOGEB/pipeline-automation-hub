#!/usr/bin/env python3
"""Read-only adapter: canonical issue/PR title taxonomy -> candidate CI bundle facets."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER = HERE.parents[1] / "issue_rank" / "title_taxonomy.py"
CATALOG = HERE / "CI_BUNDLE_CATALOG_V1.json"
SCHEMA = "jade.devops.ci_bundle_title_crosswalk.v1"
EXPLICIT_BUNDLE = re.compile(r"^B(?:0[0-9]|1[0-2])$")
CANDIDATE_NAMESPACE = "jade.devops.ci_candidate"
LEGACY_NAMESPACE = "ci-spine:bundle"


def _checked_candidate_catalog(catalog: dict) -> dict:
    """Reject legacy or promoted catalogs: a shared Bxx spelling is not identity."""
    if not isinstance(catalog, dict) or catalog.get("schema") != "jade.devops.ci_bundle_catalog.v1":
        raise ValueError("CANDIDATE_CATALOG_REQUIRED")
    if catalog.get("merge_authorized") is not False or not str(catalog.get("status", "")).startswith("ADVISORY"):
        raise ValueError("CANDIDATE_CATALOG_NOT_ADVISORY")
    if catalog.get("namespace") != CANDIDATE_NAMESPACE:
        raise ValueError("CANDIDATE_NAMESPACE_REQUIRED")
    rows = catalog.get("bundles")
    if not isinstance(rows, list) or not rows:
        raise ValueError("CANDIDATE_BUNDLES_UNAVAILABLE")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_OR_INVALID_BUNDLES")
    if any(not isinstance(row.get("key"), str) or not EXPLICIT_BUNDLE.fullmatch(row["id"]) for row in rows):
        raise ValueError("INVALID_CANDIDATE_BUNDLE")
    return {row["id"]: row for row in rows}


def _canonical_parser():
    spec = importlib.util.spec_from_file_location("jade_canonical_title_taxonomy", OWNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("CANONICAL_TITLE_TAXONOMY_UNAVAILABLE")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    return owner.parse_title


def crosswalk(title: str, catalog: dict, parser=None) -> dict:
    """Never parse a new title grammar: use only explicit scope tokens from the SSOT."""
    if not isinstance(title, str):
        raise TypeError("title must be text")
    parser = parser or _canonical_parser()
    parsed = parser(title, item_type="PullRequest")
    known = _checked_candidate_catalog(catalog)
    # Prefix only. A mention of B02 in body text is not evidence of CI ownership.
    explicit = sorted({str(tag.get("value", "")).upper()
                       for tag in parsed.get("prefix_segments", [])
                       if EXPLICIT_BUNDLE.fullmatch(str(tag.get("value", "")).upper())})
    candidates = sorted(x for x in explicit if x in known)
    scope = sorted({str(tag.get("value", "")).casefold()
                    for tag in parsed.get("prefix_segments", [])
                    if str(tag.get("value", "")).casefold() in ("ci", "devops", "test", "tests")})
    return {
        "schema": SCHEMA,
        "canonical_parser_schema": parsed.get("schema"),
        "family": parsed["family"],
        "classification": parsed["classification"],
        "programmes": parsed.get("programmes", []),
        "scope_facets": scope,
        "bundle_candidates": candidates,
        "bundle_display_aliases": [f"{x} / {known[x]['key']}" for x in candidates],
        "candidate_namespace": CANDIDATE_NAMESPACE,
        "candidate_urns": [f"{CANDIDATE_NAMESPACE}:{x}" for x in candidates],
        "legacy_spine_namespace": LEGACY_NAMESPACE,
        "legacy_label_equivalent": False,
        "explicit_bundle_count": len(candidates),
        "prefix_lint": sorted(parsed.get("lint", [])),
        "policy_flags": sorted(parsed.get("policy_flags", [])),
        "candidate_only": True,
        "workflow_names_renamed": False,
        "required_check_contexts_modified": False,
        "merge_authorized": False,
        "authority": "ADVISORY_ONLY",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--title", required=True)
    ap.add_argument("--catalog", type=Path, default=CATALOG)
    args = ap.parse_args()
    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    print(json.dumps(crosswalk(args.title, data), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
