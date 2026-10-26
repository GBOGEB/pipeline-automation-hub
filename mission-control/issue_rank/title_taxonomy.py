#!/usr/bin/env python3
"""Shared source-preserving title taxonomy for issues and PRs.

An advisory naming index, never owner-approved priority, engineering disposition,
acceptance, governance or closure. One item contributes once per primary family.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
import re

SCHEMA = "jade.title-taxonomy.v1"
ACTIONS = {
    "feat": "feat", "feature": "feat", "add": "feat",
    "fix": "fix", "bugfix": "fix", "hotfix": "fix", "repair": "fix",
    "test": "test", "tests": "test", "testing": "test",
    "ci": "ci", "cicd": "ci", "pipeline": "ci",
    "docs": "docs", "doc": "docs", "documentation": "docs",
    "metrics": "metrics", "metric": "metrics", "telemetry": "metrics",
    "chore": "chore", "build": "build", "perf": "perf", "performance": "perf",
    "refactor": "refactor", "style": "style", "revert": "revert",
    "security": "security", "release": "release", "governance": "governance",
    "source": "source", "triage": "triage", "program": "program",
}
PROGRAMS = {
    "qps": "QPS", "abacus": "ABACUS", "codex": "CODEX", "jade": "JADE",
    "jade-caste": "JADE", "mc": "MC", "missioncontrol": "MC",
    "mission-control": "MC", "gogreen": "GOGREEN", "everred": "EVERRED",
    "mycelium": "MYCELIUM", "mip": "MIP", "dmaic": "DMAIC", "rex": "REX",
    "cbd": "CBD", "bnb": "BNB", "bb": "BNB", "alat": "ALAT", "lkt": "LKT",
    "ggmath": "GGMATH", "gg-math": "GGMATH", "cbs": "CBS", "dow": "DOW",
    "keb": "KEB", "bd": "BD", "devops": "DEVOPS", "watch": "WATCH",
    "fpc": "FPC", "codepurple": "CODE_PURPLE", "code-purple": "CODE_PURPLE",
}

# Explicit vocabulary for non-exclusive semantic themes. The source is the
# title and labels only; these are heuristic associations, never typed edges.
TOPIC_FAMILIES = {
    "jade-devops": ("jade devops", "jade-devops", "jade/devops"),
    "gogreen": ("gogreen", "go green", "go-green"),
    "code-purple": ("code purple", "code-purple", "code_purple"),
    "everred": ("everred",), "p-process": ("p-process", "p proces", "p-proces"),
    "handover": ("handover", "hand-off", "handoff"),
    "watch": ("watch", "watcher"), "jade": ("jade", "jade temple"),
    "bread-butter": ("bread and butter", "bread & butter", "bnb"),
    "qps": ("qps", "cryoplant"), "mycelium": ("mycelium",),
    "federation": ("federation", "federated", "mesh"),
    "rtm": ("rtm", "requirements traceability"), "ocd": ("ocd",),
    "adr": ("adr",), "rfi": ("rfi",), "ldab": ("ldab", "lldb"),
    "dmaic": ("dmaic", "mip"), "testpilot": ("testpilot", "test pilot"),
}
TECHNICAL_CLUSTERS = {
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

def _matches(text: str, definitions: dict) -> list[str]:
    return sorted(key for key, aliases in definitions.items()
                  if any(re.search(r"(?<![a-z0-9])" + re.escape(alias.casefold())
                                   + r"(?![a-z0-9])", text.casefold())
                         for alias in aliases))

CODE = re.compile(
    r"(?:W\d+[A-Za-z0-9]*|N\+?\d+[A-Za-z0-9]*|C\d+[A-Za-z0-9]*"
    r"|U\d+[A-Za-z0-9]*|R\d+[A-Za-z0-9]*|J\d+[A-Za-z0-9]*"
    r"|G\d+[A-Za-z0-9]*|T\d+[A-Za-z0-9]*|P[0-4]|BDQ\d+|RTM-\d+"
    r"|(?:HV|NEG|ALAT|LKT|REX|HIST|CPQ|PAH|SOURCE|WCS|RTM)[-_A-Z0-9]+[0-9]+"
    r"|MACH-(?:I|II|III|IV|V|VI|VII|VIII|IX|X))\Z", re.I)
RANGE = re.compile(r"^(?:(?:N\+?|P|C|W|G)\d+)[-\u2013\u2014](?:(?:N\+?|P|C|W|G)\d+)$", re.I)
WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*")
SAFE_PATH = re.compile(r"^[A-Za-z0-9_+.-]+$")
MAX_CHARS, MAX_DEPTH, MAX_TOKENS = 240, 7, 18


def _canon(value: str) -> str:
    x = value.strip().strip("[](){}:;,.")
    if CODE.fullmatch(x) or RANGE.fullmatch(x):
        return x.upper().replace("\u2013", "-").replace("\u2014", "-")
    low = re.sub(r"[^a-z0-9]+", "-", x.lower()).strip("-")
    return PROGRAMS.get(low, low)


def _split_atom(token: str) -> list[str]:
    token = token.strip(".,:;")
    if not token:
        return []
    if re.fullmatch(r"W\d+[-/]C\d+", token, re.I):
        return [_canon(p) for p in re.split(r"[-/]", token)]
    if RANGE.fullmatch(token) or CODE.fullmatch(token):
        return [_canon(token)]
    if "-" in token and not re.fullmatch(r"\d+(?:-\d+)+", token):
        return [_canon(p) for p in token.split("-") if p]
    return [_canon(token)]


def _balanced(text: str, start: int):
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    for index in range(start, len(text)):
        char = text[index]
        if char in pairs:
            stack.append(pairs[char])
        elif char in (")", "]", "}"):
            if not stack or stack.pop() != char:
                return None, ""
            if not stack:
                return index, text[start + 1:index]
    return None, ""


def _scope_tokens(text: str, depth: int, warnings: list[str]) -> list[dict]:
    if depth > MAX_DEPTH:
        warnings.append("MAXIMUM_NESTING_DEPTH")
        return []
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in "([{":
            last, inner = _balanced(text, index)
            if last is None:
                warnings.append("UNBALANCED_SCOPE")
                return out
            out.extend(_scope_tokens(inner, depth + 1, warnings))
            index = last + 1
        elif char.isspace() or char in ",/+;":
            index += 1
        else:
            end = index
            while end < len(text) and not text[end].isspace() and text[end] not in "()[]{},/+;":
                end += 1
            out.extend({"value": t, "depth": depth, "source": "scope"}
                       for t in _split_atom(text[index:end]) if t)
            index = end
    return out


def _frontmatter(text: str, tags: list[dict], warnings: list[str]) -> str:
    rest = text
    while rest.startswith(("[", "(")):
        end, inner = _balanced(rest, 0)
        if end is None:
            warnings.append("UNBALANCED_LEADING_TAG")
            break
        tags.extend({"value": t["value"], "source": "bracket", "depth": t["depth"]}
                    for t in _scope_tokens(inner, 0, warnings))
        rest = rest[end + 1:].lstrip()
    for _ in range(5):
        m = WORD.match(rest)
        if not m or m.group(0).lower() not in ACTIONS:
            break
        action = m.group(0)
        end = m.end()
        scope = []
        if end < len(rest) and rest[end] == "(":
            close, inside = _balanced(rest, end)
            if close is None:
                warnings.append("UNBALANCED_CONVENTIONAL_SCOPE")
                break
            scope = _scope_tokens(inside, 1, warnings)
            end = close + 1
        after = rest[end:].lstrip()
        if not after.startswith(":"):
            break
        tags.append({"value": ACTIONS[action.lower()], "source": "conventional", "depth": 0})
        tags.extend(scope)
        rest = after[1:].lstrip()
    return rest


def parse_title(title: str | None, item_type: str | None = None, labels=()) -> dict:
    """Conservative prefix recursion: never infer primary family from body prose."""
    raw = title if isinstance(title, str) else ""
    text, warnings, flags, tags = raw.strip(), [], [], []
    if not text:
        return {"schema": SCHEMA, "family": "UNCLASSIFIED", "subfamily": None,
                "path": "UNCLASSIFIED", "prefix_segments": [], "raw_prefix": "",
                "remaining_title": "", "programmes": [], "codes": [], "priority": None,
                "policy_flags": [], "topic_families": [], "technical_clusters": [],
                "lint": ["EMPTY_TITLE"], "classification": "UNCLASSIFIED"}
    if len(text) > MAX_CHARS:
        warnings.append("TITLE_TOO_LONG_TRUNCATED_FOR_PARSING")
        text = text[:MAX_CHARS]
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    flag = re.match(r"^(?:[^\w\[]+\s*)?(?:DO\s+NOT\s+MERGE|NEVER\s+MERGE)\b", text, re.I)
    if flag:
        flags.append("DO_NOT_MERGE")
        text = re.sub(r"^\s*[\s:\-\u2013\u2014]+", "", text[flag.end():])
    text = _frontmatter(text, tags, warnings)
    # GitHub issue/title imports sometimes prepend Markdown heading fragments
    # to a second parenthesized qualifier: "metrics: #### ###(fix) ...".
    # Treat only explicitly recognized initial action/programme/code qualifiers
    # as taxonomy; never consume arbitrary parenthesized body prose.
    for _ in range(4):
        markdown = re.match(r"^(?:#{2,6}\s*)+", text)
        probe = text[markdown.end():].lstrip() if markdown else text
        if not probe.startswith(("(", "[")):
            break
        end, body = _balanced(probe, 0)
        if end is None:
            warnings.append("UNBALANCED_POSTFIX_QUALIFIER")
            break
        nested = _scope_tokens(body, 1, warnings)
        if not nested:
            break
        top = nested[0]["value"]
        if not (top.lower() in ACTIONS or top in PROGRAMS.values()
                or CODE.fullmatch(top)):
            break
        tags.extend({"value": x["value"], "depth": x["depth"],
                     "source": "postfix_qualifier"} for x in nested)
        text = probe[end + 1:].lstrip()
    m = re.match(r"^([^:\u2013\u2014]{1,90})([:\u2013\u2014])\s*", text)
    if m:
        clause = re.sub(r"(?i)\bCODE\s+PURPLE\b", "CODEPURPLE", m.group(1).strip().strip("- "))
        words = re.findall(r"[A-Za-z0-9_+.\-\u2013]+", clause)
        split = [p for w in words for p in _split_atom(w)]
        if split and (split[0] in PROGRAMS.values() or CODE.fullmatch(split[0])
                      or split[0].lower() in ACTIONS):
            for value in split[:MAX_TOKENS]:
                if value and SAFE_PATH.fullmatch(value):
                    tags.append({"value": value, "source": "leading_clause", "depth": 0})
            text = text[m.end():]
    if not tags and flags:
        m = re.match(r"^([A-Za-z0-9_-]+)", text)
        if m and (CODE.fullmatch(m.group(1)) or _canon(m.group(1)) in PROGRAMS.values()):
            tags.append({"value": _canon(m.group(1)), "source": "flag_context", "depth": 0})
    if not tags:
        m = re.match(r"^(P[0-4]|W\d+[A-Za-z0-9]*)\b", text, re.I)
        if m:
            tags.append({"value": _canon(m.group(1)), "source": "leading_code", "depth": 0})
    tags = tags[:MAX_TOKENS]
    actions, programmes, codes, priority = [], [], [], None
    for index, tag in enumerate(tags):
        s = tag["value"]
        if s.lower() in ACTIONS and (tag["source"] != "leading_clause" or index == 0):
            actions.append(ACTIONS[s.lower()])
        if s in PROGRAMS.values() and s not in programmes:
            programmes.append(s)
        if CODE.fullmatch(s) or RANGE.fullmatch(s):
            if s.startswith("P") and len(s) == 2 and s[1] in "01234" and priority is None:
                priority = s
            if s not in codes:
                codes.append(s)
    family = actions[0] if actions else "UNCLASSIFIED"
    segments = [family] + [tag["value"] for tag in tags
                           if tag["value"] and tag["value"] != family
                           and SAFE_PATH.fullmatch(tag["value"])]
    if family == "UNCLASSIFIED":
        warnings.append("NO_EXPLICIT_ACTION_FAMILY")
    if len(actions) > 1:
        warnings.append("NESTED_ACTION_FAMILIES_RETAINED")
    labels_text = " ".join(l if isinstance(l, str) else str(l.get("name", ""))
                           for l in (labels or []))
    semantic_text = raw + " " + labels_text
    topic_families = _matches(semantic_text, TOPIC_FAMILIES)
    technical_clusters = _matches(semantic_text, TECHNICAL_CLUSTERS)
    return {
        "schema": SCHEMA, "family": family,
        "subfamily": next((v for v in segments[1:] if v not in codes), None),
        "path": "/".join(segments[:MAX_TOKENS + 1]),
        "prefix_segments": tags, "raw_prefix": raw[:max(0, len(raw) - len(text))].strip(),
        "remaining_title": text.strip(), "programmes": programmes,
        "codes": codes, "priority": priority, "policy_flags": flags,
        "topic_families": topic_families,
        "technical_clusters": technical_clusters,
        "lint": sorted(set(warnings)),
        "classification": "EXPLICIT_ACTION" if actions else "CODES_ONLY" if tags else "UNCLASSIFIED",
    }


def summary(items: list[dict]) -> dict:
    """Mutually exclusive root families, overlapping ancestry and programme facets."""
    family = defaultdict(Counter)
    leaf = defaultdict(Counter)
    hierarchy = defaultdict(Counter)
    programmes = defaultdict(Counter)
    codes = defaultdict(Counter)
    topics = defaultdict(Counter)
    clusters = defaultdict(Counter)
    classifications, lint, types = Counter(), Counter(), Counter()
    for item in items:
        obj = item.get("title_taxonomy") or parse_title(item.get("title"), item.get("type"))
        kind = item.get("type", "Unknown")
        types[kind] += 1
        family[obj["family"]][kind] += 1
        leaf[obj["path"]][kind] += 1
        parts = obj["path"].split("/")
        for level in range(1, len(parts) + 1):
            hierarchy["/".join(parts[:level])][kind] += 1
        for name in set(obj["programmes"]):
            programmes[name][kind] += 1
        for name in set(obj["codes"]):
            codes[name][kind] += 1
        for name in set(obj.get("topic_families", [])):
            topics[name][kind] += 1
        for name in set(obj.get("technical_clusters", [])):
            clusters[name][kind] += 1
        classifications[obj["classification"]] += 1
        lint.update(obj["lint"])
    def compact(group):
        return {k: {"Issue": c.get("Issue", 0), "PullRequest": c.get("PullRequest", 0),
                    "total": sum(c.values())} for k, c in sorted(group.items())}
    return {
        "schema": SCHEMA, "total": len(items), "issues": types.get("Issue", 0),
        "prs": types.get("PullRequest", 0), "family": compact(family),
        "leaf_clusters": compact(leaf), "hierarchy_nodes_nonadditive": compact(hierarchy),
        "programmes_nonexclusive": compact(programmes),
        "codes_nonexclusive": compact(codes),
        "topic_families_nonexclusive": compact(topics),
        "technical_clusters_nonexclusive": compact(clusters),
        "classification": dict(sorted(classifications.items())),
        "lint": dict(sorted(lint.items())), "family_counts_additive_only": True,
        "hierarchy_nodes_additive": False, "merge_admission_authority": False,
        "formal_credit_delta": 0,
    }


def associated_families(items: list[dict], edges: list[dict], max_hops: int = 2) -> dict:
    """Up to two graph hops, sourced candidate labels; no destructive inheritance."""
    if not 0 <= max_hops <= 3:
        raise ValueError("bounded recursion required")
    by_key = {i["key"]: i for i in items}
    adjacent = defaultdict(list)
    for e in edges:
        src, dst = e["source"], e["target"]
        if src in by_key and dst in by_key:
            adjacent[src].append((dst, e["kind"]))
            adjacent[dst].append((src, e["kind"]))
    result = {}
    for start in by_key:
        seen, visited, queue = {}, {start}, deque([(start, 0)])
        while queue:
            source, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for target, edge_type in sorted(adjacent[source]):
                if target in visited:
                    continue
                visited.add(target)
                queue.append((target, depth + 1))
                obj = by_key[target].get("title_taxonomy") or parse_title(by_key[target].get("title"))
                family = obj["family"]
                if family == "UNCLASSIFIED":
                    continue
                candidate = {"family": family, "source_item": target,
                             "hops": depth + 1, "edge_kind": edge_type,
                             "grade": "UNVERIFIED_ASSOCIATION_ONLY"}
                old = seen.get(family)
                if old is None or (candidate["hops"], target) < (old["hops"], old["source_item"]):
                    seen[family] = candidate
        result[start] = sorted(seen.values(), key=lambda x: (x["hops"], x["family"], x["source_item"]))
    return result
