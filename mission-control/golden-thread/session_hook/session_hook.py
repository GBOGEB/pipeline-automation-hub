"""Manual sanitized chat-intent hook using Golden Thread v1 (no ChatGPT API access).

Intent summaries are *operator reconstructed*, not attested message transcripts.
No write, review, CI dispatch, owner approval or engineering authority is granted.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden_thread as gt

SCHEMA = "missioncontrol.chat_session_intake.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
INTENT = re.compile(r"^CP-SESSION-[0-9]{8}-[0-9]{3}$")
ACTION = re.compile(r"^CP-ACTION-[0-9]{8}-[0-9]{3}$")
REPO = re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+$")
ALLOWED = {"PLANNED_BEFORE_IMPLEMENTATION", "REFERENCED_PENDING_OWNER_GATE",
           "IMPLEMENTED_UNVERIFIED", "DEFERRED"}
FORBIDDEN = {"prompt", "raw_input", "raw_chat", "transcript", "full_transcript",
             "conversation_text", "api_key", "access_token"}


class SessionHookError(ValueError):
    pass


def _private_check(obj):
    if isinstance(obj, dict):
        if set(obj) & FORBIDDEN:
            raise SessionHookError("raw chat / credentials cannot enter GitHub")
        for value in obj.values():
            _private_check(value)
    elif isinstance(obj, list):
        for value in obj:
            _private_check(value)
    elif isinstance(obj, str):
        if len(obj) > 2500 or "-----BEGIN PRIVATE KEY-----" in obj or "sk-proj-" in obj:
            raise SessionHookError("unbounded or secret-like input")


def validate(data, previous=None):
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise SessionHookError("unsupported session intake schema")
    if (data.get("capture_mode"), data.get("privacy_boundary")) != (
            "MANUAL_SANITIZED_INTENT", "SANITIZED_SUMMARY_ONLY"):
        raise SessionHookError("manual sanitized ingress only")
    for key, expected in (("raw_transcript_exported", False),
                          ("session_alias_not_platform_id", True),
                          ("original_turn_ids_accessible", False),
                          ("authority_transfer", False),
                          ("merge_authorized", False),
                          ("engineering_credit", 0),
                          ("qps_disposition", "DEFER")):
        if data.get(key) != expected or type(data.get(key)) is not type(expected):
            raise SessionHookError("source or authority boundary: " + key)
    alias = data.get("session_alias")
    if not isinstance(alias, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{8,79}", alias):
        raise SessionHookError("invalid pseudonymous session alias")
    stamp = data.get("capture_checkpoint_utc")
    if not isinstance(stamp, str) or not stamp.endswith("Z"):
        raise SessionHookError("timezone-aware UTC capture required")
    gt.ts(stamp)
    _private_check(data)
    if previous is not None:
        gt.verify(previous)
        if previous.get("session_alias") != alias:
            raise SessionHookError("cross-session ledger append forbidden")
        if previous["events"] and gt.ts(stamp) < gt.ts(previous["events"][-1]["recorded_at"]):
            raise SessionHookError("recorded checkpoint cannot move backwards")
    known = set()
    if previous is not None:
        known = {e["payload"].get("intent_id") for e in previous["events"]
                 if e["event_type"] == "OBSERVED" and
                 e.get("payload", {}).get("source_class") == "SANITIZED_CHAT_INTENT"}
    intents = data.get("intent_events")
    if not isinstance(intents, list) or not 1 <= len(intents) <= 50:
        raise SessionHookError("bounded nonempty intent batch required")
    seen = set()
    action_ids = set()
    for i, item in enumerate(intents, 1):
        if not isinstance(item, dict) or not INTENT.fullmatch(str(item.get("intent_id", ""))):
            raise SessionHookError("invalid intent id")
        ident = item["intent_id"]
        if ident in known or ident in seen:
            raise SessionHookError("duplicate intent / historical rewrite")
        seen.add(ident)
        if type(item.get("logical_index")) is not int or item["logical_index"] != i:
            raise SessionHookError("logical sequence mismatch")
        if item.get("capture_checkpoint_utc") != stamp:
            raise SessionHookError("capture time mismatch")
        if (item.get("original_turn_id") is not None or
                item.get("original_message_time_utc") is not None or
                item.get("source_time_verification") != "UNKNOWN"):
            raise SessionHookError("ChatGPT message identity/time is not verified")
        if item.get("source_class") != "CURRENT_CONVERSATION_RECONSTRUCTED_USER_INTENT":
            raise SessionHookError("reconstruction source class required")
        if not isinstance(item.get("summary"), str) or not 15 <= len(item["summary"]) <= 440:
            raise SessionHookError("bounded sanitized summary required")
        parent = item.get("parent_intent_id")
        if parent is not None:
            if parent not in (seen - {ident}) | known:
                raise SessionHookError("parent must precede child")
            if item.get("relation_to_parent") != "REFINES_WITHOUT_SUPERSEDING":
                raise SessionHookError("do not silently supersede intent")
        action = item.get("action")
        if not isinstance(action, dict) or not ACTION.fullmatch(str(action.get("action_id", ""))):
            raise SessionHookError("stable action id required")
        if action["action_id"] in action_ids:
            raise SessionHookError("duplicate action id")
        action_ids.add(action["action_id"])
        if action.get("status") not in ALLOWED or action.get("verified_native_receipt") is not None:
            raise SessionHookError("manual intake cannot claim native verification")
        owner = action.get("owner_repo")
        issue = action.get("owner_issue")
        if not isinstance(owner, str) or not REPO.fullmatch(owner) or type(issue) is not int or issue < 1:
            raise SessionHookError("existing owner identity required")
        if item.get("owner_issue") != owner + "#" + str(issue):
            raise SessionHookError("action-to-intent owner mismatch")
        if action.get("existing_pr") is not None and (
                type(action["existing_pr"]) is not int or action["existing_pr"] < 1):
            raise SessionHookError("invalid existing PR")
        if not isinstance(action.get("summary"), str) or not 15 <= len(action["summary"]) <= 450:
            raise SessionHookError("bounded action summary required")
    for ref in data.get("existing_source_refs", []):
        if not isinstance(ref, dict) or not REPO.fullmatch(ref.get("repository", "")):
            raise SessionHookError("source owner invalid")
        if not isinstance(ref.get("path"), str) or not HEX40.fullmatch(ref.get("blob_sha", "")):
            raise SessionHookError("source path and exact blob required")
    forecast = data.get("forecast_pre_registered")
    if not isinstance(forecast, dict) or forecast.get("actual_native_adapter_result") is not None or forecast.get("score") != "PENDING_NATIVE_EXACT_HEAD":
        raise SessionHookError("forecast outcome must not be filled before native flight")
    return True


def build(data, previous=None):
    validate(data, previous)
    root = "SESSION-PROJECTION:" + data["session_alias"]
    events = deepcopy(previous["events"]) if previous is not None else []
    when = data["capture_checkpoint_utc"]

    def add(suffix, typ, subject, payload=None, parent=None, target=None, refs=None):
        row = {"event_id": suffix, "event_type": typ, "occurred_at": when,
               "recorded_at": when, "actor": "MissionControl.ManualSessionHook",
               "subject_ref": subject, "authority_domain": "FEDERATED_PROJECTION_ONLY",
               "evidence_class": "MANUAL_SANITIZED_INTENT_NOT_NATIVE_EVIDENCE",
               "evidence_refs": refs or [], "non_compensating_preserved": True,
               "payload": payload or {}}
        if parent is not None:
            row["from_ref"] = parent
        if target is not None:
            row["to_ref"] = target
        events.append(row)

    if previous is None:
        add("CP-GT-ROOT-" + data["session_alias"], "ROOT_CREATED", root,
            {"title": "Bounded session projection", "root_authority": "PROJECTION_ONLY",
             "canonical_bd_root": None})
    for item in data["intent_events"]:
        ident = item["intent_id"]
        ref = "USER-INTENT:" + ident
        act = item["action"]
        target = "ACTION:" + act["action_id"]
        prefix = "CP-GT-" + ident
        add(prefix + "-OBS", "OBSERVED", ref, {
            "object_type": "occurrence", "source_class": "SANITIZED_CHAT_INTENT",
            "intent_id": ident, "title": item["summary"],
            "original_turn_id": None, "original_message_time_utc": None,
            "source_time_verification": "UNKNOWN",
            "capture_checkpoint_utc": when,
            "parent_intent_id": item.get("parent_intent_id")}, refs=[item["owner_issue"]])
        add(prefix + "-LINK", "ATTACHED_TO_ROOT", ref, parent=ref, target=root)
        if item.get("parent_intent_id"):
            add(prefix + "-REFINE", "CLASSIFIED", ref, {
                "prior_intent_ref": "USER-INTENT:" + item["parent_intent_id"],
                "intent_relation": "REFINES_WITHOUT_SUPERSEDING"})
        add(prefix + "-ACTION", "WORK_ORDER_CREATED", target, {
            "title": act["summary"], "owner_repo": act["owner_repo"],
            "owner_issue": act["owner_issue"], "existing_pr": act.get("existing_pr"),
            "capture_status": act["status"], "formal_credit": 0}, parent=ref)
        add(prefix + "-HOLD", "NON_COMPENSATING_GATE_SET", target, {
            "blocking_predicate": "NATIVE_RECEIPT_AND_ELIGIBLE_OWNER_REVIEW",
            "reentry_trigger": "INDEPENDENT_VERIFICATION_ON_NEW_EXACT_HEAD"})
    ledger = {"schema": gt.LEDGER_SCHEMA, "projection_schema_version": 1,
              "authority_transfer": False, "session_alias": data["session_alias"],
              "events": events}
    result = gt.seal(ledger)
    gt.verify(result)
    return result


def projection(data, ledger, source_sha):
    if not HEX40.fullmatch(source_sha):
        raise SessionHookError("exact source SHA needed for output")
    gt.verify(ledger)
    p = gt.rebuild(ledger)
    root = "SESSION-PROJECTION:" + data["session_alias"]
    expansion = gt.expand_root(ledger, root)
    rows = [{
        "intent_id": e["intent_id"], "parent_intent_id": e.get("parent_intent_id"),
        "summary": e["summary"], "source_binding": "CHAT_TURN_UNBOUND",
        "owner": e["owner_issue"], "action_id": e["action"]["action_id"],
        "action_status": e["action"]["status"], "action_summary": e["action"]["summary"]
    } for e in data["intent_events"]]
    return {
        "schema": "missioncontrol.chat_session_projection.v1",
        "session_alias": data["session_alias"], "producer_source_sha": source_sha,
        "source_intake_digest": gt.digest(data),
        "golden_thread_head_digest": ledger["head_event_digest"],
        "golden_thread_projection_digest": p["projection_digest"],
        "intents": rows, "intent_count": len(rows),
        "work_order_count": len(expansion["work_orders"]),
        "root_authority": "PROJECTION_ONLY", "raw_chat_exported": False,
        "source_turns_unbound": len(rows), "native_verified_actions": 0,
        "evidence_credit": 0, "qps_disposition": "DEFER",
        "merge_authorized": False, "authority_transfer": False
    }


def make_mermaid(report):
    lines = ['flowchart TD', '  R["Session intent projection"]',
             '  HOLD["Owner approval and native receipt HOLD"]']
    for i, x in enumerate(report["intents"], 1):
        lines += [f'  I{i}["Sanitized user intent {i}"]',
                  f'  A{i}["Owned action {i}"]',
                  f'  R --> I{i}', f'  I{i} --> A{i}', f'  A{i} --> HOLD']
        if x["parent_intent_id"] is not None:
            for k, prior in enumerate(report["intents"], 1):
                if prior["intent_id"] == x["parent_intent_id"]:
                    lines.append(f'  I{k} -.->|refines| I{i}')
    return "\n".join(lines) + "\n"


def make_html(report):
    esc = lambda text: html.escape(str(text), quote=True)
    rows = []
    for e in report["intents"]:
        repo, issue = e["owner"].split("#")
        url = "https://github.com/" + repo + "/issues/" + issue
        rows.append('<tr><td>' + esc(e["intent_id"]) + '</td><td>' +
                    esc(e["summary"]) + '</td><td><a href="' + esc(url) +
                    '">' + esc(e["owner"]) + '</a></td><td>' +
                    esc(e["action_status"]) + '</td><td>' +
                    esc(e["source_binding"]) + '</td></tr>')
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CODE PURPLE | Session Intent Hook</title>
<style>:root{color-scheme:dark;--bg:#0b0b0b;--fg:#f7f7f7;--border:#444}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:24px 18px;overflow-wrap:anywhere}h1{font-size:1.6rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}
section{border:1px solid var(--border);border-radius:8px;padding:13px}strong{font-size:1.6rem}
.scroller{overflow-x:auto}table{width:100%;min-width:820px;border-collapse:collapse}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--border);padding:10px}
input{max-width:100%;padding:10px;color:inherit;background:transparent;border:1px solid var(--border);border-radius:6px}
a{color:inherit}footer{margin-top:25px;border-top:1px solid var(--border);padding-top:14px;overflow-wrap:anywhere}
@media(prefers-color-scheme:light){:root{--bg:white;--fg:#171717;--border:#ccc}}</style></head><body><main>
<h1>CODE PURPLE — Recursive session intent ledger</h1>
<p>Operator-sanitized, bounded chat intent. Original ChatGPT message IDs and timestamps unavailable; this is not a webhook, full transcript or engineering approval.</p>
<div class="grid"><section>Recorded intents<br><strong>''' + str(report["intent_count"]) +
'''</strong></section><section>Owned work orders<br><strong>''' +
str(report["work_order_count"]) + '''</strong></section><section>Unbound source turns<br><strong>''' +
str(report["source_turns_unbound"]) + '''</strong></section><section>Native verified actions<br><strong>0</strong></section></div>
<h2>Intent → action → owner</h2><label for="filter">Search lineage:</label>
<input id="filter" type="search" placeholder="Intent, owner, state" aria-label="Filter lineage">
<div class="scroller"><table id="intent-table"><thead><tr><th>Intent</th><th>Sanitized directive</th><th>Owner</th><th>Action</th><th>Source status</th></tr></thead><tbody>''' +
"".join(rows) + '''</tbody></table></div>
<footer>Exact source SHA: <code>''' + esc(report["producer_source_sha"]) +
'''</code><p>Golden Thread head: <code>''' + esc(report["golden_thread_head_digest"]) +
'''</code></p><p>QPS DEFER · owner admission HOLD · authority transfer false · raw chat not stored</p></footer>
</main><script>document.getElementById("filter").addEventListener("input",function(){
let q=this.value.toLowerCase();document.querySelectorAll("#intent-table tbody tr").forEach(
r=>{r.hidden=!r.textContent.toLowerCase().includes(q);});});</script></body></html>''')


def emit(data, ledger, out, source_sha):
    report = projection(data, ledger, source_sha)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "session_ledger.json": json.dumps(ledger, sort_keys=True, indent=2) + "\n",
        "session_projection.json": json.dumps(report, sort_keys=True, indent=2) + "\n",
        "session_execution_dag.mmd": make_mermaid(report),
        "session_review.html": make_html(report),
    }
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    manifest = {
        "schema": "missioncontrol.chat_session_receipt.v1",
        "producer_source_sha": source_sha,
        "source_intake_digest": report["source_intake_digest"],
        "golden_thread_head_digest": report["golden_thread_head_digest"],
        "files": {name: {"sha256": "sha256:" + hashlib.sha256(content.encode()).hexdigest(),
                         "bytes": len(content.encode())} for name, content in sorted(files.items())},
        "engineering_credit": 0, "qps_disposition": "DEFER",
        "merge_authorized": False, "authority_transfer": False
    }
    (out / "session_receipt.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--previous-ledger", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    old = json.loads(args.previous_ledger.read_text(encoding="utf-8")) if args.previous_ledger else None
    ledger = build(data, previous=old)
    report = emit(data, ledger, args.out, args.source_sha)
    print(json.dumps({"status": "SOURCE_BOUND_PROJECTION", "intents": report["intent_count"],
                      "work_orders": report["work_order_count"], "native_verified": 0,
                      "merge_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
