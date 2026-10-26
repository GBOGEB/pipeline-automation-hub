#!/usr/bin/env python3
"""GOGREEN depth census (N+10): breadth, depth, penetration, coverage and ZERO-tested stats.

Recursive use of what already exists, no new data source:
  * ADMISSION.json (N+9)                -> disposition + red/green evidence per workflow
  * scripts/zero_test_gate_audit.py      -> unittest tests collectable per invocation
  * gate.triggers() / gate.applies()     -> which tracked files fire which PR gate
  * git ls-files                         -> the file denominator

Five dimensions, each with an explicit ZERO bucket (unknown is never zero, zero is never
hidden):
  breadth      lanes with terminal evidence (master, merged-PR)        ZERO_EVIDENCE
  depth        tests the workflow executes (unittest + pytest + node)  ZERO_TESTS / UNKNOWN_TESTS
  penetration  tracked files whose change fires the workflow on a PR   ZERO_PENETRATION (dead filter)
  coverage     per area: files guarded by >=1 PR gate / ENFORCED gate  ZERO_GATED files
  tested       per area: source modules referenced by >=1 test file    ZERO_TESTED modules

Static and read-only: no test or workflow is executed. A module "referenced by a test"
means a test file imports it or is named after it; it is not line coverage.
"""
from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as g  # noqa: E402

SCHEMA = "gogreen.depth_census.v1"
# A runner invocation is a command SEGMENT that starts with the runner (after env assignments
# and wrappers). Matching the word anywhere also matched `pip install pytest pytest-cov` and
# counted the whole suite for it (N+12 correction). The head is parsed token by token (no
# nested-quantifier regex: linear on any input, CodeQL py/redos).
PYTHON_EXE = re.compile(r"python(?:3(?:\.\d+)?)?")
ENV_ASSIGN = re.compile(r"[A-Z_][A-Z0-9_]*=")
WRAPPERS = {"time", "exec", "command"}
SEGMENT = re.compile(r"\n|&&|\|\||;|\|")
# Flags that select a subset (or nothing): such a run is not the files' full test set.
SELECTING = ("-m", "-k", "--collect-only", "--co", "--benchmark-only", "--lf", "--last-failed", "--sw",
             "--stepwise", "--deselect")
SELECTING_SHORT = ("-m", "-k")  # pytest also accepts -msmoke / -m=smoke / -kexpr / -k=expr
ARG_FLAGS = {"-k", "-m", "-p", "-c", "-o", "-n", "-W", "--rootdir", "--cov", "--cov-report", "--cov-config",
             "--junitxml", "--maxfail", "--timeout", "--tb", "--durations", "--basetemp", "--ignore",
             "--deselect", "--benchmark-json", "--json-report-file", "--confcutdir", "--import-mode"}
NO_RUN = ("--version", "-V", "--help", "-h", "--fixtures", "--markers")


def _strip_wrappers(toks: list) -> list:
    i = 0
    while i < len(toks):
        t = toks[i]
        if ENV_ASSIGN.match(t) or t in WRAPPERS:
            i += 1
        elif t == "timeout":
            i += 2
        elif t == "xvfb-run":
            i += 2 if i + 1 < len(toks) and toks[i + 1] == "-a" else 1
        else:
            break
    return toks[i:]


def _runner_args(toks: list):
    """(runner, remaining tokens) when the segment invokes pytest or node --test, else None."""
    if not toks:
        return None
    if toks[:2] == ["node", "--test"]:
        return "node", toks[2:]
    i = 0
    if PYTHON_EXE.fullmatch(toks[0]) and len(toks) > 1 and toks[1] == "-m":
        i = 2
    if toks[i:i + 2] == ["coverage", "run"]:
        j = i + 2
        while j < len(toks) and toks[j] != "-m":
            if not toks[j].startswith("-"):
                return None  # coverage run script.py: not pytest
            j += 1
        i = j + 1
    if i < len(toks) and toks[i] in ("pytest", "py.test"):
        return "pytest", toks[i + 1:]
    return None


def is_selecting(toks: list) -> bool:
    for t in toks:
        if t in SELECTING or any(t.startswith(f + "=") for f in SELECTING if f.startswith("--")):
            return True
        if not t.startswith("--") and t[:2] in SELECTING_SHORT and len(t) > 2:
            return True
    return False


def runner_invocations(run: str) -> list:
    """[(runner, args, selecting)] for each command segment that invokes pytest or node --test."""
    out = []
    for seg in SEGMENT.split(run):
        seg = re.split(r"\s\d?>{1,2}\s*\S*", " " + seg.strip())[0].strip()  # drop redirections
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        hit = _runner_args(_strip_wrappers(toks))
        if not hit:
            continue
        runner, rest = hit
        if any(t in NO_RUN for t in rest):
            continue  # prints and exits: runs no tests
        out.append((runner, shlex.join(rest), is_selecting(rest)))
    return out


def _pytest_ini_section(path: Path, section: str):
    """The pytest section of an INI file as a dict, or None when the file holds none."""
    cp = configparser.ConfigParser(interpolation=None, strict=False, allow_no_value=True)
    try:
        cp.read_string(path.read_text(encoding="utf-8", errors="replace"))
    except configparser.Error:
        return None
    return dict(cp[section]) if cp.has_section(section) else None


def pytest_config(directory: Path):
    """pytest's own config for a run started in `directory` (pytest locate_config order), or None."""
    d = Path(directory)
    for name, section in (("pytest.ini", "pytest"), (".pytest.ini", "pytest"), ("pyproject.toml", None),
                          ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        f = d / name
        if not f.is_file():
            continue
        if section is None:
            try:
                data = tomllib.loads(f.read_text(encoding="utf-8", errors="replace"))
            except tomllib.TOMLDecodeError:
                continue
            opts = data.get("tool", {}).get("pytest", {}).get("ini_options")
            if isinstance(opts, dict):
                return opts
            continue
        cfg = _pytest_ini_section(f, section)
        if cfg is not None:
            return cfg
        if name == "pytest.ini":
            return {}  # pytest.ini is the config even when it has no [pytest] section
    return None


def pytest_testpaths(directory: Path) -> list:
    """What a bare `pytest` started in `directory` collects.

    pytest applies `testpaths` only when the invocation directory is the rootdir, i.e. holds
    the config itself; otherwise (or with no testpaths) it collects the invocation directory."""
    cfg = pytest_config(directory) or {}
    raw = cfg.get("testpaths")
    if isinstance(raw, str):
        try:
            paths = shlex.split(raw)  # INI: whitespace/newline separated, may span indented lines
        except ValueError:
            paths = raw.split()
    elif isinstance(raw, list):
        paths = [str(x) for x in raw]
    else:
        paths = []
    return paths or ["."]
TEST_FILE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|[^/]*\.test\.m?[jt]s)$")
SRC_EXT = (".py", ".mjs", ".js", ".ts")
# Not "zero-tested": the module IS a check (browser/QA/validator harness), or carries no logic.
HARNESS = re.compile(r"(browser_qa|_qa\.py$|(^|/)run_[^/]*qa[^/]*\.py$|(^|/)validate_[^/]*\.py$)")
NON_LOGIC = re.compile(r"(\.config\.[cm]?[jt]s$|\.d\.ts$|[-_]data\.js$|(^|/)published/)")


def tracked_files(root: Path) -> list:
    out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f]


def area(path: str) -> str:
    parts = path.split("/")
    if parts[0] in ("mission-control", "tools", ".github") and len(parts) > 2:
        return "/".join(parts[:2])
    return parts[0] if len(parts) > 1 else "(root)"


def load_audit(root: Path):
    """The hub's zero-test audit, applied to any checkout (it only reads files)."""
    sys.path.insert(0, str(HERE.parents[2] / "scripts"))
    import zero_test_gate_audit as zt  # noqa: E402
    return zt.audit(root)


def pytest_count(path: Path) -> int | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            n += 1
    return n


def node_count(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return len(re.findall(r"(?m)^\s*(?:test|it)\s*\(", text))


def resolve_targets(root: Path, wd: str, args: str, default_glob: str, default_targets=None) -> list | None:
    try:
        toks = shlex.split(args)
    except ValueError:
        return None
    if any("$" in t for t in toks):
        return None
    targets, skip = [], False
    for t in toks:
        if skip:
            skip = False
            continue
        if t in ARG_FLAGS:
            skip = True
            continue
        if t.startswith("-"):
            continue
        targets.append(t.split("::")[0])
    base = (root / wd).resolve()
    files = []
    for t in targets or (default_targets or ["."]):
        p = (base / t)
        if p.is_dir():
            files += sorted(x for x in p.rglob(default_glob) if "node_modules" not in x.parts)
        elif p.is_file():
            files.append(p)
        elif any(c in t for c in "*?["):
            files += sorted(base.glob(t))
        else:
            return None
    return files


def workflow_tests(root: Path, audit_rows: list) -> dict:
    """{workflow file name: {invocations, tests, unknown, by_runner, files: {test file: count}}}.

    `tests` sums every invocation (a suite run by three workflows counts three times: test
    executions per full CI pass). Unique tests are derived from `files` across workflows."""
    out = {}
    for r in audit_rows:
        w = out.setdefault(r["workflow"], {"invocations": 0, "tests": 0, "unknown": 0, "by_runner": {}, "files": {}})
        w["invocations"] += 1
        for f in r.get("files") or []:
            if isinstance(f.get("tests"), int):
                w["files"][f["file"]] = f["tests"]
        if r.get("state") == "UNRESOLVED":
            w["unknown"] += 1
        else:
            w["tests"] += r.get("tests_collectable", 0)
            w["by_runner"]["unittest"] = w["by_runner"].get("unittest", 0) + r.get("tests_collectable", 0)
    for wf in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        for job in (doc.get("jobs") or {}).values():
            jwd = (((job or {}).get("defaults") or {}).get("run") or {}).get("working-directory", ".")
            for step in (job or {}).get("steps") or []:
                run = step.get("run") if isinstance(step, dict) else None
                if not isinstance(run, str):
                    continue
                run = re.sub(r"\\\s*\n\s*", " ", run)
                wd = step.get("working-directory", jwd)
                for runner, args, selecting in runner_invocations(run):
                    glob, counter = (("test_*.py", pytest_count) if runner == "pytest" else ("*.test.mjs", node_count))
                    w = out.setdefault(wf.name, {"invocations": 0, "tests": 0, "unknown": 0, "by_runner": {},
                                                 "files": {}})
                    w["invocations"] += 1
                    if selecting:  # -m/-k/--collect-only: a subset of unknown size, never the full set
                        w["selected"] = w.get("selected", 0) + 1
                        w["unknown"] += 1
                        continue
                    files = resolve_targets(root, str(wd), args, glob,
                                            pytest_testpaths(root / str(wd)) if runner == "pytest" else None)
                    counts = [counter(f) for f in files] if files is not None else None
                    if counts is None or any(c is None for c in counts):
                        w["unknown"] += 1
                        continue
                    w["tests"] += sum(counts)
                    for f, c in zip(files, counts):
                        w["files"][f.relative_to(root.resolve()).as_posix() if f.is_absolute() else str(f)] = c
                    w["by_runner"][runner] = w["by_runner"].get(runner, 0) + sum(counts)
    return out


def imported_names(path: Path) -> set:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    names = set()
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    names.update(a.name.split("."))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.update(node.module.split("."))
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 300:
                # spec_from_file_location / subprocess targets: kept as a path, resolved exactly later
                for m in re.finditer(r"([A-Za-z0-9_./-]+\.(?:py|mjs))\b", node.value):
                    names.add("path:" + m.group(1).lstrip("./"))
    else:
        names.update(re.findall(r"""(?:from|import\()\s*['"][^'"]*?([A-Za-z0-9_.-]+?)(?:\.m?[jt]s)?['"]""", text))
    return names


def module_testedness(root: Path, files: list) -> dict:
    tests = [f for f in files if TEST_FILE.search(f)]
    fileset = set(files)
    referenced, local = set(), set()
    for t in tests:
        names = imported_names(root / t)
        referenced |= names
        here = Path(t).parent
        for n in names:  # bare "x.py" resolves only next to the test or one level up (ROOT / "x.py")
            if n.startswith("path:") and "/" not in n[5:]:
                for d in (here, here.parent):
                    cand = (d / n[5:]).as_posix()
                    if cand in fileset:
                        local.add(cand)
        stem = Path(t).name
        for pre, suf in (("test_", ".py"), ("", "_test.py")):
            if stem.startswith(pre) and stem.endswith(suf):
                referenced.add(stem[len(pre):len(stem) - len(suf)])
        if ".test." in stem:
            referenced.add(stem.split(".test.")[0])
    paths = {n[5:] for n in referenced if n.startswith("path:")}
    by_path = set(local)
    for f in files:
        for ref in paths:  # exact path (or path suffix with a directory), never a bare basename guess
            if f == ref or ("/" in ref and f.endswith("/" + ref)):
                by_path.add(f)
    out = {}
    for f in files:
        if not f.endswith(SRC_EXT) or TEST_FILE.search(f) or "/node_modules/" in f or f.endswith("__init__.py"):
            continue
        if Path(f).name in ("conftest.py", "setup.py") or "/fixtures/" in f or "/samples/" in f:
            continue
        if NON_LOGIC.search(f):
            continue
        if Path(f).stem in referenced or f in by_path:
            out[f] = "TESTED"
        elif HARNESS.search(f):
            out[f] = "HARNESS"
        else:
            out[f] = "ZERO_TESTED"
    return out


def penetration(root: Path, files: list, entries: dict) -> tuple:
    """(per-workflow guarded-file counts, per-file (pr_gates, enforced_gates, targeted, targeted_enforced)).

    A catch-all gate (no paths filter) fires on every file, so it inflates penetration to
    100% while saying nothing about the file. `targeted` counts only path-filtered gates."""
    trig = {}
    for path in sorted(entries):
        t = g.triggers(root / path)
        if path == g.SELF or g.fires_for_base(t, "master"):
            continue
        trig[path] = t
    per_wf = {p: 0 for p in trig}
    per_file = {}
    for f in files:
        pr = en = tg = te = 0
        for p, t in trig.items():
            if g.applies([f], t["paths"], t["paths_ignore"]):
                per_wf[p] += 1
                enf = entries[p]["disposition"] == g.ENFORCED
                pr += 1
                en += enf
                if t["paths"] or t["paths_ignore"]:
                    tg += 1
                    te += enf
        per_file[f] = (pr, en, tg, te)
    return per_wf, per_file


def build(root: Path, ledger: dict, audit: dict) -> dict:
    root = Path(root)
    files = tracked_files(root)
    entries = {e["path"]: e for e in ledger["entries"]}
    tests = workflow_tests(root, audit["rows"])
    per_wf, per_file = penetration(root, files, entries)
    tested = module_testedness(root, files)
    wrows = []
    for path, e in sorted(entries.items()):
        t = tests.get(Path(path).name, {"invocations": 0, "tests": 0, "unknown": 0, "by_runner": {}})
        ev = e.get("evidence", {})
        zero = []
        if not any(v.get("current") for v in ev.values()):
            zero.append("ZERO_EVIDENCE")
        if t["invocations"] == 0:
            zero.append("ZERO_TESTS")
        elif t["tests"] == 0 and t["unknown"]:
            zero.append("UNKNOWN_TESTS")
        elif t["tests"] == 0:
            zero.append("ZERO_TESTS")
        if path in per_wf and per_wf[path] == 0 and e["trigger"]["filter"] != "ALL":
            zero.append("ZERO_PENETRATION")
        wrows.append({"path": path, "name": e.get("name"), "disposition": e["disposition"],
                      "breadth": {"lanes": sorted(k for k, v in ev.items() if v.get("current")),
                                  "observed_heads": sum((v.get("green_streak") or 0) for v in ev.values())},
                      "depth": {"test_invocations": t["invocations"], "tests": t["tests"],
                                "unresolved_invocations": t["unknown"], "by_runner": t["by_runner"]},
                      "penetration": {"files_guarded": per_wf.get(path), "pr_scoped": path in per_wf},
                      "zero": zero})
    areas = {}
    for f in files:
        a = areas.setdefault(area(f), {"files": 0, "pr_gated": 0, "enforced_gated": 0, "zero_gated": 0,
                                       "targeted": 0, "targeted_enforced": 0, "zero_targeted": 0,
                                       "modules": 0, "modules_tested": 0, "zero_tested_modules": 0,
                                       "max_gates_on_one_file": 0})
        pr, en, tg, te = per_file[f]
        a["files"] += 1
        a["targeted"] += tg > 0
        a["targeted_enforced"] += te > 0
        a["zero_targeted"] += tg == 0
        a["pr_gated"] += pr > 0
        a["enforced_gated"] += en > 0
        a["zero_gated"] += pr == 0
        a["max_gates_on_one_file"] = max(a["max_gates_on_one_file"], pr)
        if f in tested:
            a["modules"] += 1
            a["modules_tested"] += tested[f] == "TESTED"
            a["harness_modules"] = a.get("harness_modules", 0) + (tested[f] == "HARNESS")
            a["zero_tested_modules"] += tested[f] == "ZERO_TESTED"
    for a in areas.values():
        a["pr_gated_pct"] = round(100 * a["pr_gated"] / a["files"], 1)
        a["enforced_gated_pct"] = round(100 * a["enforced_gated"] / a["files"], 1)
        a["targeted_pct"] = round(100 * a["targeted"] / a["files"], 1)
        a["targeted_enforced_pct"] = round(100 * a["targeted_enforced"] / a["files"], 1)
        a.setdefault("harness_modules", 0)
        a["modules_tested_pct"] = round(100 * a["modules_tested"] / a["modules"], 1) if a["modules"] else None
    uniq = {}
    for t in tests.values():
        uniq.update(t["files"])
    zero_counts = {}
    for w in wrows:
        for z in w["zero"]:
            zero_counts[z] = zero_counts.get(z, 0) + 1
    n = len(files)
    pr_scoped = [w for w in wrows if w["penetration"]["pr_scoped"]]
    totals = {
        "breadth": {"workflows": len(wrows), "with_evidence": sum(bool(w["breadth"]["lanes"]) for w in wrows),
                    "both_lanes": sum(len(w["breadth"]["lanes"]) == 2 for w in wrows)},
        "depth": {"workflows_with_tests": sum(w["depth"]["tests"] > 0 for w in wrows),
                  "tests_total": sum(w["depth"]["tests"] for w in wrows),
                  "unique_test_files": len(uniq), "unique_tests": sum(uniq.values()),
                  "enforced_tests": sum(w["depth"]["tests"] for w in wrows if w["disposition"] == g.ENFORCED),
                  "unresolved_invocations": sum(w["depth"]["unresolved_invocations"] for w in wrows)},
        "penetration": {"tracked_files": n,
                        "pr_gated_files": sum(v[0] > 0 for v in per_file.values()),
                        "enforced_gated_files": sum(v[1] > 0 for v in per_file.values()),
                        "zero_gated_files": sum(v[0] == 0 for v in per_file.values()),
                        "targeted_files": sum(v[2] > 0 for v in per_file.values()),
                        "targeted_enforced_files": sum(v[3] > 0 for v in per_file.values()),
                        "zero_targeted_files": sum(v[2] == 0 for v in per_file.values()),
                        "code_files": sum(f.endswith(SRC_EXT + (".tsx", ".sh", ".ps1")) for f in per_file),
                        "zero_targeted_code": sum(v[2] == 0 for f, v in per_file.items()
                                                  if f.endswith(SRC_EXT + (".tsx", ".sh", ".ps1"))),
                        "pr_scoped_workflows": len(pr_scoped),
                        "dead_filters": sum("ZERO_PENETRATION" in w["zero"] for w in wrows)},
        "tested": {"modules": len(tested), "tested": sum(v == "TESTED" for v in tested.values()),
                   "harness": sum(v == "HARNESS" for v in tested.values()),
                   "zero_tested": sum(v == "ZERO_TESTED" for v in tested.values())},
        "zero": dict(sorted(zero_counts.items()))}
    p = totals["penetration"]
    p["pr_gated_pct"] = round(100 * p["pr_gated_files"] / n, 1) if n else None
    p["enforced_gated_pct"] = round(100 * p["enforced_gated_files"] / n, 1) if n else None
    p["targeted_pct"] = round(100 * p["targeted_files"] / n, 1) if n else None
    p["targeted_enforced_pct"] = round(100 * p["targeted_enforced_files"] / n, 1) if n else None
    tt = totals["tested"]
    tt["tested_pct"] = round(100 * tt["tested"] / tt["modules"], 1) if tt["modules"] else None
    tt["tested_or_harness_pct"] = (round(100 * (tt["tested"] + tt["harness"]) / tt["modules"], 1)
                                   if tt["modules"] else None)
    doc = {"schema": SCHEMA, "ledger_sha256": ledger.get("ledger_sha256"),
           "audit_summary": audit["summary"], "totals": totals,
           "areas": dict(sorted(areas.items(), key=lambda kv: (-kv[1]["files"], kv[0]))),
           "workflows": wrows,
           "zero_tested_modules": sorted(f for f, v in tested.items() if v == "ZERO_TESTED"),
           "harness_modules": sorted(f for f, v in tested.items() if v == "HARNESS"),
           "zero_targeted_files": sorted(f for f, v in per_file.items() if v[2] == 0),
           "zero_targeted_code": sorted(f for f, v in per_file.items()
                                        if v[2] == 0 and f.endswith(SRC_EXT + (".tsx", ".sh", ".ps1"))),
           "method": {"tested": "a test file imports the module or is named after it (static; not line coverage)",
                      "penetration": "gate.applies() on each tracked file with the workflow's own pull_request trigger",
                      "depth": "unittest via zero_test_gate_audit; pytest/node by static count; unresolved = UNKNOWN"},
           "authority": {"merge_authorized": False, "actor": "AGENT"}}
    doc["digest_sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    return doc


def markdown(doc: dict, top=12) -> str:
    t = doc["totals"]
    b, d, p, s = t["breadth"], t["depth"], t["penetration"], t["tested"]
    lines = ["### GOGREEN depth census: breadth · depth · penetration · coverage · ZERO",
             "", "| Dimension | Measured | ZERO bucket |", "|---|---|---|",
             f"| Breadth | {b['with_evidence']}/{b['workflows']} workflows with red/green evidence ({b['both_lanes']} on both lanes) | "
             f"ZERO_EVIDENCE {t['zero'].get('ZERO_EVIDENCE', 0)} |",
             f"| Depth | {d['unique_tests']} unique tests in {d['unique_test_files']} files; {d['tests_total']} test executions per full "
             f"CI pass across {d['workflows_with_tests']} workflows ({d['enforced_tests']} behind ENFORCED gates) | "
             f"ZERO_TESTS {t['zero'].get('ZERO_TESTS', 0)} · UNKNOWN_TESTS {t['zero'].get('UNKNOWN_TESTS', 0)} |",
             f"| Penetration (targeted) | {p['targeted_files']}/{p['tracked_files']} files ({p['targeted_pct']}%) fire ≥1 path-filtered "
             f"PR gate; {p['targeted_enforced_files']} ({p['targeted_enforced_pct']}%) an ENFORCED one. Catch-all gates reach "
             f"{p['pr_gated_pct']}% | ZERO_TARGETED files {p['zero_targeted_files']} (code: {p['zero_targeted_code']}/"
             f"{p['code_files']}) · ZERO_GATED {p['zero_gated_files']} · "
             f"dead filters {p['dead_filters']} |",
             f"| Tested | {s['tested']}/{s['modules']} source modules ({s['tested_pct']}%) referenced by a test; "
             f"+{s['harness']} are QA/validator harnesses ({s['tested_or_harness_pct']}% together) | "
             f"ZERO_TESTED {s['zero_tested']} |", "",
             "| Area | Files | Targeted % | Targeted-enforced % | Zero-targeted | Modules tested % | Zero-tested |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name, a in list(doc["areas"].items())[:top]:
        lines.append(f"| {name} | {a['files']} | {a['targeted_pct']} | {a['targeted_enforced_pct']} | {a['zero_targeted']} | "
                     f"{a['modules_tested_pct'] if a['modules_tested_pct'] is not None else '—'} | {a['zero_tested_modules']} |")
    dead = [w for w in doc["workflows"] if "ZERO_PENETRATION" in w["zero"]]
    if dead:
        lines += ["", "**Dead path filters** (no tracked file can fire them on a PR): " +
                  ", ".join(w["path"].split("/")[-1] for w in dead[:20])]
    lines += ["", "_Static census: nothing executed. Tested = referenced by a test file, not line coverage; "
              "UNKNOWN is never counted as zero._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--ledger", help="ADMISSION.json path; 'none' = derive dispositions from workflow files only "
                                     "(any repo: no evidence, nothing enforced)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.ledger == "none":
        import admission  # noqa: E402  (same scope rules the hub ledger uses)
        ledger = admission.build(a.root, None, None, {"entries": []}, {})
    else:
        ledger = json.loads(Path(a.ledger or a.root / g.ADMISSION).read_text(encoding="utf-8"))
    doc = build(a.root, ledger, load_audit(a.root.resolve()))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "depth.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (a.out / "depth.md").write_text(markdown(doc), encoding="utf-8", newline="\n")
    print(json.dumps(doc["totals"], sort_keys=True))
    return doc


if __name__ == "__main__":
    main()
