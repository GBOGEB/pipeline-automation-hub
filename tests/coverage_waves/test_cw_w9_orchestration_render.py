"""Wave 9 coverage tests for mission-control/federation-atlas/orchestration/render.py.

A rich synthetic model drives the populated branches (programmes, cohort items,
dict broker metrics, local receipts, coverage gates and comparisons, build
commands).  HTML is checked structurally through html.parser: element
classes, attributes and counts, never exact markup.
"""
from __future__ import annotations

import importlib.util
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "federation-atlas" / "orchestration" / "render.py"


@pytest.fixture(scope="module")
def rd():
    spec = importlib.util.spec_from_file_location("cw_w9_orchestration_render", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def with_class(self, name):
        return [a for t, a in self.tags if name in (a.get("class") or "").split()]

    def named(self, tag):
        return [a for t, a in self.tags if t == tag]


SOURCE = {"repository": "GBOGEB/pipeline-automation-hub", "head_sha": "a" * 40, "dirty": False,
          "evidence_class": "LOCAL_SOURCE_INVENTORY_NOT_RUNTIME"}


def rich_model():
    return {
        "source": SOURCE,
        "taxonomy": {
            "programmes": [
                {"id": "P1", "label": "Prog", "definition_status": "DECLARED", "aliases": ["x", "y"],
                 "source_refs": ["plain-ref", {"source_path": "docs/a.md"},
                                 {"source_path": "docs/b.md", "source_url": "https://example.org/b"}]},
                {"id": "P2", "status": "PROPOSED"},
            ],
            "glossary": {"terms": [{"term": "atlas", "definition": "map"}]},
        },
        "burndown": {"cohorts": [
            {"id": "C1", "label": "One", "eligible": 4, "done": 1, "evidence_class": "BLOCKED",
             "source_path": "x.json", "series_metric": "open",
             "series": [{"metric": "open", "value": 3, "comparable": True, "eligible": 4},
                        {"open": 2, "comparable": True, "eligible": 4}],
             "items": [{"id": "i1", "title": "t", "state": "HOLD", "evidence": "MEASURED"}, "junk"]},
            {"id": "C2", "eligible": 0, "done": 0, "series": [{"open": None}, {"open": "x"}]},
        ]},
        "broker": {
            "metrics": {"queue": {"label": "Queue", "value": 3}, "mode": "FAST"},
            "tasks": [{"id": "t1"}, {"id": "t2"}],
            "local_receipt": {"evidence_class": "MEASURED", "outcome": "PASS", "metrics": {"wall": 1.5},
                              "tasks": {"t1": {"state": "DONE", "execution_seconds": 2}}},
            "decision": "admit",
            "policy": {"max": 2},
        },
        "coverage": {
            "portfolio": {"qualification": "NOT_QUALIFIED"},
            "rows": [{"id": "r1", "statements": {"classification": "NOT_APPLICABLE_BREADTH"},
                      "branches": {"classification": "NO_EXECUTABLE_ITEMS"}}],
            "gates": [{"row_id": "r1", "stage": "inventory", "status": "FAIL"}],
            "comparisons": [{"qualification": "VERIFIED", "from": "n1", "to": "n2",
                             "statements": {"delta_covered": 3, "delta_pp": 1.25, "before_pct": 50, "after_pct": 51},
                             "branches": {"delta_covered": "x", "delta_pp": "x"}}],
        },
        "build": {"commands": [{"label": "Build", "command": "python main.py"}, "junk"],
                  "outputs": [{"path": "out/index.html", "purpose": "page"}],
                  "source_path": "main.py"},
    }


def test_render_rejects_non_dict(rd, tmp_path):
    with pytest.raises(TypeError):
        rd.render([], tmp_path)


def test_render_rich_model_structure(rd, tmp_path):
    out = tmp_path / "site"
    assert rd.render(rich_model(), out) == ["index.html", "style.css", "app.js"]
    assert (out / "style.css").is_file() and (out / "app.js").is_file()
    doc = Tags((out / "index.html").read_text(encoding="utf-8"))
    assert len(doc.with_class("programme-card")) == 2
    links = doc.with_class("source-path")
    hrefs = [a.get("href") for a in links if a.get("href")]
    assert "https://example.org/b" in hrefs
    assert any(h.startswith("https://github.com/GBOGEB/pipeline-automation-hub/blob/") for h in hrefs)
    assert all(a.get("rel") == "noreferrer" for a in links if a.get("href"))
    assert len(doc.with_class("cohort-card")) == 2
    assert len(doc.with_class("trend-line")) == 1  # comparable points with equal denominators connect
    assert doc.with_class("blocked") and doc.with_class("declared") and doc.with_class("passed")
    assert len(doc.with_class("broker-metric")) == 2
    assert doc.with_class("local-proof")
    assert len(doc.with_class("copy-command")) == 2
    assert len(doc.named("progress")) == 1
    assert doc.with_class("comparison-grid")


def test_render_in_place_skips_asset_copy(rd, tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("template.html", "style.css", "app.js"):
        shutil.copyfile(MOD_PATH.parent / name, assets / name)
    monkeypatch.setattr(rd, "ASSETS", assets)
    before = (assets / "style.css").stat().st_mtime_ns
    rd.render({}, assets)
    assert (assets / "index.html").is_file()
    assert (assets / "style.css").stat().st_mtime_ns == before


def test_text_and_details_helpers(rd):
    assert rd._text(True) == "true" and rd._text(False) == "false"
    assert rd._text({"b": 1, "a": [2]}) == '{"a": [2], "b": 1}'
    doc = Tags(rd._details({"keep_me": 1, "drop": 2}, skip={"drop"}))
    assert len(doc.named("dt")) == 1


def test_source_url_forms(rd):
    assert rd._source_url({"source_url": "https://x.org/a"}, {}) == "https://x.org/a"
    url = rd._source_url({"source_path": "a b/c.py"}, SOURCE)
    assert url.startswith("https://github.com/GBOGEB/pipeline-automation-hub/blob/") and "a%20b/c.py" in url
    assert rd._source_url({"source_path": "x", "repo": "bad repo"}, {"head_sha": "h"}) is None


@pytest.mark.parametrize("value,state", [
    ("FAIL_GATE", "blocked"), ("PROPOSED", "declared"), ("PASS", "passed"), ("NOT_RUN", "unknown"), ("odd", "unknown"),
])
def test_badge_states(rd, value, state):
    attrs = Tags(rd._badge(value)).named("span")[0]
    assert state in attrs["class"].split()


def test_trend_all_unknown(rd):
    html = rd._cohort_trend({"series": [{"open": None}, {"open": -1}]})
    doc = Tags(html)
    assert not doc.named("svg") and doc.with_class("trend-empty")


def test_broker_build_and_coverage_empty_paths(rd):
    build = Tags(rd._build({"build": {}}))
    assert build.with_class("empty") and not build.named("table")
    cov = Tags(rd._coverage({}))
    assert cov.with_class("empty") and not cov.named("details")


def test_coverage_comparison_non_finite_delta_is_unknown(rd):
    # render() refuses NaN/inf in the JSON payload; the helper itself must still degrade.
    html = rd._coverage({"coverage": {"comparisons": [{"statements": {"delta_pp": float("inf"), "delta_covered": 2}}]}})
    doc = Tags(html)
    assert len(doc.with_class("subpanel")) == 1
    assert "UNKNOWN pp" in html
