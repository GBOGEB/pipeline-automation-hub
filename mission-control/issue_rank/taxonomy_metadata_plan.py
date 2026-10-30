#!/usr/bin/env python3
"""Owner-review-only issue/PR facet label suggestions: NEVER writes to GitHub."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import title_taxonomy as taxonomy

SCHEMA = "jade.taxonomy-metadata-proposal.v1"
RANK_SCHEMA = "jade.issue-rank.v1"
RANK_SCHEMAS = frozenset((RANK_SCHEMA, "jade.issue-rank.v2"))
SHA = re.compile(r"^[0-9a-f]{40}$", re.I)
IDENT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$")
TOKEN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_LABELS_PER_ITEM = 8


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _label_names(value: object) -> set[str]:
    if not isinstance(value, list):
        raise ValueError("LABELS_NOT_LIST")
    result = set()
    for label in value:
        name = label if isinstance(label, str) else label.get("name") if isinstance(label, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise ValueError("LABEL_INVALID")
        result.add(name.casefold())
    return result


def propose(model: dict, *, allow_private: bool = False, parser_sha: str | None = None) -> dict:
    if model.get("schema") not in RANK_SCHEMAS:
        raise ValueError("RANK_SCHEMA_MISMATCH")
    if parser_sha is not None and not SHA.fullmatch(parser_sha):
        raise ValueError("PARSER_SHA_MISSING_OR_INVALID")
    heads = model.get("heads")
    if not isinstance(heads, dict) or not heads:
        raise ValueError("HEADS_REQUIRED")
    for repo, head in heads.items():
        if not isinstance(head, dict) or not (SHA.fullmatch(str(head.get("head_sha") or ""))
                                             or model["schema"] == "jade.issue-rank.v2"
                                             and head.get("private") is True and head.get("head_sha") is None):
            raise ValueError("SOURCE_SHA_UNVERIFIED")
    items = model.get("items")
    if not isinstance(items, list):
        raise ValueError("ITEMS_NOT_LIST")
    proposals, excluded = [], 0
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("INVALID_ITEM")
        key, repo, kind = item.get("key"), item.get("repo"), item.get("type")
        number = item.get("number")
        if (not isinstance(key, str) or not IDENT.fullmatch(key) or repo not in heads
                or type(number) is not int or number < 1
                or key != f"{repo}#{number}" or kind not in ("Issue", "PullRequest")):
            raise ValueError("INVALID_ITEM_IDENTITY")
        if key in seen:
            raise ValueError("DUPLICATE_IDENTITY")
        seen.add(key)
        private = item.get("private")
        if type(private) is not bool or private != bool(heads[repo].get("private")):
            raise ValueError("PRIVACY_MISMATCH")
        parsed = item.get("title_taxonomy")
        if not isinstance(parsed, dict) or parsed.get("schema") != taxonomy.SCHEMA:
            raise ValueError("TAXONOMY_SCHEMA_MISMATCH")
        if private and not allow_private:
            excluded += 1
            continue
        existing = _label_names(item.get("labels") or [])
        # No ownership or guessed type is authorized by semantic matches alone.
        proposed = []
        family = parsed.get("family")
        if parsed.get("classification") == "EXPLICIT_ACTION" and isinstance(family, str) and TOKEN.fullmatch(family):
            proposed.append("type:" + family)
        for topic in sorted(set(parsed.get("topic_families") or [])):
            if not isinstance(topic, str) or not TOKEN.fullmatch(topic):
                raise ValueError("TOPIC_OUTSIDE_CANONICAL_VOCABULARY")
            proposed.append("family:" + topic)
        for cluster in sorted(set(parsed.get("technical_clusters") or [])):
            if not isinstance(cluster, str) or not TOKEN.fullmatch(cluster):
                raise ValueError("CLUSTER_OUTSIDE_CANONICAL_VOCABULARY")
            proposed.append("cluster:" + cluster)
        conflicts = sorted(x for x in existing if x.startswith("type:") and
                           x not in proposed and any(p.startswith("type:") for p in proposed))
        missing = sorted(x for x in proposed if x.casefold() not in existing)
        status = ("CONFLICT_OWNER_REVIEW" if conflicts else
                  "NEEDS_EXPLICIT_TYPE_OWNER" if family == "UNCLASSIFIED" else
                  "NO_CHANGE" if not missing else "DRY_RUN_ONLY")
        proposals.append({"key": key, "type": kind, "source_repo_sha": heads[repo]["head_sha"],
                          "classification": parsed.get("classification"),
                          "status": status, "labels_to_consider": missing[:MAX_LABELS_PER_ITEM],
                          "overflow_unapplied": max(0, len(missing) - MAX_LABELS_PER_ITEM),
                          "conflicting_existing_types": conflicts,
                          "existing_label_count": len(existing),
                          "changed_title": False, "authorized_write": False})
    safe_heads = {r: h["head_sha"] for r, h in sorted(heads.items())
                  if allow_private or not h.get("private")}
    plan = {"schema": SCHEMA, "taxonomy_schema": taxonomy.SCHEMA,
            "parser_sha": parser_sha, "source_heads": safe_heads,
            "visibility": "OWNER_PRIVATE_LOCAL" if allow_private else "PUBLIC_REDACTED",
            "excluded_private": excluded, "proposals": sorted(proposals, key=lambda x: x["key"]),
            "mutation_permitted": False, "issue_title_rewrites": 0,
            "auto_label_writes": 0, "approval_required": True,
            "closure_credit": 0, "authority_transfer": False}
    plan["projection_sha256"] = hashlib.sha256(canonical(
        {k: v for k, v in plan.items() if k != "projection_sha256"})).hexdigest()
    return plan


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--parser-sha")
    p.add_argument("--owner-private-local", action="store_true")
    a = p.parse_args(argv)
    source = json.loads(a.model.read_text(encoding="utf-8"))
    result = propose(source, allow_private=a.owner_private_local, parser_sha=a.parser_sha)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(canonical(result) + b"\n")
    print(f"DRY_RUN_ONLY {len(result['proposals'])} items, {result['excluded_private']} private excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
