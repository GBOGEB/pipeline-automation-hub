#!/usr/bin/env python3
"""Read-only CP.CLOSE continuity review; never a new queue or admission owner.

Compare two digest-bound, sanitized CP.CLOSE packets. A different session alias
requires an explicit source-bound cross-session mapping, even where SC-A### or
SC-I### IDs happen to coincide. The verdict proves only packet lineage; it
never proves causal-root closure, owner acceptance, or merge eligibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from collections import deque

SCHEMA = "missioncontrol.cp_close.todo-continuity-review.v1"
LINK_SCHEMA = "missioncontrol.cp_close.continuity-links.v1"
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
ACTION = re.compile(r"SC-A[0-9]{3}\Z")
INTENT = re.compile(r"SC-I[0-9]{3}\Z")
STATES = frozenset(("TODO", "ACTIVE", "IN_PR", "HOLD", "DEFER", "DONE", "CONTROL"))
CLOSED = frozenset(("DONE", "CONTROL"))
DISPOSITIONS = frozenset(("CONTINUED", "SUPERSEDED_WITH_LINEAGE", "DEFERRED_WITH_OWNER", "ARCHIVED_CLOSED"))
FIELDS = ("owner", "summary", "done_when", "depends_on", "priority", "evidence_urls")
MAX_FILE_BYTES = 2_000_000
MAX_MANIFEST_MEMBERS = 32
MAX_PACKET_BYTES = 16_000_000
MAX_ITEMS_PER_PACKET = 999  # CP.CLOSE format has exactly three numeric digits.


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError("CP_TODO_CONTINUITY_HOLD: " + why)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def github_owner_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    p = urlparse(value)
    return p.scheme == "https" and p.netloc == "github.com" and p.path.startswith("/GBOGEB/") and not p.username


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "duplicate JSON field " + key)
        obj[key] = value
    return obj


def read_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), "missing or linked JSON: " + path.name)
    require(path.stat().st_size <= MAX_FILE_BYTES, "oversized JSON: " + path.name)
    obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    require(isinstance(obj, dict), "JSON object required: " + path.name)
    return obj


def indexed(items: object, pattern: re.Pattern, what: str) -> dict:
    require(isinstance(items, list), what + " list required")
    out = {}
    require(len(items) <= MAX_ITEMS_PER_PACKET, what + " population cap exceeded")
    for item in items:
        require(isinstance(item, dict), "invalid " + what + " item")
        key = item.get("id")
        require(isinstance(key, str) and pattern.fullmatch(key) and key not in out,
                "invalid/duplicate " + what + " id")
        out[key] = item
    return out


def check_dag(actions: dict) -> None:
    graph = {}
    for key, item in actions.items():
        deps = item.get("depends_on")
        require(isinstance(deps, list) and len(deps) == len(set(deps))
                and all(isinstance(x, str) and x in actions and x != key for x in deps),
                "orphan/self/duplicate action dependency " + key)
        require(item.get("state") in STATES and isinstance(item.get("done_when"), str)
                and item["done_when"].strip() and isinstance(item.get("owner"), str)
                and item["owner"].strip(), "incomplete action " + key)
        graph[key] = deps
    children = {key: [] for key in graph}
    indegree = {key: len(parents) for key, parents in graph.items()}
    for key, parents in graph.items():
        for parent in parents:
            children[parent].append(key)
    ready = deque(key for key in graph if indegree[key] == 0)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for child in children[key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    require(visited == len(graph), "action dependency cycle")


def load_packet(directory: Path) -> dict:
    """Check every manifest member digest and bind packet source identities."""
    directory = directory.resolve()
    manifest_path = directory / "MANIFEST.json"
    require(manifest_path.is_file(), "missing MANIFEST")
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == "missioncontrol.cp_close.manifest.v1"
            and manifest.get("authority_transfer") is False
            and manifest.get("verbatim_transcript_claim") is False
            and manifest.get("main_merge_admission") == "INDEPENDENT_REVIEW_REQUIRED",
            "canonical CP.CLOSE manifest/authority/privacy required")
    members = manifest.get("member_sha256")
    require(isinstance(members, dict) and members
            and len(members) <= MAX_MANIFEST_MEMBERS,
            "bounded manifest member digest map required")
    required = {"STATE.json", "INTENT_ACTION_LEDGER.json", "BD_QUEUE_READONLY.json"}
    require(required <= set(members), "missing required manifest members")
    total_bytes = 0
    for name, expected in members.items():
        require(isinstance(name, str) and name not in ("", ".", "..")
                and Path(name).name == name and "/" not in name and "\\" not in name,
                "unsafe manifest member")
        require(isinstance(expected, str) and SHA64.fullmatch(expected), "invalid member SHA256")
        path = directory / name
        require(path.is_file() and not path.is_symlink(),
                "missing/linked member " + name)
        require(path.stat().st_size <= MAX_FILE_BYTES, "oversized member " + name)
        total_bytes += path.stat().st_size
        require(total_bytes <= MAX_PACKET_BYTES, "oversized CP.CLOSE packet")
        require(digest(path.read_bytes()) == expected, "missing/drifted member " + name)
    state = read_json(directory / "STATE.json")
    ledger = read_json(directory / "INTENT_ACTION_LEDGER.json")
    bd = read_json(directory / "BD_QUEUE_READONLY.json")
    require(state.get("schema") == "missioncontrol.cp_close.state.v1"
            and ledger.get("schema") == "missioncontrol.cp_close.semantic_ledger.v1"
            and bd.get("schema") == "missioncontrol.cp_close.bd_projection.v1",
            "wrong packet schema")
    require(state.get("security_waiver") is False
            and state.get("authority_transfer") is False
            and state.get("full_chat_message_count") is None
            and state.get("full_chat_prompt_count") is None
            and state.get("release_gate") == "INDEPENDENT_PR_AND_MAIN_ADMISSION"
            and bd.get("authority_transfer") is False
            and bd.get("new_canonical_bd_items") == 0,
            "canonical CP.CLOSE privacy/non-admission required")
    alias = state.get("session_alias")
    source = state.get("source")
    require(isinstance(alias, str) and alias == manifest.get("session_alias")
            and isinstance(source, dict)
            and isinstance(source.get("observed_main_sha"), str)
            and SHA40.fullmatch(source["observed_main_sha"])
            and source["observed_main_sha"] == manifest.get("observed_main_sha"),
            "session or observed-main identity mismatch")
    require(isinstance(bd.get("source_sha256"), str)
            and SHA64.fullmatch(bd["source_sha256"])
            and isinstance(manifest.get("canonical_bd_sha256"), str)
            and SHA64.fullmatch(manifest["canonical_bd_sha256"])
            and bd["source_sha256"] == manifest["canonical_bd_sha256"]
            and bd.get("read_only_historical") is True,
            "canonical BD provenance mismatch")
    actions = indexed(ledger.get("actions"), ACTION, "action")
    intents = indexed(ledger.get("intents"), INTENT, "intent")
    check_dag(actions)
    for key, item in intents.items():
        ids = item.get("actions")
        require(isinstance(ids, list) and len(ids) == len(set(ids))
                and all(x in actions for x in ids), "orphan intent-action edge " + key)
    require(state.get("action_count_reconstructed") == len(actions)
            and state.get("intent_count_reconstructed") == len(intents),
            "state/ledger population mismatch")
    require(isinstance(bd.get("focus"), list), "BD focus list required")
    ids = [x.get("id") for x in bd["focus"] if isinstance(x, dict)]
    require(len(ids) == len(bd["focus"]) and len(set(ids)) == len(ids)
            and all(isinstance(x, str) and re.fullmatch(r"CPQ-[0-9]{3}", x) for x in ids),
            "invalid or duplicate BD focus")
    return {"alias": alias, "state": state, "manifest_digest": digest(manifest_path.read_bytes()),
            "source_sha": source["observed_main_sha"], "actions": actions,
            "intents": intents, "bd": bd}


def _links(doc: dict | None, before: dict, after: dict) -> tuple[dict, dict, set]:
    if doc is None:
        return {}, {}, set()
    require(doc.get("schema") == LINK_SCHEMA
            and doc.get("from_session") == before["alias"]
            and doc.get("to_session") == after["alias"],
            "sidecar session/schema mismatch")
    require(isinstance(doc.get("from_manifest_sha256"), str)
            and SHA64.fullmatch(doc["from_manifest_sha256"])
            and isinstance(doc.get("to_manifest_sha256"), str)
            and SHA64.fullmatch(doc["to_manifest_sha256"])
            and doc["from_manifest_sha256"] == before["manifest_digest"]
            and doc["to_manifest_sha256"] == after["manifest_digest"],
            "sidecar packet digest mismatch or missing")
    maps = []
    for name, old, new in (("action_links", before["actions"], after["actions"]),
                            ("intent_links", before["intents"], after["intents"])):
        src = doc.get(name)
        require(isinstance(src, list), "missing " + name)
        rows = {}
        for item in src:
            require(isinstance(item, dict) and item.get("from") in old
                    and item["from"] not in rows and item.get("disposition") in DISPOSITIONS
                    and github_owner_url(item.get("evidence_url")),
                    "invalid/duplicate source-bound " + name)
            target = item.get("to")
            if item["disposition"] == "ARCHIVED_CLOSED":
                if name == "action_links":
                    require(old[item["from"]].get("state") in CLOSED,
                            "archive requires prior DONE/CONTROL action")
                else:
                    require(all(before["actions"][aid].get("state") in CLOSED
                                for aid in old[item["from"]].get("actions", [])),
                            "archive intent contains open historical actions")
                require(target is None, "archived item cannot falsely claim current target")
            else:
                require(isinstance(target, str) and target in new,
                        "missing/invalid successor target for " + name)
                if name == "action_links" and item["disposition"] == "DEFERRED_WITH_OWNER":
                    require(new[target].get("state") in ("HOLD", "DEFER"),
                            "deferred action must remain HOLD/DEFER")
            rows[item["from"]] = item
        maps.append(rows)
    # One-to-one continuity is the default. Several historical items may be
    # combined only through an explicitly labelled supersession, not a casual
    # many-to-one short-id join.
    for kind, rows in (("action", maps[0]), ("intent", maps[1])):
        targets = {}
        for item in rows.values():
            if item["to"] is not None:
                targets.setdefault(item["to"], []).append(item["disposition"])
        for target, dispositions in targets.items():
            if len(dispositions) > 1:
                require("SUPERSEDED_WITH_LINEAGE" in dispositions,
                        "unjustified many-to-one " + kind + " successor " + target)
    revisions = doc.get("revisions", [])
    require(isinstance(revisions, list), "revision list required")
    approved = set()
    for r in revisions:
        require(isinstance(r, dict) and r.get("kind") in ("action", "intent")
                and isinstance(r.get("id"), str)
                and github_owner_url(r.get("evidence_url"))
                and isinstance(r.get("reason"), str) and r["reason"].strip(),
                "unbound revision evidence")
        pair = (r["kind"], r["id"])
        population = (before["actions"] if r["kind"] == "action" else before["intents"])
        successors = (after["actions"] if r["kind"] == "action" else after["intents"])
        require(r["id"] in population and r["id"] in successors, "unmatched revision identity")
        require(pair not in approved, "duplicate revision evidence")
        approved.add(pair)
    return maps[0], maps[1], approved


def reconcile(before: dict, after: dict, links: dict | None = None) -> dict:
    """Project ONLY continuity metadata; not closure, live source, or priority scores."""
    b_actions, a_actions = before["actions"], after["actions"]
    b_intents, a_intents = before["intents"], after["intents"]
    same = before["alias"] == after["alias"]
    action_links, intent_links, revisions = _links(links, before, after)
    old_actions, old_intents = set(b_actions), set(b_intents)
    new_actions, new_intents = set(a_actions), set(a_intents)
    removed_actions = sorted(old_actions - new_actions) if same else []
    removed_intents = sorted(old_intents - new_intents) if same else []
    unmapped_actions = (removed_actions if same else sorted(old_actions - set(action_links)))
    unmapped_intents = (removed_intents if same else sorted(old_intents - set(intent_links)))
    altered = []
    promotions = []
    state_transitions = []
    if same:
        for key in sorted(old_actions & new_actions):
            was, now = b_actions[key], a_actions[key]
            if any(was.get(f) != now.get(f) for f in FIELDS) and ("action", key) not in revisions:
                altered.append(key)
            if was.get("state") not in CLOSED and now.get("state") in CLOSED:
                promotions.append(key)
            elif was.get("state") != now.get("state") and ("action", key) not in revisions:
                state_transitions.append(key)
        for key in sorted(old_intents & new_intents):
            if b_intents[key] != a_intents[key] and ("intent", key) not in revisions:
                altered.append(key)
    else:
        for old, link in action_links.items():
            if link["disposition"] == "ARCHIVED_CLOSED":
                continue
            new = a_actions[link["to"]]
            was = b_actions[old]
            expected_deps = sorted(action_links[d]["to"] for d in was["depends_on"]
                                   if d in action_links and action_links[d]["to"] is not None)
            different = any(was.get(f) != new.get(f)
                            for f in ("owner", "summary", "done_when", "priority", "evidence_urls")) \
                or sorted(new.get("depends_on", [])) != expected_deps
            if different and not (isinstance(link.get("revision_reason"), str)
                                  and link["revision_reason"].strip()
                                  and github_owner_url(link.get("revision_evidence_url"))):
                altered.append("action:" + old + ">" + link["to"])
            if was.get("state") not in CLOSED and new.get("state") in CLOSED:
                promotions.append(old)
            elif was.get("state") != new.get("state") and not (
                isinstance(link.get("revision_reason"), str) and link["revision_reason"].strip()
                and github_owner_url(link.get("revision_evidence_url"))
            ):
                state_transitions.append(old)
        for old, link in intent_links.items():
            if link["disposition"] == "ARCHIVED_CLOSED":
                continue
            was, new = b_intents[old], a_intents[link["to"]]
            expected = sorted(action_links[d]["to"] for d in was.get("actions", [])
                              if d in action_links and action_links[d]["to"] is not None)
            old_provenance = {k: v for k, v in was.items() if k not in ("id", "actions")}
            new_provenance = {k: v for k, v in new.items() if k not in ("id", "actions")}
            different = old_provenance != new_provenance \
                or sorted(new.get("actions", [])) != expected
            if different and not (isinstance(link.get("revision_reason"), str)
                                  and link["revision_reason"].strip()
                                  and github_owner_url(link.get("revision_evidence_url"))):
                altered.append("intent:" + old + ">" + link["to"])
    missing = bool(unmapped_actions or unmapped_intents or altered or promotions or state_transitions)
    return {
        "schema": SCHEMA,
        "source": "SANITIZED_CP_CLOSE_PACKETS_ONLY",
        "from_session": before["alias"], "to_session": after["alias"],
        "from_manifest_sha256": before["manifest_digest"],
        "to_manifest_sha256": after["manifest_digest"],
        "from_source_sha": before["source_sha"], "to_source_sha": after["source_sha"],
        "comparison": "SAME_SESSION_REVISION" if same else "EXPLICIT_CROSS_SESSION_LINKS_REQUIRED",
        "historical_action_ids": sorted(old_actions),
        "historical_intent_ids": sorted(old_intents),
        "new_action_ids": sorted(new_actions - old_actions) if same else sorted(new_actions),
        "new_intent_ids": sorted(new_intents - old_intents) if same else sorted(new_intents),
        "unmapped_historical_actions": unmapped_actions,
        "unmapped_historical_intents": unmapped_intents,
        "unproven_semantic_revisions": sorted(altered),
        "candidate_state_promotions_not_accepted": sorted(promotions),
        "unproven_state_transitions": sorted(state_transitions),
        "bd_focus_removed_projection_only": sorted(
            {x["id"] for x in before["bd"]["focus"]} - {x["id"] for x in after["bd"]["focus"]}),
        "bd_global_root_closure_inference": None,
        "accepted_distinct_root_closures": None,
        "weighted_closure": None,
        "complete_transcript_certified": False,
        "dispatch_authorized": False,
        "merge_authorized": False,
        "acceptance": "HOLD_LINEAGE_GAPS" if missing else "PASS_LINEAGE_ONLY_NOT_ADMISSION",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="Older CP.CLOSE record directory")
    parser.add_argument("--after", type=Path, required=True, help="Newer CP.CLOSE record directory")
    parser.add_argument("--links", type=Path, help="Optional explicit owner/source-bound continuity mapping")
    parser.add_argument("--out", type=Path, help="Optional read-only JSON review destination")
    args = parser.parse_args(argv)
    doc = read_json(args.links) if args.links else None
    report = reconcile(load_packet(args.before), load_packet(args.after), doc)
    raw = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(raw, encoding="utf-8", newline="\n")
    else:
        print(raw, end="")
    return 2 if report["acceptance"].startswith("HOLD") else 0


if __name__ == "__main__":
    raise SystemExit(main())
