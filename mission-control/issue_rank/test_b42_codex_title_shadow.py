"""B42 negative and source-role ownership probes."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

PILOT = Path(__file__).with_name("b42_codex_title_shadow.py")
spec = importlib.util.spec_from_file_location("b42", PILOT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
CODEX_ROOT = Path(os.environ["B42_CODEX_ROOT"])


def test_exact_alias_is_inert_and_title_is_unchanged():
    title = "fix(jade): bounded ledger repair"
    result = pilot.observe(CODEX_ROOT, "next ambitious slice", title)
    assert result["action_candidate"]["canonical_id"] == "G3A"
    assert result["action_candidate"]["dispatch_authorized"] is False
    assert result["changed_title"] is False
    assert result["title_classification"]["schema"] == "jade.title-taxonomy.v1"
    assert result["merge_authorized"] is False
    assert result["formal_credit_delta"] == 0


@pytest.mark.parametrize("phrase", ["CG", "3P", "unknown meaningful suggestion", "next ambitious slice; rm -rf /"])
def test_reserved_unknown_or_instruction_text_is_not_routed(phrase):
    receipt = pilot.observe(CODEX_ROOT, phrase, "docs: title ownership")
    assert receipt["action_candidate"] is None
    assert receipt["action_refusal"]
    assert receipt["dispatch_authorized"] is False
    assert receipt["title_classification"]["schema"] == "jade.title-taxonomy.v1"


def test_source_sha_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(pilot, "_sha", lambda _: "f" * 40)
    with pytest.raises(ValueError, match="CODEX_EXACT_SOURCE_MISMATCH"):
        pilot.observe(CODEX_ROOT, "next ambitious slice", "test: source")


def test_title_blob_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(pilot, "_blob", lambda _: "f" * 40)
    with pytest.raises(ValueError, match="HUB_TITLE_OWNER_DRIFT"):
        pilot.observe(CODEX_ROOT, "next ambitious slice", "test: source")
