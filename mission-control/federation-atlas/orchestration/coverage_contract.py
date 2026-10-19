"""Source-qualified coverage observations; historical notes never become native proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

SOURCE = "mission-control/federation-atlas/orchestration/COVERAGE_OBSERVATIONS_v1.json"
SCHEMA = "missioncontrol.coverage.observation_atlas.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(root, name):
    require(isinstance(name, str) and bool(name) and "\\" not in name, "invalid evidence path")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "evidence path traversal")
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root), "evidence symlink escape")
    return path


def metric(value, unit):
    """Preserve unknown, real zero, branchless and empty executable populations."""
    require(isinstance(value, dict), "metric must be a mapping")
    covered, eligible = value.get("covered"), value.get("eligible")
    for name, number in (("covered", covered), ("eligible", eligible)):
        require(number is None or (type(number) is int and number >= 0), "invalid " + unit + " " + name)
    require(covered is None or eligible is not None, "numerator without denominator")
    require(covered is None or covered <= eligible, "covered exceeds eligible")
    if eligible == 0:
        require(covered in (None, 0), "nonzero numerator for empty population")
        classification = "BRANCHLESS_NOT_APPLICABLE" if unit == "branches" else "NO_EXECUTABLE_ITEMS"
    elif covered is None:
        classification = "UNKNOWN"
    elif covered == 0:
        classification = "ZERO_COVERED"
    elif covered == eligible:
        classification = "FULLY_COVERED"
    else:
        classification = "PARTIAL_COVERAGE"
    return {"covered": covered, "eligible": eligible,
            "pct": 100 * covered / eligible if covered is not None and eligible else None,
            "remaining": eligible - covered if covered is not None and eligible is not None else None,
            "classification": classification, "unit": unit}


def seal_event(payload):
    payload_hash = digest(canonical(payload))
    return {**payload, "event_sha256": payload_hash,
            "event_id": payload["logical_id"] + "::sha256:" + payload_hash}


def validate_event(event):
    require(isinstance(event, dict), "event must be a mapping")
    payload = {k: v for k, v in event.items() if k not in {"event_id", "event_sha256"}}
    require(isinstance(payload.get("logical_id"), str) and payload["logical_id"], "event logical identity missing")
    expected = seal_event(payload)
    require(event.get("event_sha256") == expected["event_sha256"] and event.get("event_id") == expected["event_id"], "immutable event payload drift")
    require(event.get("observation_kind") in {"CODE_COVERAGE", "INVENTORY_ONLY", "FEDERATION_BREADTH"}, "unknown observation kind")
    require(isinstance(event.get("repository"), str) and "/" in event["repository"], "repository missing")
    for name in ("eligible_modules", "instrumented_modules", "zero_covered_modules", "unmeasured_modules", "zero_branch_sets"):
        value = event.get(name)
        require(value is None or (type(value) is int and value >= 0), "invalid " + name)
    eligible, measured = event.get("eligible_modules"), event.get("instrumented_modules")
    require(measured is None or eligible is None or measured <= eligible, "measured modules exceed inventory")
    names = event.get("known_module_names", [])
    require(isinstance(names, list) and all(isinstance(name, str) and name for name in names), "invalid known module names")
    require(len(names) == len(set(names)) and (eligible is None or len(names) <= eligible), "module identities exceed inventory or duplicate")
    behavior = event.get("critical_behavior_verified")
    require(behavior is None or type(behavior) is bool, "invalid behavioral verification")
    for unit in ("statements", "branches", "changed_lines"):
        metric(event.get(unit, {}), unit)
    tests = event.get("tests", {})
    require(isinstance(tests, dict), "tests must be a mapping")
    for value in tests.values():
        require(value is None or (type(value) is int and value >= 0), "invalid test count")
    require(type(event.get("independently_verified")) is bool, "verification flag missing")
    if event["observation_kind"] == "FEDERATION_BREADTH":
        breadth = event.get("breadth", {})
        metric({"covered": breadth.get("observed"), "eligible": breadth.get("eligible")}, "breadth_cells")
    return json.loads(canonical(payload))


def validate_append_only(previous_events, current_events):
    """Check a supplied Git/source baseline; no hidden persistent store exists."""
    require(isinstance(previous_events, list) and isinstance(current_events, list), "event history must be ordered lists")
    require(len(current_events) >= len(previous_events), "coverage history event removed")
    for event in [*previous_events, *current_events]:
        validate_event(event)
    require(canonical(previous_events) == canonical(current_events[:len(previous_events)]), "coverage history prefix changed or reordered")
    require(len({e["event_id"] for e in current_events}) == len(current_events), "duplicate event in history")
    require(len({e["logical_id"] for e in current_events}) == len(current_events), "correction requires a new logical identity")
    return {"status": "ORDERED_SOURCE_PREFIX_PRESERVED", "retained": len(previous_events),
            "appended": len(current_events) - len(previous_events),
            "authority": "SUPPLIED_SOURCE_BASELINE_ONLY_NOT_A_PERSISTENT_DATABASE"}


def comparison_key(event, root):
    """Qualify a live series only from available, hash-checked evidence bytes.

    Full Git heads can differ for test-only changes; the unchanged production
    manifest/configuration/denominator identities define measurement continuity.
    Independent verification is an input assertion backed by a native receipt,
    not a conclusion inferred from a reported percentage.
    """
    if event.get("independently_verified") is not True:
        return None
    proof, native = event.get("proof", {}), event.get("native", {})
    required = ("source_manifest", "coverage_config", "denominator_manifest", "native_receipt")
    if not all(isinstance(proof.get(k), dict) and proof[k].get("path") and HEX64.fullmatch(str(proof[k].get("sha256", ""))) for k in required):
        return None
    if not HEX40.fullmatch(str(native.get("head_sha", ""))) or not all(type(native.get(k)) is int and native[k] > 0 for k in ("run_id", "attempt", "job_id")):
        return None
    if not event.get("instrumentation_version") or not event.get("coverage_policy_id"):
        return None
    values = {}
    for key in required:
        path = safe_path(root, proof[key]["path"])
        require(path.is_file(), "missing coverage proof bytes: " + key)
        raw = path.read_bytes()
        require(digest(raw) == proof[key]["sha256"], "coverage proof digest mismatch: " + key)
        values[key] = json.loads(raw) if key != "coverage_config" else None
    manifest = values["source_manifest"]
    require(isinstance(manifest, dict) and isinstance(manifest.get("files"), dict) and manifest["files"], "source manifest population missing")
    for name, member_hash in manifest["files"].items():
        safe_path(root, name)
        require(HEX64.fullmatch(str(member_hash)) is not None, "invalid source member digest")
    if event.get("eligible_modules") is not None:
        require(len(manifest["files"]) == event["eligible_modules"], "manifest/module inventory mismatch")
    denominators = values["denominator_manifest"]
    for unit in ("statements", "branches", "changed_lines"):
        require(denominators.get(unit) == event.get(unit, {}).get("eligible"), "denominator evidence mismatch: " + unit)
    receipt = values["native_receipt"]
    require(all(receipt.get(k) == native.get(k) for k in ("repository", "head_sha", "run_id", "attempt", "job_id")), "native receipt identity mismatch")
    require(native.get("repository") == event["repository"] and receipt.get("terminal") is True, "native terminal receipt missing")
    require(type(receipt.get("executed_steps")) is int and receipt["executed_steps"] > 0, "native execution steps missing")
    for unit in ("statements", "branches", "changed_lines"):
        require(receipt.get("coverage", {}).get(unit) == event.get(unit, {}), "native coverage measurement mismatch: " + unit)
    require(receipt.get("source_manifest_sha256") == proof["source_manifest"]["sha256"]
            and receipt.get("coverage_config_sha256") == proof["coverage_config"]["sha256"]
            and receipt.get("denominator_manifest_sha256") == proof["denominator_manifest"]["sha256"], "native receipt proof binding mismatch")
    key = {"repository": event["repository"], "family": event.get("family"), "cohort_id": event.get("cohort_id"),
           "source_manifest_sha256": proof["source_manifest"]["sha256"], "coverage_config_sha256": proof["coverage_config"]["sha256"],
           "denominator_manifest_sha256": proof["denominator_manifest"]["sha256"],
           "instrumentation_version": event["instrumentation_version"], "coverage_policy_id": event["coverage_policy_id"]}
    return digest(canonical(key))


def gate_rows(row):
    if row["observation_kind"] == "FEDERATION_BREADTH":
        return []
    verified = row["comparison_key"] is not None
    inventory_known = all(row.get(name) is not None for name in ("eligible_modules", "instrumented_modules", "unmeasured_modules"))
    rules = [
        ("inventory", "INVENTORY", None if not verified or not inventory_known else row.get("unmeasured_modules") == 0 and row.get("instrumented_modules") == row.get("eligible_modules")),
        ("zero-statements", "ZERO_COVERAGE", None if row.get("zero_covered_modules") is None else row["zero_covered_modules"] == 0),
        ("zero-branches", "ZERO_COVERAGE", None if row.get("zero_branch_sets") is None else row["zero_branch_sets"] == 0),
        ("behavior", "BEHAVIORAL_DEPTH", row.get("critical_behavior_verified")),
        ("broad-main-floor", "AGGREGATE", row["statements"]["pct"] >= 75 if row.get("scope") == "BROAD_MAIN" and row["statements"]["pct"] is not None else None),
        ("changed-lines", "AGGREGATE", row["changed_lines"]["pct"] >= 80 if row["changed_lines"]["pct"] is not None else None),
        ("native-execution", "NATIVE_EVIDENCE", True if verified else None),
    ]
    return [{"id": row["id"] + "::" + identity, "row_id": row["id"], "stage": stage,
             "status": "UNKNOWN" if result is None else "FAIL" if result is False else "PASS" if verified else "HOLD_UNVERIFIED",
             "reported_condition_met": result, "noncompensating": True,
             "reason": "Independent current source and native proof required; aggregate cannot compensate for preceding gates."}
            for identity, stage, result in rules]


def hierarchy(rows):
    repositories = {}
    for row in rows:
        repo = repositories.setdefault(row["repository"], {"id": row["repository"], "kind": "REPOSITORY", "label": row["repository"], "children": {}})
        family = repo["children"].setdefault(row["family"], {"id": row["repository"] + "::" + row["family"], "kind": "SOURCE_FAMILY", "label": row["family"], "children": []})
        family["children"].append({"id": row["id"], "kind": "COHORT", "label": row["label"], "row_id": row["id"],
            "unknown_module_identity_count": row["unknown_module_identity_count"],
            "children": [{"id": row["id"] + "::module:" + m["name"], "kind": "MODULE", "label": m["name"],
                          "qualification": "BASENAME_ONLY_ATTACHMENT_MEMBERSHIP", "statements": m["statements"], "branches": m["branches"],
                          "deeper_evidence": "UNKNOWN_FUNCTION_BRANCH_TEST_NATIVE_IDENTITY", "children": []} for m in row["modules"]]})
    for repo in repositories.values():
        repo["children"] = list(repo["children"].values())
    return {"id": "PORTFOLIO", "kind": "PORTFOLIO", "label": "Coverage portfolio · not qualified", "children": list(repositories.values()),
            "levels": ["PORTFOLIO", "REPOSITORY", "SOURCE_FAMILY", "COHORT", "MODULE", "FUNCTION_BRANCH", "TEST_CONTEXT", "NATIVE_EVIDENCE"]}


def build_model(root, profile=None, source_path=None):
    path = source_path or (profile or {}).get("sources", {}).get("coverage", SOURCE)
    source = json.loads(safe_path(root, path).read_bytes())
    require(source.get("schema") == "missioncontrol.coverage.observations.v1", "coverage source schema")
    require(source.get("authority_transfer") is False, "coverage source authority violation")
    note = source.get("provenance", {})
    require(note.get("kind") == "USER_PROVIDED_ATTACHMENT" and HEX64.fullmatch(str(note.get("sha256", ""))) is not None, "attachment provenance missing")
    events = source.get("events", [])
    require(isinstance(events, list) and events, "coverage events missing")
    ids, logical_ids, rows, ledger = set(), set(), [], []
    for event in events:
        validate_event(event)
        require(event["event_id"] not in ids and event["logical_id"] not in logical_ids, "duplicate coverage event identity")
        require(event.get("supersedes_event_id") is None or event["supersedes_event_id"] in ids, "superseded event must precede its correction")
        require(event.get("source_note_sha256") == note["sha256"], "event provenance mismatch")
        ids.add(event["event_id"])
        logical_ids.add(event["logical_id"])
        key = comparison_key(event, root)
        row = {**event, "id": event["logical_id"], "comparison_key": key,
               "independent_verification_reported": event["independently_verified"], "independently_verified": bool(key),
               "qualification": "NATIVE_RECEIPT_BYTES_VERIFIED" if key else "ATTACHMENT_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
               "source_provenance": note, "current_head_freshness": "UNKNOWN", "worst_file_coverage_pct": None,
               "portfolio_aggregation_eligible": False, "inventory_completeness_qualified": False,
               "modules": [{"name": name, "path": None, "membership": "ATTACHMENT_REPORTED_BASENAME_ONLY",
                            "statements": metric({}, "statements"), "branches": metric({}, "branches")}
                           for name in event.get("known_module_names", [])]}
        for unit in ("statements", "branches", "changed_lines"):
            row[unit] = metric(event.get(unit, {}), unit)
            if event["observation_kind"] == "FEDERATION_BREADTH":
                row[unit]["classification"] = "NOT_APPLICABLE_BREADTH"
        eligible = row.get("eligible_modules")
        row["unknown_module_identity_count"] = None if eligible is None else max(0, eligible - len(row["modules"]))
        row["additional_statements_to_75pct"] = max(0, (row["statements"]["eligible"] * 75 + 99) // 100 - row["statements"]["covered"]) if row.get("scope") == "BROAD_MAIN" and row["statements"]["covered"] is not None else None
        rows.append(row)
        ledger.append({"schema": "missioncontrol.coverage.burndown_event.v1", "event_id": event["event_id"],
                       "event_sha256": event["event_sha256"], "row_id": row["id"], "repository": row["repository"],
                       "cohort_id": row["cohort_id"], "comparison_key": key, "statements": row["statements"], "branches": row["branches"],
                       "qualification": row["qualification"], "independently_verified": bool(key),
                       "history_authority": "REGENERATED_PROJECTION_OF_IMMUTABLE_SOURCE_EVENTS_NOT_PERSISTENT_APPEND_LOG"})
    by_id = {row["id"]: row for row in rows}
    comparisons = []
    for anchor in source.get("reported_comparisons", []):
        require(anchor["from"] in by_id and anchor["to"] in by_id, "comparison anchor missing")
        before, after = by_id[anchor["from"]], by_id[anchor["to"]]
        require(before["repository"] == after["repository"] and before["family"] == after["family"], "cross-population comparison")
        result = {**anchor, "independently_verified": False, "qualification": "ATTACHMENT_REPORTED_MATCHED_HISTORY",
                  "comparable_for_live_series": False, "from_event_id": before["event_id"], "to_event_id": after["event_id"]}
        for unit in ("statements", "branches"):
            a, b = before[unit], after[unit]
            require(a["eligible"] == b["eligible"] and a["eligible"] and a["covered"] is not None and b["covered"] is not None, "comparison denominator or measurement mismatch")
            result[unit] = {"delta_covered": b["covered"] - a["covered"], "delta_pp": b["pct"] - a["pct"],
                            "before_pct": a["pct"], "after_pct": b["pct"], "eligible": a["eligible"]}
            require(result[unit]["delta_covered"] == anchor["reported_deltas"][unit], "reported comparison arithmetic mismatch")
        comparisons.append(result)
    gates = [gate for row in rows for gate in gate_rows(row)]
    return {"schema": SCHEMA, "source_path": path, "source_sha256": digest(safe_path(root, path).read_bytes()),
            "provenance": note, "rows": rows, "hierarchy": hierarchy(rows), "gates": gates,
            "gate_order": ["INVENTORY", "ZERO_COVERAGE", "BEHAVIORAL_DEPTH", "AGGREGATE", "NATIVE_EVIDENCE"],
            "comparisons": comparisons, "ledger_records": ledger,
            "portfolio": {"qualification": "NOT_QUALIFIED", "statement_pct": None, "branch_pct": None,
                          "rule": "No aggregate across unverified or overlapping populations; breadth is separate from code coverage."},
            "history_contract": "Immutable content-bound event IDs; source payload drift and duplicates rejected. JSONL is a regenerated projection, not proof of persistent append-only storage.",
            "authority_transfer": False, "merge_admission": "HOLD", "engineering_acceptance": "WITHHELD"}


def write_outputs(model, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metric_observations.json").write_bytes(canonical(model))
    (out / "coverage_burndown.jsonl").write_bytes(b"".join(canonical(event) for event in model["ledger_records"]))
    return {"metric_observations.json": digest((out / "metric_observations.json").read_bytes()),
            "coverage_burndown.jsonl": digest((out / "coverage_burndown.jsonl").read_bytes())}
