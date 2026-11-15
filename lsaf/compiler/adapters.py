"""Adapters from canonical Hub producers into LSAF records.

The session census is owned by tools/threads/session_census.py (#1211).
This module consumes its JSON output; it never rescans transcripts itself.
"""
from __future__ import annotations

import re
from typing import Any

UNKNOWN = "UNKNOWN"
_PR = re.compile(r"^(?P<repo>[^#]+)#(?P<number>\d+):(?P<state>[^:]+)$")
_TS = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2})$")


def _iso_or_unknown(value: Any) -> str:
    if not isinstance(value, str):
        return UNKNOWN
    m = _TS.match(value.strip())
    if not m:
        return UNKNOWN
    return f"{m.group('date')}T{m.group('time')}:00Z"


def repository_bindings(record: dict[str, Any]) -> list[str]:
    """Return stable unique repositories observed in census PR bindings."""
    repos: set[str] = set()
    for raw in record.get("prs_app") or []:
        if not isinstance(raw, str):
            continue
        m = _PR.match(raw)
        if m:
            repos.add(m.group("repo"))
    return sorted(repos)


def session_from_census(record: dict[str, Any]) -> dict[str, Any]:
    """Project one canonical census record into an LSAF session genome.

    Missing/ambiguous values remain UNKNOWN or null. In particular, cwd is retained
    only as a physical-worktree *candidate*; the census does not prove it is a git
    worktree.
    """
    sid = str(record.get("id") or UNKNOWN)
    repos = repository_bindings(record)
    cwd = record.get("cwd") if isinstance(record.get("cwd"), str) and record.get("cwd") else None
    return {
        "schema": "lsaf/session/v0.1",
        "session_id": sid,
        "titles": {
            "original": str(record.get("title") or ""),
            "canonical": None,
            "aliases": [],
        },
        "temporal": {
            "observed_at": _iso_or_unknown(record.get("last")),
            "created_at": _iso_or_unknown(record.get("created")),
            "window": None,
            "predecessor": record.get("parent"),
        },
        "pin_rank": None,
        "fragments": [],
        "source": "session_census",
        "source_evidence": {
            "verdict": record.get("verdict", UNKNOWN),
            "flags": sorted(str(x) for x in (record.get("flags") or [])),
            "archived": record.get("archived", UNKNOWN),
            "family": record.get("family"),
            "number": record.get("number"),
        },
        "allocation_observation": {
            "repositories": repos,
            "primary_repo": repos[0] if len(repos) == 1 else None,
            "logical_worktree": f"VSW:{sid}" if sid != UNKNOWN else None,
            "physical_worktree": None,
            "physical_worktree_candidate": cwd,
            "physical_worktree_evidence": UNKNOWN if cwd else None,
        },
        "github_observation": {
            "prs_app": sorted(str(x) for x in (record.get("prs_app") or [])),
            "branches": sorted(str(x) for x in (record.get("branches") or [])),
        },
    }
