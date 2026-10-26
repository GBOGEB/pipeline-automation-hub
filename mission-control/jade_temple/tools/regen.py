"""One entrypoint for the committed JADE outputs that pin their sources.

    python mission-control/jade_temple/tools/regen.py            # --check: report stale steps, exit 1 if any
    python mission-control/jade_temple/tools/regen.py --write    # regenerate in dependency order, then check all
    python mission-control/jade_temple/tools/regen.py --list     # print the chain

The JADE pages and the CI/CD DAG pin blob OIDs and sha256 digests of their inputs (AGENTS.md L7,
data/CICD_DAG_POLICY.json). A change to any pinned input turns JADE QA red until every generator
downstream of it has been re-run, in order. CHAIN below is that order, in one place; the CI step in
.github/workflows/jade-temple-readonly-qa.yml runs the same checks (tests/test_regen.py keeps them in
sync).

Steps marked external cannot be regenerated offline from the repository (they need fetched reports
or a live harvest); --write leaves them alone and --check still verifies them where a check exists.
The launcher reads blob OIDs at a commit, so it is regenerated only when its inputs are committed.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JT = "mission-control/jade_temple"


@dataclass(frozen=True)
class Step:
    id: str
    script: str
    write: tuple[str, ...] | None  # args for regeneration; None = no offline write mode
    check: tuple[str, ...] | None  # args for the drift check; None = no check mode
    after: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    note: str = ""
    needs_commit: bool = field(default=False)


CHAIN: tuple[Step, ...] = (
    Step("pprocess", "mission-control/qps-triage-ultra/p-process/refresh.py", None, None,
         outputs=("mission-control/qps-triage-ultra/p-process/site/**",),
         note="external: live EVERRED harvest; site pinned by p-process tests and by the CI/CD DAG"),
    Step("redtrace", f"{JT}/site/build_redtrace.py", (), ("--check",),
         outputs=(f"{JT}/site/redtrace.html", f"{JT}/site/redtrace-slides.html", f"{JT}/site/redtrace-manifest.json"),
         note="data/RED_TRACE_FEDERATION_N8.json comes from build_redtrace_data.py --reports (external)"),
    Step("rolling5", f"{JT}/tools/rolling5.py", ("--write",), ("--check",),
         outputs=(f"{JT}/site/rolling5.json", f"{JT}/site/rolling5.csv")),
    Step("dashboard", f"{JT}/site/build_dashboard.py", (), ("--check",), outputs=(f"{JT}/site/index.html",)),
    Step("green", f"{JT}/site/build_green.py", (), ("--check",), after=("dashboard",),
         outputs=(f"{JT}/site/green.html", f"{JT}/site/site-manifest.json")),
    Step("burndown", f"{JT}/site/build_burndown.py", (), ("--check",),
         outputs=(f"{JT}/site/burndown.html", f"{JT}/site/burndown-manifest.json")),
    Step("eight_point_contract", f"{JT}/tools/eight_point_contract.py", None, (),
         note="contract run, no outputs"),
    Step("eightpoint", f"{JT}/site/build_eightpoint.py", (), ("--check",), after=("eight_point_contract",),
         outputs=(f"{JT}/site/eightpoint.html", f"{JT}/site/eightpoint-manifest.json")),
    Step("gate12", f"{JT}/tools/build_gate12_dov.py", ("--write",), ("--check",),
         outputs=(f"{JT}/site/gate12_data.json", f"{JT}/site/gate12_bd_queue.csv")),
    Step("cicd_dag", f"{JT}/tools/cicd_dag.py", ("--write",), ("--check",),
         after=("pprocess", "redtrace", "rolling5"),
         outputs=(f"{JT}/site/cicd_dag.json", f"{JT}/site/cicd_dag_crosswalk.csv", f"{JT}/diagrams/CICD_DAG_*.mmd")),
    Step("cicd_dag_page", f"{JT}/site/build_cicd_dag.py", (), ("--check",), after=("cicd_dag",),
         outputs=(f"{JT}/site/cicd_dag.html",)),
    Step("launcher", "mission-control/gogreen/launcher/build_launcher.py", (), ("--check",),
         after=("rolling5", "burndown", "eightpoint", "cicd_dag_page"),
         outputs=("mission-control/gogreen/launcher/launcher.json", "mission-control/gogreen/launcher/index.html"),
         note="reads owner outputs at HEAD: commit the steps above first", needs_commit=True),
)


def by_id() -> dict[str, Step]:
    return {s.id: s for s in CHAIN}


def run(step: Step, args: tuple[str, ...]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, step.script, *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def dirty(paths: tuple[str, ...]) -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8")
    return [line[3:] for line in out.stdout.splitlines()]


def check_all() -> list[tuple[Step, str]]:
    stale = []
    for s in CHAIN:
        if s.check is None:
            continue
        r = run(s, s.check)
        if r.returncode != 0:
            tail = (r.stdout + r.stderr).strip().splitlines()
            stale.append((s, tail[-1] if tail else f"exit {r.returncode}"))
    return stale


def write_all() -> int:
    pending = [o for s in CHAIN if not s.needs_commit for o in s.outputs]
    for s in CHAIN:
        if s.write is None:
            print(f"REGEN_SKIP {s.id}: {s.note}")
            continue
        if s.needs_commit and dirty(pending):
            print(f"REGEN_DEFER {s.id}: {s.note}; uncommitted: {', '.join(dirty(pending)[:3])}")
            continue
        # a fresh step is left alone: some outputs embed the commit (launcher links), so rewriting churns
        if s.check is not None and run(s, s.check).returncode == 0:
            print(f"REGEN_FRESH {s.id}")
            continue
        r = run(s, s.write)
        print(f"REGEN_WROTE {s.id}" if r.returncode == 0 else f"REGEN_FAIL {s.id}: exit {r.returncode}")
        if r.returncode != 0:
            sys.stdout.write(r.stdout[-2000:] + r.stderr[-2000:])
            return 1
    return report(check_all())


def report(stale: list[tuple[Step, str]]) -> int:
    if not stale:
        print("REGEN_OK: every committed JADE output matches its sources")
        return 0
    for s, why in stale:
        print(f"REGEN_STALE {s.id}: {why}")
    first = stale[0][0]
    hint = first.note if first.write is None else "python mission-control/jade_temple/tools/regen.py --write"
    print(f"first stale step: {first.id}; fix: {hint}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify committed outputs (default)")
    mode.add_argument("--write", action="store_true", help="regenerate in dependency order, then verify")
    mode.add_argument("--list", action="store_true", help="print the chain")
    a = ap.parse_args(argv)
    if a.list:
        for i, s in enumerate(CHAIN, 1):
            flags = ("external " if s.write is None else "") + ("needs-commit " if s.needs_commit else "")
            print(f"{i:2d}. {s.id:22s} {s.script}  {flags}{('after ' + ','.join(s.after)) if s.after else ''}")
        return 0
    return write_all() if a.write else report(check_all())


if __name__ == "__main__":
    raise SystemExit(main())
