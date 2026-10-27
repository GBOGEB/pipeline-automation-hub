#!/usr/bin/env python3
"""Source-pinned, non-authoritative title taxonomy pulse for issue-rank models.

Only one source item contributes to each primary-family/composite denominator.
Topic and technical memberships overlap and must not be summed as totals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import title_taxonomy as tax

SCHEMA = "jade.taxonomy-pulse.v1"
RANK_SCHEMA = "jade.issue-rank.v1"
# issue_rank method v2 (jade.issue-rank.v2) keeps every field this reader uses.
RANK_SCHEMAS = frozenset((RANK_SCHEMA, "jade.issue-rank.v2"))
JADE_REPOS = {"ABACUS", "CODEX", "cryoplant-project", "pipeline-automation-hub"}
SHA = re.compile(r"^[0-9a-f]{40}$", re.I)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("FETCH_TIMESTAMP_MISSING")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("FETCH_TIMESTAMP_INVALID") from exc
    if dt.tzinfo is None:
        raise ValueError("FETCH_TIMESTAMP_MUST_INCLUDE_OFFSET")
    return dt


def visible(model: dict, *, public: bool) -> dict:
    """Validate identity/pins BEFORE removing private material; never emit titles."""
    if model.get("schema") not in RANK_SCHEMAS:
        raise ValueError("RANK_SCHEMA_MISMATCH")
    observed = model.get("fetched_at")
    _timestamp(observed)
    heads = model.get("heads")
    if not isinstance(heads, dict) or not heads:
        raise ValueError("REPO_HEADS_MISSING")
    rows = model.get("items")
    if not isinstance(rows, list):
        raise ValueError("ITEMS_MISSING")
    # A redacted private head may have no visible SHA only after the public
    # projection erased the original receipt. Never relax validation for a raw
    # private model, nor for any public repository.
    projection = model.get("privacy_projection") or {}
    marked = projection.get("validated_then_redacted_heads") or []
    for repo, h in heads.items():
        if not isinstance(h, dict):
            raise ValueError("INVALID_SOURCE_HEAD:" + str(repo))
        if SHA.fullmatch(str(h.get("head_sha") or "")):
            continue
        private_items = [i for i in rows if isinstance(i, dict) and i.get("repo") == repo]
        safely_redacted = bool(private_items) and all(
            i.get("title") is None
            and str(i.get("key", "")).startswith(str(repo) + "#PRIVATE-")
            and (i.get("title_taxonomy") or {}).get("family") == "REDACTED_PRIVATE"
            for i in private_items
        )
        marked_valid = (
            isinstance(marked, list) and repo in marked
            and all(isinstance(i, dict) and i.get("title") is None
                    and (i.get("title_taxonomy") or {}).get("family") == "REDACTED_PRIVATE"
                    for i in private_items)
        )
        if not (public and h.get("private") is True
                and h.get("head_sha") is None
                and (safely_redacted or marked_valid)):
            raise ValueError("INVALID_SOURCE_HEAD:" + str(repo))
    seen = set()
    retained = []
    excluded = 0
    for item in rows:
        ident, repo, kind = item.get("key"), item.get("repo"), item.get("type")
        if not isinstance(ident, str) or repo not in heads or not ident.startswith(repo + "#"):
            raise ValueError("ITEM_IDENTITY_REPO_MISMATCH")
        if ident in seen:
            raise ValueError("DUPLICATE_ITEM_IDENTITY:" + ident)
        seen.add(ident)
        if kind not in ("Issue", "PullRequest"):
            raise ValueError("UNKNOWN_ITEM_TYPE")
        if bool(item.get("private")) != bool(heads[repo].get("private")):
            raise ValueError("ITEM_PRIVACY_HEAD_MISMATCH")
        t = item.get("title_taxonomy")
        if not isinstance(t, dict) or t.get("schema") != tax.SCHEMA:
            raise ValueError("ITEM_TAXONOMY_SCHEMA_MISMATCH")
        if not t.get("family") or not t.get("path"):
            raise ValueError("ITEM_FAMILY_MISSING")
        if item.get("private") and public:
            excluded += 1
            continue
        retained.append({
            "key": ident, "repo": repo, "type": kind,
            "family": t["family"], "path": t["path"],
            "topic_families": sorted(set(t.get("topic_families") or [])),
            "technical_clusters": sorted(set(t.get("technical_clusters") or [])),
            "codes": sorted(set(t.get("codes") or [])),
            "programmes": sorted(set(t.get("programmes") or [])),
            "classification": t.get("classification", "UNCLASSIFIED"),
            "lint": sorted(set(t.get("lint") or [])),
            "subfamily": t.get("subfamily"),
        })
    # Projection contains NO free-text title, action, dependency or graph source.
    safe_heads = {r: {"head_sha": h["head_sha"],
                      "default_branch": h.get("default_branch")}
                  for r, h in sorted(heads.items())
                  if not (public and h.get("private"))}
    return {"fetched_at": observed, "heads": safe_heads,
            "items": sorted(retained, key=lambda x: x["key"]),
            "excluded_private_count": excluded,
            "source_grade": "NON_ATOMIC_API_HEADS_AND_OPEN_ITEMS"}


def _slug(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def facets(item: dict) -> dict:
    """A single explainable composite, not a Cartesian explosion of facets."""
    action = _slug(item["family"]) or "untyped"
    topics = item["topic_families"]
    if "jade-devops" in topics:
        scope = "jade-devops"
    elif topics:
        scope = sorted(topics, key=lambda x: (-len(x), x))[0]
    else:
        scope = _slug(item.get("subfamily")) or "unscoped"
    clusters = item["technical_clusters"]
    if "census" in clusters:
        family = "census"
    elif clusters:
        family = clusters[0]
    else:
        family = scope if scope != "unscoped" else "general"
    remaining = [c for c in clusters if c != family]
    cluster = remaining[0] if remaining else (clusters[0] if clusters and family == scope else "general")
    return {"action": action, "scope": scope, "family": family,
            "cluster": cluster,
            "composite": "/".join((action, scope, family, cluster))}


def _scope_items(items: list[dict], scope: str) -> list[dict]:
    if scope == "USER":
        return items
    if scope == "JADE":
        return [i for i in items if i["repo"].split("/", 1)[-1] in JADE_REPOS]
    return [i for i in items if i["repo"] == scope]


def aggregate(items: list[dict]) -> dict:
    """Count primary families and composites once; keep overlaps explicit."""
    family, composite, peers, quality, kinds = Counter(), Counter(), Counter(), Counter(), Counter()
    topic, cluster, code = Counter(), Counter(), Counter()
    for item in items:
        kind = item["type"]
        kinds[kind] += 1
        family[item["family"]] += 1
        f = facets(item)
        composite[f["composite"]] += 1
        peers[f["action"] + "/" + f["scope"]] += 1
        quality[item["classification"]] += 1
        for name in set(item["topic_families"]):
            topic[name] += 1
        for name in set(item["technical_clusters"]):
            cluster[name] += 1
        for name in set(item["codes"]):
            code[name] += 1
        for name in set(item["lint"]):
            quality["lint:" + name] += 1
    count = len(items)
    if sum(family.values()) != count or sum(composite.values()) != count:
        raise ValueError("NONADDITIVE_PRIMARY_DENOMINATOR")
    return {
        "total": count, "issues": kinds["Issue"], "prs": kinds["PullRequest"],
        "primary_family": dict(sorted(family.items())),
        "single_composite": dict(sorted(composite.items())),
        "peer_cohorts": dict(sorted(peers.items())),
        "topic_memberships_nonadditive": dict(sorted(topic.items())),
        "cluster_memberships_nonadditive": dict(sorted(cluster.items())),
        "code_memberships_nonadditive": dict(sorted(code.items())),
        "quality": dict(sorted(quality.items())),
        "typed_prefix_rate": round(quality["EXPLICIT_ACTION"] / count, 6) if count else None,
        "family_and_composite_additive": True,
        "memberships_additive": False,
    }


def _breakdown(items: list[dict], heads: dict) -> dict:
    # Zero-item repositories still belong in the measured source population.
    repos = sorted(heads)
    scopes = ["USER", "JADE"] + repos
    return {scope: aggregate(_scope_items(items, scope)) for scope in scopes}


def changes(previous: dict, current: dict) -> dict:
    if set(previous["heads"]) != set(current["heads"]):
        return {"comparable": False, "reason": "REPOSITORY_POPULATION_CHANGED",
                "verified_closed": None, "formal_credit_delta": 0}
    if _timestamp(previous["fetched_at"]) > _timestamp(current["fetched_at"]):
        raise ValueError("PULSE_TIMESTAMP_REVERSED")
    older = {x["key"]: x for x in previous["items"]}
    newer = {x["key"]: x for x in current["items"]}
    new, absent = sorted(newer.keys() - older.keys()), sorted(older.keys() - newer.keys())
    persisting = sorted(older.keys() & newer.keys())
    moves = []
    for key in persisting:
        a, b = older[key], newer[key]
        if a["type"] != b["type"]:
            raise ValueError("IDENTITY_ITEM_TYPE_MUTATED:" + key)
        changed = [field for field in ("family", "path", "topic_families",
                   "technical_clusters", "codes", "classification", "lint")
                   if a[field] != b[field]]
        if changed:
            moves.append({"key": key, "changed_dimensions": changed,
                          "from_family": a["family"], "to_family": b["family"],
                          "from_path": a["path"], "to_path": b["path"],
                          "evidence": "CLASSIFICATION_CHANGE_NOT_ROOT_CLOSURE"})
    return {
        "comparable": True, "reason": "SAME_REPO_POPULATION_AND_TAXONOMY_SCHEMA",
        "newly_open_observed": len(new), "absent_from_open_not_verified_closed": len(absent),
        "persisting_open": len(persisting), "reclassified": len(moves),
        "new_item_keys": new, "absent_item_keys": absent, "classification_moves": moves,
        "new_by_primary_family": dict(sorted(Counter(newer[k]["family"] for k in new).items())),
        "absent_by_primary_family": dict(sorted(Counter(older[k]["family"] for k in absent).items())),
        "verified_closed": None, "formal_credit_delta": 0,
    }


def _history_point(wave: str, projection: dict) -> dict:
    rollups = _breakdown(projection["items"], projection["heads"])
    return {
        "wave": wave, "observed_at": projection["fetched_at"],
        "source_heads": projection["heads"],
        "visible_projection_sha256": hashlib.sha256(canonical(
            {"heads": projection["heads"], "items": projection["items"]})).hexdigest(),
        "rollups": rollups,
    }


def build(current_model: dict, previous_model: dict | None = None, *,
          public: bool = True, parser_sha: str | None = None,
          previous_parser_sha: str | None = None) -> dict:
    for name, value in (("parser", parser_sha), ("previous_parser", previous_parser_sha)):
        if value is not None and not SHA.fullmatch(value):
            raise ValueError("INVALID_" + name.upper() + "_SHA")
    cur = visible(current_model, public=public)
    previous = visible(previous_model, public=public) if previous_model is not None else None
    if previous is not None and _timestamp(previous["fetched_at"]) >= _timestamp(cur["fetched_at"]):
        raise ValueError("PULSE_TIMESTAMP_NOT_STRICTLY_LATER")
    points = ([_history_point("N", previous)] if previous is not None else [])
    points.append(_history_point("N+1" if previous is not None else "N0", cur))
    scales = points[-1]["rollups"]
    delta = (changes(previous, cur) if previous is not None else
             {"comparable": False, "reason": "BASELINE_ONLY",
              "verified_closed": None, "formal_credit_delta": 0})
    if previous is not None:
        delta["parser_identity_comparable"] = (
            parser_sha is not None and previous_parser_sha is not None
            and parser_sha == previous_parser_sha
        )
        delta["classification_attribution"] = (
            "SAME_PINNED_PARSER" if delta["parser_identity_comparable"]
            else "WITHHELD_PARSER_VERSION_NOT_MATCHED"
        )
    return {
        "schema": SCHEMA, "taxonomy_schema": tax.SCHEMA,
        "observed_at": cur["fetched_at"],
        "source_grade": cur["source_grade"], "source_heads": cur["heads"],
        "parser_sha": parser_sha, "parser_pin_state": "PINNED" if parser_sha else "UNKNOWN",
        "previous_parser_sha": previous_parser_sha,
        "visibility": "PUBLIC_PROJECTION" if public else "PRIVATE_LOCAL_ONLY",
        "private_items_excluded": cur["excluded_private_count"],
        "visible_projection_sha256": points[-1]["visible_projection_sha256"],
        "population": {"total": scales["USER"]["total"],
                       "issues": scales["USER"]["issues"], "prs": scales["USER"]["prs"]},
        "rollups": scales,
        "history_points": points,
        "wave_semantics": "N/N+1 are distinct snapshots, never additive work-item totals",
        "delta": delta,
        "closure_authority": False, "merge_admission_authority": False,
        "root_causal_claims": "WITHHELD", "formal_credit_delta": 0,
    }


def csv_view(report: dict) -> str:
    """Long-form two-pulse table: one row per facet/point/scope, no raw titles."""
    buff = io.StringIO()
    writer = csv.writer(buff, lineterminator="\n")
    writer.writerow(["observed_at", "wave", "scope", "facet_dimension", "facet",
                     "count", "scope_denominator", "additive"])
    for point in report["history_points"]:
        for scope, roll in sorted(point["rollups"].items()):
            for dimension in ("primary_family", "single_composite", "peer_cohorts",
                              "topic_memberships_nonadditive", "cluster_memberships_nonadditive",
                              "code_memberships_nonadditive"):
                for name, number in sorted(roll[dimension].items()):
                    writer.writerow([point["observed_at"], point["wave"], scope,
                                     dimension, name, number, roll["total"],
                                     dimension in ("primary_family", "single_composite")])
    return buff.getvalue()

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--current", type=Path, required=True)
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--json-out", type=Path, required=True)
    ap.add_argument("--csv-out", type=Path)
    ap.add_argument("--parser-sha")
    ap.add_argument("--previous-parser-sha")
    ap.add_argument("--private-local", action="store_true",
                    help="Only for private owner-controlled local storage; public is default")
    a = ap.parse_args(argv)
    cur = json.loads(a.current.read_text(encoding="utf-8"))
    prev = json.loads(a.previous.read_text(encoding="utf-8")) if a.previous else None
    report = build(cur, prev, public=not a.private_local, parser_sha=a.parser_sha,
                   previous_parser_sha=a.previous_parser_sha)
    a.json_out.parent.mkdir(parents=True, exist_ok=True)
    a.json_out.write_bytes(canonical(report) + b"\n")
    if a.csv_out:
        a.csv_out.parent.mkdir(parents=True, exist_ok=True)
        a.csv_out.write_text(csv_view(report), encoding="utf-8", newline="\n")
    print("TAXONOMY_PULSE:", report["population"], report["delta"].get("reason"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
