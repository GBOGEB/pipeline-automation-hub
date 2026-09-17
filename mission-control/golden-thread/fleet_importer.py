#!/usr/bin/env python3
"""Golden Thread P4: controlled, read-only GitHub fleet occurrence importer.

The importer consumes an explicit scope manifest, fetches current GitHub issue
snapshots, normalizes them deterministically, and appends Golden Thread OBSERVED
events only when source state is new or changed.

P0 is reused for transaction/obligation identity. P3 remains responsible for
checkpoint cadence. This module performs no GitHub writes and grants no
classification, closure, engineering, compliance, release or visual-fidelity
credit.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import golden_thread as gt
import side_effect_receipts as sr

SCOPE_SCHEMA = "missioncontrol.golden_thread_fleet_import_scope.v1"
REGISTRY_SCHEMA = "missioncontrol.golden_thread_fleet_import_registry.v1"
RECEIPT_SCHEMA = "missioncontrol.golden_thread_fleet_import_receipt.v1"
NORMALIZED_SCHEMA = "missioncontrol.github_issue_normalized.v1"


class FleetImportError(ValueError):
    pass


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _seal_registry(registry: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(registry)
    out.pop("registry_digest", None)
    out["registry_digest"] = gt.digest(out)
    return out


def _verify_registry_digest(registry: Dict[str, Any]) -> None:
    body = copy.deepcopy(registry)
    supplied = body.pop("registry_digest", None)
    if supplied != gt.digest(body):
        raise FleetImportError("fleet import registry digest mismatch")


def normalize_scope(scope: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(scope, dict) or scope.get("schema") != SCOPE_SCHEMA:
        raise FleetImportError("fleet import scope schema mismatch")
    if scope.get("read_only") is not True:
        raise FleetImportError("fleet import scope must be read_only=true")
    if scope.get("authority_transfer") is not False:
        raise FleetImportError("fleet import scope authority_transfer must remain false")
    if scope.get("classification_credit") not in (0, False):
        raise FleetImportError("fleet importer may not grant classification credit")
    if scope.get("visual_fidelity_credit") is not False:
        raise FleetImportError("fleet importer may not grant visual fidelity credit")
    max_items = scope.get("max_items")
    if not isinstance(max_items, int) or max_items < 1 or max_items > 100:
        raise FleetImportError("scope max_items must be between 1 and 100")
    sources = scope.get("sources")
    if not isinstance(sources, list) or not sources:
        raise FleetImportError("scope sources must be a non-empty list")
    normalized_sources: List[Dict[str, Any]] = []
    total = 0
    for source in sources:
        if not isinstance(source, dict):
            raise FleetImportError("scope source must be an object")
        repo = source.get("repository")
        nums = source.get("issue_numbers")
        if not isinstance(repo, str) or repo.count("/") != 1:
            raise FleetImportError("scope repository must be owner/repo")
        if not isinstance(nums, list) or not nums or any(not isinstance(n, int) or n < 1 for n in nums):
            raise FleetImportError("scope issue_numbers must be positive integers")
        unique = sorted(set(nums))
        total += len(unique)
        normalized_sources.append({"repository": repo, "issue_numbers": unique})
    if total > max_items:
        raise FleetImportError("scope item count exceeds max_items")
    out = {
        "schema": SCOPE_SCHEMA,
        "read_only": True,
        "max_items": max_items,
        "include_pull_requests": bool(scope.get("include_pull_requests", False)),
        "sources": sorted(normalized_sources, key=lambda x: x["repository"]),
        "classification_credit": 0,
        "engineering_credit": 0,
        "compliance_credit": 0,
        "release_credit": 0,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    out["scope_digest"] = gt.digest(out)
    return out


def normalize_issue(repository: str, issue: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(issue, dict):
        raise FleetImportError("GitHub issue payload must be an object")
    number = issue.get("number")
    if not isinstance(number, int) or number < 1:
        raise FleetImportError("GitHub issue number invalid")
    labels = issue.get("labels") or []
    assignees = issue.get("assignees") or []
    is_pr = isinstance(issue.get("pull_request"), dict)
    body = issue.get("body")
    normalized = {
        "schema": NORMALIZED_SCHEMA,
        "source_key": f"{repository}#{number}",
        "repository": repository,
        "number": number,
        "github_id": issue.get("id"),
        "github_node_id": issue.get("node_id"),
        "title": issue.get("title") or "",
        "state": issue.get("state"),
        "state_reason": issue.get("state_reason"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "closed_at": issue.get("closed_at"),
        "html_url": issue.get("html_url"),
        "api_url": issue.get("url"),
        "labels": sorted(
            str(item.get("name"))
            for item in labels
            if isinstance(item, dict) and item.get("name") is not None
        ),
        "assignees": sorted(
            str(item.get("login"))
            for item in assignees
            if isinstance(item, dict) and item.get("login") is not None
        ),
        "milestone_number": (
            issue.get("milestone", {}).get("number")
            if isinstance(issue.get("milestone"), dict)
            else None
        ),
        "is_pull_request": is_pr,
        "body_sha256": None if body is None else _digest_bytes(str(body).encode("utf-8")),
    }
    normalized["source_snapshot_digest"] = gt.digest(normalized)
    return normalized


def import_intent(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    digest = snapshot.get("source_snapshot_digest")
    return {
        "authority_domain": snapshot["repository"],
        "action": "GITHUB_ISSUE_IMPORT",
        "target": snapshot["source_key"],
        "mechanism": "REG",
        "source_state_digest": digest,
        "payload_digest": digest,
        "schema_version": NORMALIZED_SCHEMA,
        "expected_semantic_delta": "APPEND_OBSERVATION_ONLY",
    }


def empty_registry(scope: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_scope(scope)
    registry = {
        "schema": REGISTRY_SCHEMA,
        "scope_digest": normalized["scope_digest"],
        "sources": {},
        "obligation_heads": {},
        "source_write_count": 0,
        "classification_credit": 0,
        "engineering_credit": 0,
        "compliance_credit": 0,
        "release_credit": 0,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    return _seal_registry(registry)


def verify_registry(registry: Dict[str, Any], scope: Dict[str, Any]) -> Dict[str, Any]:
    normalized_scope = normalize_scope(scope)
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise FleetImportError("fleet import registry schema mismatch")
    if registry.get("scope_digest") != normalized_scope["scope_digest"]:
        raise FleetImportError("fleet import registry scope mismatch")
    if registry.get("authority_transfer") is not False:
        raise FleetImportError("fleet import registry authority_transfer must remain false")
    if registry.get("source_write_count") != 0:
        raise FleetImportError("fleet importer must remain read-only")
    for credit in ("classification_credit", "engineering_credit", "compliance_credit", "release_credit"):
        if registry.get(credit) not in (0, False):
            raise FleetImportError(f"fleet importer may not grant {credit}")
    if registry.get("visual_fidelity_credit") is not False:
        raise FleetImportError("fleet importer may not grant visual fidelity credit")
    if not isinstance(registry.get("sources"), dict) or not isinstance(registry.get("obligation_heads"), dict):
        raise FleetImportError("fleet import registry mappings missing")
    _verify_registry_digest(registry)
    event_ids = set()
    tx_ids = set()
    lineage_edges = 0
    for source_key, source in registry["sources"].items():
        if source.get("source_key") != source_key:
            raise FleetImportError("fleet source registry key mismatch")
        history = source.get("history")
        if not isinstance(history, list) or not history:
            raise FleetImportError("fleet source history missing")
        prior_tx = None
        for row in history:
            tx_id = row.get("transaction_id")
            event_id = row.get("event_id")
            if tx_id in tx_ids or event_id in event_ids:
                raise FleetImportError("duplicate fleet import transaction/event identity")
            tx_ids.add(tx_id)
            event_ids.add(event_id)
            if row.get("parent_transaction_id") != prior_tx:
                raise FleetImportError("fleet import successor chain mismatch")
            if row.get("obligation_id") != source.get("obligation_id"):
                raise FleetImportError("fleet import obligation mismatch")
            prior_tx = tx_id
            if row.get("parent_transaction_id"):
                lineage_edges += 1
        if source.get("current_transaction_id") != prior_tx:
            raise FleetImportError("fleet source current transaction mismatch")
        if source.get("current_snapshot_digest") != history[-1].get("source_snapshot_digest"):
            raise FleetImportError("fleet source current snapshot mismatch")
        if registry["obligation_heads"].get(source["obligation_id"]) != prior_tx:
            raise FleetImportError("fleet obligation head mismatch")
    return {
        "schema": "missioncontrol.golden_thread_fleet_import_registry_verification.v1",
        "status": "PASS",
        "source_count": len(registry["sources"]),
        "transaction_count": len(tx_ids),
        "lineage_edge_count": lineage_edges,
        "registry_digest": registry["registry_digest"],
        "source_write_count": 0,
        "authority_transfer": False,
    }


def _event_id(transaction_id: str) -> str:
    return "GTI-" + transaction_id.split(":", 1)[-1][:20].upper()


def _observation_event(snapshot: Dict[str, Any], tx_id: str, recorded_at: str, first_import: bool) -> Dict[str, Any]:
    occurred_at = snapshot.get("updated_at") or snapshot.get("created_at") or recorded_at
    payload = {
        "object_type": "occurrence",
        "source_key": snapshot["source_key"],
        "source_snapshot_digest": snapshot["source_snapshot_digest"],
        "github_node_id": snapshot.get("github_node_id"),
        "title": snapshot.get("title"),
        "source_state": snapshot.get("state"),
        "source_state_reason": snapshot.get("state_reason"),
        "source_created_at": snapshot.get("created_at"),
        "source_updated_at": snapshot.get("updated_at"),
        "source_closed_at": snapshot.get("closed_at"),
        "labels": snapshot.get("labels", []),
        "assignees": snapshot.get("assignees", []),
        "milestone_number": snapshot.get("milestone_number"),
        "body_sha256": snapshot.get("body_sha256"),
        "import_transaction_id": tx_id,
        "import_state": "UNCLASSIFIED_READER_REQUIRED",
        "classification_credit": 0,
    }
    event = {
        "event_id": _event_id(tx_id),
        "event_type": "BOOTSTRAP_RECONSTRUCTED" if first_import else "OBSERVED",
        "occurred_at": occurred_at,
        "recorded_at": recorded_at,
        "actor": "MissionControl.FleetImporter",
        "subject_ref": snapshot["source_key"],
        "authority_domain": snapshot["repository"],
        "evidence_class": "LIVE_GITHUB_IMPORT",
        "evidence_refs": [snapshot.get("html_url") or snapshot.get("api_url") or snapshot["source_key"]],
        "source_snapshot_digest": snapshot["source_snapshot_digest"],
        "non_compensating_preserved": True,
        "payload": payload,
    }
    if first_import:
        event.update(
            {
                "observed_source_timestamp": occurred_at,
                "reconstruction_timestamp": recorded_at,
                "reconstruction_method": "live_github_current_state_import",
            }
        )
    return event


def import_snapshots(
    ledger: Dict[str, Any],
    registry: Dict[str, Any],
    scope: Dict[str, Any],
    snapshots: Iterable[Dict[str, Any]],
    *,
    recorded_at: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    gt.verify_ledger(ledger)
    verify_registry(registry, scope)
    normalized_scope = normalize_scope(scope)
    allowed = {
        f"{source['repository']}#{number}"
        for source in normalized_scope["sources"]
        for number in source["issue_numbers"]
    }
    incoming = sorted(list(snapshots), key=lambda x: x["source_key"])
    if len(incoming) > normalized_scope["max_items"]:
        raise FleetImportError("incoming snapshot count exceeds scope max_items")
    if any(snapshot.get("source_key") not in allowed for snapshot in incoming):
        raise FleetImportError("incoming snapshot is outside governed import scope")
    if not normalized_scope["include_pull_requests"] and any(snapshot.get("is_pull_request") for snapshot in incoming):
        raise FleetImportError("pull request encountered while include_pull_requests=false")

    out_registry = copy.deepcopy(registry)
    raw_ledger = copy.deepcopy(ledger)
    raw_ledger.pop("head_event_digest", None)
    added: List[Dict[str, Any]] = []
    replayed: List[str] = []
    for snapshot in incoming:
        if snapshot.get("schema") != NORMALIZED_SCHEMA:
            raise FleetImportError("incoming snapshot schema mismatch")
        if snapshot.get("source_snapshot_digest") != gt.digest({k: v for k, v in snapshot.items() if k != "source_snapshot_digest"}):
            raise FleetImportError("incoming source snapshot digest mismatch")
        intent = import_intent(snapshot)
        tx_id = sr.transaction_id(intent)
        obligation_id = sr.obligation_id(intent)
        source_key = snapshot["source_key"]
        current = out_registry["sources"].get(source_key)
        if current and current.get("current_transaction_id") == tx_id:
            replayed.append(source_key)
            continue
        parent_tx = current.get("current_transaction_id") if current else None
        if current and current.get("obligation_id") != obligation_id:
            raise FleetImportError("source obligation identity changed unexpectedly")
        event = _observation_event(snapshot, tx_id, recorded_at, first_import=current is None)
        raw_ledger.setdefault("events", []).append(event)
        row = {
            "transaction_id": tx_id,
            "obligation_id": obligation_id,
            "parent_transaction_id": parent_tx,
            "event_id": event["event_id"],
            "source_snapshot_digest": snapshot["source_snapshot_digest"],
            "recorded_at": recorded_at,
        }
        if current is None:
            current = {
                "source_key": source_key,
                "repository": snapshot["repository"],
                "number": snapshot["number"],
                "obligation_id": obligation_id,
                "history": [],
            }
            out_registry["sources"][source_key] = current
        current["history"].append(row)
        current["current_transaction_id"] = tx_id
        current["current_snapshot_digest"] = snapshot["source_snapshot_digest"]
        out_registry["obligation_heads"][obligation_id] = tx_id
        added.append(row)

    sealed = gt.seal(raw_ledger)
    out_registry = _seal_registry(out_registry)
    verify_registry(out_registry, scope)
    gt.verify_ledger(sealed)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "scope_digest": normalized_scope["scope_digest"],
        "input_snapshot_count": len(incoming),
        "added_event_count": len(added),
        "replayed_snapshot_count": len(replayed),
        "added": added,
        "replayed_source_keys": replayed,
        "before_head_event_digest": ledger.get("head_event_digest"),
        "after_head_event_digest": sealed.get("head_event_digest"),
        "registry_digest": out_registry["registry_digest"],
        "source_write_count": 0,
        "classification_credit": 0,
        "engineering_credit": 0,
        "compliance_credit": 0,
        "release_credit": 0,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    receipt["receipt_digest"] = gt.digest(receipt)
    return sealed, out_registry, receipt


class GitHubIssueReader:
    def __init__(self, token: Optional[str] = None):
        self.token = token

    def get_issue(self, repository: str, number: int) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{repository}/issues/{number}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GBOGEB-Golden-Thread-P4",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FleetImportError(f"GitHub GET {repository}#{number} failed {exc.code}: {detail}") from exc


def fetch_scope(scope: Dict[str, Any], token: Optional[str] = None) -> List[Dict[str, Any]]:
    normalized_scope = normalize_scope(scope)
    reader = GitHubIssueReader(token)
    snapshots: List[Dict[str, Any]] = []
    for source in normalized_scope["sources"]:
        for number in source["issue_numbers"]:
            issue = reader.get_issue(source["repository"], number)
            snapshot = normalize_issue(source["repository"], issue)
            if snapshot["is_pull_request"] and not normalized_scope["include_pull_requests"]:
                raise FleetImportError(f"scope source resolved to pull request: {snapshot['source_key']}")
            snapshots.append(snapshot)
    return sorted(snapshots, key=lambda x: x["source_key"])


def _load(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FleetImportError(f"{path}: top-level JSON must be an object")
    return value


def _dump(value: Any, path: Optional[Path] = None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path:
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("scope", type=Path)
    p.add_argument("--token-env", default="GITHUB_TOKEN")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("new-registry")
    p.add_argument("scope", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        scope = _load(args.scope)
        if args.command == "fetch":
            snapshots = fetch_scope(scope, os.environ.get(args.token_env))
            _dump({"scope": normalize_scope(scope), "snapshots": snapshots}, args.out)
        else:
            _dump(empty_registry(scope), args.out)
        return 0
    except (OSError, ValueError, KeyError, FleetImportError, gt.GoldenThreadError, sr.SideEffectError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
