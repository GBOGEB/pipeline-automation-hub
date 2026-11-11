#!/usr/bin/env python3
"""ISO week-year schedule projection for the existing JADE/Kahn lifecycle.

Pure, plan-only adapter. It does not dispatch tasks, approve milestones, or
override owner-held gates. The canonical DAG algorithm stays in devops/lifecycle.py.
"""
from __future__ import annotations

from datetime import date
from html import escape
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SCHEMA = "jade.iso-schedule.v1"
CANONICALIZATION = "JADE_CANONICAL_UTF8_JSON_V1"
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
WCODE = re.compile(r"^w([0-5][0-9])(MON|TUE|WED|THU|FRI|SAT|SUN)$")
HERE = Path(__file__).resolve().parent


def from_w_code(iso_year: int, code: str) -> date:
    """Interpret a w##DDD label *only* with its mandatory ISO week-year."""
    if type(iso_year) is not int or not (1 <= iso_year <= 9999):
        raise ValueError("iso_year must be an integer in 1..9999")
    if not isinstance(code, str):
        raise ValueError("week code must be text")
    match = WCODE.fullmatch(code)
    if not match:
        raise ValueError(f"invalid week code: {code!r}")
    week = int(match.group(1))
    try:
        return date.fromisocalendar(iso_year, week, DAYS.index(match.group(2)) + 1)
    except ValueError as exc:
        raise ValueError(f"{iso_year} has no {code!r}") from exc


def week_address(day: date) -> dict:
    """Carry the ISO week-year explicitly across Gregorian-year boundaries."""
    year, week, weekday = day.isocalendar()
    return {"iso_year": year, "code": f"w{week:02d}{DAYS[weekday - 1]}",
            "date": day.isoformat()}


def planning_quarter(iso_year: int, week: int) -> str:
    """13-week planning buckets, NOT Gregorian calendar quarters."""
    from_w_code(iso_year, f"w{week:02d}MON")
    return f"{iso_year}-PQ{min(4, (week - 1) // 13 + 1)}"


def _owner_layers(nodes: list[str], prerequisites: dict[str, list[str]]) -> list[list[str]]:
    spec = importlib.util.spec_from_file_location(
        "jade_schedule_lifecycle_owner", HERE.parent / "devops" / "lifecycle.py")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    return owner.topo_layers(nodes, [(pre, task, "FEEDFORWARD")
                                     for task, parents in prerequisites.items() for pre in parents])


def validate_schedule(plan: dict) -> dict:
    """Reject missing inputs, cycles and impossible finish-to-start dates.

    Tasks carry a named ISO week-year and w##DDD start/end. Milestones have
    start == end; a successor must start strictly after predecessor end.
    No completion, holiday, staffing, or calendar-quarter claim is inferred.
    """
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    year = plan.get("iso_year")
    if type(year) is not int:
        raise ValueError("iso_year is required")
    rows = plan.get("tasks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("tasks must be a non-empty list")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each task must be an object")
        task_id, title = row.get("id"), row.get("title")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", task_id):
            raise ValueError("invalid task id")
        if task_id in indexed:
            raise ValueError(f"duplicate task id: {task_id}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{task_id}: missing title")
        start = from_w_code(year, row.get("start"))
        end = from_w_code(year, row.get("end"))
        if end < start:
            raise ValueError(f"{task_id}: end before start")
        kind = row.get("kind", "task")
        if kind not in ("task", "milestone"):
            raise ValueError(f"{task_id}: unknown kind")
        if kind == "milestone" and start != end:
            raise ValueError(f"{task_id}: milestone must be one day")
        parents = row.get("depends_on", [])
        if not isinstance(parents, list) or any(not isinstance(p, str) for p in parents):
            raise ValueError(f"{task_id}: depends_on must be a list of IDs")
        if len(parents) != len(set(parents)):
            raise ValueError(f"{task_id}: duplicate predecessor")
        indexed[task_id] = {"id": task_id, "title": title.strip(), "start": start, "end": end,
                            "start_code": row["start"], "end_code": row["end"],
                            "kind": kind, "depends_on": parents}
    # Reuse the canonical Kahn owner: missing nodes and cycles fail closed.
    layers = _owner_layers(list(indexed), {k: v["depends_on"] for k, v in indexed.items()})
    for node in indexed.values():
        for parent in node["depends_on"]:
            if indexed[parent]["end"] >= node["start"]:
                raise ValueError(f"{node['id']}: finish-to-start violation after {parent}")
    return {"schema": SCHEMA, "iso_year": year, "tasks": indexed, "waves": layers,
            "status": "DECLARED_PLAN_ONLY", "authority_transfer": False}


def canonical_receipt_bytes(record: dict) -> bytes:
    """Canonical UTF-8 JSON v1; fixed ASCII object keys; Unicode scalar string values.

    Exact wire contract: no digest field, sorted ASCII keys recursively, no spaces,
    compact JSON escaping, raw UTF-8 Unicode values, no BOM or newline. Arrays
    retain order; numbers are integers. Integrity never implies source authority.
    """
    if type(record) is not dict or "receipt_sha256" in record:
        raise ValueError("canonical receipt payload must exclude receipt_sha256")

    def visit(value):
        if type(value) is dict:
            for key, child in value.items():
                if type(key) is not str or not key.isascii():
                    raise ValueError("all receipt object keys must be ASCII")
                visit(child)
        elif type(value) is list:
            for child in value:
                visit(child)
        elif type(value) not in (str, int, bool, type(None)):
            raise ValueError("unsupported receipt value type")

    visit(record)
    try:
        return json.dumps(record, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("receipt strings must be Unicode scalar sequences") from exc


def portable_receipt(plan: dict) -> dict:
    """Return a versioned UTF-8 JSON integrity-bound *declared* plan for handover.

    This makes the date-rich internal validated model transportable without
    copying its Kahn implementation into GEMINI. The digest proves payload
    consistency only, not Git source authenticity, a Drive revision or approval.
    """
    validated = validate_schedule(plan)
    tasks = {}
    for key, task in validated["tasks"].items():
        tasks[key] = {
            "id": task["id"], "title": task["title"],
            "start": task["start"].isoformat(), "end": task["end"].isoformat(),
            "start_code": task["start_code"], "end_code": task["end_code"],
            "kind": task["kind"], "depends_on": list(task["depends_on"]),
        }
    record = {
        "schema": SCHEMA, "iso_year": validated["iso_year"],
        "generation_method": "JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1",
        "canonicalization": CANONICALIZATION,
        "tasks": tasks, "waves": validated["waves"],
        "status": "DECLARED_PLAN_ONLY", "authority_transfer": False,
    }
    payload = canonical_receipt_bytes(record)
    record["receipt_sha256"] = hashlib.sha256(payload).hexdigest()
    return record


def mermaid_dag(validated: dict) -> str:
    """Read-only dependency view; generated node IDs prevent Mermaid injection."""
    tasks = list(validated["tasks"].values())
    node_ids = {t["id"]: f"N{i}" for i, t in enumerate(tasks)}
    lines = ["flowchart LR"]
    for task in tasks:
        label = escape(" ".join(f"{task['start_code']} {task['id']}: {task['title']}".split()), quote=True)
        lines.append(f'    {node_ids[task["id"]]}["{label}"]')
    for task in tasks:
        for p in task["depends_on"]:
            lines.append(f'    {node_ids[p]} --> {node_ids[task["id"]]}')
    return "\n".join(lines) + "\n"


def mermaid_gantt(validated: dict) -> str:
    """Date-anchored Gantt view; inclusive plan ends become exclusive Mermaid ends."""
    lines = ["gantt", f"    title ISO {validated['iso_year']} (plan only)",
             "    dateFormat YYYY-MM-DD", "    axisFormat %d %b"]
    for i, task in enumerate(validated["tasks"].values()):
        title = " ".join(re.sub(r"[:\n\r]", " ", task["title"]).split())
        label = f"{task['start_code']} {title}"
        style = "milestone, " if task["kind"] == "milestone" else ""
        endpoint = "0d" if task["kind"] == "milestone" else f"{(task['end'] - task['start']).days + 1}d"
        lines.append(f'    {label} :{style}t{i}, {task["start"].isoformat()}, {endpoint}')
    return "\n".join(lines) + "\n"
