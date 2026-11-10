"""Actual Chromium regression checks; explicitly enabled by the native owner workflow."""
import os
from pathlib import Path

import pytest

import build_mermaid_check as bmc

pytestmark = pytest.mark.skipif(os.environ.get("RUN_MERMAID_BROWSER") != "1", reason="opt-in Chromium QA")


def render(diagrams, tmp_path):
    configured = os.environ.get("MERMAID_BUNDLE")
    return bmc.render_headless(
        diagrams, tmp_path,
        bundle=Path(configured) if configured else None,
        chromium_executable=os.environ.get("CHROMIUM_EXECUTABLE"),
    )


def test_real_gantt_ids_do_not_collide_with_neighbor_flowcharts(tmp_path):
    diagrams = [
        bmc.Diagram("fixture", 1, "flowchart TD\nA[Before] --> B[After]\n"),
        bmc.Diagram("fixture", 2, "gantt\n dateFormat YYYY-MM-DD\n axisFormat w%V\n Task :m1, 2026-11-09, 3d\n"),
        bmc.Diagram("fixture", 3, "flowchart TD\nC[One] --> D[Two]\n"),
    ]
    result = render(diagrams, tmp_path)
    assert result["ok"], result
    assert len(result["svg_geometry"]) == 3
    assert len(list(tmp_path.glob("diagram-*.svg"))) == 3
    assert len(list(tmp_path.glob("diagram-*.png"))) == 3
    assert result["results"][1]["ticks"]
    assert result["merge_admission"] == "HOLD" and result["closure_credit"] == 0


def test_invalid_mermaid_remains_red_with_saved_receipt(tmp_path):
    result = render([bmc.Diagram("invalid", 1, "flowchart TD\nA[unterminated\n")], tmp_path)
    assert result["ok"] is False
    assert result["results"][0]["ok"] is False
    assert "error" in result["results"][0]
    assert (tmp_path / "receipt.json").is_file()


def test_empty_input_cannot_produce_positive_browser_proof(tmp_path):
    result = render([], tmp_path)
    assert result["ok"] is False
    assert result["expected_diagrams"] == 0
