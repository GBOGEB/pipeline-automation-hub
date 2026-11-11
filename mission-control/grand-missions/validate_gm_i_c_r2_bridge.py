#!/usr/bin/env python3
"""Fail-closed validator for the GM-I-C R2 re-open overlay (two-way Drive bridge with broker).

The overlay may add waves' progress, contracts, REX and evidence. It may not rewrite the v0.1
baseline, the wave plan, or any authority. Everything that would let a YAML edit claim progress
or authority is pinned here, so changing it needs a reviewed change to this file:

- the wave set, each wave's repository, gates and owner-action flag, and the minimum dependency graph;
- the baseline pointers, SHAs and treatment;
- the broker functions, runtime-worker authorities and merge authority.

A wave is PASS only with merged evidence, P1 to P3 pulses and an owner-admitted post-merge receipt.
The owner-only IC3 gate additionally needs an injected hosted attestor; YAML fields never suffice.
Malformed input fails with a clean ``FAIL:`` message, never a traceback.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
CONTROL = ROOT / "GM_I_C_R2_BIDIRECTIONAL_BRIDGE_CONTROL_v1.yaml"
BASELINE_CONTROL = ROOT / "GM-I-C_CROSS_AGENT_DRIVE_FEDERATION_CONTROL_v0.1.yaml"
BASELINE_CREW = ROOT / "GM-I-C_CREW_ALLOCATION_v0.1.yaml"

SHA40 = re.compile(r"[0-9a-f]{40}")
OPEN_STATES = {"PLANNED", "IN_PROGRESS", "BLOCKED_ON_OWNER"}
DONE_STATE = "PASS"
PENDING = "PENDING"
IC3_GATE = "IC3_AUTH"
IC3_PASS_STATE = "IC3_DRIVE_READONLY_GT0_STEP_PASS"
RECEIPT_DIR = "mission-control/grand-missions/"
HUB = "GBOGEB/pipeline-automation-hub"
PROVIDER = "GBOGEB/GEMINI"

REQUIRED_NONCLAIMS = {
    "R2_REOPEN_NE_IC3_PASS",
    "R2_OFFLINE_CONTRACT_PASS_NE_HOSTED_DRIVE_PASS",
    "DRIVE_SNAPSHOT_NE_SOURCE_OF_TRUTH",
    "BROKER_DRAFT_PR_NE_REVIEW_OR_MERGE",
    "NO_GM_VI_NO_RENUMBERING",
    "OFFLINE_RECEIPT_CROSSCHECK_NE_GITHUB_VERIFICATION",
}
CANDIDATE_RECEIPT_NONCLAIMS = {
    "POSTMERGE_DOV_CANDIDATE_NE_P2_INDEPENDENT_REVIEW",
    "POSTMERGE_DOV_CANDIDATE_NE_OWNER_ADMISSION",
}

# The wave plan. Editing a wave's gates, repository or owner flag in YAML must not move work
# around a gate (for example, dropping IC3_AUTH from R2-W3 to pass it without the attestor).
PINNED_WAVES = {
    "R2-W0": {"repo": HUB, "maps_to_gates": ["IC0_REGISTER"], "owner_action_required": False},
    "R2-W1": {"repo": PROVIDER, "maps_to_gates": ["IC2_BRIDGE"], "owner_action_required": False},
    "R2-W2": {"repo": PROVIDER, "maps_to_gates": ["IC7_ROUNDTRIP", "IC8_ADVERSARIAL"], "owner_action_required": False},
    "R2-W3": {"repo": PROVIDER, "maps_to_gates": [IC3_GATE], "owner_action_required": True},
    "R2-W4": {"repo": PROVIDER, "maps_to_gates": ["IC2_BRIDGE", "IC7_ROUNDTRIP"], "owner_action_required": False},
    "R2-W5": {"repo": PROVIDER, "maps_to_gates": ["IC5_CONSUMER_B", "IC6_PARITY"], "owner_action_required": True},
    "R2-W6": {"repo": PROVIDER, "maps_to_gates": ["IC8_ADVERSARIAL", "IC9_CONTROL"], "owner_action_required": False},
}
# Minimum dependency graph (DO_NOT_START_A_BLOCKED_WAVE_BEFORE_ITS_BLOCKER_IS_PASS).
REQUIRED_DEPENDENCIES = {
    "R2-W4": {"R2-W3"},
    "R2-W5": {"R2-W4"},
    "R2-W6": {"R2-W5"},
}
PINNED_BASELINE = {
    "historical_control": RECEIPT_DIR + BASELINE_CONTROL.name,
    "historical_crew": RECEIPT_DIR + BASELINE_CREW.name,
    "current_pointer": RECEIPT_DIR + "GM_I_C_CURRENT_v1.yaml",
    "treatment": "OVERLAY_DO_NOT_REWRITE_V0_1_CONTROL_CREW_REGISTER_OR_REGISTRY",
    "home_repo": HUB,
    "home_base_sha": "bc974acdde8c0f28ba8e6e0d64386157697e4db1",
    "provider_repo": PROVIDER,
    "provider_main_sha_at_reopen": "6136b9ebd976b994afefc57cc7d3497060e45a3e",
}
PINNED_BROKER = {
    "is_crew": False,
    "identity": "BROKER_GITHUB_APP",
    "functions": {
        "HOLD": "KEEP_INBOX_ITEMS_UNTIL_INGESTED_QUARANTINE_REJECTS_WITH_REASON",
        "READ": "DRIVE_API_READ_AND_DOCS_EXPORT_CONTENT_IS_UNTRUSTED_DATA",
        "PUBLISH": "GIT_ARCHIVE_AT_EXACT_SHA_PLUS_REPO_SNAPSHOT_MANIFEST",
        "REVIEW": "NONE_ITSELF_OPENS_DRAFT_PR_FOR_CI_AGENT_AND_OWNER_REVIEW",
        "UPDATE": "THREE_WAY_FROM_DECLARED_BASE_SHA_THEN_REBASE_ONTO_DEFAULT_HEAD",
        "FIX": "NEVER_CONFLICTS_GO_TO_PR_FLAGGED_FOR_AGENT_RESOLUTION",
        "COMMIT": "BROKER_BRANCHES_ONLY_NEVER_DEFAULT_BRANCH",
        "DISJOINTED_COMMIT": "STALE_BASE_BLOB_FORCES_THREE_WAY_OR_CONFLICT_DRAFT",
        "DISJOINTED_CENSUS": "COMPARE_ONLY_AT_EQUAL_SHA_ELSE_LABEL_STALE",
    },
}
PINNED_WORKER_AUTHORITY = {
    "CLAUDE_CODE_LOCAL": "BRANCH_AND_PR_VIA_OWNER_GH_KEYRING",
    "CLAUDE_DRIVE_CONSUMER": "NONE_UNTIL_INSTANTIATED",
    "CODEX_GITHUB": "BRANCH_AND_PR_ONLY",
    "GEMINI_DRIVE_APP": "INBOX_PROPOSAL_ONLY",
    "BROKER_GITHUB_APP": "BROKER_BRANCH_AND_DRAFT_PR_ONLY",
    "GOOGLE_WIF_PUBLISH_PRINCIPAL": "WRITER_ON_SNAPSHOT_FOLDER_ONLY",
}
PINNED_MISSION_CONTROL = {
    "home": HUB,
    "governor": "U01",
    "merge_authority": "HUMAN_OWNER_VIA_PROTECTED_DEFAULT_BRANCH",
}


class Fail(SystemExit):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Fail(f"FAIL: {message}")


def is_int(value) -> bool:
    """A real int: bool is a subclass of int in Python and must not count as a PR number."""
    return type(value) is int


def is_sha40(value) -> bool:
    return isinstance(value, str) and SHA40.fullmatch(value) is not None


def mapping(value, what: str) -> dict:
    require(isinstance(value, dict), f"{what} must be a mapping")
    return value


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_repo_yaml(rel_path: str):
    require(isinstance(rel_path, str), "receipt path must be a string")
    path = (REPO / rel_path).resolve()
    require(path.is_relative_to((REPO / RECEIPT_DIR).resolve()), f"receipt outside {RECEIPT_DIR}: {rel_path}")
    require(path.is_file(), f"referenced receipt missing: {rel_path}")
    return load_yaml(path)


def validate_postmerge_receipt(control: dict, wave: dict, ev: dict, receipt) -> None:
    """Cross-check a referenced post-merge DoV receipt against the wave's control evidence."""
    wid = wave["id"]
    source_sha = ev["postmerge_source_sha"]
    receipt = mapping(receipt, f"{wid} post-merge receipt")
    require(receipt.get("mission") == control["mission_id"], f"{wid} post-merge receipt mission mismatch")
    require(receipt.get("reopen_id") == control["reopen_id"], f"{wid} post-merge receipt reopen_id mismatch")
    require(receipt.get("wave") == wid, f"{wid} post-merge receipt is bound to wave {receipt.get('wave')}")
    require(receipt.get("authority_transfer") is False, f"{wid} post-merge receipt transfers authority")
    require(
        is_int(receipt.get("formal_credit_delta")) and receipt["formal_credit_delta"] == 0,
        f"{wid} post-merge receipt claims credit",
    )

    pub = mapping(receipt.get("publication"), f"{wid} post-merge receipt publication")
    require(pub.get("repository") == wave["repo"], f"{wid} post-merge receipt publication repo mismatch")
    require(is_int(pub.get("pr")) and pub["pr"] == ev["pr"], f"{wid} post-merge receipt PR mismatch")
    require(pub.get("merge_sha") == ev["merge_sha"], f"{wid} post-merge receipt merge SHA mismatch")

    src = mapping(receipt.get("validated_source"), f"{wid} post-merge receipt validated_source")
    require(src.get("repository") == wave["repo"], f"{wid} post-merge receipt validated-source repo mismatch")
    require(src.get("commit_sha") == source_sha, f"{wid} post-merge receipt validated-source SHA mismatch")
    require(src.get("contains_merge") == ev["merge_sha"], f"{wid} post-merge receipt validated source does not contain the merge")

    hosted = mapping(receipt.get("hosted_postmerge_runs"), f"{wid} post-merge receipt hosted_postmerge_runs")
    require(hosted.get("event") == "push", f"{wid} post-merge receipt hosted runs are not push (post-merge) runs")
    require(hosted.get("head_sha") == source_sha, f"{wid} post-merge receipt hosted-run head mismatch")
    runs = hosted.get("runs")
    require(isinstance(runs, list) and bool(runs), f"{wid} post-merge receipt lists no hosted runs")
    for run in runs:
        run = mapping(run, f"{wid} post-merge receipt hosted run")
        require(is_int(run.get("run_id")), f"{wid} post-merge receipt hosted run without a run id")
        require(run.get("conclusion") == "success", f"{wid} post-merge receipt hosted run {run.get('run_id')} not success")

    dogfood = receipt.get("dogfood_against_real_repo")
    if dogfood is not None:
        dogfood = mapping(dogfood, f"{wid} post-merge receipt dogfood")
        require(dogfood.get("head_sha") == source_sha, f"{wid} post-merge receipt dogfood head mismatch")

    status = receipt.get("status")
    require(isinstance(status, str), f"{wid} post-merge receipt has no status")
    if wave["state"] == DONE_STATE:
        require(status.startswith("ADMITTED"), f"{wid} PASS needs an owner-ADMITTED post-merge receipt, got {status}")
    else:
        require(status.startswith("CANDIDATE"), f"{wid} not PASS but post-merge receipt is not a CANDIDATE")
        nonclaims = receipt.get("nonclaims")
        require(isinstance(nonclaims, list), f"{wid} candidate post-merge receipt has no nonclaims")
        missing = CANDIDATE_RECEIPT_NONCLAIMS - set(nonclaims)
        require(not missing, f"{wid} candidate post-merge receipt is missing nonclaims {sorted(missing)}")


def validate_evidence(control: dict, wave: dict, receipt_loader) -> None:
    """Evidence is checked whenever present; PASS additionally requires all of it."""
    wid = wave["id"]
    passed = wave["state"] == DONE_STATE
    pulses = mapping(wave.get("pulses") or {}, f"{wid} pulses")
    ev = wave.get("evidence")
    if ev is None:
        require(not passed, f"{wid} PASS without a PR number")
        return
    ev = mapping(ev, f"{wid} evidence")
    if "pr" in ev or passed:
        require(is_int(ev.get("pr")), f"{wid} evidence PR must be an integer" if "pr" in ev else f"{wid} PASS without a PR number")
    if "merge_sha" in ev or passed:
        require(is_sha40(ev.get("merge_sha")), f"{wid} evidence merge SHA must be a full 40-hex SHA")

    p1 = pulses.get("P1", PENDING)
    if "pr" in ev and p1 != PENDING:
        require(p1 == f"{wave['repo']}#{ev['pr']}", f"{wid} P1 pulse {p1} does not match evidence {wave['repo']}#{ev['pr']}")

    has_receipt = "postmerge_dov_candidate" in ev
    has_source = "postmerge_source_sha" in ev
    require(has_receipt == has_source, f"{wid} post-merge receipt and source SHA must be declared together")
    if passed:
        for pulse in ("P1", "P2", "P3"):
            value = pulses.get(pulse, PENDING)
            require(isinstance(value, str) and value and value != PENDING, f"{wid} PASS while pulse {pulse} is {value}")
        require(has_receipt, f"{wid} PASS without a bound post-merge receipt (P3)")
    if not has_receipt:
        return
    require(is_int(ev.get("pr")) and "merge_sha" in ev, f"{wid} post-merge receipt needs evidence PR and merge SHA")
    require(is_sha40(ev["postmerge_source_sha"]), f"{wid} post-merge source SHA must be a full 40-hex SHA")
    validate_postmerge_receipt(control, wave, ev, receipt_loader(ev["postmerge_dov_candidate"]))


def validate(
    control: dict, baseline: dict, crew: dict, brief_text: str, hosted_ic3_attestor=None, receipt_loader=load_repo_yaml
) -> dict:
    try:
        return _validate(control, baseline, crew, brief_text, hosted_ic3_attestor, receipt_loader)
    except Fail:
        raise
    except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
        raise Fail(f"FAIL: malformed overlay or receipt: {type(exc).__name__}: {exc}") from None


def _validate(control, baseline, crew, brief_text, hosted_ic3_attestor, receipt_loader) -> dict:
    control = mapping(control, "overlay")
    require(control.get("mission_id") == "GM-I-C", "overlay mission id must be GM-I-C")
    require(control.get("parent") == "GM-I", "overlay parent must remain GM-I")
    require(control.get("authority_transfer") is False, "authority transfer must remain false")
    require(
        is_int(control.get("formal_credit_delta")) and control["formal_credit_delta"] == 0,
        "formal credit delta must remain integer zero",
    )
    require(control.get("reopen_kind") == "BRIEF_EXPANSION_OVERLAY", "re-open must be an overlay")

    base = mapping(control.get("baseline"), "baseline")
    for key, pinned in PINNED_BASELINE.items():
        require(base.get(key) == pinned, f"baseline {key} changed from pinned {pinned}")
    for key in ("historical_control", "historical_crew", "current_pointer"):
        require((REPO / base[key]).is_file(), f"baseline file missing: {base[key]}")

    mc = mapping(control.get("mission_control"), "mission_control")
    for key, pinned in PINNED_MISSION_CONTROL.items():
        require(mc.get(key) == pinned, f"mission_control {key} changed from pinned {pinned}")

    first_red = mapping(control.get("first_red"), "first_red")
    require(first_red.get("gate") == baseline["first_red"]["gate"] == IC3_GATE, "first red must remain IC3_AUTH")
    require(first_red.get("owner") == baseline["first_red"]["owner"], "first-red owner must match baseline")
    require(first_red.get("unchanged_from_baseline") is True, "first red must be declared unchanged")
    require(isinstance(first_red.get("state"), str), "first_red.state must be a string")

    gate_ids = [row["id"] for row in baseline["mission_gates"]]
    reserve = {row["crew_id"]: set(row.get("wake_on") or []) for row in crew["reserve_crew"]}
    active_ids = {row["crew_id"] for row in crew["active_crew"]}
    crew_ids = active_ids | set(reserve)

    waves = control.get("waves")
    require(isinstance(waves, list), "waves must be a list")
    for wave in waves:
        mapping(wave, "wave")
    wave_ids = [w.get("id") for w in waves]
    require(wave_ids == list(PINNED_WAVES), f"wave set must be exactly {list(PINNED_WAVES)}, got {wave_ids}")

    ic3_pass = False
    states = {}
    for wave in waves:
        wid = wave["id"]
        pinned = PINNED_WAVES[wid]
        for key, value in pinned.items():
            require(wave.get(key) == value, f"{wid} {key} changed from pinned {value}")
        for gate in wave["maps_to_gates"]:
            require(gate in gate_ids, f"{wid} maps to unknown gate {gate}")
        wave_crew = wave.get("crew")
        require(isinstance(wave_crew, list) and bool(wave_crew), f"{wid} must name its crew")
        unknown = set(wave_crew) - crew_ids
        require(not unknown, f"{wid} assigns crew outside the v0.1 roster: {sorted(unknown)}")
        require(bool(wave.get("dod")), f"{wid} has no definition of done")

        reserve_used = sorted(set(wave_crew) - active_ids)
        wake = wave.get("reserve_wake") or {}
        wake = mapping(wake, f"{wid} reserve_wake")
        for member in reserve_used:
            trigger = wake.get(member)
            require(trigger is not None, f"{wid} wakes reserve crew {member} without a named trigger in reserve_wake")
            require(trigger in reserve[member], f"{wid} wakes {member} on {trigger}, not one of its v0.1 wake_on triggers")
        require(set(wake) <= set(reserve_used), f"{wid} reserve_wake names crew not woken in this wave: {sorted(set(wake) - set(reserve_used))}")

        deps = wave.get("depends_on")
        require(isinstance(deps, list), f"{wid} must declare depends_on (use [] for none)")
        for dep in deps:
            require(dep in wave_ids and wave_ids.index(dep) < wave_ids.index(wid), f"{wid} depends on unknown or later wave {dep}")
        missing_deps = REQUIRED_DEPENDENCIES.get(wid, set()) - set(deps)
        require(not missing_deps, f"{wid} drops pinned dependency {sorted(missing_deps)}")

        state = wave.get("state")
        require(isinstance(state, str), f"{wid} state must be a string")
        states[wid] = state
        validate_evidence(control, wave, receipt_loader)
        if state == DONE_STATE:
            if IC3_GATE in pinned["maps_to_gates"]:
                # Overlay YAML is untrusted as proof of hosted credentials or a >0-step run.
                # A hosted IC3 gate must inject an independent verifier, not a YAML flag.
                require(
                    callable(hosted_ic3_attestor) and hosted_ic3_attestor(wave) is True,
                    "IC3_AUTH PASS requires independently verified hosted >0-step receipt on exact head",
                )
                ic3_pass = True
        elif state.startswith("BLOCKED_ON_R2-W"):
            blocker = state.removeprefix("BLOCKED_ON_")
            require(blocker in wave_ids and wave_ids.index(blocker) < wave_ids.index(wid), f"{wid} blocked on unknown or later wave {blocker}")
            require(blocker in deps, f"{wid} blocked on {blocker} which is not in its depends_on")
        else:
            require(state in OPEN_STATES, f"{wid} has unknown state {state}")

    for wave in waves:
        state = wave["state"]
        unpassed = [d for d in wave["depends_on"] if states[d] != DONE_STATE]
        if unpassed:
            # Any state other than BLOCKED_ON_<an unpassed dependency> would start or plan the
            # wave past its blocker, so PLANNED, IN_PROGRESS, BLOCKED_ON_OWNER and PASS all fail.
            require(
                state in {f"BLOCKED_ON_{d}" for d in unpassed},
                f"{wave['id']} is {state} but dependency {unpassed[0]} is not PASS; it must stay BLOCKED_ON_{unpassed[0]}",
            )
            continue
        if state.startswith("BLOCKED_ON_R2-W"):
            continue
        if state == DONE_STATE:
            for earlier in waves[: wave_ids.index(wave["id"])]:
                require(earlier["state"] == DONE_STATE, f"{wave['id']} PASS while earlier {earlier['id']} not PASS")
    if ic3_pass:
        require(first_red["state"] == IC3_PASS_STATE, "IC3 PASS contradicts withheld or incorrect first_red.state")
    else:
        require(first_red["state"].startswith("WITHHELD"), "IC3 not passed: first red must stay WITHHELD")

    contracts = {c["id"]: c for c in control["contracts"]}
    require(len(contracts) == len(control["contracts"]), "duplicate contract ids")
    for cid, c in contracts.items():
        require(c["owner_repo"] == PROVIDER, f"{cid} must be owned by the provider repo")
        require(c["wave"] in wave_ids, f"{cid} bound to unknown wave")
        if c["disposition"] != "NEW_NO_EXISTING_OWNER":
            require(bool(c.get("reuse_of")), f"{cid} reuses something but names no owner")
    require("gmi.proposal_profile.v1" in contracts, "contract gmi.proposal_profile.v1 missing")
    require(contracts["gmi.proposal_profile.v1"]["disposition"] == "PROFILE_OF_EXISTING", "proposal must profile the GMI package contract")

    broker = mapping(control.get("broker"), "broker")
    require(broker == PINNED_BROKER, "broker identity, crew flag or function definitions changed from pinned values")

    workers = control.get("runtime_workers_added")
    require(isinstance(workers, list), "runtime_workers_added must be a list")
    seen = set()
    for worker in workers:
        worker = mapping(worker, "runtime worker")
        wid = worker.get("id")
        require(wid in PINNED_WORKER_AUTHORITY, f"runtime worker {wid} is not in the pinned set")
        require(wid not in seen, f"duplicate runtime worker {wid}")
        seen.add(wid)
        require(worker.get("is_crew") is False, f"{wid} must not be crew")
        require(wid not in crew_ids, f"{wid} collides with a crew id")
        require(worker.get("authority") == PINNED_WORKER_AUTHORITY[wid], f"{wid} authority changed from pinned {PINNED_WORKER_AUTHORITY[wid]}")
    require(seen == set(PINNED_WORKER_AUTHORITY), f"runtime workers missing: {sorted(set(PINNED_WORKER_AUTHORITY) - seen)}")

    rex_ids = [r["id"] for r in control["rex_new"]]
    require(len(rex_ids) == len(set(rex_ids)), "duplicate REX ids")
    inherited = {r["id"] for r in baseline["inherited_rex"]}
    require(not (set(rex_ids) & inherited), "new REX ids collide with inherited REX")
    for rex in control["rex_new"]:
        require(all(rex.get(k) for k in ("learning", "evidence", "action")), f"{rex['id']} incomplete")

    missing_nonclaims = REQUIRED_NONCLAIMS - set(control["explicit_nonclaims"])
    require(not missing_nonclaims, f"missing non-claims: {sorted(missing_nonclaims)}")

    for token in wave_ids + rex_ids + list(contracts):
        require(token in brief_text, f"brief does not mention {token}")

    return {
        "result": "PASS_GM_I_C_R2_OVERLAY",
        "mission_id": "GM-I-C",
        "reopen_id": control["reopen_id"],
        "waves": states,
        "first_red": first_red["gate"],
        "first_red_state": first_red["state"],
        "contracts": sorted(contracts),
        "rex_new": rex_ids,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, default=CONTROL)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    control = load_yaml(args.control)
    require(isinstance(control, dict) and isinstance(control.get("brief"), str), "overlay has no brief path")
    brief_path = REPO / control["brief"]
    require(brief_path.is_file(), f"brief missing: {control['brief']}")
    result = validate(control, load_yaml(BASELINE_CONTROL), load_yaml(BASELINE_CREW), brief_path.read_text(encoding="utf-8"))
    text = json.dumps(result, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
