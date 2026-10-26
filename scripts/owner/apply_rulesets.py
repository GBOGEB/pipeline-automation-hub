#!/usr/bin/env python3
"""Owner-only: import the P-process BASIC (or HARD) branch rulesets with one command.

Reads ``manifest.json`` and the ``*.basic.json`` / ``*.hard.json`` files from
``mission-control/qps-triage-ultra/p-process/rulesets/`` (read-only; this script never
writes there) and, per target repo:

1. GETs the repo's existing rulesets and finds the one with the same ``name``;
2. prints a plan: CREATE (no ruleset of that name), UPDATE (field diff shown) or NOOP;
3. only with ``--apply``: POSTs (create) or PUTs (update by name) the ruleset;
4. re-reads the ruleset and the effective default-branch rules and reports enforcement.

Default is a dry run: no write call is ever made without ``--apply``. The script never
deletes a ruleset (the gh wrapper refuses DELETE). ``--verify`` is a read-only recurring
check that reports, per repo, whether the expected ruleset is active and effective.

Effective-rule gap detection reuses ``verify_rulesets.gaps`` / ``probe_status`` from the
p-process folder instead of re-implementing it.

Requires ``gh`` logged in as a repo admin. Stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULESETS_DIR = ROOT / "mission-control" / "qps-triage-ultra" / "p-process" / "rulesets"
# Fields of a ruleset we own. Everything else in a GET (id, node_id, _links, timestamps,
# source, current_user_can_bypass) is server-side metadata and is ignored in the diff.
MANAGED_FIELDS = ("name", "target", "enforcement", "conditions", "bypass_actors", "rules")
WRITE_METHODS = {"POST", "PUT"}


# --------------------------------------------------------------------------- gh access
def gh_api(path: str, method: str = "GET", body: dict | None = None):
    """Call ``gh api``. Returns ``(data, None)`` on success or ``(None, error)``.

    Never deletes: DELETE (and anything other than GET/POST/PUT) is refused here so no
    code path in this script can remove a ruleset.
    """
    method = method.upper()
    if method not in {"GET"} | WRITE_METHODS:
        raise ValueError(f"refusing gh api method {method}: this tool never deletes or patches")
    cmd = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    payload = None
    if body is not None:
        cmd += ["--input", "-"]
        payload = json.dumps(body)
    try:
        r = subprocess.run(cmd, input=payload, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return None, "gh CLI not found on PATH"
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip().splitlines()
        return None, (msg[-1] if msg else f"gh exited {r.returncode}")[:300]
    try:
        return (json.loads(r.stdout) if r.stdout.strip() else {}), None
    except json.JSONDecodeError as e:
        return None, f"non-JSON response: {e}"


def _load_verify_module(rulesets_dir: Path):
    """Import verify_rulesets.py from the p-process folder (reuse, do not copy)."""
    path = rulesets_dir / "verify_rulesets.py"
    spec = importlib.util.spec_from_file_location("p_process_verify_rulesets", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- inputs
def load_targets(rulesets_dir: Path, tier: str, repo_filter: list[str] | None):
    """Return ``[(repo, branch, desired_ruleset_or_None, note)]`` from the manifest."""
    manifest = json.loads((rulesets_dir / "manifest.json").read_text(encoding="utf-8"))
    wanted = None
    if repo_filter:
        wanted = {r.lower() for r in repo_filter} | {r.split("/")[-1].lower() for r in repo_filter}
    out = []
    for repo, m in manifest.items():
        if wanted is not None and repo.lower() not in wanted and repo.split("/")[-1].lower() not in wanted:
            continue
        key = "file" if tier == "basic" else "hard_file"
        fname = m.get(key)
        if not fname:
            out.append((repo, m["branch"], None, f"no {tier} ruleset in manifest"))
            continue
        desired = json.loads((rulesets_dir / fname).read_text(encoding="utf-8"))
        out.append((repo, m["branch"], desired, fname))
    if wanted is not None and not out:
        raise SystemExit(f"--repo {repo_filter} matched nothing in manifest.json")
    return out


# --------------------------------------------------------------------------- diff
def _subset_diff(desired, actual, path: str) -> list[str]:
    """Differences where ``actual`` does not carry what ``desired`` asks for.

    Dicts compare only the keys we set (GitHub adds defaults such as extra rule
    parameters); lists and scalars compare exactly.
    """
    if isinstance(desired, dict) and isinstance(actual, dict):
        out = []
        for k, v in desired.items():
            if k not in actual:
                out.append(f"{path}.{k}: missing -> {json.dumps(v)}")
            else:
                out += _subset_diff(v, actual[k], f"{path}.{k}")
        return out
    if isinstance(desired, list) and isinstance(actual, list):
        if all(isinstance(x, dict) for x in desired + actual):
            norm = lambda xs: sorted(json.dumps(x, sort_keys=True) for x in xs)  # noqa: E731
            if norm(desired) == norm(actual):
                return []
        elif sorted(map(json.dumps, desired)) == sorted(map(json.dumps, actual)):
            return []
        return [f"{path}: {json.dumps(actual)} -> {json.dumps(desired)}"]
    if desired != actual:
        return [f"{path}: {json.dumps(actual)} -> {json.dumps(desired)}"]
    return []


def _rules_by_type(rules):
    return {r["type"]: (r.get("parameters") or {}) for r in rules or []}


def diff_ruleset(desired: dict, actual: dict) -> list[str]:
    """Human-readable field diff from ``actual`` (live) to ``desired`` (file)."""
    out = []
    for f in MANAGED_FIELDS:
        if f == "rules":
            continue
        out += _subset_diff(desired.get(f), actual.get(f), f)
    want, have = _rules_by_type(desired.get("rules")), _rules_by_type(actual.get("rules"))
    for t in want:
        if t not in have:
            out.append(f"rules[{t}]: add")
        else:
            out += _subset_diff(want[t], have[t], f"rules[{t}]")
    for t in have:
        if t not in want:
            out.append(f"rules[{t}]: present live, not in file (PUT replaces the rule list, so it is dropped)")
    return out


# --------------------------------------------------------------------------- plan
def plan_repo(repo: str, desired: dict, gh=gh_api) -> dict:
    """Read-only. Decide CREATE / UPDATE / NOOP / ERROR for one repo."""
    listing, err = gh(f"repos/{repo}/rulesets?per_page=100&includes_parents=false")
    if err is not None or not isinstance(listing, list):
        return {"repo": repo, "action": "ERROR", "error": f"list rulesets: {err or listing}"}
    others = [s for s in listing if s.get("name") != desired["name"]]
    same = [s for s in listing if s.get("name") == desired["name"]
            and s.get("source_type", "Repository") == "Repository"]
    plan = {"repo": repo, "name": desired["name"],
            "other_rulesets": [f"{s.get('id')} '{s.get('name')}' ({s.get('enforcement')})" for s in others]}
    if len(same) > 1:
        return {**plan, "action": "ERROR",
                "error": f"{len(same)} rulesets named '{desired['name']}'; resolve by hand"}
    if not same:
        return {**plan, "action": "CREATE", "diff": ["new ruleset"]}
    rid = same[0]["id"]
    full, err = gh(f"repos/{repo}/rulesets/{rid}")
    if err is not None:
        return {**plan, "action": "ERROR", "id": rid, "error": f"read ruleset {rid}: {err}"}
    d = diff_ruleset(desired, full)
    return {**plan, "id": rid, "action": "UPDATE" if d else "NOOP", "diff": d}


def apply_plan(plan: dict, desired: dict, gh=gh_api) -> dict:
    """Perform the single write the plan calls for. Never called in dry-run."""
    repo = plan["repo"]
    if plan["action"] == "CREATE":
        data, err = gh(f"repos/{repo}/rulesets", "POST", desired)
    elif plan["action"] == "UPDATE":
        data, err = gh(f"repos/{repo}/rulesets/{plan['id']}", "PUT", desired)
    else:
        return {"written": False}
    if err is not None:
        return {"written": False, "error": err}
    return {"written": True, "id": (data or {}).get("id", plan.get("id"))}


# --------------------------------------------------------------------------- verify
def verify_repo(repo: str, branch: str, desired: dict, verify_mod, gh=gh_api) -> dict:
    """Read-only: is the named ruleset active, targeted, and effective on ``branch``?"""
    listing, err = gh(f"repos/{repo}/rulesets?per_page=100&includes_parents=false")
    rulesets = listing if err is None and isinstance(listing, list) else None
    found, untargeted = None, []
    for s in rulesets or []:
        full, ferr = gh(f"repos/{repo}/rulesets/{s['id']}")
        if ferr is not None:
            continue
        inc = (((full.get("conditions") or {}).get("ref_name") or {}).get("include")) or []
        if full.get("enforcement") == "active" and not inc:
            untargeted.append(f"ruleset {s['id']} '{s.get('name')}' is active but targets no branch")
        if full.get("name") == desired["name"]:
            found = full
    effective, eerr = gh(f"repos/{repo}/rules/branches/{branch}")
    br, berr = gh(f"repos/{repo}/branches/{branch}")
    probe = verify_mod.probe_status(effective if eerr is None else {"_error": eerr},
                                    rulesets if rulesets is not None else {"_error": err},
                                    br if berr is None else {"_error": berr},
                                    desired, untargeted)
    if rulesets is None:
        ruleset_state = "UNKNOWN"
    elif found is None:
        ruleset_state = "ABSENT"
    elif found.get("enforcement") != "active":
        ruleset_state = f"PRESENT_{str(found.get('enforcement')).upper()}"
    elif not (((found.get("conditions") or {}).get("ref_name") or {}).get("include")):
        ruleset_state = "ACTIVE_UNTARGETED"
    else:
        ruleset_state = "ACTIVE"
    # ok = the expected ruleset is active, targeted and every expected rule is effective.
    # Other stale untargeted rulesets are reported (they keep the EVERRED drift probe,
    # probe_status, at CONFIRMED_DRIFT) but do not make the expected ruleset inactive.
    ok = ruleset_state == "ACTIVE" and not probe["gaps"] and not probe["unknown_readbacks"]
    return {"repo": repo, "branch": branch, "name": desired["name"],
            "ruleset_id": (found or {}).get("id"), "ruleset_state": ruleset_state,
            "ok": ok, "untargeted_rulesets": untargeted, **probe}


# --------------------------------------------------------------------------- CLI
def _print_verify(v: dict) -> None:
    flag = "OK  " if v["ok"] else "RED "
    rid = v["ruleset_id"] if v["ruleset_id"] is not None else "-"
    print(f"{flag} {v['repo']:34s} ruleset={v['ruleset_state']:<18s} id={rid!s:<10s} "
          f"drift-probe={v['probe_status']}")
    for g in v["gaps"]:
        print(f"       gap: {g}")
    for u in v["unknown_readbacks"]:
        print(f"       unknown: {u}")
    for u in v["untargeted_rulesets"]:
        print(f"       note: {u}")


def main(argv=None, gh=gh_api) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually POST/PUT (default: dry-run plan only)")
    ap.add_argument("--verify", action="store_true", help="read-only: report which repos have the ruleset active")
    ap.add_argument("--repo", action="append", help="limit to this repo (OWNER/NAME or NAME); repeatable")
    ap.add_argument("--tier", choices=["basic", "hard"], default="basic")
    ap.add_argument("--rulesets-dir", type=Path, default=RULESETS_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON instead of text")
    a = ap.parse_args(argv)
    if a.apply and a.verify:
        ap.error("--apply and --verify are exclusive (--apply already verifies after writing)")

    targets = load_targets(a.rulesets_dir, a.tier, a.repo)
    verify_mod = _load_verify_module(a.rulesets_dir)
    results, rc = [], 0

    if a.verify:
        for repo, branch, desired, note in targets:
            if desired is None:
                results.append({"repo": repo, "ok": None, "skipped": note})
                if not a.json:
                    print(f"SKIP {repo:34s} {note}")
                continue
            v = verify_repo(repo, branch, desired, verify_mod, gh)
            results.append(v)
            rc |= 0 if v["ok"] else 1
            if not a.json:
                _print_verify(v)
        if a.json:
            print(json.dumps({"mode": "verify", "tier": a.tier, "repos": results}, indent=2))
        else:
            n_ok = sum(1 for r in results if r.get("ok"))
            n = sum(1 for r in results if r.get("ok") is not None)
            print(f"\n{n_ok}/{n} repos have the {a.tier.upper()} ruleset active and effective.")
        return rc

    mode = "APPLY" if a.apply else "DRY-RUN (no writes; add --apply to import)"
    if not a.json:
        print(f"{mode} - tier {a.tier.upper()} - source {a.rulesets_dir}\n")
    for repo, branch, desired, note in targets:
        if desired is None:
            results.append({"repo": repo, "action": "SKIP", "note": note})
            if not a.json:
                print(f"SKIP   {repo}: {note}")
            continue
        p = plan_repo(repo, desired, gh)
        p["file"] = note
        if not a.json:
            print(f"{p['action']:<6s} {repo} <- {note}  '{desired['name']}'"
                  + (f" (id {p['id']})" if p.get("id") else ""))
            for line in p.get("diff", []) if p["action"] == "UPDATE" else []:
                print(f"         {line}")
            for o in p.get("other_rulesets", []):
                print(f"         other ruleset left untouched: {o}")
            if p["action"] == "ERROR":
                print(f"         error: {p['error']}")
        if p["action"] == "ERROR":
            rc = 1
        if a.apply and p["action"] in {"CREATE", "UPDATE"}:
            w = apply_plan(p, desired, gh)
            p["write"] = w
            if not w["written"]:
                rc = 1
                if not a.json:
                    print(f"         WRITE FAILED: {w.get('error')}")
            elif not a.json:
                print(f"         written: ruleset id {w.get('id')}")
        if a.apply and p["action"] in {"CREATE", "UPDATE", "NOOP"}:
            v = verify_repo(repo, branch, desired, verify_mod, gh)
            p["verify"] = v
            if not v["ok"]:
                rc = 1
            if not a.json:
                print("         readback: ", end="")
                _print_verify(v)
        results.append(p)
    if a.json:
        print(json.dumps({"mode": "apply" if a.apply else "dry-run", "tier": a.tier, "repos": results}, indent=2))
    elif not a.apply:
        todo = sum(1 for r in results if r.get("action") in {"CREATE", "UPDATE"})
        print(f"\n{todo} ruleset write(s) pending. Nothing was changed.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
