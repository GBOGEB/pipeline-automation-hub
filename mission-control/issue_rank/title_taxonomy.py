#!/usr/bin/env python3
"""Shared read-only PR/issue title facets for issue_rank. No admission/closure authority.

Facets are observational projections of existing titles/labels. A missing facet stays
unclassified. Link inheritance is limited to explicit CHILD/PARENT graph edges and
never changes action type, title, scope, gate or owner authority.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

SCHEMA = "jade.issue-rank.title-taxonomy.v1"
TYPES = frozenset({
    "fix", "feat", "ci", "docs", "test", "refactor", "perf", "build",
    "chore", "revert", "style", "security", "ops", "release", "data",
    "research", "metrics", "program",
})
TYPE_ALIASES = {
    "doc": "docs", "documentation": "docs", "feature": "feat",
    "bugfix": "fix", "hotfix": "fix", "tests": "test", "metric": "metrics",
}
SCOPE_ALIASES = {
    "jade devops": "jade-devops", "jade_devops": "jade-devops",
    "jade/devops": "jade-devops", "jade-dev-ops": "jade-devops",
    "p-proces": "p-process", "p-proceses": "p-process",
    "p_process": "p-process", "p process": "p-process",
    "go green": "gogreen", "go-green": "gogreen",
    "code purple": "code-purple", "code_purple": "code-purple",
    "bread and butter": "bread-butter", "bread & butter": "bread-butter",
    "b&b": "bread-butter", "bd": "burndown",
}
KNOWN_SCOPES = frozenset({
    "handover", "gogreen", "jade-devops", "jade", "watch", "p-process",
    "everred", "code-purple", "qps", "burndown", "security",
    "governance", "coverage", "deps-pip", "deps-npm", "mycelium",
    "testpilot", "rtm", "ocd", "adr", "cost", "releases", "depth",
    "metrics", "federation", "ci", "docs",
})
# Not mutually exclusive. Distinguish families from technical clusters.
FAMILIES = {
    "jade-devops": ("jade devops", "jade-devops", "jade/devops"),
    "gogreen": ("gogreen", "go green", "go-green"),
    "code-purple": ("code purple", "code-purple", "code_purple"),
    "everred": ("everred",),
    "p-process": ("p-process", "p proces", "p-proces", "p_process"),
    "handover": ("handover", "hand-off", "handoff"),
    "watch": ("watch", "watcher"),
    "jade": ("jade", "jade temple", "jade_temple"),
    "bread-butter": ("bread and butter", "bread & butter", "bnb"),
    "qps": ("qps", "cryoplant"),
    "mycelium": ("mycelium",),
    "federation": ("federation", "federated", "mesh"),
    "rtm": ("rtm", "requirements traceability"),
    "ocd": ("ocd",),
    "adr": ("adr",),
    "rfi": ("rfi",),
    "ldab": ("ldab", "lldb"),
    "dmaic": ("dmaic", "mip"),
    "testpilot": ("testpilot", "test pilot"),
}
CLUSTERS = {
    "census": ("census", "recensus", "inventory"),
    "telemetry": ("telemetry", "metrics", "statistics", "dashboard", "kpi"),
    "integrity": ("integrity", "hash chain", "hash-chain", "signed payload", "outbox"),
    "fail-closed": ("fail closed", "fail-closed", "missing blob", "missing blobs"),
    "governance": ("governance", "ruleset", "protection", "branch protection"),
    "admission": ("admission", "merge gate", "required gate", "canary"),
    "first-red": ("first red", "first-red", "root red", "root-red"),
    "coverage": ("coverage", "changed line", "changed-line"),
    "security": ("security", "codeql", "bandit", "privacy", "secret"),
    "review": ("review", "approval", "disposition"),
    "ci": ("ci", "workflow", "runner", "checks"),
    "handover": ("handover", "handoff", "lossless"),
    "release": ("release", "point release", "deployment", "publish", "pages"),
    "dependencies": ("dependabot", "dependency", "dependencies", "deps"),
    "documentation": ("documentation", "docs", "readme"),
    "cost": ("commercial", "cost", "capex", "opex", "pricing", "mto"),
    "engineering": ("mass flow", "thermal", "cryogenic", "icd", "fat", "sat"),
    "source": ("master_input", "source-bound", "provenance", "sha", "receipt"),
    "retirement": ("retire", "supersede", "archive"),
}
PREFIX = re.compile(
    r"^\s*(?:\[[^\]]{1,40}\]\s*)*"
    r"(?P<action>[A-Za-z][A-Za-z0-9-]{1,30})"
    r"(?:\((?P<scope>[^()]{1,90})\))?"
    r"(?P<breaking>!)?:\s*(?P<description>\S.+)$"
)
BRACKETS = re.compile(r"\[([^\[\]]{1,40})\]")
WAVES = re.compile(r"(?<![A-Za-z0-9])(?:W\d{1,4}|N\+?\d{1,4})(?![A-Za-z0-9])", re.I)
GATES = re.compile(r"(?<![A-Za-z0-9])H(?:0?[1-9]|1[0-2])(?![A-Za-z0-9])", re.I)
PRIORITY = re.compile(r"(?<![A-Za-z0-9])P[0-4](?![A-Za-z0-9])", re.I)


def slug(value: str) -> str:
    value = value.casefold().strip().replace("&", " and ")
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", value)).strip("-")


def canonical_scope(value: str) -> str:
    low = value.casefold().strip()
    return SCOPE_ALIASES.get(low, slug(low))


def _contains(haystack: str, phrase: str) -> bool:
    # Prevent 'watch' matching 'watchdog', 'ci' matching 'specific', etc.
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase.casefold()) + r"(?![a-z0-9])",
                     haystack.casefold()) is not None


def _matches(haystack: str, patterns: dict) -> list[str]:
    return sorted(k for k, aliases in patterns.items()
                  if any(_contains(haystack, alias) for alias in aliases))


def classify_title(title: str | None, labels=(), item_type: str = "Issue") -> dict:
    """Extract orthogonal facets without asserting missing/legacy types."""
    title = title or ""
    labels = [x if isinstance(x, str) else str(x.get("name", "")) for x in (labels or [])]
    m = PREFIX.match(title)
    recognized = bool(m and (m.group("action").casefold() in TYPES
                              or m.group("action").casefold() in TYPE_ALIASES))
    action_type = ("unclassified" if not recognized else
                   TYPE_ALIASES.get(m.group("action").casefold(),
                                    m.group("action").casefold()))
    raw_scope = m.group("scope").strip() if recognized and m.group("scope") else ""
    scope = canonical_scope(raw_scope) if raw_scope else "unclassified"
    label_text = " ".join(labels)
    scope_text = raw_scope.replace("_", " ") if raw_scope else ""
    text = " ".join((title, scope_text, label_text)).casefold()
    families = _matches(text, FAMILIES)
    if scope in FAMILIES and scope not in families:
        families.append(scope)
    families.sort()
    clusters = _matches(text, CLUSTERS)
    tags = sorted(set(t.strip() for t in BRACKETS.findall(title) if t.strip()))
    waves = sorted(set(x.upper() for x in WAVES.findall(title)))
    gates = sorted(set(x.upper() for x in GATES.findall(title)))
    prios = sorted(set(x.upper() for x in PRIORITY.findall(title)))
    warnings = []
    if not recognized:
        warnings.append("legacy-or-untyped-title")
    if recognized and not raw_scope:
        warnings.append("missing-scope")
    if raw_scope and scope not in KNOWN_SCOPES:
        warnings.append("unregistered-scope")
    if raw_scope and scope != slug(raw_scope):
        warnings.append("scope-alias")
    if recognized and m.group("action").casefold() != action_type:
        warnings.append("type-alias")
    primary_family = (scope if scope in families else families[0]) if families else "unclassified"
    primary_cluster = clusters[0] if clusters else "unclassified"
    return {
        "schema": SCHEMA, "item_kind": item_type, "action_type": action_type,
        "scope": scope, "raw_scope": raw_scope,
        "families": families, "clusters": clusters,
        "primary_family": primary_family, "primary_cluster": primary_cluster,
        "composite": "/".join((action_type, scope, primary_family, primary_cluster)),
        "bracket_ids": tags, "waves": waves, "gates": gates, "priorities": prios,
        "breaking": bool(recognized and m.group("breaking")),
        "classification": "explicit-prefix" if recognized else "inferred-keywords",
        "inherited_from": None, "lint": warnings,
    }


def inherit_parent_families(items: list[dict], edges: list[dict]) -> None:
    """Fill only missing *family* from a unique explicit parent; cycles remain bounded.

    A child with two differently classified parents is ambiguous, not arbitrarily
    assigned. Never infer action_type, scope, work state, approval or gate success.
    """
    by_key = {x["key"]: x for x in items}
    parents = defaultdict(set)
    for edge in edges:
        if edge.get("kind") == "PARENT":
            child, parent = edge.get("source"), edge.get("target")
        elif edge.get("kind") == "CHILD":
            child, parent = edge.get("target"), edge.get("source")
        else:
            continue
        if child != parent and child in by_key and parent in by_key:
            parents[child].add(parent)
    for _ in range(len(by_key)):
        changed = False
        for key in sorted(by_key):
            child = by_key[key]
            facet = child["taxonomy"]
            if child["type"] != "Issue" or facet["families"]:
                continue
            sources = [(p, by_key[p]["taxonomy"]["primary_family"])
                       for p in sorted(parents[key])
                       if by_key[p]["taxonomy"]["primary_family"] != "unclassified"]
            candidates = {family for _, family in sources}
            if len(candidates) > 1:
                if "ambiguous-parent-family" not in facet["lint"]:
                    facet["lint"].append("ambiguous-parent-family")
            elif len(candidates) == 1:
                family = next(iter(candidates))
                facet["families"] = [family]
                facet["primary_family"] = family
                facet["inherited_from"] = sources[0][0]
                facet["classification"] = "inherited-parent"
                facet["composite"] = "/".join((facet["action_type"], facet["scope"],
                                                family, facet["primary_cluster"]))
                changed = True
        if not changed:
            break


def rollup(items: list[dict]) -> dict:
    """Taxonomy memberships may be multi-label; never add them as item totals."""
    types, scopes, families, clusters, composites, peers, lint = (Counter() for _ in range(7))
    by_kind = defaultdict(Counter)
    for item in items:
        f = item["taxonomy"]
        types[f["action_type"]] += 1
        scopes[f["scope"]] += 1
        composites[f["composite"]] += 1
        by_kind[item["type"]][f["action_type"]] += 1
        peers[f'{item["type"]}|{f["action_type"]}|{f["primary_family"]}'] += 1
        families.update(f["families"] or ["unclassified"])
        clusters.update(f["clusters"] or ["unclassified"])
        lint.update(f["lint"])
    return {
        "schema": SCHEMA, "denominator": len(items),
        "type_counts": dict(sorted(types.items())),
        "scope_counts": dict(sorted(scopes.items())),
        "family_memberships": dict(sorted(families.items())),
        "cluster_memberships": dict(sorted(clusters.items())),
        "composite_counts": dict(sorted(composites.items())),
        "peer_cohorts": dict(sorted(peers.items())),
        "by_kind_type_counts": {k: dict(sorted(v.items())) for k, v in sorted(by_kind.items())},
        "lint_counts": dict(sorted(lint.items())),
        "typed_prefix_rate": (round((len(items) - types["unclassified"]) / len(items), 4)
                              if items else None),
        "inherited_count": sum(bool(x["taxonomy"]["inherited_from"]) for x in items),
        "multi_label_counts_are_not_additive": True,
    }
