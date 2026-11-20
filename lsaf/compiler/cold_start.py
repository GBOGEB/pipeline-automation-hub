"""Repository-only cold-start reconstruction for LSAF.

This module is deterministic and side-effect free. It proves that repository
artifacts contain enough information to reconstruct the operational view, but it
does not self-certify independence. Independent qualification must be performed by
a separate session/reviewer with no reliance on prior chat context.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lsaf.compiler.dag import compile_dag


def _yaml():
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML is required (Hub pin: pyyaml>=6.0.3)") from exc
    return yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = _yaml().safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def reconstruct(
    *,
    cohort: dict[str, Any],
    graph: dict[str, Any],
    predictions: dict[str, Any],
) -> dict[str, Any]:
    sessions = cohort.get("sessions") or []
    epics = sorted({
        str(epic)
        for session in sessions if isinstance(session, dict)
        for epic in (session.get("epics") or [])
    })
    repos = sorted({
        str(repo)
        for session in sessions if isinstance(session, dict)
        for repo in (session.get("repos") or [])
    })
    next_predicates = sorted({
        str(item)
        for session in sessions if isinstance(session, dict)
        for item in (session.get("next") or [])
    })
    prediction_ids = sorted(
        str(p.get("prediction_id"))
        for p in (predictions.get("predictions") or [])
        if isinstance(p, dict) and p.get("prediction_id")
    )
    dag = compile_dag(graph.get("nodes") or [])
    return {
        "schema": "lsaf/cold-start-reconstruction/v0.1",
        "independent_qualification": False,
        "active_epics": epics,
        "repositories": repos,
        "ready": dag["ready"],
        "blocked": dag["blocked"],
        "cycles": dag["cycle"],
        "next_predicates": next_predicates,
        "prediction_ids": prediction_ids,
    }


def reconstruct_from_files(
    *,
    cohort_path: Path,
    graph_path: Path,
    predictions_path: Path,
) -> dict[str, Any]:
    return reconstruct(
        cohort=load_yaml(cohort_path),
        graph=load_yaml(graph_path),
        predictions=load_yaml(predictions_path),
    )
