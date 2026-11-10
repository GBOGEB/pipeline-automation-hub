"""Native, read-only source QA for P0005 Mermaid DAG and SIPOC projections.

Reuse the canonical JADE Kahn topo_layers owner; this is *not* a second scheduler
or a Mermaid/browser renderer. See #1175 for the distinct rendering method.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ASSETS = HERE / "diagrams"
NAMES = (
    "GM_I_C_R2_EXECUTION_LANES_P0005.mmd",
    "GM_I_C_R2_PROMOTION_DEPENDENCIES_P0005.mmd",
    "GM_I_C_R2_SIPOC_P0005.mmd",
)
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*")
LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\s*[\[\{(]")


def _topo_layers():
    path = REPO / "mission-control" / "jade_temple" / "devops" / "lifecycle.py"
    spec = importlib.util.spec_from_file_location("gmic_p0005_jade_kahn_owner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.topo_layers


def _source_graph(path: Path):
    """Extract the explicit P0005 flowchart edge subset, not arbitrary Mermaid syntax."""
    text = path.read_text(encoding="utf-8")
    first = text.splitlines()[0].strip()
    assert first in {"flowchart LR", "flowchart TD"}, f"unexpected graph kind: {first}"
    nodes, edges = set(), []
    for line in text.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith(("%%", "class ", "classDef ", "subgraph ", "end")):
            continue
        segments = [item.strip() for item in line.split("-->")]
        node_ids = []
        for fragment in segments:
            m = IDENTIFIER.match(fragment)
            if not m:
                continue
            node_id = m.group()
            node_ids.append(node_id)
            if LABEL.match(fragment):
                nodes.add(node_id)
        if len(segments) > 1:
            assert len(node_ids) == len(segments), f"edge without node: {line!r}"
            edges.extend(zip(node_ids, node_ids[1:]))
    return nodes, edges


def _paths_from(source: str, edges):
    reached, frontier = set(), [source]
    while frontier:
        item = frontier.pop()
        if item in reached:
            continue
        reached.add(item)
        frontier.extend(b for a, b in edges if a == item)
    return reached


@pytest.mark.parametrize(
    "asset,expected",
    [(NAMES[0], (17, 15, 7)), (NAMES[1], (22, 20, 7)), (NAMES[2], (17, 16, 6))],
)
def test_source_structure_matches_documented_p0005_qa(asset, expected):
    nodes, edges = _source_graph(ASSETS / asset)
    assert (len(nodes), len(edges)) == expected[:2]
    assert len(edges) == len(set(edges)), "duplicate dependency edge"
    assert all(a in nodes and b in nodes for a, b in edges)
    waves = _topo_layers()(sorted(nodes), [(a, b, "FEEDFORWARD") for a, b in edges])
    assert len(waves) == expected[2], "topological layer drift from README P0005"
    assert set().union(*map(set, waves)) == nodes


def test_w4_promotion_has_all_five_noncompensating_prerequisites():
    nodes, edges = _source_graph(ASSETS / NAMES[1])
    assert "ADMIT" in nodes and "W4" in nodes and "IC3" in nodes
    incoming = {a for a, b in edges if b == "ADMIT"}
    assert incoming == {"B21", "B09", "B29", "B37", "IC3"}
    assert {a for a, b in edges if b == "W4"} == {"ADMIT"}
    assert {a for a, b in edges if b == "W5"} == {"W4"}
    assert {a for a, b in edges if b == "W6"} == {"W5"}


def test_iso_batch_remains_separate_from_hosted_w4():
    _, edges = _source_graph(ASSETS / NAMES[1])
    assert "ADMIT" not in _paths_from("B30", edges)
    assert "W4" not in _paths_from("B30", edges)
    assert "ISO" in _paths_from("B30", edges)


def test_owner_hosted_ic3_is_never_bypassed_by_broker_ci():
    _, edges = _source_graph(ASSETS / NAMES[1])
    assert "IC3" in _paths_from("B19", edges)
    assert "ADMIT" in _paths_from("IC3", edges)
    assert ("B35", "ADMIT") not in edges  # native tests alone cannot bypass owner DoV
    assert ("B19", "ADMIT") not in edges  # WIF setup is not an IC3 hosted pass
    assert "ADMIT" not in _paths_from("B30", edges)


def test_cycle_and_unknown_endpoint_are_rejected_by_existing_kahn_owner():
    topo_layers = _topo_layers()
    nodes, edges = _source_graph(ASSETS / NAMES[1])
    with pytest.raises(ValueError, match="cycle"):
        topo_layers(sorted(nodes), [(a, b, "FEEDFORWARD") for a, b in edges] + [("W6", "B12", "FEEDFORWARD")])
    with pytest.raises(ValueError, match="unknown"):
        topo_layers(sorted(nodes), [(a, b, "FEEDFORWARD") for a, b in edges] + [("W4", "UNKNOWN_ENDPOINT", "FEEDFORWARD")])
