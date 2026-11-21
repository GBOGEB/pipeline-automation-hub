"""Read-only ROOT NEXT -> CONTROL evidence consumer.

This module is a projection, not an issue owner, status publisher or deployment
authority. Claimed PASS records are candidate evidence, never verified closure.
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

SCHEMA = "jade.root-next-control.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+$")
KINDS = {
    "library": ("source", "issue_pr", "native", "security", "review", "merge",
                "release", "control"),
    "engineering_document": ("source", "issue_pr", "native", "review", "merge",
                             "artifact", "owner_acceptance", "control"),
    "hosted_application": ("source", "issue_pr", "native", "security", "review",
                           "merge", "release", "deploy", "operate", "control"),
}
DECISIONS = frozenset(("PASS", "PENDING", "NOT_APPLICABLE"))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def link(value):
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if (parts.scheme != "https" or parts.hostname != "github.com"
            or parts.username or parts.password or parts.port or not parts.path):
        return None
    return value


def project(doc, private_repos=()):
    """Validate source-bound obligations and emit public-safe unresolved gates.

    No evidence declaration, including a complete set of PASS values, is
    authorization to mark a source root CLOSED. Verification/acceptance are
    separately controlled by native source owners and human reviewers.
    """
    if doc is None:
        return {"schema": SCHEMA, "status": "NOT_SUPPLIED", "items": [],
                "private_aggregate": 0, "total": 0, "closure_verified": 0,
                "actionable": 0, "gate_deficits": {}}
    need(isinstance(doc, dict) and doc.get("schema") == SCHEMA, "root next schema")
    rows = doc.get("items")
    need(isinstance(rows, list), "root next items must be list")
    # A cohort-level source identity may bind a bounded one-repository pilot.
    # Source equality is necessary, but still not independently verified DoV.
    scope_commit = doc.get("source_commit")
    scope_blob = doc.get("source_blob_sha")
    need(scope_commit is None or (isinstance(scope_commit, str)
         and bool(HEX40.fullmatch(scope_commit))), "cohort source commit")
    need(scope_blob is None or (isinstance(scope_blob, str)
         and bool(HEX40.fullmatch(scope_blob))), "cohort source blob")
    need((scope_commit is None) == (scope_blob is None),
         "cohort commit and blob must be supplied together")
    # GitHub repository identity is case-insensitive; public projection must not
    # leak a controlled owner through differently cased input spellings.
    private = {name.casefold() for name in private_repos}
    ids = set()
    out = []
    private_count = 0
    deficits = Counter()
    for row in rows:
        need(isinstance(row, dict), "root next item must be object")
        repo = row.get("repo")
        need(isinstance(repo, str) and REPO.fullmatch(repo), "owner repository")
        root_id = row.get("root_id")
        need(isinstance(root_id, str) and bool(root_id.strip()) and root_id not in ids,
             "unique root id")
        ids.add(root_id)
        if repo.casefold() in private or row.get("private") is True:
            # Do not copy source paths, SHA, issues, owners, notes or receipts.
            private_count += 1
            deficits["PRIVATE_OWNER_VERIFICATION"] += 1
            continue
        source = row.get("root_source")
        need(isinstance(source, dict), "root source object")
        need(isinstance(source.get("path"), str)
             and source["path"] == "README.md", "source must be root README")
        need(type(source.get("line")) is int and source["line"] > 0,
             "positive root line number")
        need(isinstance(source.get("blob_sha"), str)
             and HEX40.fullmatch(source["blob_sha"]), "exact blob identity")
        if scope_blob is not None:
            need(source["blob_sha"] == scope_blob,
                 "root README blob conflicts with cohort source identity")
        kind = row.get("kind")
        need(kind in KINDS, "product class")
        owner = row.get("owner")
        need(isinstance(owner, str) and bool(owner.strip()), "accountable owner")
        issues = row.get("issue_pr")
        need(isinstance(issues, list) and bool(issues)
             and all(link(u) for u in issues), "canonical GitHub issues/PR links")
        depends = row.get("prerequisites", [])
        need(isinstance(depends, list) and all(isinstance(d, str) and d for d in depends),
             "typed prerequisites")
        gates = row.get("gates", {})
        need(isinstance(gates, dict)
             and set(gates).issubset(set(KINDS[kind])), "gate contract keys")
        pending = []
        declarations = 0
        for gate in KINDS[kind]:
            item = gates.get(gate)
            if not isinstance(item, dict) or item.get("decision") not in DECISIONS:
                pending.append(gate)
                deficits[gate] += 1
                continue
            decision = item["decision"]
            if decision == "PENDING":
                pending.append(gate)
                deficits[gate] += 1
            elif decision == "PASS":
                need(link(item.get("receipt_url")) is not None
                     and isinstance(item.get("head_sha"), str)
                     and HEX40.fullmatch(item["head_sha"]),
                     "PASS needs exact SHA and GitHub receipt")
                declarations += 1
            else:
                need(gate not in ("source", "issue_pr", "review", "control"),
                     "foundational gate cannot be NOT_APPLICABLE")
                need(isinstance(item.get("reason"), str) and bool(item["reason"].strip())
                     and isinstance(item.get("decision_owner"), str)
                     and bool(item["decision_owner"].strip())
                     and link(item.get("receipt_url")) is not None,
                     "NOT_APPLICABLE needs reason, owner and decision receipt")
                declarations += 1
        next_action = row.get("next_action")
        need(isinstance(next_action, str) and bool(next_action.strip()), "next action")
        out.append({
            "root_id": root_id, "repo": repo, "root_source": source,
            "source_commit": scope_commit,
            "kind": kind, "owner": owner, "issue_pr": issues,
            "prerequisites": depends, "next_action": next_action,
            "gate_candidates": declarations, "gate_total": len(KINDS[kind]),
            "pending_gates": pending,
            "status": "EVIDENCE_CANDIDATE_UNVERIFIED" if not pending
                      else "PROOF_REQUIRED",
            "closure_verified": False,
        })
    return {"schema": SCHEMA, "status": "READ_ONLY_PROJECTION",
            "items": out, "private_aggregate": private_count,
            "total": len(rows), "closure_verified": 0, "actionable": len(out),
            "gate_deficits": dict(sorted(deficits.items())),
            "authority_transfer": False, "merge_admission": "WITHHELD"}
