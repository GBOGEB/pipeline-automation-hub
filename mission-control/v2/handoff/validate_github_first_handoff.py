"""Fail-closed structural check of an additive GitHub-first CP.HANDOFF checkpoint.

This NEVER authenticates GitHub, admits a PR, sends a dispatch or proves live CI.
"""
import argparse
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPOS = {
    "GBOGEB/pipeline-automation-hub",
    "GBOGEB/ABACUS",
    "GBOGEB/CODEX",
    "GBOGEB/cryoplant-project",
    "GBOGEB/gg_MATH",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(profile, state):
    require(profile.get("schema") == "code_purple.chat_continuation_transport_profile.v1", "profile schema")
    require(profile.get("profile") == "GITHUB_FIRST_MINIMAL", "transport identity")
    require(profile.get("not_executable_api") is True, "not executable")
    require(profile.get("not_second_ssot") is True, "authority boundary")
    require(profile.get("archive_rule", "").startswith("DO_NOT_CREATE_ARCHIVE"), "archive precedence")
    require(state.get("schema") == "code_purple.github_first_continuation_checkpoint.v1", "state schema")
    require(state.get("snapshot_atomic") is False, "non-atomic status")
    heads = state.get("source_heads")
    require(isinstance(heads, dict) and set(heads) == REPOS, "five-repo denominator")
    for repo, value in heads.items():
        require(isinstance(value, dict), "head record")
        require(isinstance(value.get("sha"), str) and SHA.fullmatch(value["sha"]), "source SHA " + repo)
        require(value.get("ref") in ("main", "master"), "source ref " + repo)
    chain = state.get("candidate_pr_chain")
    require(isinstance(chain, list) and [p.get("pr") for p in chain] == [620, 621, 631], "PR lineage")
    for pr in chain:
        require(isinstance(pr.get("head_sha"), str) and SHA.fullmatch(pr["head_sha"]), "PR head")
        require(pr.get("status") == "OPEN_UNMERGED", "intervening state must be recensused")
    require(state.get("accepted_n") is None and state.get("accepted_n_delta") is None, "false accepted advance")
    require(state.get("formal_root_closures") is None, "false root closure")
    require(state.get("pulse_n15_source_sha") is None, "unverified N15 head")
    screenshot = state.get("user_screenshot_historical", {})
    require(screenshot.get("native_admission_credit") is False, "screenshot native credit")
    require(screenshot.get("source_sha") is None and screenshot.get("run_id") is None, "screenshot provenance")
    current = state["github_current"]
    require(current["head_sha"] == chain[-1]["head_sha"], "current PR head mismatch")
    outcomes = current["workflow_conclusions"]
    require(outcomes["success"] + outcomes["failure"] == outcomes["total"], "workflow denominator")
    require(outcomes["failure"] > 0, "independent failure must be retained")
    for key in ("n3_native_python_311", "n3_native_python_312"):
        require(current[key]["tests_passed"] > 0 and current[key]["tests_failed"] == 0, "native test record")
    fpc = current["independent_first_pass_closure"]
    require(fpc["status"] == "FAIL" and fpc["merge_allowed"] is False, "FPC noncompensation")
    require(bool(fpc.get("latest_failed_job_id")), "FPC original job")
    controls = state["controls"]
    require(controls.get("merge_admission") == "HOLD", "admission HOLD")
    for key in (
        "security_waiver",
        "authority_transfer",
        "authenticated_crew_dispatch",
        "verified_qps_acceptance",
        "main_merge_performed_by_this_handover",
    ):
        require(controls.get(key) is False, "unproved authority: " + key)
    return {
        "status": "STRUCTURAL_PASS_NOT_LIVE_AUTHENTICATION",
        "repo_heads": len(heads),
        "candidate_prs": len(chain),
        "workflow_conclusions": outcomes,
        "admission": "HOLD",
    }


def main():
    base = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=base / "GITHUB_FIRST_PROFILE_V1.json")
    parser.add_argument("--state", type=Path, default=base / "STATE_N13_N15_20261017.json")
    args = parser.parse_args()
    result = validate(json.loads(args.profile.read_text(encoding="utf-8")),
                      json.loads(args.state.read_text(encoding="utf-8")))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

