"""Deterministic, non-authoritative human projections from LSAF state."""
from __future__ import annotations

from typing import Any


def _items(values: Any) -> list[str]:
    return sorted(str(x) for x in (values or []))


def render_dag_mermaid(dag: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    for node in _items(dag.get("nodes")):
        lines.append(f'  {node}["{node}"]')
    for edge in sorted(dag.get("edges") or [], key=lambda e: (str(e["from"]), str(e["to"]))):
        lines.append(f"  {edge['from']} --> {edge['to']}")
    return "\n".join(lines) + "\n"


def render_handover(manifest: dict[str, Any], dag: dict[str, Any]) -> str:
    handover = manifest.get("handover") or {}
    lines = [
        "# Generated LSAF Handover",
        "",
        "> DERIVED projection. The machine manifest/event evidence remains authoritative.",
        "",
        f"- Repository: {handover.get('repository', 'UNKNOWN')}",
        f"- Parent issue: {handover.get('parent_issue', 'UNKNOWN')}",
        f"- Pull request: {handover.get('pull_request', 'UNKNOWN')}",
        f"- Branch: {handover.get('branch', 'UNKNOWN')}",
        f"- Authority transfer: {str(handover.get('authority_transfer', False)).lower()}",
        "",
        "## READY",
    ]
    ready = _items(dag.get("ready"))
    lines.extend(f"- {x}" for x in ready) if ready else lines.append("- none")
    lines += ["", "## BLOCKED"]
    blocked = _items(dag.get("blocked"))
    lines.extend(f"- {x}" for x in blocked) if blocked else lines.append("- none")
    lines += ["", "## CYCLES"]
    cycle = _items(dag.get("cycle"))
    lines.extend(f"- {x}" for x in cycle) if cycle else lines.append("- none")
    return "\n".join(lines) + "\n"


def render_dropin(manifest: dict[str, Any], dag: dict[str, Any]) -> str:
    handover = manifest.get("handover") or {}
    ready = ", ".join(_items(dag.get("ready"))) or "none"
    blocked = ", ".join(_items(dag.get("blocked"))) or "none"
    return (
        "Continue the existing LSAF pilot.\n\n"
        f"Repository: {handover.get('repository', 'UNKNOWN')}\n"
        f"PR: {handover.get('pull_request', 'UNKNOWN')}\n"
        f"Branch: {handover.get('branch', 'UNKNOWN')}\n"
        f"READY: {ready}\n"
        f"BLOCKED: {blocked}\n\n"
        "Preserve authority_transfer=false. Treat this text as a DERIVED view; "
        "re-read machine manifests and exact-head evidence before writing.\n"
    )


def render_bd_queue(dag: dict[str, Any]) -> str:
    lines = ["# Generated LSAF BD Queue", "", "## READY"]
    ready = _items(dag.get("ready"))
    lines.extend(f"- [ ] {x}" for x in ready) if ready else lines.append("- none")
    lines += ["", "## BLOCKED"]
    blocked = _items(dag.get("blocked"))
    lines.extend(f"- [ ] {x}" for x in blocked) if blocked else lines.append("- none")
    return "\n".join(lines) + "\n"


def render_sipoc() -> str:
    return (
        "flowchart LR\n"
        '  S["Suppliers: sessions / repos / GitHub / worktrees"] --> I["Inputs: events / evidence / decisions"]\n'
        '  I --> P["Process: capture / fingerprint / bind / DAG / validate"]\n'
        '  P --> O["Outputs: manifest / ready queue / receipts / forecasts"]\n'
        '  O --> C["Consumers: next session / workers / repo owners"]\n'
    )


def project_all(manifest: dict[str, Any], dag: dict[str, Any]) -> dict[str, str]:
    return {
        "handover.md": render_handover(manifest, dag),
        "dropin.md": render_dropin(manifest, dag),
        "bd_queue.md": render_bd_queue(dag),
        "dag.mmd": render_dag_mermaid(dag),
        "sipoc.mmd": render_sipoc(),
    }
