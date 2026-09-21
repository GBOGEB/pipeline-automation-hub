#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "mission-control/historian/FLEET_OPEN_ISSUE_CONVERGENCE_CURRENT_v1.json"
W260 = ROOT / "mission-control/qps-triage-ultra/missions/LM-10_W260_BD_CONVERGENCE_CURRENT_v1.yaml"
LM10 = ROOT / "mission-control/qps-triage-ultra/missions/LM-10_MISSION_CONTROL_v3.yaml"


def _section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index(heading) + 1
    except ValueError as exc:
        raise AssertionError(f"missing YAML section: {heading}") from exc
    out: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        out.append(line)
    return "\n".join(out)


def _scalar(section: str, key: str) -> str:
    prefix = f"  {key}:"
    for line in section.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise AssertionError(f"missing YAML scalar: {key}")


def _top_scalar(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise AssertionError(f"missing top-level YAML scalar: {key}")


def _bd_states(text: str) -> dict[str, str]:
    section = _section(text, "bd_queue:")
    states: dict[str, str] = {}
    current: str | None = None
    for line in section.splitlines():
        if line.startswith("  BD-") and line.endswith(":"):
            current = line.strip()[:-1]
            assert current not in states, ("duplicate BD entry", current)
            continue
        if current is not None and line.startswith("    state:"):
            states[current] = line.split(":", 1)[1].strip()
            current = None
    return states


def _classify_bd_states(states: dict[str, str]) -> dict[str, int]:
    counts = {"control": 0, "active": 0, "blocked": 0, "dormant": 0}
    for bd, state in states.items():
        if state == "DONE_CONTROL_WATCH":
            counts["control"] += 1
        elif state == "ACTIVE_PROVE":
            counts["active"] += 1
        elif "BLOCKED" in state:
            counts["blocked"] += 1
        elif state == "NOT_REQUIRED_THIS_CYCLE_REENTER_ON_REAL_CONSUMER_NEED":
            counts["dormant"] += 1
        else:
            raise AssertionError(("unclassified W260 BD state", bd, state))
    return counts


def _assert_w260_projection(w260_text: str, nested: dict[str, object]) -> None:
    w260_metrics = _section(w260_text, "observed_queue_metrics:")
    w260_states = _bd_states(w260_text)
    w260_counts = _classify_bd_states(w260_states)

    assert len(w260_states) == 6, ("canonical W260 BD population", w260_states)
    assert set(w260_states) == {f"BD-260.{n}" for n in range(1, 7)}
    assert nested["bd_total"] == len(w260_states)
    assert nested["control_count"] == w260_counts["control"]
    assert nested["active_downstream_count"] == w260_counts["active"]
    assert nested["blocked_count"] == w260_counts["blocked"]
    assert nested["dormant_reentry_count"] == w260_counts["dormant"]

    assert int(_scalar(w260_metrics, "total_bd_items")) == len(w260_states)
    assert int(_scalar(w260_metrics, "done_control_watch")) == w260_counts["control"]
    assert int(_scalar(w260_metrics, "active_prove")) == w260_counts["active"]
    assert int(_scalar(w260_metrics, "dependency_blocked")) == w260_counts["blocked"]
    assert int(_scalar(w260_metrics, "dormant_reentry")) == w260_counts["dormant"]
    assert int(_scalar(w260_metrics, "executable_frontier_width")) == w260_counts["active"]

    assert nested["active_downstream_owner"] is None
    assert w260_states["BD-260.5"] == "DONE_CONTROL_WATCH"
    assert (
        w260_states["BD-260.6"]
        == "NOT_REQUIRED_THIS_CYCLE_REENTER_ON_REAL_CONSUMER_NEED"
    )


def _self_test() -> None:
    d = json.loads(P.read_text(encoding="utf-8"))
    nested = d["repositories"]["GBOGEB/gg_MATH"]["nested_queue"]
    w260_text = W260.read_text(encoding="utf-8")
    _assert_w260_projection(w260_text, nested)

    mutated = w260_text.replace(
        "  BD-260.1:\n    state: DONE_CONTROL_WATCH",
        "  BD-260.1:\n    state: ACTIVE_PROVE",
        1,
    )
    assert mutated != w260_text
    try:
        _assert_w260_projection(mutated, nested)
    except AssertionError:
        print("PASS_FLEET_W260_CANONICAL_BD_MUTATION")
        return
    raise AssertionError("mutation escaped canonical W260 projection validation")


def main():
    d = json.loads(P.read_text(encoding="utf-8"))
    w260_text = W260.read_text(encoding="utf-8")
    lm10_text = LM10.read_text(encoding="utf-8")
    lm10_frontier = _section(lm10_text, "current_development_frontier:")

    assert d["schema"] == "missioncontrol.fleet_open_issue_convergence.v1"
    assert d["authority_transfer"] is False
    assert d["formal_credit_delta"] == 0
    repos = d["repositories"]
    assert len(repos) == 7

    total = control = active = blocked = 0
    seen_global = set()
    for repo, row in repos.items():
        c = set(row["control"])
        a = set(row["active"])
        b = set(row["blocked"])
        assert not (c & a or c & b or a & b), (repo, "overlap")
        assert len(c) + len(a) + len(b) == row["open_issues"], (
            repo,
            len(c),
            len(a),
            len(b),
            row["open_issues"],
        )
        total += row["open_issues"]
        control += len(c)
        active += len(a)
        blocked += len(b)
        for n in c | a | b:
            key = (repo, n)
            assert key not in seen_global
            seen_global.add(key)
        assert len(a) <= 1, (repo, "active WIP cap")

    f = d["fleet"]
    assert (total, control, active, blocked) == (93, 30, 1, 62)
    assert (f["open_issues"], f["control"], f["active"], f["blocked"]) == (93, 30, 1, 62)
    assert f["executable_frontier_width"] == 1
    assert abs(f["control_share"] - 30 / 93) < 1e-10
    assert abs(f["active_share"] - 1 / 93) < 1e-10
    assert abs(f["blocked_share"] - 62 / 93) < 1e-10
    assert sum(len(row["active"]) for row in repos.values()) == 1

    assert repos["GBOGEB/cryoplant-project"]["open_issues"] == 54
    assert (
        len(
            repos["GBOGEB/cryoplant-project"]["blocked_breakdown"][
                "external_source_decision_return"
            ]
        )
        == 32
    )

    nested = repos["GBOGEB/gg_MATH"]["nested_queue"]
    _assert_w260_projection(w260_text, nested)

    assert _top_scalar(lm10_text, "state") == "W260_CONTROLLED_COMPLETE_REENTRY_GOVERNED"
    assert _scalar(lm10_frontier, "state") == "CONTROL_WATCH_ONLY"
    assert _scalar(lm10_frontier, "provider_WIP_cap") == "0"
    assert (
        _scalar(lm10_frontier, "bd260_6")
        == "NOT_REQUIRED_THIS_CYCLE_REENTER_ON_REAL_CONSUMER_NEED"
    )

    assert repos["GBOGEB/ABACUS"]["active"] == [776]
    assert d["proof_integrity"]["prior_result"] == "FAIL"
    assert d["proof_integrity"]["new_bd_root"] is False
    assert 129 in repos["GBOGEB/pipeline-automation-hub"]["control"]
    assert len(d["active_frontiers"]) == 1
    frontier = d["active_frontiers"][0]
    assert frontier["repo"] == "GBOGEB/ABACUS"
    assert frontier["issue"] == 776
    assert frontier["kind"] == "PROVE"

    print("PASS_FLEET_OPEN_ISSUE_CONVERGENCE_93_30_1_62")


if __name__ == "__main__":
    import sys

    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
