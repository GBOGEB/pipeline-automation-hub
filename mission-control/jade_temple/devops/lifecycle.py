#!/usr/bin/env python3
"""JADE N+9 DevOps lifecycle model: stages, SIPOC, maturity ladder and probe scoring.

Pure functions only (no I/O). The census (census.py) supplies per-repository facts; this
module turns them into per-stage probes (PASS / FAIL / UNKNOWN), a cumulative maturity level
L0..L5, a completion fraction and a fleet formalization status.

Ladder rule: a stage is at level L when every probe tagged 1..L is PASS. UNKNOWN is never
PASS, so an unobservable probe (for example branch protection without an API token) caps the
level honestly instead of being waived. Completion = PASS probes / all probes of the stage.

The stage graph is a DAG inside one pulse. S9_CONTROL feeds S0_PLAN of the NEXT pulse
(a temporal FEEDBACK edge), the same unroll rule as CODE_PURPLE_BEAMS_DAG_v1 and the
JADE P-loop `recurse` edge, so the unrolled graph stays acyclic.
"""
from __future__ import annotations

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
STATES = (PASS, FAIL, UNKNOWN)
LEVELS = {0: "ABSENT", 1: "AD_HOC", 2: "DEFINED", 3: "AUTOMATED", 4: "GATED", 5: "CONTROLLED"}

# key, title, question, DMAIC/H-gate crosswalk (JADE ROLLING5 H01..H12; DP = deploy contract)
STAGES = [
    ("S0_PLAN", "Plan", "Is work routed, owned and protected before code lands?", ["H03"]),
    ("S1_CODE", "Code", "Is source linted and type-checked by the same rules locally and in CI?", ["H01", "H02"]),
    ("S2_BUILD", "Build", "Is the build declared, pinned and reproducible to one digest?", ["H04"]),
    ("S3_TEST", "Test", "Do tests run on every change, fail closed on zero tests and hold a floor?", ["H05", "H06", "H10"]),
    ("S4_SECURE", "Secure", "Are dependencies, workflows and artefacts scanned, pinned and attested?", ["H07"]),
    ("S5_RELEASE", "Release", "Is a versioned, test-gated, provenance-bearing release cut automatically?", ["H11", "H12"]),
    ("S6_DEPLOY", "Deploy", "Is the same artefact promoted by digest into a named, serialized environment and verified?", ["H11", "DP1-DP10"]),
    ("S7_OPERATE", "Operate", "Is the running service described, health-checked, protected and rollback-able?", ["DP-OPS"]),
    ("S8_MONITOR", "Monitor", "Is production re-verified on a clock and do failures raise work items?", ["DP-MON"]),
    ("S9_CONTROL", "Control", "Do red signals become ledgered, root-caused work that prevents recurrence?", ["H08", "H09", "P-loop"]),
]
STAGE_KEYS = [s[0] for s in STAGES]

# Feedforward edges inside one pulse plus the single temporal feedback edge.
EDGES = [
    ("S0_PLAN", "S1_CODE", "FEEDFORWARD"), ("S1_CODE", "S2_BUILD", "FEEDFORWARD"),
    ("S2_BUILD", "S3_TEST", "FEEDFORWARD"), ("S3_TEST", "S4_SECURE", "FEEDFORWARD"),
    ("S2_BUILD", "S4_SECURE", "FEEDFORWARD"), ("S3_TEST", "S5_RELEASE", "FEEDFORWARD"),
    ("S4_SECURE", "S5_RELEASE", "FEEDFORWARD"), ("S5_RELEASE", "S6_DEPLOY", "FEEDFORWARD"),
    ("S6_DEPLOY", "S7_OPERATE", "FEEDFORWARD"), ("S7_OPERATE", "S8_MONITOR", "FEEDFORWARD"),
    ("S3_TEST", "S9_CONTROL", "FEEDFORWARD"), ("S8_MONITOR", "S9_CONTROL", "FEEDFORWARD"),
    ("S9_CONTROL", "S0_PLAN", "FEEDBACK_NEXT_PULSE"),
]

SIPOC = {
    "S0_PLAN": {"S": ["owners", "issue register / BD queue", "Mission Control roster"],
                "I": ["issues", "BD items", "red-trace first-red roots", "ADR / roadmap"],
                "P": ["triage", "route by CODEOWNERS", "protect default branch"],
                "O": ["owned, prioritised work item", "protected branch with required checks"],
                "C": ["S1_CODE authors", "reviewers"]},
    "S1_CODE": {"S": ["authors", "agents"], "I": ["work item", "lint / format / type config"],
                "P": ["edit", "pre-commit", "lint + type check in CI"],
                "O": ["reviewed commit (40-hex SHA)", "lint receipt"], "C": ["S2_BUILD"]},
    "S2_BUILD": {"S": ["S1_CODE commit", "package registries"], "I": ["manifest", "lockfile", "pinned actions"],
                 "P": ["resolve pinned deps", "build once", "hash artefact"],
                 "O": ["artefact + sha256 manifest"], "C": ["S3_TEST", "S4_SECURE", "S5_RELEASE"]},
    "S3_TEST": {"S": ["S2_BUILD artefact", "test authors"], "I": ["test suites", "coverage floor", "min test count"],
                "P": ["run tests on PR/push", "zero-test guard", "coverage gate"],
                "O": ["test receipt (ran N, coverage %)", "first-red on failure"], "C": ["S5_RELEASE", "S9_CONTROL"]},
    "S4_SECURE": {"S": ["advisory DBs", "scanners"], "I": ["dependency graph", "workflow permissions", "action pins"],
                  "P": ["dependency update bot", "SAST / audit", "least-privilege tokens", "attest"],
                  "O": ["scan receipt", "provenance attestation"], "C": ["S5_RELEASE", "auditors"]},
    "S5_RELEASE": {"S": ["S3_TEST + S4_SECURE receipts"], "I": ["version", "changelog", "artefact digest"],
                   "P": ["tag semver", "cut release gated on tests", "attach digest + provenance"],
                   "O": ["immutable release (tag SHA + artefact digest)"], "C": ["S6_DEPLOY", "consumers"]},
    "S6_DEPLOY": {"S": ["S5_RELEASE artefact"], "I": ["artefact digest", "environment name", "deploy contract DP1..DP10"],
                  "P": ["admit", "verify digest", "deploy serialized per environment", "post-deploy readback"],
                  "O": ["deployment receipt (env, SHA, digest, URL, parity)"], "C": ["S7_OPERATE", "end users"]},
    "S7_OPERATE": {"S": ["S6_DEPLOY receipt", "platform"], "I": ["runtime descriptor", "runbook", "health check"],
                   "P": ["run", "health-check", "protect production environment", "rollback by previous digest"],
                   "O": ["available service at a known SHA"], "C": ["users", "S8_MONITOR"]},
    "S8_MONITOR": {"S": ["S7_OPERATE service", "schedulers"], "I": ["served URL", "expected SHA / digests", "SLO"],
                   "P": ["scheduled readback", "observability", "alert -> issue"],
                   "O": ["parity / SLO receipts", "incident issue on failure"], "C": ["S9_CONTROL", "owners"]},
    "S9_CONTROL": {"S": ["S3_TEST first-red", "S8_MONITOR alerts", "red-trace ledger"],
                   "I": ["EVERRED / GREEN_TO_RED / RED_TO_GREEN classes", "BD/REX lifecycle"],
                   "P": ["classify", "root (root_red)", "repair lane", "verify progressive", "control + recurse"],
                   "O": ["BD item in DONE/CONTROL", "prevention gate"], "C": ["S0_PLAN of next pulse"]},
}

# probe id, stage, level, description. Every probe is evaluated by PROBE_FN below.
PROBES = [
    ("plan.readme_root", "S0_PLAN", 1, "README at repository root"),
    ("plan.templates", "S0_PLAN", 2, "Issue or PR template declared"),
    ("plan.codeowners", "S0_PLAN", 3, "CODEOWNERS routes review automatically"),
    ("plan.protection", "S0_PLAN", 4, "Default branch protection / ruleset effective (API)"),
    ("plan.register", "S0_PLAN", 5, "Decision or work register in repo (ADR, roadmap, BD queue)"),
    ("code.source", "S1_CODE", 1, "Source files present"),
    ("code.lint_config", "S1_CODE", 2, "Lint / format configuration declared"),
    ("code.lint_ci", "S1_CODE", 3, "Lint runs in CI"),
    ("code.typecheck_ci", "S1_CODE", 4, "Type check runs in CI"),
    ("code.precommit_ci", "S1_CODE", 5, "pre-commit declared and executed in CI (local = CI rules)"),
    ("build.manifest", "S2_BUILD", 1, "Build manifest declared"),
    ("build.lock", "S2_BUILD", 2, "Dependencies locked or pinned"),
    ("build.ci", "S2_BUILD", 3, "Install / build runs in CI"),
    ("build.pinned_actions", "S2_BUILD", 4, ">= 90% of third-party actions pinned to a 40-hex SHA"),
    ("build.artifact_digest", "S2_BUILD", 5, "CI publishes an artefact with a sha256 manifest"),
    ("test.files", "S3_TEST", 1, "Test files present"),
    ("test.cases", "S3_TEST", 2, "Test cases declared (> 0)"),
    ("test.ci", "S3_TEST", 3, "Tests run in CI on pull_request or push"),
    ("test.fail_closed", "S3_TEST", 4, "Zero-test guard or coverage floor in CI, and no zero-case test files"),
    ("test.controlled", "S3_TEST", 5, "Coverage floor >= 80 and <= 20% untested Python modules"),
    ("secure.policy", "S4_SECURE", 1, "SECURITY.md or dependency-update config"),
    ("secure.depbot", "S4_SECURE", 2, "Dependabot / Renovate configured"),
    ("secure.scan_ci", "S4_SECURE", 3, "Security scan runs in CI"),
    ("secure.least_privilege", "S4_SECURE", 4, "Every workflow declares permissions; none uses write-all"),
    ("secure.provenance", "S4_SECURE", 5, "Provenance attestation or SBOM produced"),
    ("release.notes", "S5_RELEASE", 1, "CHANGELOG / release notes or declared version"),
    ("release.tags", "S5_RELEASE", 2, "At least one tag"),
    ("release.automation", "S5_RELEASE", 3, "Release workflow (release / tag trigger or release step)"),
    ("release.gated", "S5_RELEASE", 4, "Release job needs a test job"),
    ("release.provenance", "S5_RELEASE", 5, "Release job attaches digest or attestation"),
    ("deploy.descriptor", "S6_DEPLOY", 1, "Deploy descriptor present or site served"),
    ("deploy.workflow", "S6_DEPLOY", 2, "Deploy job present in a workflow"),
    ("deploy.environment", "S6_DEPLOY", 3, "Deploy job targets a named environment"),
    ("deploy.contract", "S6_DEPLOY", 4, "A deploy job passes DP1..DP6 + DP9 + DP10 (build once, digest, env, serialized, least privilege, pinned, gated, exact ref)"),
    ("deploy.verified", "S6_DEPLOY", 5, "A deploy job verifies the served result and leaves a receipt (DP7 + DP8)"),
    ("operate.runtime", "S7_OPERATE", 1, "Runtime descriptor present or site live (HTTP 200)"),
    ("operate.runbook", "S7_OPERATE", 2, "Runbook / operations / rollback doc"),
    ("operate.health", "S7_OPERATE", 3, "Health check or hosted-parity readback declared"),
    ("operate.rollback", "S7_OPERATE", 4, "Rollback path automated (dispatch deploy of a prior ref / digest)"),
    ("operate.protected_env", "S7_OPERATE", 5, "Production environment protection rules (API)"),
    ("monitor.schedule", "S8_MONITOR", 1, "At least one scheduled workflow"),
    ("monitor.canary", "S8_MONITOR", 2, "Scheduled verification / readback / smoke"),
    ("monitor.observability", "S8_MONITOR", 3, "Observability config or red-trace ledger"),
    ("monitor.live_parity", "S8_MONITOR", 4, "Live site HTTP 200 and served SHA equals HEAD"),
    ("monitor.alerting", "S8_MONITOR", 5, "Failure opens an issue or notifies automatically"),
    ("control.ledger", "S9_CONTROL", 1, "Receipts / BD queue / red-trace / DMAIC ledger in repo"),
    ("control.gates", "S9_CONTROL", 2, "Gate / admission / guard workflows"),
    ("control.zero_test_guard", "S9_CONTROL", 3, "Zero-test guard present in CI"),
    ("control.red_trace", "S9_CONTROL", 4, "Red-trace observed and no EVERRED workflow"),
    ("control.no_red", "S9_CONTROL", 5, "Red-trace observed and nothing currently red"),
]
PROBE_IDS = [p[0] for p in PROBES]


def _b(value):
    """Tri-state from a fact: None -> UNKNOWN, truthy -> PASS, falsy -> FAIL."""
    if value is None:
        return UNKNOWN
    return PASS if value else FAIL


def _ratio_ok(num, den, floor):
    if not den:
        return None
    return num / den >= floor


def _live(f, key):
    """A live-code test count (archived copies excluded); censuses before N+11 only carry the total."""
    return f["tests"].get(f"live_{key}", f["tests"][key])


def probe_states(f: dict) -> dict:
    """Evaluate every probe from a flat fact dictionary built by census.facts()."""
    wf = f["wf"]
    rt = f.get("red_trace")
    pages = f.get("pages") or {}
    api = f.get("api") or {}
    live = pages.get("status") == 200 if pages.get("status") is not None else None
    parity = pages.get("source_sha_match")
    s = {
        "plan.readme_root": _b(f["has"]("readme_root")),
        "plan.templates": _b(f["has"]("issue_template") or f["has"]("pr_template")),
        "plan.codeowners": _b(f["has"]("codeowners")),
        "plan.protection": _b(api.get("protected")),
        "plan.register": _b(f["has"]("register")),
        "code.source": _b(f["source_files"] > 0),
        "code.lint_config": _b(f["has"]("lint_config")),
        "code.lint_ci": _b(wf["lint"] > 0),
        "code.typecheck_ci": _b(wf["typecheck"] > 0),
        "code.precommit_ci": _b(f["has"]("precommit") and wf["precommit"] > 0),
        "build.manifest": _b(f["has"]("build_manifest")),
        "build.lock": _b(f["has"]("lockfile") or f["pinned_requirements"]),
        "build.ci": _b(wf["build"] > 0),
        "build.pinned_actions": _b(_ratio_ok(wf["actions_pinned"], wf["actions_total"], 0.9)),
        "build.artifact_digest": _b(wf["artifact_digest"] > 0),
        "test.files": _b(f["tests"]["files"] > 0),
        "test.cases": _b(f["tests"]["cases"] > 0),
        "test.ci": _b(wf["tests_ci"] > 0),
        "test.fail_closed": _b((wf["zero_test_guard"] + wf["zero_test_guard_implicit"] > 0
                                or wf["coverage_floor_max"] is not None)
                               and f["tests"]["files"] > 0
                               and f["tests"].get("live_zero_case_files", f["tests"]["zero_case_files"]) == 0),
        "test.controlled": _b((wf["coverage_floor_max"] or 0) >= 80 and _live(f, "py_modules") > 0
                              and _live(f, "py_untested") <= 0.2 * _live(f, "py_modules")),
        "secure.policy": _b(f["has"]("security_policy") or f["has"]("dependency_bot")),
        "secure.depbot": _b(f["has"]("dependency_bot")),
        "secure.scan_ci": _b(wf["security"] > 0),
        "secure.least_privilege": _b(wf["workflows"] > 0 and wf["permissions_declared"] == wf["workflows"]
                                     and wf["write_all"] == 0),
        "secure.provenance": _b(wf["provenance"] > 0 or f["has"]("sbom")),
        "release.notes": _b(f["has"]("changelog") or f["declared_version"]),
        "release.tags": _b(f["tags"]["count"] > 0 if f["tags"]["count"] is not None else None),
        "release.automation": _b(wf["release"] > 0),
        "release.gated": _b(wf["release_gated"] > 0),
        "release.provenance": _b(wf["release_provenance"] > 0),
        "deploy.descriptor": _b(f["has"]("deploy_descriptor") or bool(live)),
        "deploy.workflow": _b(wf["deploy"] > 0),
        "deploy.environment": _b(wf["deploy_env"] > 0),
        "deploy.contract": _b(wf["deploy_contract_core"] > 0),
        "deploy.verified": _b(wf["deploy_verified"] > 0),
        "operate.runtime": _b(f["has"]("runtime_descriptor") or bool(live)),
        "operate.runbook": _b(f["has"]("runbook")),
        "operate.health": _b(f["has"]("healthcheck") or wf["verify"] > 0),
        "operate.rollback": _b(wf["rollback"] > 0),
        "operate.protected_env": _b(api.get("protected_production")),
        "monitor.schedule": _b(wf["scheduled"] > 0),
        "monitor.canary": _b(wf["scheduled_verify"] > 0),
        "monitor.observability": _b(f["has"]("observability") or rt is not None),
        "monitor.live_parity": _b(live if not live else parity),
        "monitor.alerting": _b(wf["alerting"] > 0),
        "control.ledger": _b(f["has"]("control_ledger")),
        "control.gates": _b(wf["gates"] > 0),
        "control.zero_test_guard": _b(wf["zero_test_guard"] > 0),
        "control.red_trace": _b(None if rt is None else rt["counts"].get("EVERRED", 0) == 0),
        "control.no_red": _b(None if rt is None else rt["currently_red"] == 0),
    }
    missing = set(PROBE_IDS) - set(s)
    if missing:  # pragma: no cover - guarded by tests
        raise KeyError(sorted(missing))
    return s


def stage_score(states: dict, stage: str) -> dict:
    probes = [(pid, lvl) for pid, st, lvl, _ in PROBES if st == stage]
    level = 0
    for lvl in range(1, 6):
        tier = [pid for pid, plv in probes if plv == lvl]
        if tier and all(states[p] == PASS for p in tier):
            level = lvl
        else:
            break
    passed = sum(states[p] == PASS for p, _ in probes)
    unknown = sum(states[p] == UNKNOWN for p, _ in probes)
    blocker = next(({"probe": p, "state": states[p]} for p, lv in sorted(probes, key=lambda x: x[1])
                    if states[p] != PASS), None)
    return {"level": level, "label": LEVELS[level], "completion": round(passed / len(probes), 4),
            "pass": passed, "fail": len(probes) - passed - unknown, "unknown": unknown,
            "probes": len(probes), "next_blocker": blocker}


def score(states: dict) -> dict:
    return {k: stage_score(states, k) for k in STAGE_KEYS}


def formalization(levels: list[int], contract_present: bool) -> str:
    """Fleet status of one stage from per-repo levels and whether the hub holds a written contract.

    FORMALIZED: written contract and at least one repo GATED (L4+) on it.
    PARTIAL   : contract or at least one repo AUTOMATED (L3+), but not both conditions above.
    INFORMAL  : evidence exists somewhere (L1+) but no contract and no automation.
    ABSENT    : nothing observed.
    """
    top = max(levels) if levels else 0
    if contract_present and top >= 4:
        return "FORMALIZED"
    if contract_present or top >= 3:
        return "PARTIAL"
    if top >= 1:
        return "INFORMAL"
    return "ABSENT"


def topo_layers(nodes: list[str], edges: list[tuple]) -> list[list[str]]:
    """Kahn layering over FEEDFORWARD edges; raises ValueError on a cycle or unknown node."""
    known = set(nodes)
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for a, b, kind in edges:
        if a not in known or b not in known:
            raise ValueError(f"unknown edge endpoint {a}->{b}")
        if kind.startswith("FEEDBACK"):
            continue
        out[a].append(b)
        indeg[b] += 1
    layer = sorted(n for n in nodes if indeg[n] == 0)
    layers, seen = [], 0
    while layer:
        layers.append(layer)
        seen += len(layer)
        nxt = []
        for n in layer:
            for m in out[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    nxt.append(m)
        layer = sorted(nxt)
    if seen != len(nodes):
        raise ValueError("cycle in feedforward graph")
    return layers


# RF waves extend the existing JADE lifecycle authority. These descending maturity
# targets apply to experimental qualification, NOT merge protections or required gates.
RF_PHASE_MATURITY = {"P0_CONTROL": 5, "P1_PILOT": 4, "P2_EXPAND": 3,
                     "P3_SCALE": 2, "P4_SCOUT": 1}
RF_CREW = {"SCOUT", "READER", "DOCTOR", "BUILDER", "RUNNER", "AUDITOR"}
RF_STATES = {"READY", "RUNNING", "DONE", "FAILED", "HOLD"}


def rf_pulse_plan(steps: list[dict], *, source_sha: str, max_parallel: int = 6,
                  per_cluster: int = 2, open_stack: int = 0, max_stack: int = 5) -> dict:
    """Pure ON/OFF plan: no real dispatch, PR creation, gate change or merge authority.

    Actual run, job and cost metrics remain owned by actions_metrics.py; a T0
    source reference is mandatory for every work item. Failed items enter OFF
    repair, while selected items enter OFF measurement/qualification before N+1.
    """
    if len(source_sha) != 40 or any(c not in "0123456789abcdef" for c in source_sha):
        raise ValueError("RF requires an exact lowercase 40-hex source SHA")
    limits = (max_parallel, per_cluster, open_stack, max_stack)
    if any(not isinstance(n, int) or isinstance(n, bool) for n in limits):
        raise ValueError("RF limits must be integers")
    if not 1 <= max_parallel <= 32 or not 1 <= per_cluster <= max_parallel:
        raise ValueError("RF concurrency out of bounds")
    if not 0 <= open_stack <= max_stack <= 5:
        raise ValueError("RF PR stack maximum is five")
    if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
        raise ValueError("RF steps must be a list of objects")
    ids = [s.get("id") for s in steps]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("RF ids must be unique nonempty strings")
    states, edges, unbound = {}, [], {}
    for s in steps:
        sid = s["id"]
        if s.get("phase") not in RF_PHASE_MATURITY or s.get("crew") not in RF_CREW:
            raise ValueError(f"{sid}: invalid phase/CREW")
        if s.get("state") not in RF_STATES:
            raise ValueError(f"{sid}: invalid state")
        if not isinstance(s.get("cluster"), str) or not s["cluster"].strip():
            raise ValueError(f"{sid}: missing cluster")
        deps = s.get("depends_on", [])
        if not isinstance(deps, list) or len(deps) != len(set(deps)):
            raise ValueError(f"{sid}: bad dependencies")
        edges.extend((dep, sid, "FEEDFORWARD") for dep in deps)
        paths = s.get("touch_paths", [])
        # Canonical relative paths only: "./x.py", "a//b" or "a\b" would alias and dodge the overlap check.
        if (not isinstance(paths, list) or any(not isinstance(p, str) or "\\" in p or
                                               any(part in ("", ".", "..") for part in p.split("/"))
                                               for p in paths)):
            raise ValueError(f"{sid}: bad changed paths")
        if not isinstance(s.get("write_pr", False), bool):
            raise ValueError(f"{sid}: write_pr must be boolean")
        if s.get("write_pr", False) and not paths:
            raise ValueError(f"{sid}: write must name paths")
        states[sid] = s["state"]
        if s.get("source_sha") != source_sha:
            unbound[sid] = "STALE_SOURCE_SHA"
        elif not isinstance(s.get("t0_ref"), str) or not s["t0_ref"].strip():
            unbound[sid] = "MISSING_T0_RECEIPT"
    topo_layers(ids, edges)  # rejects cycles and missing endpoints, keeps temporal feedback separate
    on, held, off = [], [], []
    clusters, used_paths, writes = {}, set(), 0
    for s in sorted(steps, key=lambda a: (-RF_PHASE_MATURITY[a["phase"]], a["id"])):
        sid, state = s["id"], s["state"]
        if state == "DONE":
            continue
        if state == "FAILED" and sid in unbound:  # no repair prescription without its own evidence
            held.append({"id": sid, "reason": unbound[sid]})
            continue
        if state == "FAILED":
            held.append({"id": sid, "reason": "FIRST_RED_REPAIR"})
            off.append({"id": sid, "crew": "DOCTOR", "mode": "REPAIR_FIRST_RED",
                        "actions": ["classify first-red", "repair isolated branch",
                                    "retest exact-head", "prepare next-pulse receipt"]})
            continue
        reason = None
        if state != "READY":
            reason = "NOT_READY"
        elif sid in unbound:
            reason = unbound[sid]
        elif any(states[d] != "DONE" or d in unbound for d in s.get("depends_on", [])):
            reason = "DEPENDENCY_NOT_DONE"
        elif len(on) >= max_parallel:
            reason = "PARALLEL_CAP"
        elif clusters.get(s["cluster"], 0) >= per_cluster:
            reason = "CLUSTER_CAP"
        elif s.get("write_pr", False) and open_stack + writes >= max_stack:
            reason = "PR_STACK_CAP"
        elif s.get("write_pr", False) and used_paths.intersection(s.get("touch_paths", [])):
            reason = "OVERLAPPING_PATHS"
        if reason:
            held.append({"id": sid, "reason": reason})
            continue
        on.append({"id": sid, "cluster": s["cluster"], "phase": s["phase"],
                   "qualification_target": RF_PHASE_MATURITY[s["phase"]],
                   "crew": s["crew"], "source_sha": source_sha,
                   "t0_ref": s["t0_ref"], "write_pr": bool(s.get("write_pr", False)),
                   "dispatch": "CANDIDATE_NOT_LAUNCHED"})
        clusters[s["cluster"]] = clusters.get(s["cluster"], 0) + 1
        if s.get("write_pr", False):
            writes += 1
            used_paths.update(s["touch_paths"])
        off.append({"id": sid, "crew": "AUDITOR", "mode": "TAKE_STOCK_NEXT_PULSE",
                    "actions": ["record exact run/job/attempt and denominators",
                                "compare T0 and T1 with canonical metrics",
                                "classify and repair regressions",
                                "requalify exact head before N+1"]})
    return {"schema": "jade.devops.rf-pulse-plan.v1", "source_sha": source_sha,
            "on": on, "off": off, "held": held,
            "concurrency": {"max_parallel": max_parallel, "per_cluster": per_cluster,
                            "existing_stack": open_stack, "max_stack": max_stack},
            "authority": {"dispatch_performed": False, "merge_authorized": False,
                          "gate_policy": "UNCHANGED", "feedback": "NEXT_PULSE_ONLY"}}
