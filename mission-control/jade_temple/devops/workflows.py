#!/usr/bin/env python3
"""GitHub Actions workflow analysis for the JADE N+9 DevOps census and deploy contract.

parse()      : workflow YAML text -> normalized workflow (triggers, permissions, job needs-DAG,
               steps) with a descriptive OID and a sha256 of every job definition.
signals()    : per-job lifecycle signals (tests, coverage floor, zero-test guard, build, lint,
               security, provenance, release, deploy, post-deploy verify, alerting).
deploy_gates : the deploy/production contract DP1..DP10 for one deploy job.

CLI: python workflows.py lint FILE... [--require-deploy]
     exits 1 when a deploy job fails any DP gate (or no deploy job exists with --require-deploy).
     python workflows.py secrets-lint FILE...
     exits 1 when a pull_request run can reach a repository secret (pr_secret_exposure()).
Nothing is executed; workflows are data. Heuristic signals are labelled as such in the census.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

import yaml

SHA40 = re.compile(r"^[0-9a-f]{40}$")
DP_GATES = {
    "DP1": "BUILD_ONCE: deploy consumes an upstream artefact (download-artifact), never rebuilds",
    "DP2": "DIGEST_VERIFIED: sha256 of the artefact is verified before deploy",
    "DP3": "ENVIRONMENT: job targets a named GitHub environment",
    "DP4": "SERIALIZED: concurrency group without cancel-in-progress",
    "DP5": "LEAST_PRIVILEGE: explicit permissions, never write-all",
    "DP6": "PINNED: every third-party action pinned to a 40-hex commit SHA",
    "DP7": "POST_DEPLOY_VERIFY: served result is read back (HTTP / parity / smoke)",
    "DP8": "RECEIPT: a deployment receipt artefact is uploaded",
    "DP9": "GATED_ON_TESTS: a job in the needs-closure runs tests",
    "DP10": "EXACT_REF: deploy is bound to an exact SHA or a protected ref",
}
DP_CORE = ("DP1", "DP2", "DP3", "DP4", "DP5", "DP6", "DP9", "DP10")
DP_VERIFIED = ("DP7", "DP8")
# A caller job that pins the hub reusable deploy inherits the gates that workflow enforces internally
# (it is itself linted against DP1..DP10 in the hub's jade-devops-census workflow).
REUSABLE_DEPLOY = re.compile(r"/\.github/workflows/jade-reusable-deploy\.ya?ml@[0-9a-f]{40}$")
DELEGATED = ("DP4", "DP5", "DP7", "DP8", "DP10")
TEST_EVIDENCE_RX = re.compile(r"tests[-_]ran|ci[-_]receipt", re.I)

_RX = lambda p: re.compile(p, re.I | re.M)
TEST_RX = _RX(r"\b(pytest|py\.test|unittest|nose2|tox|nox|jest|vitest|mocha|ava|karma|playwright test|go test|"
              r"cargo test|dotnet test|invoke-pester|pester|ctest|phpunit|rspec|bun test|deno test)\b|"
              r"\b(npm|yarn|pnpm) (run )?test\b|\bmake +(test|check)\b|\bmvn\b.*\btest\b|\bgradlew? .*\btest\b")
PYTEST_RX = _RX(r"\b(pytest|py\.test)\b")
COV_RX = _RX(r"--cov\b|--cov=|\bcoverage (run|report|json|xml|html)\b|--coverage\b|\bcodecov\b|\bcoveralls\b|\bc8 |\bnyc ")
COV_FLOOR_RX = [_RX(r"--cov-fail-under[= ]+(\d+(?:\.\d+)?)"), _RX(r"--fail-under[= ]+(\d+(?:\.\d+)?)"),
                _RX(r"fail_under\s*[=:]\s*(\d+(?:\.\d+)?)"),
                _RX(r"percent_(?:statements_|branches_)?covered['\"]?\]?\s*<\s*(\d+(?:\.\d+)?)"),
                _RX(r"--coverage-floor[= ]+(\d+(?:\.\d+)?)"), _RX(r"coverage[-_]floor\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)")]
ZERO_GUARD_RX = _RX(r"\bran \[1-9\]|\bran \(\[0-9\]\+\) tests|zero[-_ ]?tests?\b|test_population|"
                    r"no tests (ran|collected)|\bmin[-_]tests\b|tests[-_]ran\b")
SOFT_FAIL_RX = _RX(r"\|\|\s*(true|:|exit 0)\b|--exitfirst=no")
LINT_RX = _RX(r"\b(ruff|flake8|pylint|pycodestyle|black --check|isort --check|eslint|prettier (--check|-c)|"
              r"markdownlint|yamllint|actionlint|shellcheck|invoke-scriptanalyzer|psscriptanalyzer|golangci-lint|"
              r"gofmt|cargo clippy|cargo fmt|hadolint|super-linter|pre-commit run|biome (check|lint)|stylelint)\b")
TYPE_RX = _RX(r"\b(mypy|pyright|pytype|basedpyright|vue-tsc|tsc|go vet|cargo check)\b")
PRECOMMIT_RX = _RX(r"pre-commit run|pre-commit/action")
BUILD_RX = _RX(r"\b(pip install|python -m build|poetry (install|build)|uv (sync|build|pip install)|npm (ci|install|run build)|"
               r"yarn (install|build)|pnpm (install|build)|go build|cargo build|dotnet (build|publish|restore)|"
               r"docker (build|buildx)|mvn |gradlew? |msbuild|setup\.py|make\b)")
DIGEST_RX = _RX(r"sha256sum|shasum -a 256|hashlib\.sha256|get-filehash|sha256")
DIGEST_VERIFY_RX = _RX(r"sha256sum (-c|--check)|shasum -a 256 (-c|--check)|hashlib\.sha256\(.*\)\.hexdigest\(\)\s*(==|!=)|"
                       r"hexdigest\(\)\s*(==|!=)|(==|!=)\s*hashlib\.sha256|get-filehash.*-ne|digest.*(==|!=|-ne|-eq)|"
                       r"verify[-_]?(digest|manifest|hash)")
SEC_RUN_RX = _RX(r"\b(bandit|pip-audit|safety check|trivy|gitleaks|semgrep|npm audit|yarn audit|osv-scanner|"
                 r"govulncheck|cargo audit|grype|detect-secrets|trufflehog|zizmor)\b")
SEC_USES = ("github/codeql-action", "actions/dependency-review-action", "aquasecurity/trivy-action",
            "gitleaks/gitleaks-action", "returntocorp/semgrep-action", "semgrep/", "snyk/actions",
            "ossf/scorecard-action", "anchore/scan-action", "pypa/gh-action-pip-audit", "zaproxy/", "zizmorcore/")
PROV_RUN_RX = _RX(r"\b(cosign|syft|cyclonedx|sbom|in-toto|slsa)\b")
PROV_USES = ("actions/attest-build-provenance", "actions/attest", "slsa-framework/", "sigstore/",
             "anchore/sbom-action")
REL_RUN_RX = _RX(r"\bgh release (create|upload|edit)|\btwine upload|\bnpm publish|\bsemantic-release|\bgoreleaser|"
                 r"\bcargo publish|\bdotnet nuget push|\bvsce publish|\bovsx publish|\bpoetry publish|\buv publish")
REL_USES = ("softprops/action-gh-release", "ncipollo/release-action", "actions/create-release",
            "pypa/gh-action-pypi-publish", "googleapis/release-please-action",
            "google-github-actions/release-please-action", "goreleaser/goreleaser-action", "changesets/action",
            "cycjimmy/semantic-release-action", "js-devtools/npm-publish")
DEP_RUN_RX = _RX(r"\bkubectl (apply|rollout|set image)|\bhelm (upgrade|install)|\bterraform apply|\bpulumi up|"
                 r"\bfly(ctl)? deploy|\bvercel (deploy|--prod)|\bnetlify deploy|\bwrangler (deploy|publish)|"
                 r"\bgcloud (run|app|functions) deploy|\baz (webapp|functionapp|containerapp) (deploy|up|update)|"
                 r"\baws (ecs update-service|s3 sync|lambda update-function-code|cloudformation deploy)|"
                 r"\bdocker push|\bmkdocs gh-deploy|\bgit push\b.*\bgh-pages\b")
DEP_USES = ("actions/deploy-pages", "peaceiris/actions-gh-pages", "jamesives/github-pages-deploy-action",
            "azure/webapps-deploy", "azure/k8s-deploy", "azure/functions-action", "azure/container-apps-deploy",
            "aws-actions/amazon-ecs-deploy", "google-github-actions/deploy-", "appleboy/ssh-action",
            "superfly/flyctl-actions", "amondnet/vercel-action", "nwtgck/actions-netlify",
            "cloudflare/wrangler-action", "cloudflare/pages-action", "/.github/workflows/jade-reusable-deploy.")
VERIFY_RX = _RX(r"hosted_parity|hosted_pages_verify|hosted_readback|\breadback\b|\bsmoke\b|health ?check|healthz|"
                r"curl\s+[^\n]*https?://|curl\s+[^\n]*\$\{?\{?\s*\w*url|invoke-webrequest|wget [^\n]*https?://|"
                r"urllib\.request|requests\.get|\bparity\b")
ALERT_RX = _RX(r"gh issue (create|comment)|issues\.create|create-an-issue|slack|msteams|teams webhook|webhook|"
               r"sendmail|pagerduty|opsgenie|notify")
ROLLBACK_INPUT_RX = _RX(r"^(ref|sha|commit|digest|version|tag|rollback|artifact|artifact[-_]name|manifest[-_]sha256)$")
GATE_NAME_RX = _RX(r"gate|admission|closure|guard|qualif|required|governor|readiness|stop[-_]?rule|first[-_]?red")
REF_BIND_RX = _RX(r"github\.ref\b|github_ref\b|refs/heads/|refs/tags/|head\.sha|github\.sha|workflow_sha")


def _list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [x for x in v if x is not None]
    return [v]


def _text(v) -> str:
    return "" if v is None else (v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str))


def _canon(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)


def action_ref(uses: str) -> dict:
    """Classify a `uses:` reference: local, docker, reusable workflow or action, and its pin state."""
    u = (uses or "").strip()
    if u.startswith("./"):
        return {"uses": u, "kind": "local", "third_party": False, "pinned": True}
    if u.startswith("docker://"):
        return {"uses": u, "kind": "docker", "third_party": True, "pinned": "@sha256:" in u}
    name, _, ref = u.partition("@")
    kind = "reusable" if "/.github/workflows/" in name else "action"
    return {"uses": u, "kind": kind, "third_party": True, "pinned": bool(SHA40.match(ref)), "name": name.lower()}


def _on(doc: dict):
    # PyYAML (YAML 1.1) reads the bare key `on` as boolean True.
    return doc.get("on", doc.get(True))


def _triggers(on) -> tuple[list, dict]:
    if isinstance(on, str):
        return [on], {}
    if isinstance(on, list):
        return sorted(str(x) for x in on), {}
    if isinstance(on, dict):
        return sorted(str(k) for k in on), on
    return [], {}


def parse(text: str, path: str = "", blob_oid: str | None = None, repo: str = "") -> dict:
    """Normalize one workflow file. A YAML or shape error is recorded, never raised."""
    base = {"path": path, "blob_oid": blob_oid, "oid": f"jade:wf:{repo}:{path}", "parse_error": None}
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return dict(base, parse_error=f"YAML: {str(exc).splitlines()[0][:160]}", jobs=[])
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        return dict(base, parse_error="SHAPE: no jobs mapping", jobs=[])
    triggers, on = _triggers(_on(doc))
    push = on.get("push") if isinstance(on.get("push"), dict) else {}
    dispatch = on.get("workflow_dispatch") if isinstance(on.get("workflow_dispatch"), dict) else {}
    perms = doc.get("permissions")
    wf = dict(base,
              name=str(doc.get("name") or path.rsplit("/", 1)[-1]),
              triggers=triggers,
              schedules=sorted(str(s.get("cron")) for s in _list(on.get("schedule")) if isinstance(s, dict)),
              dispatch_inputs=sorted(str(k) for k in (dispatch.get("inputs") or {})),
              reusable="workflow_call" in triggers,
              push_tags=bool(push.get("tags")),
              paths_filtered=any(isinstance(on.get(k), dict) and ("paths" in on[k] or "paths-ignore" in on[k])
                                 for k in ("push", "pull_request", "pull_request_target")),
              permissions=_perm_class(perms),
              concurrency=_concurrency(doc.get("concurrency")),
              jobs=[])
    for jid, job in doc["jobs"].items():
        if not isinstance(job, dict):
            wf["jobs"].append({"id": str(jid), "parse_error": "SHAPE: job is not a mapping", "needs": [],
                               "steps": [], "oid": f"jade:job:{repo}:{path}#{jid}"})
            continue
        env = job.get("environment")
        env_name = env.get("name") if isinstance(env, dict) else env
        steps = []
        for st in _list(job.get("steps")):
            if isinstance(st, dict):
                steps.append({"name": _text(st.get("name")), "uses": _text(st.get("uses")) or None,
                              "run": _text(st.get("run")), "with": st.get("with") or {},
                              "if": _text(st.get("if")), "continue_on_error": st.get("continue-on-error") is True})
        wf["jobs"].append({
            "id": str(jid), "oid": f"jade:job:{repo}:{path}#{jid}",
            "def_sha256": hashlib.sha256(_canon(job).encode()).hexdigest(),
            "name": _text(job.get("name")) or str(jid),
            "needs": sorted(str(n) for n in _list(job.get("needs"))),
            "if": _text(job.get("if")),
            "environment": None if env_name in (None, "") else str(env_name),
            "uses": _text(job.get("uses")) or None,
            "with": job.get("with") or {},
            "permissions": _perm_class(job.get("permissions")),
            "concurrency": _concurrency(job.get("concurrency")),
            "continue_on_error": job.get("continue-on-error") is True,
            "steps": steps,
        })
    wf["jobs"].sort(key=lambda j: j["id"])
    wf["dag"] = job_dag(wf["jobs"])
    for j in wf["jobs"]:
        j["layer"] = wf["dag"]["layer_of"].get(j["id"])
    return wf


def _perm_class(p):
    if p is None:
        return "default"
    if p == "write-all":
        return "write-all"
    if p == "read-all" or p == {}:
        return "read"
    if isinstance(p, dict):
        writes = sorted(k for k, v in p.items() if v == "write")
        return "write:" + ",".join(writes) if writes else "read"
    return "declared"


def _concurrency(c):
    if c is None:
        return None
    if isinstance(c, str):
        return {"group": c, "cancel_in_progress": False}
    if isinstance(c, dict):
        cancel = c.get("cancel-in-progress")
        return {"group": _text(c.get("group")), "cancel_in_progress": cancel is True or isinstance(cancel, str)}
    return None


def job_dag(jobs: list) -> dict:
    ids = {j["id"] for j in jobs}
    dangling = sorted({f"{j['id']}->{n}" for j in jobs for n in j["needs"] if n not in ids})
    indeg = {j["id"]: sum(1 for n in j["needs"] if n in ids) for j in jobs}
    children = {i: [] for i in ids}
    for j in jobs:
        for n in j["needs"]:
            if n in ids:
                children[n].append(j["id"])
    layer, layers, layer_of = sorted(i for i, d in indeg.items() if d == 0), [], {}
    while layer:
        layers.append(layer)
        for i in layer:
            layer_of[i] = len(layers) - 1
        nxt = []
        for i in layer:
            for c in children[i]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    nxt.append(c)
        layer = sorted(nxt)
    return {"layers": layers, "dangling": dangling, "cycle": len(layer_of) != len(ids), "layer_of": layer_of,
            "edges": sorted([n, j["id"]] for j in jobs for n in j["needs"] if n in ids)}


def _job_text(job: dict) -> str:
    parts = [job.get("if") or "", job.get("uses") or "", _text(job.get("with"))]
    for st in job["steps"]:
        parts += [st["run"], st["uses"] or "", _text(st["with"]), st["if"], st["name"]]
    return "\n".join(parts)


def _uses(job: dict) -> list[str]:
    out = [s["uses"] for s in job["steps"] if s["uses"]]
    if job.get("uses"):
        out.append(job["uses"])
    return out


def coverage_floors(text: str) -> list[float]:
    return sorted({float(m) for rx in COV_FLOOR_RX for m in rx.findall(text)})


def signals(job: dict, wf: dict) -> dict:
    """Lifecycle signals of one job (heuristic, text and action based)."""
    t = _job_text(job)
    runs = "\n".join(s["run"] for s in job["steps"])
    uses = [u.lower() for u in _uses(job)]
    refs = [action_ref(u) for u in _uses(job)]
    third = [r for r in refs if r["third_party"]]
    tests = bool(TEST_RX.search(runs)) or "jade-reusable-ci" in (job.get("uses") or "")
    test_steps = [s for s in job["steps"] if TEST_RX.search(s["run"])]
    soft = job["continue_on_error"] or any(s["continue_on_error"] or SOFT_FAIL_RX.search(s["run"]) for s in test_steps)
    floors = coverage_floors(t)
    deploy = bool(DEP_RUN_RX.search(runs)) or any(p in u for u in uses for p in DEP_USES) or (
        "docker/build-push-action" in " ".join(uses) and re.search(r"push['\"]?\s*:\s*['\"]?true", t, re.I) is not None)
    deploy = deploy or bool(job.get("environment"))
    release = bool(REL_RUN_RX.search(runs)) or any(p in u for u in uses for p in REL_USES)
    s = {
        "tests": tests,
        "test_evidence": bool(TEST_EVIDENCE_RX.search(t)),
        "pytest": bool(PYTEST_RX.search(runs)),
        "coverage": bool(COV_RX.search(t)) or any("codecov" in u for u in uses),
        "coverage_floor": max(floors) if floors else None,
        "zero_test_guard": bool(ZERO_GUARD_RX.search(t)) or "jade-reusable-ci" in (job.get("uses") or ""),
        "soft_fail_tests": bool(tests and soft),
        "lint": bool(LINT_RX.search(runs)) or any(("lint" in u or "ruff" in u or "pre-commit" in u) for u in uses),
        "typecheck": bool(TYPE_RX.search(runs)),
        "precommit": bool(PRECOMMIT_RX.search(t)),
        "build": bool(BUILD_RX.search(runs)) or any("docker/build-push-action" in u for u in uses),
        "artifact_upload": any("actions/upload-artifact" in u for u in uses),
        "artifact_download": any("actions/download-artifact" in u for u in uses),
        "digest": bool(DIGEST_RX.search(runs)),
        "digest_verify": bool(DIGEST_VERIFY_RX.search(runs)),
        "security": bool(SEC_RUN_RX.search(runs)) or any(p in u for u in uses for p in SEC_USES),
        "provenance": bool(PROV_RUN_RX.search(runs)) or any(p in u for u in uses for p in PROV_USES),
        "release": release,
        "deploy": deploy,
        "verify": bool(VERIFY_RX.search(runs)),
        "alerting": "failure()" in t and bool(ALERT_RX.search(t)),
        "ref_bound": bool(REF_BIND_RX.search(t)),
        "actions_total": len(third),
        "actions_pinned": sum(1 for r in third if r["pinned"]),
    }
    s["implicit_zero_guard"] = s["pytest"] and not s["soft_fail_tests"]
    return s


def _closure(jobs_by_id: dict, jid: str) -> set:
    seen, stack = set(), list(jobs_by_id[jid]["needs"])
    while stack:
        n = stack.pop()
        if n in seen or n not in jobs_by_id:
            continue
        seen.add(n)
        stack.extend(jobs_by_id[n]["needs"])
    return seen


def _dependents(jobs_by_id: dict, jid: str) -> set:
    return {k for k in jobs_by_id if jid in _closure(jobs_by_id, k)}


def deploy_gates(wf: dict, jid: str, sig: dict | None = None) -> dict:
    """DP1..DP10 for deploy job `jid` of a parsed workflow (PASS / FAIL)."""
    by_id = {j["id"]: j for j in wf["jobs"] if "def_sha256" in j}
    sig = sig or {k: signals(j, wf) for k, j in by_id.items()}
    job, s = by_id[jid], sig[jid]
    up, down = _closure(by_id, jid), _dependents(by_id, jid)
    conc = job.get("concurrency") or wf.get("concurrency")
    perm = job["permissions"] if job["permissions"] != "default" else wf["permissions"]
    with_keys = " ".join(str(k).lower() for k in (job.get("with") or {}))
    g = {
        "DP1": s["artifact_download"] or ("artifact" in with_keys),
        "DP2": s["digest_verify"] or ("digest" in with_keys or "sha256" in with_keys),
        "DP3": bool(job.get("environment")) or "environment" in with_keys,
        "DP4": bool(conc) and not conc["cancel_in_progress"],
        "DP5": perm not in ("default", "write-all"),
        "DP6": s["actions_total"] == s["actions_pinned"],
        "DP7": s["verify"] or any(sig[d]["verify"] for d in down),
        "DP8": (s["artifact_upload"] and s["verify"]) or any(sig[d]["artifact_upload"] for d in down),
        "DP9": any(sig[u]["tests"] or sig[u]["test_evidence"] for u in up),
        "DP10": s["ref_bound"] or any(sig[u]["ref_bound"] for u in up),
    }
    if REUSABLE_DEPLOY.search(job.get("uses") or ""):
        g.update({k: True for k in DELEGATED})
    return {k: ("PASS" if v else "FAIL") for k, v in g.items()}


def analyse(wf: dict) -> dict:
    """Attach signals and (for deploy jobs) DP gates; return a compact census record."""
    jobs = [j for j in wf.get("jobs", []) if "def_sha256" in j]
    sig = {j["id"]: signals(j, wf) for j in jobs}
    out_jobs = []
    for j in wf.get("jobs", []):
        if "def_sha256" not in j:
            out_jobs.append({"id": j["id"], "oid": j["oid"], "parse_error": j.get("parse_error")})
            continue
        s = sig[j["id"]]
        rec = {"id": j["id"], "oid": j["oid"], "def_sha256": j["def_sha256"], "needs": j["needs"],
               "layer": j["layer"], "environment": j["environment"], "uses": j["uses"],
               "permissions": j["permissions"],
               "signals": sorted(k for k, v in s.items() if v is True),
               "coverage_floor": s["coverage_floor"],
               "actions": [s["actions_pinned"], s["actions_total"]]}
        if s["deploy"]:
            rec["dp"] = deploy_gates(wf, j["id"], sig)
        out_jobs.append(rec)
    rec = {k: wf[k] for k in ("path", "blob_oid", "oid", "parse_error")}
    if wf["parse_error"]:
        return dict(rec, jobs=out_jobs, sig={})
    rec.update({k: wf[k] for k in ("name", "triggers", "schedules", "dispatch_inputs", "reusable", "push_tags",
                                   "paths_filtered", "permissions")})
    rec["concurrency"] = bool(wf["concurrency"])
    rec["dag"] = {k: wf["dag"][k] for k in ("layers", "edges", "dangling", "cycle")}
    rec["jobs"] = out_jobs
    rec["sig"] = sig
    return rec


def lint(paths: list[str], require_deploy: bool = False) -> tuple[int, list[dict]]:
    report, failed = [], 0
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            wf = parse(fh.read(), path=p)
        if wf["parse_error"]:
            report.append({"path": p, "error": wf["parse_error"]})
            failed += 1
            continue
        rec = analyse(wf)
        deploys = [j for j in rec["jobs"] if "dp" in j]
        for j in deploys:
            bad = sorted((k for k, v in j["dp"].items() if v != "PASS"), key=lambda k: int(k[2:]))
            failed += bool(bad)
            report.append({"path": p, "job": j["id"], "failed": bad})
        if require_deploy and not deploys:
            failed += 1
            report.append({"path": p, "error": "no deploy job"})
    return (1 if failed else 0), report


PR_EVENTS = {"pull_request", "pull_request_target"}
SECRET_RX = re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)")
EXPR_RX = re.compile(r"\$\{\{(.*?)\}\}", re.S)
# A condition keeps a secret off pull-request runs when it rejects the PR events by name, or only
# admits named non-PR events. Anything else (no condition, an unrelated one) counts as reachable.
NOT_PR_RX = re.compile(r"github\.event_name\s*!=\s*'pull_request(_target)?'")
ONLY_RX = re.compile(r"github\.event_name\s*==\s*'([a-z_]+)'")


def _excludes_pr(cond: str) -> bool:
    if NOT_PR_RX.search(cond or ""):
        return True
    named = ONLY_RX.findall(cond or "")
    return bool(named) and "pull_request" not in (cond or "")


def _secret_refs(value, guarded: bool) -> list[tuple[str, bool]]:
    """(secret, guarded) for each `secrets.X` in value; an expression that itself rejects PR events guards it."""
    out = []
    for expr in EXPR_RX.findall(_text(value)):
        safe = guarded or bool(NOT_PR_RX.search(expr))
        out += [(name, safe) for name in SECRET_RX.findall(expr)]
    return out


def pr_secret_exposure(text: str, path: str = "") -> list[dict]:
    """Repository secrets a pull-request run can reach. GITHUB_TOKEN is per-run and excluded.

    On a same-repo pull_request, the PR head supplies both the workflow file and the code the job
    runs, so a secret in such a job is readable by anyone who can push a branch. This is the
    YAML half of the control: the owner half is to hold these secrets in an environment that only
    admits the default branch.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        return []
    triggers, _ = _triggers(_on(doc))
    if not PR_EVENTS & set(triggers):
        return []
    found = []
    for jid, job in doc["jobs"].items():
        if not isinstance(job, dict):
            continue
        job_safe = _excludes_pr(_text(job.get("if")))
        if job.get("secrets") == "inherit" and not job_safe:
            found.append({"path": path, "job": str(jid), "step": None, "secret": "INHERIT"})
        refs = _secret_refs([job.get("env"), job.get("with"), job.get("secrets")], job_safe)
        for i, st in enumerate(_list(job.get("steps"))):
            if isinstance(st, dict):
                safe = job_safe or _excludes_pr(_text(st.get("if")))
                name = _text(st.get("name")) or f"step {i + 1}"
                refs += [(s, g, name) for s, g in _secret_refs([st.get("env"), st.get("with"), st.get("run")], safe)]
        for ref in refs:
            secret, guarded, step = (ref + (None,))[:3]
            if secret != "GITHUB_TOKEN" and not guarded:
                found.append({"path": path, "job": str(jid), "step": step, "secret": secret})
    return found


def secrets_lint(paths: list[str]) -> tuple[int, list[dict]]:
    report = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            report += pr_secret_exposure(fh.read(), path=p)
    return (1 if report else 0), report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("lint", help="check deploy jobs against DP1..DP10")
    lp.add_argument("files", nargs="+")
    lp.add_argument("--require-deploy", action="store_true")
    sp = sub.add_parser("secrets-lint", help="fail when a pull-request run can reach a repository secret")
    sp.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "secrets-lint":
        rc, report = secrets_lint(a.files)
        print(json.dumps({"schema": "jade.devops.pr_secret_lint.v1", "result": report,
                          "verdict": "PASS" if rc == 0 else "PR_SECRET_EXPOSURE"}, indent=1, sort_keys=True))
        return rc
    rc, report = lint(a.files, a.require_deploy)
    print(json.dumps({"schema": "jade.devops.deploy_lint.v1", "gates": DP_GATES, "result": report,
                      "verdict": "PASS" if rc == 0 else "DEPLOY_CONTRACT_FIRST_RED"}, indent=1, sort_keys=True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
