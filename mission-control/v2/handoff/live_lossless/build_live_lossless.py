#!/usr/bin/env python3
"""Build a source-bound Live Lossless HTML read-only view.

Never imports a transcript, contacts GitHub, mutates BD, invokes a worker, or
grants merge admission. Dynamic browser readback is explicitly supplementary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CLOSE = ROOT / "mission-control/v2/handoff"
FROZEN = CLOSE / "closeout/records/CP-G3P-HTMLQA-20261017"
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
SCHEMA = "missioncontrol.live_lossless.dashboard.v1"
FILES = ("index.html", "app.js", "style.css", "snapshot.json", "manifest.json")
ALLOWED = {"TODO", "ACTIVE", "IN_PR", "HOLD", "DEFER", "DONE", "CONTROL"}


def fail(reason):
    raise ValueError("LIVE_LOSSLESS_FAIL_CLOSED: " + reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jsonbytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read(path):
    data = path.read_bytes()
    return json.loads(data), sha(data)


def public_link(url):
    try:
        p = urlparse(url)
        return p.scheme == "https" and p.netloc == "github.com" and p.path.startswith("/GBOGEB/") and not p.username
    except (TypeError, ValueError):
        return False


def validate_frozen():
    manifest, mh = read(FROZEN / "MANIFEST.json")
    if manifest.get("schema") != "missioncontrol.cp_close.manifest.v1" or manifest.get("authority_transfer") is not False:
        fail("frozen manifest authority")
    if manifest.get("verbatim_transcript_claim") is not False:
        fail("unavailable full ChatGPT transcript promotion")
    for filename, claimed in manifest["member_sha256"].items():
        if filename not in {"STATE.json", "CHAT_STATS.json", "INTENT_ACTION_LEDGER.json",
                            "BD_QUEUE_READONLY.json", "LOSSLESS_HANDOVER.md",
                            "NEXT_CHAT_DROPIN.md", "START_HERE.md", "TODO_BD_QUEUE.csv"}:
            fail("unexpected frozen file")
        if sha((FROZEN / filename).read_bytes()) != claimed:
            fail("frozen handover SHA256 mismatch: " + filename)
    state, _ = read(FROZEN / "STATE.json")
    stats, _ = read(FROZEN / "CHAT_STATS.json")
    ledger, _ = read(FROZEN / "INTENT_ACTION_LEDGER.json")
    bd, _ = read(FROZEN / "BD_QUEUE_READONLY.json")
    if (state.get("schema") != "missioncontrol.cp_close.state.v1"
            or state.get("session_alias") != "CP-G3P-HTMLQA-20261017"
            or state.get("intent_count_reconstructed") != len(ledger.get("intents", []))
            or state.get("action_count_reconstructed") != len(ledger.get("actions", []))
            or len(ledger["intents"]) != 6 or len(ledger["actions"]) != 7
            or stats.get("full_chat_total_prompts") is not None
            or stats.get("full_chat_total_messages") is not None
            or bd.get("new_canonical_bd_items") != 0
            or len(bd.get("focus", [])) != 3
            or state.get("authority_transfer") is not False):
        fail("frozen snapshot cardinality / privacy / BD drift")
    return state, stats, ledger, bd, {"frozen_manifest_sha256": mh}


def validate_delta(delta, observed, ledger):
    if delta.get("schema") != "missioncontrol.live_lossless.continuation_delta.v1":
        fail("delta schema")
    if (delta.get("source_class") != "USER_VISIBLE_CHAT_INTENT_SUMMARIZED_NOT_VERBATIM"
            or delta.get("authority_transfer") is not False
            or delta.get("security_waiver") is not False
            or delta.get("merge_admission") != "HOLD"
            or delta.get("original_chat_message_id") is not None
            or delta.get("original_chat_timestamp") is not None):
        fail("delta source scope and authority")
    intent = delta.get("intent", {})
    if intent.get("id") in {i["id"] for i in ledger["intents"]} or intent.get("id") != "SC-I007":
        fail("delta intent ID must be append-only")
    prior = {a["id"] for a in ledger["actions"]}
    actions = delta.get("actions", [])
    ids = {a.get("id") for a in actions}
    if len(actions) != 4 or len(ids) != len(actions) or ids & prior or ids != set(intent.get("actions", [])):
        fail("delta action coverage/identities")
    allids = ids | prior
    for a in actions:
        if (a.get("state") not in ALLOWED or a.get("priority") not in {"P0", "P1", "P2", "P3"}
                or not a.get("summary") or not a.get("done_when") or not a.get("owner")
                or not all(public_link(u) for u in a.get("evidence_urls", []))
                or not set(a.get("depends_on", [])).issubset(allids)):
            fail("invalid owned delta action")
    # Append-only dependencies cannot create an execution DAG cycle.
    deps = {a["id"]: a.get("depends_on", []) for a in ledger["actions"] + actions}
    visited, active = set(), set()
    def walk(item):
        if item in active:
            fail("cycle in source-owned continuation DAG")
        if item not in visited:
            active.add(item)
            for parent in deps[item]:
                if parent not in deps:
                    fail("dangling DAG edge")
                walk(parent)
            active.remove(item)
            visited.add(item)
    for item in deps:
        walk(item)
    subs = delta.get("subrequests", [])
    if len(subs) < 4 or len({s.get("id") for s in subs}) != len(subs):
        fail("missing distinct subrequests")
    for s in subs:
        if not s.get("title") or not s.get("detail") or not set(s.get("actions", [])).issubset(ids):
            fail("unowned subrequest")
    if observed.get("schema") != "missioncontrol.live_lossless.github_observation.v1":
        fail("observed GitHub schema")
    if (observed.get("repository") != "GBOGEB/pipeline-automation-hub"
            or observed.get("default_branch") != "master"
            or observed.get("time_precision") != "DATE_ONLY"
            or observed.get("authority_transfer") is not False
            or observed.get("security_waiver") is not False
            or observed.get("engineering_credit_delta") != 0
            or not HEX40.fullmatch(observed.get("main_sha", ""))):
        fail("observed GitHub authority/source identity")
    numbers = set()
    for pr in observed.get("prs", []):
        n = pr.get("number")
        if n in numbers or type(n) is not int or pr.get("state") not in {"OPEN", "MERGED", "CLOSED_UNMERGED"}:
            fail("duplicate or invalid observed PR")
        if not HEX40.fullmatch(pr.get("head", "")) or (pr["state"] == "MERGED" and not HEX40.fullmatch(pr.get("merge", ""))):
            fail("missing SHA for PR")
        numbers.add(n)
    if not {620, 621, 631, 640, 641, 642}.issubset(numbers):
        fail("required PR source observations missing")
    run = observed.get("native_run", {})
    if run.get("head_sha") != observed["main_sha"] or run.get("conclusion") != "success":
        fail("native matched SHA")
    if type(run.get("tests_total")) is not int or type(run.get("tests_passing")) is not int or run["tests_total"] < 1 or run["tests_passing"] > run["tests_total"]:
        fail("native QA denominator")
    if not public_link(run.get("url", "")):
        fail("native run source URL")
    lm = observed.get("live_monitor", {})
    if not (lm.get("default_frequency_minutes") == 15
            and lm.get("supported_frequency_minutes") == [0, 15, 60]
            and set(lm.get("pull_requests", [])) <= numbers
            and lm.get("merge_admission") == "INDEPENDENT_HOLD"):
        fail("unsafe polling or requalification")
    return True


def validate_closeout_profile(profile, protocol):
    if profile.get("moniker") == "CP.CLOSEOUT":
        return
    if (profile.get("moniker") != "CP.CLOSEOUT_ALIAS_OF_CP.CLOSE"
            or profile.get("status") != "OPTIONAL_REPORTING_ANNEX_NOT_CANONICAL"
            or profile.get("control") != "mission-control/v2/handoff/closeout/CP_CLOSE_GITHUB_v1.json"
            or protocol.get("schema") != "missioncontrol.cp_close.protocol.v1"
            or protocol.get("name") != "CP.CLOSE"):
        fail("canonical moniker drift")


def build_data():
    state, stats, frozen, bd, provenance = validate_frozen()
    delta, delta_hash = read(HERE / "FOLLOWUP_DELTA_20261017.json")
    observed, observed_hash = read(HERE / "GITHUB_OBSERVED_20261017.json")
    profile, profile_hash = read(CLOSE / "CHAT_CLOSEOUT_PROFILE_V1.json")
    _operator, operator_hash = read(CLOSE / "CP_HANDOFF_RESUME_V1.json")
    protocol, _ = read(CLOSE / "closeout/CP_CLOSE_GITHUB_v1.json")
    validate_closeout_profile(profile, protocol)
    live_profile, live_profile_hash = read(HERE / "LIVE_LOSSLESS_PROFILE_v1.json")
    if (live_profile.get("schema") != "missioncontrol.live_lossless.profile.v1"
            or live_profile.get("moniker") != "CP.LIVE"
            or live_profile.get("review", {}).get("authority_transfer") is not False
            or live_profile.get("data_population_policy", {}).get("original_user_prompt_count") is not None):
        fail("CP.LIVE cannot replace canonical source or invent prompt counts")
    validate_delta(delta, observed, frozen)
    intents = frozen["intents"] + [delta["intent"]]
    actions = frozen["actions"] + delta["actions"]
    ids = {a["id"] for a in actions}
    for i in intents:
        if not set(i.get("actions", [])) <= ids:
            fail("unresolved intent link")
    summary = {
        "reconstructed_intents": len(intents),
        "original_intents": len(frozen["intents"]),
        "current_new_intents": 1,
        "tracked_actions": len(actions),
        "original_actions": len(frozen["actions"]),
        "new_actions": len(delta["actions"]),
        "subrequests": len(delta["subrequests"]),
        "bd_focus": len(bd["focus"]),
        "open_actions": sum(a["state"] not in {"DONE","CONTROL"} for a in actions),
        "action_states": dict(sorted(Counter(a["state"] for a in actions).items())),
        "full_chat_user_prompts": None,
        "full_chat_messages": None,
        "full_chat_tokens": None,
        "native_closeout_tests": {"k": observed["native_run"]["tests_passing"],
                                  "d": observed["native_run"]["tests_total"],
                                  "population": "CP.CLOSE_EXACT_MAIN_ONLY",
                                  "run": observed["native_run"]["url"]},
        "global_code_coverage": None,
        "n_accepted": None
    }
    repo_url = "https://github.com/GBOGEB/pipeline-automation-hub/"
    frozen_path = "mission-control/v2/handoff/closeout/records/CP-G3P-HTMLQA-20261017/"
    monikers = [
        {"name":"CP.CLOSEOUT", "scope":"CANONICAL_SESSION_OPERATOR",
         "invocation": profile["invocation"],
         "details":"Capture the complete accessible sanitized intent, latest owned PR/CI and BD, verify and pursue governed main custody.",
         "url":repo_url+"blob/master/mission-control/v2/handoff/CHAT_CLOSEOUT_OPERATOR_V1.md"},
        {"name":"CP.LIVE", "scope":"ROLLING_IN_CHAT_GITHUB_SNAPSHOT",
         "invocation":live_profile["display"],
         "details":live_profile["purpose"]+" Browser refresh is read-only, and no background ChatGPT worker is launched.",
         "url":repo_url+"blob/master/mission-control/v2/handoff/live_lossless/LIVE_LOSSLESS_PROFILE_v1.json"},
        {"name":"CP.CLOSE", "scope":"EXPANDED_NINE_ARTIFACT_ALIAS",
         "invocation":'CP.CLOSE(scope="CURRENT_SESSION",target="GBOGEB/pipeline-automation-hub:master",mode="GITHUB_FIRST_LOSSLESS")',
         "details":"Expanded deterministic closeout implementation; compatibility document #642 is a pending draft and not yet canonical main.",
         "url":repo_url+"pull/642"},
        {"name":"CP.HANDOFF", "scope":"LOSSLESS_TRANSPORT",
         "invocation":'CP.HANDOFF(scope="CURRENT_SESSION",mode="LOSSLESS_INTENT",artifact="ZIP+DROPIN+STATE+MANIFEST")',
         "details":"Source-bound frozen handover ZIP and state; only complete original bytes if accessible.",
         "url":repo_url+"blob/master/mission-control/v2/handoff/README.md"},
        {"name":"CP.RESUME", "scope":"NEXT_OR_CURRENT_CHAT_REFRESH",
         "invocation":'CP.RESUME(source="GITHUB_FIRST",mode="VERIFY_REFRESH_EXECUTE",horizon="G3P:N_TO_N_PLUS_3")',
         "details":"Refresh native GitHub source heads and custody before any next authorized pulse.",
         "url":repo_url+"blob/master/"+frozen_path+"NEXT_CHAT_DROPIN.md"},
        {"name":"G3P.EXECUTE", "scope":"GOVERNED_THREE_PULSE_WAVE",
         "invocation":'G3P.EXECUTE(N,N+3)',
         "details":"One three-pulse bounded engineering wave; measured feedback is not three accepted advances.",
         "url":repo_url+"blob/master/mission-control/v2/N3_CONTINUATION_GUIDE.md"}
    ]
    public = {
        "schema": SCHEMA,
        "source_class": "FROZEN_SEMANTIC_HANDOVER_PLUS_READ_ONLY_GITHUB_OBSERVATION",
        "privacy": "SANITIZED_NOT_VERBATIM",
        "authority_transfer": False, "security_waiver": False,
        "merge_admission": "INDEPENDENT_HOLD",
        "publisher": "EXISTING_MISSIONCONTROL_METHOD_ATLAS_ONLY",
        "snapshot_time": {"date": observed["observed_date"], "precision": "DATE_ONLY"},
        "source": {"repository": observed["repository"], "branch": "master",
                   "frozen_main_sha": state["source"]["observed_main_sha"],
                   "current_observed_main_sha": observed["main_sha"],
                   "live_head_only_after_remote_readback": True},
        "summary": summary,
        "session": {"alias": state["session_alias"], "capture_scope": state["capture_scope"],
                    "complete_transcript_available": False,
                    "full_chat_prompts": None, "full_chat_messages": None,
                    "native_source_status": "SOURCE_OBSERVED_NONATOMIC",
                    "closeout_original_state": state["session_action_states"],
                    "statistics": stats},
        "intents": intents, "actions": actions,
        "subrequests": delta["subrequests"],
        "decisions": frozen["decisions"], "insights": frozen["insights"],
        "metric_observations": frozen["metrics"],
        "bd_queue": bd, "prs": observed["prs"], "issues": observed["issues"],
        "monikers": monikers,
        "github_monitor": observed["live_monitor"],
        "source_links": {
            "canonical_handover": repo_url+"blob/master/"+frozen_path+"LOSSLESS_HANDOVER.md",
            "frozen_manifest": repo_url+"blob/master/"+frozen_path+"MANIFEST.json",
            "session_statistics": repo_url+"blob/master/"+frozen_path+"CHAT_STATS.json",
            "bd_owner": repo_url+"blob/master/mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json",
            "closeout_operator": repo_url+"blob/master/mission-control/v2/handoff/CHAT_CLOSEOUT_OPERATOR_V1.md",
            "next_chat": repo_url+"blob/master/"+frozen_path+"NEXT_CHAT_DROPIN.md"
        },
        "provenance": {
            **provenance,
            "continuation_delta_sha256": delta_hash,
            "github_observation_sha256": observed_hash,
            "closeout_profile_sha256": profile_hash,
            "live_profile_sha256": live_profile_hash,
            "handoff_contract_sha256": operator_hash,
            "native_run": observed["native_run"],
            "local_browser_qa_is_not_hosted_proof": True
        }
    }
    return public


def build(out, check=False):
    snapshot = jsonbytes(build_data())
    assets = {"index.html": (HERE/"index.html").read_bytes(),
              "app.js":(HERE/"app.js").read_bytes(),
              "style.css":(HERE/"style.css").read_bytes(),
              "snapshot.json":snapshot}
    manifest = {
        "schema":"missioncontrol.live_lossless.publication_manifest.v1",
        "source_class":"STATIC_READONLY_CANDIDATE",
        "files_sha256":{k:sha(v) for k,v in sorted(assets.items())},
        "publisher":"EXISTING_PAGES_ONLY",
        "authority_transfer":False, "security_waiver":False,
        "merge_admission":"HOLD",
        "complete_transcript_claim":False
    }
    assets["manifest.json"] = jsonbytes(manifest)
    if check:
        if not out.is_dir():
            fail("published source directory absent")
        for name, data in assets.items():
            if not (out/name).is_file() or (out/name).read_bytes()!=data:
                fail("published artifact byte drift: "+name)
        if {p.name for p in out.iterdir() if p.is_file()} != set(FILES):
            fail("unrecognized/extra public files")
    else:
        out.mkdir(parents=True,exist_ok=True)
        for name,data in assets.items():
            (out/name).write_bytes(data)
    return {"schema":SCHEMA,"artifacts":len(assets),
            "snapshot_sha256":sha(snapshot),"manifest_sha256":sha(assets["manifest.json"]),
            "prompts":None,"merge_admission":"HOLD"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=HERE/"published")
    p.add_argument("--check",action="store_true")
    args=p.parse_args()
    print(json.dumps(build(args.out,args.check),sort_keys=True))


if __name__=="__main__":
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
