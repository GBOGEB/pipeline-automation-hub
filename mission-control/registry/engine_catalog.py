#!/usr/bin/env python3
"""Check and read ENGINE_CATALOG.yaml, the catalogue of QA engines and K-<TYPE>-NN checks by binary type.

  validate         Fail when the catalogue is inconsistent, claims an implementation it cannot show, or holds project data.
  matrix           Print the check matrix as Markdown.
  probe            Report which engines this machine has, with versions. Read-only. Absent is reported, never a failure,
                   unless --require names the engine.

Tiers G0-G5 belong to mission-control/gogreen/BINARY_TESTFLIGHT.md. Read-only: runs no document and grants no authority.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CATALOG = HERE / "ENGINE_CATALOG.yaml"
TIERS = {f"G{i}" for i in range(6)}
PILLARS = {"identity", "safety", "provenance", "structure", "schema", "render", "visual", "native", "roundtrip", "recalc", "conformance", "runtime", "accessibility"}
ROLES = {"build", "structure", "render", "runtime", "native", "validate", "safety", "diff", "provenance"}
REQUIRED_CHECK_KEYS = {"id", "pillar", "tier", "severity", "status", "engines", "rule"}
CHECK_KEYS = REQUIRED_CHECK_KEYS | {"evidence"}
# The repository is public: the catalogue may name file types, never individual binaries or their hashes.
LEAKS = (re.compile(r"[\w%+-]\.(?:pptx|pptm|docx|docm|xlsx|xlsm|pdf|html?|svg)\b", re.IGNORECASE), re.compile(r"\b[0-9a-f]{40,64}\b", re.IGNORECASE))


def load(path: Path = CATALOG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(cat: dict, root: Path = ROOT, raw_text: str | None = None) -> list[str]:
    errors: list[str] = []
    types, engines, checks = cat["types"], cat["engines"], cat["checks"]
    for name, eng in engines.items():
        errors += [f"engine {name}: unknown role {r}" for r in eng["roles"] if r not in ROLES]
        errors += [f"engine {name}: unknown type {t}" for t in eng["types"] if t not in types]
        kinds = [k for k in eng["probe"] if k != "args"]
        if len(kinds) != 1 or kinds[0] not in ("python", "command", "com", "none"):
            errors.append(f"engine {name}: probe needs exactly one of python, command, com, none")
    seen: set[str] = set()
    covered: dict[str, set[str]] = {t: set() for t in types}
    for chk in checks:
        cid = chk.get("id", "(no id)")
        if set(chk) - CHECK_KEYS or not REQUIRED_CHECK_KEYS <= set(chk) or not isinstance(chk.get("rule"), str):
            errors.append(f"{cid}: check fields must be {sorted(REQUIRED_CHECK_KEYS)}, plus optional evidence, and rule must be text")
            continue
        if cid in seen:
            errors.append(f"{cid}: duplicate id")
        seen.add(cid)
        m = re.fullmatch(r"K-([A-Z]+)-(\d{2})", cid)
        if not m or m.group(1) not in types:
            errors.append(f"{cid}: id must be K-<TYPE>-NN with a catalogue type")
            continue
        covered[m.group(1)].add(chk["pillar"])
        if chk["pillar"] not in PILLARS:
            errors.append(f"{cid}: unknown pillar {chk['pillar']}")
        if chk["tier"] not in TIERS:
            errors.append(f"{cid}: unknown tier {chk['tier']}")
        if chk["severity"] not in cat["severities"] or chk["status"] not in cat["statuses"]:
            errors.append(f"{cid}: unknown severity or status")
        errors += [f"{cid}: unknown engine {e}" for e in chk["engines"] if e not in engines]
        if chk["status"] == "implemented":
            errors += _evidence_errors(cid, chk.get("evidence"), root)
        elif "evidence" in chk:
            errors.append(f"{cid}: evidence on a check that is not implemented")
    for t, spec in types.items():
        errors += [f"type {t}: no check for required pillar {p}" for p in spec["required_pillars"] if p not in covered[t]]
    text = raw_text if raw_text is not None else CATALOG.read_text(encoding="utf-8")
    for pat in LEAKS:
        errors += [f"public catalogue holds project data: {hit.group(0)}" for hit in pat.finditer(text)]
    return errors


def _evidence_errors(cid: str, ev: dict | None, root: Path) -> list[str]:
    """An implemented claim must name a real symbol and a real test of it."""
    if not ev:
        return [f"{cid}: implemented without evidence"]
    module = root / ev["path"]
    if not module.is_file():
        return [f"{cid}: evidence path missing: {ev['path']}"]
    errors = []
    if not re.search(rf"^\s*(?:def|class)\s+{re.escape(ev['symbol'])}\b", module.read_text(encoding="utf-8"), re.MULTILINE):
        errors.append(f"{cid}: symbol {ev['symbol']} not in {ev['path']}")
    tests = module.parent / "tests" / f"test_{module.stem}.py"
    if not tests.is_file() or not re.search(rf"\bdef\s+{re.escape(ev['test'])}\b", tests.read_text(encoding="utf-8")):
        errors.append(f"{cid}: test {ev['test']} not in {tests.relative_to(root).as_posix()}")
    return errors


def matrix(cat: dict) -> str:
    rows = ["| Check | Pillar | Tier | Severity | Status | Engines | Rule |", "|---|---|---|---|---|---|---|"]
    for c in cat["checks"]:
        rows.append(f"| {c['id']} | {c['pillar']} | {c['tier']} | {c['severity']} | {c['status']} | {', '.join(c['engines']) or 'standard library'} | {c['rule']} |")
    done = sum(c["status"] == "implemented" for c in cat["checks"])
    rows.append(f"\n{done} of {len(cat['checks'])} checks implemented here. A planned check is not a pass.")
    return "\n".join(rows)


def _first_line(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (out.stdout or out.stderr).strip().splitlines()
    return lines[0][:120] if lines else None


def _com_present(prog_id: str) -> bool:
    try:
        import winreg
    except ImportError:
        return False
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id))
    except OSError:
        return False
    return True


def probe_engine(spec: dict) -> dict:
    """One engine: present true/false, or null when it cannot be probed. A version is never guessed."""
    kind, value = next(iter(spec.items()))
    if kind == "python":
        try:
            return {"present": True, "version": importlib.metadata.version(value)}
        except importlib.metadata.PackageNotFoundError:
            return {"present": False, "version": None}
    if kind == "command":
        raise ValueError("command probes need probe_command")
    if kind == "com":
        return {"present": _com_present(value), "version": None}
    return {"present": None, "version": None, "note": value}


def probe_command(names: list[str], args: list[str]) -> dict:
    for name in names:
        found = shutil.which(name)
        if found:
            return {"present": True, "version": _first_line([found, *args])}
    return {"present": False, "version": None}


def probe(cat: dict) -> dict:
    out = {}
    for name, eng in cat["engines"].items():
        p = eng["probe"]
        out[name] = probe_command(p["command"], p.get("args", [])) if "command" in p else probe_engine(p)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("matrix")
    pr = sub.add_parser("probe")
    pr.add_argument("--require", nargs="*", default=[], help="engines that must be present, else exit 1")
    a = ap.parse_args(argv)
    cat = load()
    if a.cmd == "matrix":
        print(matrix(cat))
        return 0
    if a.cmd == "probe":
        res = probe(cat)
        print(json.dumps({"schema": "gbogeb.registry.engine-probe.v1", "engines": res}, indent=1))
        unknown = [e for e in a.require if e not in res]
        absent = [e for e in a.require if e in res and not res[e]["present"]]
        if unknown or absent:
            print(f"required engines absent: {absent}; not in catalogue: {unknown}", file=sys.stderr)
            return 1
        return 0
    errors = validate(cat)
    for e in errors:
        print(f"FAIL {e}")
    if not errors:
        print(f"PASS {len(cat['checks'])} checks, {len(cat['engines'])} engines, {len(cat['types'])} types")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
