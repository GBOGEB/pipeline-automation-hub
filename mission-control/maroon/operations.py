#!/usr/bin/env python3
"""Durable MAROON work ledger and bounded host-local execution admission.

GitHub observations are data, never executable commands or permission grants. Registered trusted
adapters own native reads/writes and must recheck provider heads before side effects. The flock and
fencing below coordinate this host only; federation requires a shared external compare-and-swap
lease service. Root grouping is a diagnosis batch, never evidence that its members can be closed.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit
import uuid

HERE = Path(__file__).resolve().parent
SCHEMA = "code_maroon.operations.v1"
STAGES = ("diagnose", "treat", "verify", "publish", "reply", "resolve", "readback", "close", "rex")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RT = _module("maroon_operations_review", HERE / "review_threads.py")
BROKER = _module("maroon_operations_broker", HERE.parent / "federation-atlas/orchestration/broker.py")
LIFECYCLE = _module("maroon_operations_lifecycle", HERE.parent / "jade_temple/devops/lifecycle.py")

_REPOSITORY = HERE.parents[1]
_CORE_PATHS = (
    "mission-control/maroon/operations.py", "mission-control/maroon/review_threads.py",
    "mission-control/maroon/closure.py", "mission-control/jade_temple/devops/lifecycle.py",
    "mission-control/federation-atlas/orchestration/broker.py",
    "mission-control/gogreen/regime_controller.py", "scripts/first_pass_closure_gate.py",
)


def _core_manifest():
    result = {}
    for path in _CORE_PATHS:
        content = (_REPOSITORY / path).read_bytes()
        result[path] = hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content,
                                   usedforsecurity=False).hexdigest()
    return result


_LOADED_CORE_OIDS = _core_manifest()


def runtime_core_oids():
    """Git blob identities of the actual loaded execution core, not a security signature."""
    current = _core_manifest()
    if current != _LOADED_CORE_OIDS:
        raise LeaseError("execution core changed on disk; restart and replan")
    return dict(current)


class LeaseError(ValueError):
    """A claim is absent, expired, superseded or bound to different evidence."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _clock(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise ValueError("a timezone-aware timestamp is required")
    return result.astimezone(timezone.utc)


def _iso(value):
    return _clock(value).isoformat(timespec="microseconds")


def _integer(value, name, low=1, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError(f"invalid {name}")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {name}")
    return value


def _path(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(mark in value for mark in "*?[]")):
        raise ValueError("paths must be canonical literal repository-relative paths")
    return value


def _oids(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("OID references must be a path-to-OID object")
    for path, oid in value.items():
        _path(path)
        if not isinstance(oid, str) or not (SHA.fullmatch(oid) or DIGEST.fullmatch(oid)):
            raise ValueError("invalid pinned object OID")
    return dict(sorted(value.items()))


def _empty():
    return {"schema": SCHEMA, "revision": 0, "next_fence": 1, "pulses": {},
            "observations": {}, "roots": {}, "events": [], "lock_scope": "HOST_LOCAL"}


class LedgerStore:
    """Private JSON plus a host-local advisory lock; every mutation atomically replaces the file."""

    def __init__(self, path):
        self.path = Path(os.path.abspath(path))
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _load(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return _empty()
        with os.fdopen(fd, encoding="utf-8") as stream:
            data = json.load(stream)
        if (not isinstance(data, dict) or data.get("schema") != SCHEMA
                or any(not isinstance(data.get(key), dict) for key in ("pulses", "observations", "roots"))
                or not isinstance(data.get("events"), list)):
            raise ValueError("invalid MAROON ledger schema")
        _integer(data.get("revision"), "ledger revision", low=0)
        _integer(data.get("next_fence"), "fencing generation")
        return data

    def _save(self, data):
        if self.path.is_symlink():
            raise ValueError("ledger destination cannot be a symlink")
        fd, tmp = tempfile.mkstemp(prefix=".maroon-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(_json(data) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @contextmanager
    def transaction(self):
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            data = self._load()
            before = _json(data)
            yield data
            if _json(data) != before:
                data["revision"] += 1
                self._save(data)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def read(self):
        with self.transaction() as data:
            return copy.deepcopy(data)


def observation_id(repo, pr, comment_id):
    return "obs-" + _digest([repo, pr, comment_id])[:24]


def _scanner_reference(repo, thread):
    """Accept only an explicit, exact same-repository native alert URL, never URLs mined from prose."""
    url = thread.get("canonical_alert_url")
    if not url:
        return None
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
            or not re.fullmatch(re.escape(f"/{repo}/security/") + r"(?:code-scanning|dependabot|secret-scanning)/[1-9][0-9]*", parsed.path)):
        raise ValueError("invalid canonical scanner alert reference")
    return url


def _group(repo, thread):
    ref = thread.get("pr_head_ref")
    branch = ref if isinstance(ref, str) and ref else f"UNKNOWN-PR-{thread['pr']}"
    target = thread.get("pr_head_repo") or repo
    path = thread.get("path")
    if path:
        _path(path)
    reference = _scanner_reference(repo, thread)
    title = " ".join((thread.get("title") or "").casefold().split())
    # Missing path/title/anchor must not create one enormous "unknown" diagnosis batch.
    fallback = thread["number"] if not path or not title or not thread.get("anchor") else None
    subject = [reference] if reference else [path, title, thread.get("anchor"), fallback]
    root_id = "mr-" + _digest([repo, target, branch, subject])[:24]
    return root_id, target, branch


def _source(thread, entry, raw, previous=None):
    unchanged_head = previous is not None and previous.get("head_sha") == thread.get("pr_head")
    blob_supplied = "blob_oids" in thread or "blob_oids" in entry or "path_blob_oid" in thread
    blobs = _oids(thread.get("blob_oids", entry.get("blob_oids")))
    if not blob_supplied and unchanged_head:
        blobs = dict(previous["blob_oids"])
    if thread.get("path_blob_oid") is not None:
        blobs.update(_oids({thread.get("path"): thread["path_blob_oid"]}))
    core = _oids(thread.get("core_oids", entry.get("core_oids", raw.get("core_oids"))))
    body_hash = thread.get("body_hash") or hashlib.sha256((thread.get("body") or "").encode()).hexdigest()
    discussion_hash = thread.get("discussion_hash")
    if not isinstance(discussion_hash, str) or not DIGEST.fullmatch(discussion_hash):
        raise ValueError("review intake must supply a complete discussion_hash")
    return {"head_sha": thread.get("pr_head"), "base_sha": thread.get("pr_base_sha"),
            "head_ref": thread.get("pr_head_ref"), "base_ref": thread.get("pr_base_ref"),
            "head_repo": thread.get("pr_head_repo"), "body_hash": body_hash,
            "discussion_hash": discussion_hash, "blob_oids": blobs, "core_oids": core}


def _root_state(data, root):
    members = [data["observations"][key] for key in root["member_ids"]]
    if not members:
        return "SUPERSEDED"
    return "CLOSED" if all(item["semantic_state"] == "closed" for item in members) else "OPEN"


def _closure_still_valid(previous, source, thread):
    """Exclude only a journaled reply with its exact verified body, never an author or marker class."""
    if not previous.get("closure_receipts"):
        return False
    receipt = previous["closure_receipts"][-1]["receipt"]
    if any(source.get(field) != receipt.get(field, {}) for field in ("head_sha", "blob_oids", "core_oids")):
        return False
    if receipt.get("base_sha") is not None and source["base_sha"] != receipt["base_sha"]:
        return False
    if source["discussion_hash"] == receipt["discussion_hash"]:
        return True
    reply_id, body_hash = receipt.get("reply_id"), receipt.get("reply_body_hash")
    comments = thread.get("comments")
    if not reply_id or not body_hash or not isinstance(comments, list):
        return False
    owned = [comment for comment in comments if comment.get("id") == reply_id]
    if len(owned) != 1 or hashlib.sha256((owned[0].get("body") or "").encode()).hexdigest() != body_hash:
        return False
    remaining = sorted([comment for comment in comments if comment.get("id") != reply_id],
                       key=lambda comment: (comment.get("created_at") or "", comment["id"]))
    digest = hashlib.sha256(json.dumps(remaining, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest == receipt["discussion_hash"]


def ingest(store, raw_review, pulse_id, *, now=None):
    """Idempotently ingest an OPEN/all census. Sightings, revisions and provider reopens are separate."""
    _text(pulse_id, "pulse identity")
    if (not isinstance(raw_review, dict) or raw_review.get("state") not in {"open", "all"}
            or not isinstance(raw_review.get("repos"), dict)):
        raise ValueError("operations intake requires an explicit open/all PR census")
    raw_review = copy.deepcopy(raw_review)
    if "core_oids" not in raw_review:
        raw_review["core_oids"] = runtime_core_oids()
    when, pulse_hash = _iso(now), _digest(raw_review)
    with store.transaction() as data:
        existing = data["pulses"].get(pulse_id)
        if existing:
            if existing["digest"] != pulse_hash:
                raise ValueError("pulse identity reused with different observations")
            return copy.deepcopy(data)
        seen = set()
        for repo, entry in raw_review["repos"].items():
            _text(repo, "repository")
            coverage = entry.get("coverage", "unknown")
            for thread in [*entry.get("alerts", []), *entry.get("linked_alerts", [])]:
                _integer(thread.get("pr"), "PR number")
                _integer(thread.get("number"), "comment identity")
                key = observation_id(repo, thread["pr"], thread["number"])
                if key in seen:
                    raise ValueError("duplicate observation in one pulse")
                seen.add(key)
                root_id, target, branch = _group(repo, thread)
                previous = data["observations"].get(key)
                source = _source(thread, entry, raw_review, previous)
                assignment = (previous or {}).get("manual_group")
                preserve_group = bool(assignment and assignment["head_sha"] == source["head_sha"]
                                      and assignment["body_hash"] == source["body_hash"]
                                      and assignment["path"] == thread.get("path"))
                if preserve_group:
                    root_id = previous["root_id"]
                row = copy.deepcopy(previous) if previous else {
                    "id": key, "repo": repo, "pr": thread["pr"], "comment_id": thread["number"],
                    "first_seen": when, "sighting_count": 0, "revision_count": 0,
                    "head_change_count": 0, "reopen_count": 0, "semantic_state": "open",
                    "root_history": [], "closure_receipts": []}
                if assignment and not preserve_group:
                    row.pop("manual_group", None)
                provider_state = "resolved" if thread.get("state") == "resolved" else "open"
                if previous:
                    row["revision_count"] += int(previous["discussion_hash"] != source["discussion_hash"])
                    row["head_change_count"] += int(previous["head_sha"] != source["head_sha"])
                    reopened = previous["provider_state"] == "resolved" and provider_state == "open"
                    row["reopen_count"] += int(reopened)
                    changed = any(previous.get(field) != source[field] for field in source)
                    if reopened:
                        row["semantic_state"] = "open"
                    elif previous["semantic_state"] == "closed" and (changed or previous["root_id"] != root_id) and not (
                            previous["root_id"] == root_id and _closure_still_valid(previous, source, thread)):
                        row["semantic_state"] = "revalidation_required"
                if row.get("root_id") != root_id:
                    if row.get("root_id"):
                        data["roots"][row["root_id"]]["member_ids"].remove(key)
                    row["root_history"].append({"root_id": root_id, "pulse_id": pulse_id, "assigned_at": when})
                row.update(source)
                row.update(root_id=root_id, thread_id=thread.get("thread_id"), pr_state=thread.get("pr_state"),
                           provider_state=provider_state, last_seen=when, last_pulse_id=pulse_id,
                           observation_status="OBSERVED" if coverage == "ok" else "UNKNOWN", coverage=coverage,
                           path=thread.get("path"), title=thread.get("title"), anchor=thread.get("anchor"),
                           reviewer=thread.get("reviewer"), severity=thread.get("severity"),
                           provider_alert_owner=thread.get("provider_alert_owner"),
                           scanner_alert_state=thread.get("scanner_alert_state"),
                           negative_canary=thread.get("negative_canary"),
                           url=thread.get("url"), latest_comment_id=thread.get("latest_comment_id"))
                row["sighting_count"] += 1
                row.pop("unknown_reason", None)
                data["observations"][key] = row
                root = data["roots"].setdefault(root_id, {"id": root_id, "repo": repo, "target_repo": target,
                    "branch": branch, "member_ids": [], "depends_on": [], "lease": None,
                    "attempts": [], "stages": {}, "grouping": "DIAGNOSIS_BATCH_NOT_CLOSURE_PROOF"})
                root["member_ids"] = sorted(set(root["member_ids"]) | {key})
        for key, row in data["observations"].items():
            if key not in seen and row["repo"] in raw_review["repos"]:
                row["observation_status"] = "UNKNOWN"
                row["unknown_reason"] = "not_observed_in_pulse"
                row["last_missing_pulse_id"] = pulse_id
        for root in data["roots"].values():
            root["state"] = _root_state(data, root)
        data["pulses"][pulse_id] = {"digest": pulse_hash, "observed_at": when, "seen_items": len(seen)}
        data["events"].append({"kind": "intake", "pulse_id": pulse_id, "at": when})
    return store.read()


def group_findings(store, item_ids, remediation_key, *, method, proof_refs, now=None):
    """A trusted diagnosis groups coherent manifestations into one branch-bound worker packet.

    Record why the same treatment covers each child. This changes scheduling identity only;
    every thread still needs its own current proof and provider readback for closure.
    """
    _text(remediation_key, "remediation key")
    _text(method, "shared diagnosis method")
    if not isinstance(item_ids, list) or len(item_ids) < 2 or len(set(item_ids)) != len(item_ids):
        raise ValueError("group at least two distinct manifestation IDs")
    if not isinstance(proof_refs, list) or not proof_refs or any(not isinstance(ref, str) or not ref for ref in proof_refs):
        raise ValueError("shared diagnosis needs source proof references")
    with store.transaction() as data:
        rows = [data["observations"][key] for key in item_ids]
        for field in ("repo", "pr", "head_repo", "head_ref", "head_sha", "base_sha"):
            if len({row[field] for row in rows}) != 1:
                raise ValueError("a treatment packet must share one target PR/branch and current head")
        if any(row["observation_status"] != "OBSERVED" or row.get("negative_canary") is not False for row in rows):
            raise ValueError("shared diagnosis requires current, non-canary source observations")
        old_roots = {row["root_id"] for row in rows}
        if any(_holds_scope(data["roots"][key].get("lease")) or data["roots"][key].get("stages") for key in old_roots):
            raise LeaseError("finish or reconcile existing work before regrouping")
        if any(set(data["roots"][key]["member_ids"]) - set(item_ids) for key in old_roots):
            raise ValueError("regroup entire existing diagnosis batches; do not strand their children")
        first = rows[0]
        new_id = "mr-" + _digest([first["repo"], first["head_repo"], first["head_ref"], "remediation", remediation_key])[:24]
        if new_id in data["roots"] and new_id not in old_roots:
            raise ValueError("remediation key already belongs to another group")
        dependencies = sorted({parent for key in old_roots for parent in data["roots"][key]["depends_on"]} - old_roots)
        root = {"id": new_id, "repo": first["repo"], "target_repo": first["head_repo"] or first["repo"],
                "branch": first["head_ref"], "member_ids": sorted(item_ids), "depends_on": dependencies,
                "lease": None, "attempts": [], "stages": {}, "grouping": "SOURCE_JUSTIFIED_SHARED_DIAGNOSIS",
                "remediation_key": remediation_key, "method": method, "proof_refs": copy.deepcopy(proof_refs)}
        for key in old_roots:
            data["roots"][key]["member_ids"] = []
            data["roots"][key]["state"] = "SUPERSEDED"
        data["roots"][new_id] = root
        for row in rows:
            row["root_id"] = new_id
            row["manual_group"] = {"key": remediation_key, "head_sha": row["head_sha"],
                                   "body_hash": row["body_hash"], "path": row["path"],
                                   "method": method, "proof_refs": copy.deepcopy(proof_refs)}
            row["root_history"].append({"root_id": new_id, "assigned_at": _iso(now),
                                         "method": method, "proof_refs": copy.deepcopy(proof_refs)})
        for other in data["roots"].values():
            if other["id"] not in old_roots | {new_id}:
                other["depends_on"] = sorted({new_id if dep in old_roots else dep for dep in other["depends_on"]})
        root["state"] = _root_state(data, root)
        _graph(data)  # Reject newly introduced cycles before saving the transaction.
        data["events"].append({"kind": "shared_diagnosis", "root_id": new_id,
                               "member_ids": sorted(item_ids), "at": _iso(now), "proof_refs": proof_refs})
    return new_id


def _packet(data, root):
    members = [data["observations"][key] for key in root["member_ids"]]
    fields = ("id", "pr", "comment_id", "thread_id", "head_sha", "base_sha", "head_ref", "base_ref",
              "head_repo", "discussion_hash", "body_hash", "blob_oids", "core_oids", "pr_state",
              "provider_state", "observation_status", "semantic_state", "negative_canary", "path")
    evidence = [{field: row.get(field) for field in fields} for row in members]
    heads, bases = {row.get("head_sha") for row in members}, {row.get("base_sha") for row in members}
    refs = {row.get("head_ref") for row in members}
    blockers = []
    if any(row["observation_status"] != "OBSERVED" for row in members):
        blockers.append("COVERAGE_UNKNOWN")
    if any(row.get("pr_state") != "open" for row in members):
        blockers.append("PR_NOT_OPEN")
    if any(row.get("negative_canary") is not False for row in members):
        blockers.append("ANALYZE_ONLY_CANARY_OR_UNKNOWN_INTENT")
    if len(heads) != 1 or any(not isinstance(head, str) or not SHA.fullmatch(head) for head in heads):
        blockers.append("MISSING_OR_INCOHERENT_HEAD")
    if len(bases) != 1 or any(not isinstance(base, str) or not SHA.fullmatch(base) for base in bases):
        blockers.append("MISSING_OR_INCOHERENT_BASE")
    if len(refs) != 1 or not all(isinstance(ref, str) and ref for ref in refs):
        blockers.append("MISSING_OR_INCOHERENT_BRANCH")
    blobs, core = {}, {}
    for row in members:
        for field, combined in (("blob_oids", blobs), ("core_oids", core)):
            for path, oid in row[field].items():
                if path in combined and combined[path] != oid:
                    blockers.append("INCOHERENT_" + field.upper())
                combined[path] = oid
    current_core = runtime_core_oids()
    if any(row["core_oids"] != current_core for row in members):
        blockers.append("EXECUTION_CORE_OID_MISMATCH")
    packet = {"root_id": root["id"], "repo": root["repo"], "target_repo": root["target_repo"],
              "branch": root["branch"], "head_sha": next(iter(heads)) if len(heads) == 1 else None,
              "base_sha": next(iter(bases)) if len(bases) == 1 else None,
              "member_ids": root["member_ids"], "members": evidence,
              "paths": sorted({row["path"] for row in members if row.get("path")}),
              "blob_oids": blobs, "core_oids": core, "depends_on": root["depends_on"],
              "evidence_hash": _digest(evidence), "blocked_reasons": sorted(set(blockers)),
              "grouping": root["grouping"], "lock_scope": "HOST_LOCAL"}
    packet["sipoc"] = {
        "suppliers": [root["repo"] + " reviewers/scanners", "source owner", "prior REX"],
        "inputs": ["current head/base and source OIDs", "thread identities and discussion", "verified prerequisites"],
        "process": list(STAGES), "outputs": ["source/proof receipt", "thread readback", "ledger child closure", "REX"],
        "customers": ["PR owner", "dependent root workers", "next intake pulse"],
    }
    packet["idempotency_key"] = _digest({"root_id": root["id"], "evidence": evidence, "dependencies": root["depends_on"]})
    return packet


def _active(lease, now):
    return bool(lease and not lease.get("released_at") and _clock(lease["expires_at"]) > now)


def _holds_scope(lease):
    # Expiry does not stop an in-flight native operation. Keep ownership until its old executor and
    # every ambiguous side effect have been explicitly reconciled by the trusted adapter.
    return bool(lease and not lease.get("released_at"))


def _graph(data):
    nodes, edges = [], []
    for root in data["roots"].values():
        nodes.extend(f"{root['id']}:{stage}" for stage in STAGES)
        edges.extend((f"{root['id']}:{a}", f"{root['id']}:{b}", "FEEDFORWARD") for a, b in zip(STAGES, STAGES[1:]))
        edges.extend((f"{parent}:rex", f"{root['id']}:diagnose", "FEEDFORWARD") for parent in root["depends_on"])
    return nodes, edges, LIFECYCLE.topo_layers(nodes, edges)


def set_dependencies(store, root_id, depends_on):
    if not isinstance(depends_on, list) or any(not isinstance(key, str) for key in depends_on) or len(depends_on) != len(set(depends_on)):
        raise ValueError("dependencies must be unique root identities")
    with store.transaction() as data:
        data["roots"][root_id]["depends_on"] = sorted(depends_on)
        _graph(data)
    return store.read()


def _plan(data, now, workers):
    _integer(workers, "worker count", high=4)
    nodes, edges, layers = _graph(data)
    packets, ready, held = [], [], []
    active_count = sum(_holds_scope(root.get("lease")) for root in data["roots"].values())
    for root_id, root in sorted(data["roots"].items()):
        packet = _packet(data, root)
        reasons = list(packet["blocked_reasons"])
        if root["state"] in {"CLOSED", "SUPERSEDED"}:
            reasons.append(root["state"])
        if _active(root.get("lease"), now):
            reasons.append("LEASED")
        elif _holds_scope(root.get("lease")):
            reasons.append("EXPIRED_LEASE_UNCERTAIN")
        if any(data["roots"][parent]["state"] != "CLOSED" or
               data["roots"][parent]["stages"].get("rex", {}).get("state") != "succeeded"
               for parent in root["depends_on"]):
            reasons.append("PREDECESSOR_REX_NOT_COMPLETE")
        packet["admission_reasons"] = reasons
        packets.append(packet)
        (held if reasons else ready).append(root_id)
    return {"schema": "code_maroon.queue-plan.v1", "generated_at": _iso(now), "packets": packets,
            "ready": ready, "held": held, "workers": workers, "active_claims": active_count,
            "available_slots": max(0, workers - active_count), "nodes": nodes, "edges": edges, "layers": layers,
            "lock_scope": "HOST_LOCAL", "native_actions_executed": 0, "merge_authorized": False}


def plan(store, *, now=None, workers=2):
    return _plan(store.read(), _clock(now), workers)


def _leased_packet(packet, lease):
    return {**copy.deepcopy(packet), "lease": copy.deepcopy(lease),
            **{key: lease[key] for key in ("lease_token", "fence", "expires_at", "worker_id")}}


def claim(store, root_id, worker_id, *, ttl_seconds=900, now=None, workers=2):
    _text(worker_id, "worker identity")
    _integer(ttl_seconds, "lease lifetime", high=3600)
    clock = _clock(now)
    with store.transaction() as data:
        proposed = _plan(data, clock, workers)
        if root_id not in proposed["ready"]:
            raise LeaseError("root is not ready for a claim")
        if proposed["available_slots"] == 0:
            raise LeaseError("worker admission bound reached")
        packet = next(item for item in proposed["packets"] if item["root_id"] == root_id)
        for other in data["roots"].values():
            lease = other.get("lease")
            if not _holds_scope(lease):
                continue
            occupied = lease["packet"]
            if packet["target_repo"] != occupied["target_repo"]:
                continue
            if packet["branch"] == occupied["branch"]:
                raise LeaseError("another worker owns this repository branch")
            left = {"write_paths": packet["paths"], "read_paths": []}
            right = {"write_paths": occupied["paths"], "read_paths": []}
            if BROKER.conflicts(left, right):
                raise LeaseError("declared paths overlap another active claim")
        lease = {"lease_token": str(uuid.uuid4()), "fence": data["next_fence"], "worker_id": worker_id,
                 "issued_at": _iso(clock), "expires_at": _iso(clock + timedelta(seconds=ttl_seconds)),
                 "packet_key": packet["idempotency_key"], "packet": copy.deepcopy(packet)}
        data["next_fence"] += 1
        root = data["roots"][root_id]
        previous_lease = root.get("lease")
        if root.get("lease"):
            root["attempts"].append(copy.deepcopy(root["lease"]))
        root["lease"] = lease
        if not previous_lease or previous_lease["packet_key"] != packet["idempotency_key"]:
            root["stages"] = {}
        else:
            for stage in root["stages"].values():
                stage["inherited_from_fence"] = stage.get("fence")
                stage["fence"] = lease["fence"]
        data["events"].append({"kind": "claim", "root_id": root_id, "fence": lease["fence"], "at": _iso(clock)})
        return _leased_packet(packet, lease)


def _check(data, root_id, token, fence, now, *, allow_completed=False):
    root = data["roots"].get(root_id)
    lease = root.get("lease") if root else None
    if (not lease or lease.get("lease_token") != token or lease.get("fence") != fence
            or type(fence) is not int or not _active(lease, now) or _clock(lease["issued_at"]) > now):
        raise LeaseError("lease is absent, expired or superseded")
    packet = _packet(data, root)
    if packet["idempotency_key"] != lease["packet_key"]:
        raise LeaseError("source head, OIDs, discussion, scope or membership changed")
    if packet["blocked_reasons"] or (root["state"] != "OPEN" and not allow_completed):
        raise LeaseError("current source is not eligible")
    return root, lease, packet


def check_lease(store, root_id, lease_token, fence, *, now=None):
    with store.transaction() as data:
        _, lease, packet = _check(data, root_id, lease_token, fence, _clock(now), allow_completed=True)
        return _leased_packet(packet, lease)


def release(store, root_id, lease_token, fence, *, now=None, reason="released"):
    clock = _clock(now)
    with store.transaction() as data:
        # Release cannot revive or erase a newer claim. Source drift need not prevent relinquishing
        # our own still-live lease, but an expired/stale token can never affect its successor.
        root = data["roots"].get(root_id)
        lease = root.get("lease") if root else None
        if type(fence) is not int or not lease or lease.get("lease_token") != lease_token or lease.get("fence") != fence or not _active(lease, clock):
            raise LeaseError("cannot release a stale lease")
        if any(stage["state"] in {"running", "uncertain"} for stage in root["stages"].values()):
            raise LeaseError("an in-flight/uncertain stage requires reconciliation before release")
        lease["released_at"] = _iso(clock)
        lease["release_reason"] = str(reason)
        data["events"].append({"kind": "release", "root_id": root_id, "fence": fence, "at": _iso(clock)})
    return store.read()


def reconcile_claim(store, root_id, lease_token, fence, *, owner_stopped, proof_refs, stage_results=None, now=None):
    """Record trusted executor/native readback reconciliation, never infer safety from expiry.

    owner_stopped must come from actual executor/process evidence. Every running/uncertain stage
    needs an explicit succeeded result or retryable result backed by native readback proof. This
    local API validates the report; it cannot authenticate a remote executor or prove its shutdown.
    """
    if owner_stopped is not True or not isinstance(proof_refs, list) or not proof_refs or any(not isinstance(ref, str) or not ref for ref in proof_refs):
        raise ValueError("reconciliation requires stopped-owner proof references")
    clock = _clock(now)
    with store.transaction() as data:
        root = data["roots"][root_id]
        lease = root.get("lease")
        if type(fence) is not int or not lease or lease["lease_token"] != lease_token or lease["fence"] != fence or lease.get("released_at"):
            raise LeaseError("reconciliation cannot affect a different claim")
        unresolved = {name for name, stage in root["stages"].items() if stage["state"] in {"running", "uncertain"}}
        supplied = stage_results or {}
        if not isinstance(supplied, dict) or set(supplied) != unresolved:
            raise ValueError("every uncertain stage needs a specific reconciliation")
        for name, result in supplied.items():
            if not isinstance(result, dict) or result.get("state") not in {"succeeded", "retryable"} or not result.get("proof_refs"):
                raise ValueError("stage reconciliation needs a terminal native readback")
            if result["state"] == "succeeded" and (not isinstance(result.get("result"), dict) or result["result"].get("ok") is not True):
                raise ValueError("successful reconciliation requires an explicit verified stage result")
            root["stages"][name].update(state="succeeded" if result["state"] == "succeeded" else "failed",
                                       result=result.get("result"), reconciliation=copy.deepcopy(result))
        lease["released_at"] = lease["reconciled_at"] = _iso(clock)
        lease["reconciliation_proof_refs"] = list(proof_refs)
        data["events"].append({"kind": "executor_reconciled", "root_id": root_id, "fence": fence,
                               "proof_refs": list(proof_refs), "at": _iso(clock)})
    return store.read()


def _rebind(root, lease, packet):
    lease["packet_key"], lease["packet"] = packet["idempotency_key"], copy.deepcopy(packet)
    for stage in root["stages"].values():
        # An explicit trusted advancement preserves the predecessor receipts' original input key.
        stage["accepted_packet_key"] = packet["idempotency_key"]


def advance_claim(store, root_id, lease_token, fence, updates, *, reason, proof_refs, now=None):
    """Rebind intended commit advancement after a trusted native adapter verifies it.

    This is not a provider verification function: proof refs and new OIDs are an adapter report.
    Branch/member identity stays fixed; unexpected scan drift still fails the existing lease check.
    """
    _text(reason, "advancement reason")
    if not isinstance(proof_refs, list) or not proof_refs or any(not isinstance(ref, str) or not ref for ref in proof_refs):
        raise ValueError("advancement needs proof references")
    clock = _clock(now)
    with store.transaction() as data:
        root, lease, packet = _check(data, root_id, lease_token, fence, clock)
        if not isinstance(updates, dict) or set(updates) != set(root["member_ids"]):
            raise ValueError("advancement must refresh every member of the claim")
        before = packet["idempotency_key"]
        for item_id, patch in updates.items():
            if not isinstance(patch, dict) or not set(patch) <= {"head_sha", "base_sha", "discussion_hash", "blob_oids", "core_oids"}:
                raise ValueError("advancement cannot change branch, members or diagnosis identity")
            for field in ("head_sha", "base_sha"):
                if field in patch and (not isinstance(patch[field], str) or not SHA.fullmatch(patch[field])):
                    raise ValueError("advancement needs an exact SHA")
            if "discussion_hash" in patch and not DIGEST.fullmatch(str(patch["discussion_hash"])):
                raise ValueError("advancement needs a discussion digest")
            for field in ("blob_oids", "core_oids"):
                if field in patch:
                    _oids(patch[field])
            data["observations"][item_id].update(copy.deepcopy(patch))
        current = _packet(data, root)
        if current["blocked_reasons"]:
            raise ValueError("advancement created an incoherent source packet")
        _rebind(root, lease, current)
        data["events"].append({"kind": "verified_adapter_advancement", "root_id": root_id, "fence": fence,
                               "old_packet_key": before, "new_packet_key": current["idempotency_key"],
                               "reason": reason, "proof_refs": proof_refs, "at": _iso(clock)})
        return _leased_packet(current, lease)


def mark_closed(store, item_id, receipt, *, now=None):
    """Record a trusted native adapter's verified readback; caller JSON is not authentication."""
    if not isinstance(receipt, dict):
        raise ValueError("closure receipt required")
    clock = _clock(now)
    with store.transaction() as data:
        item = data["observations"][item_id]
        # A retried journal callback is a no-op only for the exact already-recorded receipt.
        digest = _digest(receipt)
        if item["semantic_state"] == "closed" and any(row["digest"] == digest for row in item["closure_receipts"]):
            return copy.deepcopy(item)
        if receipt.get("item_id") != item_id or receipt.get("root_id") != item["root_id"]:
            raise ValueError("receipt target mismatch")
        root, lease, _ = _check(data, item["root_id"], receipt.get("lease_token"), receipt.get("fence"), clock)
        for field in ("head_sha", "discussion_hash", "thread_id"):
            if not item.get(field) or receipt.get(field) != item[field]:
                raise ValueError("closure receipt source mismatch: " + field)
        if "base_sha" in receipt and receipt["base_sha"] != item["base_sha"]:
            raise ValueError("closure receipt base mismatch")
        for field in ("blob_oids", "core_oids"):
            if _oids(receipt.get(field)) != item[field]:
                raise ValueError("closure receipt OID mismatch: " + field)
        disposition = receipt.get("disposition")
        if disposition not in {"fixed", "already_fixed", "false_positive", "duplicate"}:
            raise ValueError("closure requires a supported evidence-based disposition")
        _text(receipt.get("method"), "closure method")
        proof_refs = receipt.get("proof_refs")
        if not isinstance(proof_refs, list) or not proof_refs or any(not isinstance(ref, str) or not ref for ref in proof_refs):
            raise ValueError("closure needs proof references")
        if disposition == "duplicate":
            other = data["observations"].get(receipt.get("duplicate_of"))
            if not other or other["id"] == item_id or other["semantic_state"] != "closed" or other["repo"] != item["repo"] or other["head_sha"] != item["head_sha"]:
                raise ValueError("duplicate grouping alone cannot authorize closure")
        readback = receipt.get("provider_readback") or {
            "resolved": receipt.get("provider_resolved"), "observed_at": receipt.get("provider_readback_at"),
            "reference": receipt.get("provider_readback_ref"), "head_sha": receipt.get("head_sha"),
            "discussion_hash": receipt.get("discussion_hash"), "thread_id": receipt.get("thread_id")}
        if readback.get("resolved") is not True:
            raise ValueError("positive provider resolution readback is required")
        for field in ("head_sha", "discussion_hash", "thread_id"):
            if readback.get(field) != item[field]:
                raise ValueError("readback does not match the treated source")
        _text(readback.get("reference"), "provider readback reference")
        read_at = _clock(readback.get("observed_at")) if readback.get("observed_at") else None
        if read_at is None or read_at > clock or read_at < _clock(lease["issued_at"]):
            raise ValueError("provider readback is stale or in the future")
        item["semantic_state"], item["provider_state"] = "closed", "resolved"
        item["closed_at"], item["disposition"] = _iso(clock), disposition
        item["closure_receipts"].append({"digest": digest, "receipt": copy.deepcopy(receipt), "recorded_at": _iso(clock)})
        root["state"] = _root_state(data, root)
        # Our own verified closure changes operational state, not the source identity. Rebind the
        # claim so it can close its remaining members and finish REX under the same fencing token.
        packet = _packet(data, root)
        _rebind(root, lease, packet)
        data["events"].append({"kind": "closed", "item_id": item_id, "fence": lease["fence"], "at": _iso(clock)})
        return copy.deepcopy(item)


def _record_stage(store, root_id, token, fence, stage, result, now=None):
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("trusted stage handler did not return ok=true")
    _json(result)
    with store.transaction() as data:
        root, _, packet = _check(data, root_id, token, fence, _clock(now), allow_completed=True)
        index = STAGES.index(stage)
        if index and root["stages"].get(STAGES[index - 1], {}).get("state") != "succeeded":
            raise ValueError("predecessor has not produced a verified stage result")
        if stage == "close" and root["state"] != "CLOSED":
            raise ValueError("close stage requires native readback receipts for every member")
        prior = root["stages"].get(stage, {})
        root["stages"][stage] = {**prior, "state": "succeeded", "result": copy.deepcopy(result), "at": _iso(now), "fence": fence,
                                 "input_packet_key": prior.get("input_packet_key", packet["idempotency_key"]),
                                 "accepted_packet_key": packet["idempotency_key"]}
    return True


def _begin_stage(store, root_id, token, fence, stage, now=None):
    with store.transaction() as data:
        root, _, packet = _check(data, root_id, token, fence, _clock(now), allow_completed=True)
        prior = root["stages"].get(stage)
        if prior and prior["state"] in {"running", "uncertain"}:
            raise LeaseError("stage outcome is uncertain; reconcile before restarting")
        if prior and prior["state"] == "succeeded":
            if prior.get("accepted_packet_key") != packet["idempotency_key"]:
                raise LeaseError("completed stage belongs to different source evidence")
            return copy.deepcopy(prior["result"])
        index = STAGES.index(stage)
        if index and root["stages"].get(STAGES[index - 1], {}).get("state") != "succeeded":
            raise LeaseError("predecessor result is not verified")
        root["stages"][stage] = {"state": "running", "fence": fence, "started_at": _iso(now),
                                 "input_packet_key": packet["idempotency_key"],
                                 "accepted_packet_key": packet["idempotency_key"]}
        return None


def _stage_problem(store, root_id, token, fence, stage, error):
    with store.transaction() as data:
        root = data["roots"][root_id]
        lease = root.get("lease")
        if lease and lease["lease_token"] == token and lease["fence"] == fence:
            row = root["stages"].get(stage)
            if row and row["state"] == "running":
                row["state"] = "failed" if stage in {"diagnose", "verify", "readback"} else "uncertain"
                row["error_type"] = type(error).__name__


def run_claimed(store, root_id, lease_token, fence, handlers, *, now=None):
    """Run one claimed root through registered trusted callables; no shell strings are accepted.

    Each handler receives no arguments and returns {"ok": true, ...}. An evidence-only handler can
    implement treat/publish as justified no-ops. Native closure still requires mark_closed receipts.
    The canonical broker blocks all descendants of a failed handler or failed output validation.
    """
    packet = check_lease(store, root_id, lease_token, fence, now=now)
    if not isinstance(handlers, dict) or set(handlers) != set(STAGES) or any(not callable(handler) for handler in handlers.values()):
        raise ValueError("every stage requires a registered trusted callable")
    root = store.read()["roots"][root_id]
    if any(stage["state"] in {"running", "uncertain"} for stage in root["stages"].values()):
        raise LeaseError("an interrupted stage requires native reconciliation before resume")
    tasks = []
    for i, stage in enumerate(STAGES):
        tasks.append({"id": f"{root_id}:{stage}", "repo": packet["repo"],
                      "needs": [f"{root_id}:{STAGES[i - 1]}"] if i else [],
                      "read_paths": packet["paths"], "write_paths": packet["paths"] if stage in {"treat", "publish"} else [],
                      "input_contract": {}, "output_contract": {"required_result_keys": ["ok"]}})
    LIFECYCLE.topo_layers([task["id"] for task in tasks], [(parent, task["id"], "FEEDFORWARD") for task in tasks for parent in task["needs"]])

    def validate_input(task):
        check_lease(store, root_id, lease_token, fence, now=now)
        return True

    def validate_output(task, result):
        stage = task["id"].rsplit(":", 1)[1]
        try:
            return _record_stage(store, root_id, lease_token, fence, stage, result, now)
        except Exception as error:
            _stage_problem(store, root_id, lease_token, fence, stage, error)
            raise

    def handler_for(stage):
        def execute():
            prior = _begin_stage(store, root_id, lease_token, fence, stage, now)
            if prior is not None:
                return prior
            try:
                return handlers[stage]()
            except Exception as error:
                _stage_problem(store, root_id, lease_token, fence, stage, error)
                raise
        return execute

    receipt = BROKER.run_local(tasks, {f"{root_id}:{stage}": handler_for(stage) for stage in handlers},
                               workers=2, max_pending=8, root=HERE, input_validator=validate_input,
                               output_validator=validate_output)
    with store.transaction() as data:
        root = data["roots"][root_id]
        if root.get("lease", {}).get("lease_token") == lease_token and root["lease"]["fence"] == fence:
            root["last_execution"] = copy.deepcopy(receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="read all OPEN PRs and update the private work ledger")
    scan.add_argument("--repos", required=True)
    scan.add_argument("--pulse", required=True)
    scan.add_argument("--threads", choices=("graphql", "ccr"), default="graphql")
    load = commands.add_parser("ingest", help="ingest a previously fetched OPEN/all review census")
    load.add_argument("--raw", required=True, type=Path)
    load.add_argument("--pulse", required=True)
    planner = commands.add_parser("plan")
    planner.add_argument("--workers", type=int, default=2)
    acquire = commands.add_parser("claim")
    acquire.add_argument("--root", required=True)
    acquire.add_argument("--worker", required=True)
    acquire.add_argument("--ttl", type=int, default=900)
    acquire.add_argument("--workers", type=int, default=2)
    relinquish = commands.add_parser("release")
    relinquish.add_argument("--root", required=True)
    relinquish.add_argument("--lease", required=True)
    relinquish.add_argument("--fence", required=True, type=int)
    relinquish.add_argument("--reason", default="released")
    args = parser.parse_args(argv)
    store = LedgerStore(args.ledger)
    if args.command in {"scan", "ingest"}:
        if args.command == "scan":
            resolver = RT.resolved_via_ccr if args.threads == "ccr" else RT.resolved_via_graphql
            raw = RT.fetch([repo.strip() for repo in args.repos.split(",") if repo.strip()], 30, state="open", resolved=resolver)
        else:
            raw = json.loads(args.raw.read_text(encoding="utf-8"))
        ingest(store, raw, args.pulse)
        output = plan(store)
    elif args.command == "plan":
        output = plan(store, workers=args.workers)
    elif args.command == "claim":
        output = claim(store, args.root, args.worker, ttl_seconds=args.ttl, workers=args.workers)
    else:
        release(store, args.root, args.lease, args.fence, reason=args.reason)
        output = plan(store)
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
