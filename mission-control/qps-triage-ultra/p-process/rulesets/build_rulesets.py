#!/usr/bin/env python3
"""Generate BASIC (and ABACUS HARD) branch rulesets as importable GitHub ruleset JSON.

Required checks were chosen from live data (survey.json): each appears exactly once on every
one of the last 12 merged PRs, comes from GitHub Actions (integration_id 15368) and passed
or was skipped on at least 90% of them. A required check that does not run on every PR blocks
merges forever, so path-filtered jobs are excluded.

One owner-approved exception (2026-10-24): the hub also requires `GOGREEN required gate`. On the
last 12 merged PRs (#814-#831) it ran 12/12 times, unfiltered, from GitHub Actions, and passed 9/12
(75%). All three failures were true reds, not flakes: #815, #820 and #821 merged with the JADE suite
red (CI/CD DAG outputs stale, outdated pin test), repaired by #829. The 90% bar exists to keep flaky
checks out; this gate missed it only because it caught real red merges, which is what it is for.

Second owner-requested exception (2026-10-29): the hub also requires the head status
`First-Pass Closure Gate / first-pass-closure`. It is the status the trusted pull_request_target
controller publishes on the PR head (docs/W305_FIRST_PASS_CLOSURE_GATE.md, R7), not the job's
check run, which a candidate workflow could imitate. It is unfiltered (no paths), and is published
by GitHub Actions (15368). On the last 12 merged PRs (#984-#1018) it was SUCCESS at merge time on
1/12 (#998), FAILURE on 3, PENDING on 3, absent on 5 (the gate skips drafts). It is far below the
90% bar for the same reason as GOGREEN: the merges were red, not the gate. #838 and #931 merged
with it red. Expect it to block until a PR carries an exact-head receipt and a completed Codex
review; drafts must be marked ready first, and Dependabot PRs need an owner-written receipt.

Import: Settings -> Rules -> Rulesets -> New ruleset -> Import a ruleset (upload the .json),
or: gh api -X POST repos/OWNER/REPO/rulesets --input FILE.json   (owner only; agents never apply)
"""
import json
from pathlib import Path

import yaml

ACTIONS = 15368  # GitHub Actions app id: pins each required check to Actions so a status cannot spoof it
# Required contexts that are commit statuses, not job check runs: context -> (workflow file, publishing job).
STATUS_PRODUCERS = {
    "First-Pass Closure Gate / first-pass-closure": ("first-pass-closure-gate.yml", "first-pass-closure"),
}

REPOS = {
    "GBOGEB/ABACUS": {"branch": "main", "checks": ["YAML syntax scaffold", "smoke", "a10-guard", "dependency-review"],
                      "methods": ["merge", "squash", "rebase"],
                      "why": "Fast, reliable PR checks: syntax, smoke, restricted-term guard, dependency review. Full-red jobs (coverage, quality, security) stay out until their EVERRED roots close."},
    "GBOGEB/CODEX": {"branch": "main", "checks": ["lint", "self-smoke (3.12)", "bandit", "governance-adversary"],
                     "methods": ["merge", "squash", "rebase"],
                     "why": "Lint, smoke, Bandit and the governance adversary pass on every PR. governance-gate (50% red) and semantic-validation stay out until triaged."},
    "GBOGEB/cryoplant-project": {"branch": "main", "checks": ["verify", "recurrence-control", "federation-smoke"],
                                 "methods": ["merge", "squash", "rebase"],
                                 "why": "Engineering-authority repo: verification, recurrence control and federation smoke on every PR."},
    "GBOGEB/gg_MATH": {"branch": "main", "checks": ["first-kernel", "monte-carlo-reference"],
                       "methods": ["merge", "squash", "rebase"],
                       "why": "Numerical kernels: first kernel and Monte-Carlo reference run on every PR."},
    "GBOGEB/pipeline-automation-hub": {"branch": "master", "checks": ["validate-ultra-control", "canonical-self-test-and-mutation", "GOGREEN required gate",
                                                                      "First-Pass Closure Gate / first-pass-closure"],
                                       "methods": ["squash", "rebase"], "linear": True, "copilot_review": True,
                                       "why": "Hosts the Code Purple review site. Keeps linear history and Copilot review from the existing ruleset, which currently targets no branch. GOGREEN required gate is the MACH-II compensating check for the solo-owner review waiver; it is below the 90% bar (9/12) only because it failed on true reds (#815, #820, #821). First-Pass Closure Gate / first-pass-closure is the trusted controller's head status (W305 R7), required so a red gate blocks the merge button; 1/12 recent merges had it green, so it blocks until receipts and exact-head Codex reviews are routine."},
    "GBOGEB/Q_engineering_tools": {"branch": "main", "checks": ["build-and-exercise", "engineering-source-smoke"],
                                   "methods": ["merge", "squash", "rebase"],
                                   "why": "Build and engineering-source smoke run on every PR."},
}


def path_filtered_jobs(workflows_dir: Path) -> dict[str, bool]:
    """Job name -> True when its workflow's pull_request trigger has paths/paths-ignore.

    A required check from a path-filtered workflow never reports on PRs outside those paths and blocks
    them forever (the hub's zero-test 'audit' job was proposed this way on 16 Oct and removed)."""
    out: dict[str, bool] = {}
    for f in sorted(Path(workflows_dir).glob("*.y*ml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(d, dict):
            continue
        on = d.get(True, d.get("on"))
        if isinstance(on, str):
            on = {on: None}
        elif isinstance(on, list):
            on = {k: None for k in on}
        if not isinstance(on, dict) or not ({"pull_request", "pull_request_target"} & set(on)):
            continue
        pr = on.get("pull_request") or on.get("pull_request_target") or {}
        filtered = bool(isinstance(pr, dict) and (pr.get("paths") or pr.get("paths-ignore")))
        for jid, j in (d.get("jobs") or {}).items():
            for name in {jid, (j or {}).get("name", jid) if isinstance(j, dict) else jid}:
                out[str(name)] = out.get(str(name), False) or filtered
    return out


def basic(repo: str, cfg: dict) -> dict:
    rules = [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "pull_request", "parameters": {
            "required_approving_review_count": 0,          # solo owner: an approval count of 1 needs a second account
            "dismiss_stale_reviews_on_push": True,
            "require_code_owner_review": False,
            "require_last_push_approval": False,
            "required_review_thread_resolution": True,      # unresolved review threads block merge
            "allowed_merge_methods": cfg["methods"]}},
        {"type": "required_status_checks", "parameters": {
            "strict_required_status_checks_policy": False,  # BASIC: no forced rebase on every main move (avoids CI storms)
            "do_not_enforce_on_create": False,
            "required_status_checks": [{"context": c, "integration_id": ACTIONS} for c in cfg["checks"]]}},
    ]
    if cfg.get("linear"):
        rules.append({"type": "required_linear_history"})
    if cfg.get("copilot_review"):
        rules.append({"type": "copilot_code_review", "parameters": {"review_on_push": True, "review_draft_pull_requests": False}})
    return {"name": f"P-BASIC {repo.split('/')[1]} default branch", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [],  # break glass by adding a bypass actor for one merge, never by deleting rules
            "rules": rules}


def hard_abacus(b: dict) -> dict:
    h = json.loads(json.dumps(b))
    h["name"] = "P-HARD ABACUS default branch"
    for r in h["rules"]:
        if r["type"] == "required_status_checks":
            r["parameters"]["strict_required_status_checks_policy"] = True
            r["parameters"]["required_status_checks"].insert(0, {"context": "PR Feedback Gate", "integration_id": ACTIONS})
        if r["type"] == "pull_request":
            r["parameters"].update({"required_approving_review_count": 1, "require_last_push_approval": True})
    return h


def main():
    out = Path(__file__).parent
    lf = {"encoding": "utf-8", "newline": "\n"}  # same bytes from Windows and Linux
    manifest = {}
    for repo, cfg in REPOS.items():
        b = basic(repo, cfg)
        name = repo.split("/")[1]
        (out / f"{name}.basic.json").write_text(json.dumps(b, indent=2) + "\n", **lf)
        manifest[repo] = {"file": f"{name}.basic.json", "branch": cfg["branch"], "checks": cfg["checks"], "why": cfg["why"]}
        if repo == "GBOGEB/ABACUS":
            (out / "ABACUS.hard.json").write_text(json.dumps(hard_abacus(b), indent=2) + "\n", **lf)
            manifest[repo]["hard_file"] = "ABACUS.hard.json"
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", **lf)
    print("\n".join(f"{r}: {m['file']} -> {', '.join(m['checks'])}" for r, m in manifest.items()))


if __name__ == "__main__":
    main()
