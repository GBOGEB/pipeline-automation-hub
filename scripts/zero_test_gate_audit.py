#!/usr/bin/env python3
"""Static audit: every `python -m unittest` CI gate must collect at least one test.

Why: on Python <= 3.11, `python -m unittest <file>` exits 0 when it collects zero
tests (bare pytest-style functions are invisible to unittest). A workflow can then
report green with no executed tests (ZERO_STEP_NE_APPLICATION_FAIL).

The audit parses every workflow under .github/workflows, resolves each unittest
invocation against the step's working directory, and counts unittest-collectable
test methods by AST (no test code is executed).

Exit codes (REX contract): 0 PASS, 1 FAIL (a zero-test gate exists),
2 INCOMPLETE (with --strict, an invocation could not be resolved statically).
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import shlex
import sys
from pathlib import Path

import yaml

UNITTEST_RX = re.compile(r"\bpython(?:3(?:\.\d+)?)?\s+-m\s+unittest\b([^\n]*)")
FLAGS_WITH_ARG = {"-k", "-s", "-p", "-t", "--start-directory", "--pattern", "--top-level-directory"}
SHELL_STOP = {"|", "||", "&&", ";", ">", ">>", "2>&1", "&"}


def _testcase_classes(tree: ast.Module) -> list[ast.ClassDef]:
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    is_tc: dict[str, bool] = {}

    def base_names(cls: ast.ClassDef) -> list[str]:
        out = []
        for b in cls.bases:
            if isinstance(b, ast.Name):
                out.append(b.id)
            elif isinstance(b, ast.Attribute):
                out.append(b.attr)
        return out

    changed = True
    while changed:
        changed = False
        for name, cls in classes.items():
            if is_tc.get(name):
                continue
            if any(b.endswith("TestCase") or is_tc.get(b) for b in base_names(cls)):
                is_tc[name] = True
                changed = True
    return [classes[n] for n, ok in is_tc.items() if ok]


def count_unittest_tests(path: Path) -> tuple[int | None, str]:
    """Return (count, note). count None means not statically countable."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return None, f"unparseable: {exc.__class__.__name__}"
    if any(isinstance(n, ast.FunctionDef) and n.name == "load_tests" for n in tree.body):
        return None, "load_tests hook is dynamic"
    total = 0
    for cls in _testcase_classes(tree):
        total += sum(
            1
            for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")
        )
    bare = sum(1 for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test"))
    note = f"{bare} bare test functions invisible to unittest" if total == 0 and bare else ""
    return total, note


def _discover(start: Path, pattern: str) -> list[Path]:
    found: list[Path] = []
    if not start.is_dir():
        return found
    for p in sorted(start.iterdir()):
        if p.is_file() and fnmatch.fnmatch(p.name, pattern) and p.suffix == ".py":
            found.append(p)
        elif p.is_dir() and (p / "__init__.py").exists():
            found.extend(_discover(p, pattern))
    return found


def _resolve_dotted(wd: Path, target: str) -> Path | None:
    parts = target.split(".")
    for n in range(len(parts), 0, -1):
        cand = wd.joinpath(*parts[:n]).with_suffix(".py")
        if cand.is_file():
            return cand
    return None


def _tokens(arg_text: str) -> list[str] | None:
    try:
        toks = shlex.split(arg_text, comments=True)
    except ValueError:
        return None
    out = []
    for t in toks:
        if t in SHELL_STOP or t.startswith(("|", ">", "2>")):
            break
        out.append(t)
    return out


def resolve_invocation(repo: Path, wd_rel: str, arg_text: str) -> dict:
    wd = (repo / wd_rel).resolve()
    rec: dict = {"working_directory": wd_rel, "args": arg_text.strip()}
    if "$" in arg_text:
        return {**rec, "state": "UNRESOLVED", "reason": "shell or expression variable in arguments"}
    toks = _tokens(arg_text)
    if toks is None:
        return {**rec, "state": "UNRESOLVED", "reason": "unparseable arguments"}
    files: list[Path] = []
    if toks and toks[0] == "discover":
        start, pattern, pos = ".", "test*.py", []
        it = iter(toks[1:])
        for t in it:
            if t in ("-s", "--start-directory"):
                start = next(it, start)
            elif t in ("-p", "--pattern"):
                pattern = next(it, pattern)
            elif t in ("-t", "--top-level-directory", "-k"):
                next(it, None)
            elif not t.startswith("-"):
                pos.append(t)
        if pos:
            start = pos[0]
        if len(pos) > 1:
            pattern = pos[1]
        files = _discover(wd / start, pattern)
    else:
        positional, it = [], iter(toks)
        for t in it:
            if t in FLAGS_WITH_ARG:
                next(it, None)
            elif not t.startswith("-"):
                positional.append(t)
        if not positional:
            files = _discover(wd, "test*.py")
        for t in positional:
            p = (wd / t) if t.endswith(".py") else _resolve_dotted(wd, t)
            if p is None or not p.is_file():
                return {**rec, "state": "UNRESOLVED", "reason": f"target not found: {t}"}
            files.append(p)
    counts, unknown = [], []
    for f in files:
        n, note = count_unittest_tests(f)
        rel = f.relative_to(repo).as_posix() if f.is_relative_to(repo) else str(f)
        if n is None:
            unknown.append({"file": rel, "reason": note})
        else:
            counts.append({"file": rel, "tests": n, "note": note})
    total = sum(c["tests"] for c in counts)
    if unknown and total == 0:
        return {**rec, "state": "UNRESOLVED", "reason": "dynamic collection", "files": counts + unknown}
    state = "ZERO_TESTS" if total == 0 else "OK"
    return {**rec, "state": state, "tests_collectable": total, "files": counts}


def _join_continuations(script: str) -> str:
    return re.sub(r"\\\s*\n\s*", " ", script)


def audit(repo: Path) -> dict:
    rows = []
    for wf in sorted((repo / ".github" / "workflows").glob("*.y*ml")):
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            rows.append({"workflow": wf.name, "state": "UNRESOLVED", "reason": "invalid YAML"})
            continue
        wf_wd = ((doc.get("defaults") or {}).get("run") or {}).get("working-directory", ".")
        for job_id, job in (doc.get("jobs") or {}).items():
            job_wd = ((job.get("defaults") or {}).get("run") or {}).get("working-directory", wf_wd)
            for idx, step in enumerate(job.get("steps") or []):
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                wd = step.get("working-directory", job_wd)
                for m in UNITTEST_RX.finditer(_join_continuations(run)):
                    rec = resolve_invocation(repo, str(wd), m.group(1))
                    rows.append({"workflow": wf.name, "job": job_id, "step": idx, **rec})
    summary = {
        "unittest_gates_total": len(rows),
        "zero_test_gates": sum(r["state"] == "ZERO_TESTS" for r in rows),
        "unresolved_gates": sum(r["state"] == "UNRESOLVED" for r in rows),
        "ok_gates": sum(r["state"] == "OK" for r in rows),
    }
    return {"schema": "missioncontrol.zero_test_gate_audit.v1", "summary": summary, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--out")
    ap.add_argument("--strict", action="store_true", help="unresolved invocations exit 2")
    args = ap.parse_args(argv)
    result = audit(Path(args.repo).resolve())
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    s = result["summary"]
    for r in result["rows"]:
        if r["state"] != "OK":
            print(f"{r['state']}: {r['workflow']} :: python -m unittest {r.get('args', '')} "
                  f"({r.get('reason') or 'collects 0 unittest tests'})")
    print(f"ZERO_TEST_GATE_AUDIT gates={s['unittest_gates_total']} ok={s['ok_gates']} "
          f"zero={s['zero_test_gates']} unresolved={s['unresolved_gates']}")
    if s["zero_test_gates"]:
        return 1
    if args.strict and s["unresolved_gates"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
