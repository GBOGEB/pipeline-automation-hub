"""Coverage wave r9: branch/statement coverage for mission-control/gogreen/wave_timeline.py.

All fixtures are synthetic; nothing is written into the repository.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import runpy
import sys
from datetime import datetime as real_datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "gogreen" / "wave_timeline.py"
sys.path.insert(0, str(MODULE_PATH.parent))

_spec = importlib.util.spec_from_file_location("cw_r9_wave_timeline_mod", MODULE_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

REPO = "GBOGEB/pipeline-automation-hub"
CURRENT = "c" * 40


def _focused(covered=10, eligible=20, bcov=4, belig=8, digest="a" * 64):
    return {
        "tool": "coverage.py",
        "tool_version": "7.13.3",
        "source_file": "mission-control/gogreen/pulse_rollup.py",
        "source_file_sha256": digest,
        "statements": {"covered": covered, "eligible": eligible},
        "branches": {"covered": bcov, "eligible": belig},
    }


def _wave(i, *, observed=1, status_only=0, tests=None, focused=None, roots=None):
    run_id = 1000 + i
    return {
        "wave": f"G{i}",
        "ordinal": i,
        "kind": "SYNTHETIC",
        "observed_at_utc": f"2026-10-1{i}T08:00:00Z",
        "repository": REPO,
        "source_sha": f"{i}" * 40,
        "run_conclusion": "success",
        "run_id": run_id,
        "job_id": 2000 + i,
        "run_attempt": 1,
        "archive_artifact_id": 3000 + i,
        "workflow_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
        "archive_sha256": "sha256:" + "b" * 64,
        "archive_bytes_independently_verified": False,
        "fleet": {
            "catalog_cells": 42,
            "observed_cells": observed,
            "status_only_cells": status_only,
            "verified_source_archive_bytes": 0,
        },
        "tests": tests if tests is not None else {
            "suite_id": "GOGREEN_G4_NATIVE_UNITTTEST_DISCOVERY",
            "executed": None, "passed": None, "failed": None, "skipped": None,
        },
        "focused": focused,
        "root_predicates_recovered": roots,
        "scope_notes": f"scope {i}",
    }


def _tests(n, skipped=0):
    return {
        "suite_id": "GOGREEN_G4_NATIVE_UNITTTEST_DISCOVERY",
        "executed": n, "passed": n - skipped, "failed": 0, "skipped": skipped,
    }


def ledger():
    catalog = [
        {"repository": f"GBOGEB/repo{k}", "sha": f"{k}" * 40, "target_family_cells": 7}
        for k in range(6)
    ]
    return {
        "schema": m.SCHEMA,
        "cohort": "SIX_REPO_FIXED_42_CELLS",
        "authority_transfer": False,
        "merge_authorized": False,
        "qps_disposition": "DEFER",
        "wave_clock": "LOGICAL_WAVE_NOT_INDEPENDENT_GIT_REVISION",
        "measurement_rules": {"unknown_not_zero": True},
        "catalog": catalog,
        "waves": [
            _wave(0, observed=1),
            _wave(1, observed=6, status_only=2, tests=_tests(10), focused=_focused(10),
                  roots=3),
            _wave(2, observed=21, tests=_tests(15, skipped=1), focused=_focused(15),
                  roots=5),
        ],
    }


def test_canonical_is_sorted_compact_unicode():
    assert m.canonical({"b": 1, "a": "é"}) == '{"a":"é","b":1}'


@pytest.mark.parametrize("value,positive", [(True, False), ("1", False), (-1, False), (0, True)])
def test_integer_rejects(value, positive):
    with pytest.raises(ValueError, match="invalid integer x"):
        m._integer(value, "x", positive=positive)


def test_integer_accepts():
    assert m._integer(0, "x") is None
    assert m._integer(1, "x", positive=True) is None


def test_valid_synthetic_ledger():
    assert m.validate(ledger()) is True


def _top(key, value):
    def mut(d):
        d[key] = value
    return mut


def _wave_set(i, path, value):
    def mut(d):
        target = d["waves"][i]
        for p in path[:-1]:
            target = target[p]
        target[path[-1]] = value
    return mut


def _wave_del(i, key):
    def mut(d):
        del d["waves"][i][key]
    return mut


TOP_CASES = [
    (_top("schema", "x"), "unsupported cohort"),
    (_top("cohort", "x"), "unsupported cohort"),
    (_top("authority_transfer", True), "cannot grant authority"),
    (_top("merge_authorized", None), "cannot grant authority"),
    (_top("qps_disposition", "PROMOTE"), "QPS owner"),
    (_top("wave_clock", "GIT"), "logical wave clock"),
    (_top("measurement_rules", []), "fail closed"),
    (_top("measurement_rules", {}), "fail closed"),
    (_top("measurement_rules", {"a": 1}), "fail closed"),
    (_top("measurement_rules", {"a": False}), "fail closed"),
    (_top("catalog", {}), "six fixed"),
    (lambda d: d["catalog"].pop(), "six fixed"),
    (lambda d: d["catalog"][0].__setitem__("repository", 5), "invalid or duplicate"),
    (lambda d: d["catalog"][0].__setitem__("repository", "other/x"), "invalid or duplicate"),
    (lambda d: d["catalog"][1].__setitem__("repository", "GBOGEB/repo0"), "invalid or duplicate"),
    (lambda d: d["catalog"][0].__setitem__("sha", "z" * 40), "catalog SHA"),
    (lambda d: d["catalog"][0].pop("sha"), "catalog SHA"),
    (lambda d: d["catalog"][0].__setitem__("target_family_cells", 0), "catalog target"),
    (lambda d: d["catalog"][0].__setitem__("target_family_cells", 8), "denominator drift"),
    (_top("waves", None), "at least two"),
    (lambda d: d["waves"].pop() and d["waves"].pop(), "at least two"),
]


@pytest.mark.parametrize("mutate,msg", TOP_CASES)
def test_validate_top_level_rejections(mutate, msg):
    d = ledger()
    mutate(d)
    with pytest.raises(ValueError, match=msg):
        m.validate(d)


WAVE_CASES = [
    (_wave_del(1, "observed_at_utc"), "invalid UTC wave evidence"),
    (_wave_set(1, ["observed_at_utc"], 5), "invalid UTC wave evidence"),
    (_wave_set(1, ["observed_at_utc"], "2026-10-11T08:00:00"), "invalid UTC wave evidence"),
    (_wave_set(1, ["observed_at_utc"], "garbageZ"), "invalid UTC wave evidence"),
    (_wave_set(1, ["observed_at_utc"], "2026-10-01T08:00:00Z"), "chronology reversed"),
    (_wave_set(1, ["wave"], "G9"), "wave ordering"),
    (_wave_set(1, ["ordinal"], 7), "wave ordering"),
    (_wave_set(1, ["repository"], "GBOGEB/other"), "source identity"),
    (_wave_set(1, ["source_sha"], "x"), "source identity"),
    (_wave_del(1, "source_sha"), "source identity"),
    (_wave_set(1, ["run_conclusion"], "failure"), "native terminal PASS"),
    (_wave_set(1, ["run_id"], 0), "invalid integer run_id"),
    (_wave_set(1, ["job_id"], "1"), "invalid integer job_id"),
    (_wave_set(1, ["run_attempt"], 0), "invalid integer run_attempt"),
    (_wave_set(1, ["archive_artifact_id"], None), "invalid integer archive_artifact_id"),
    (_wave_set(1, ["workflow_url"], "https://example.invalid"), "URL provenance"),
    (_wave_set(1, ["archive_sha256"], "md5:00"), "archive digest"),
    (_wave_del(1, "archive_sha256"), "archive digest"),
    (_wave_set(1, ["archive_bytes_independently_verified"], None), "independent archive"),
    (_wave_set(1, ["fleet"], []), "denominator changed"),
    (_wave_set(1, ["fleet", "catalog_cells"], 43), "denominator changed"),
    (_wave_set(1, ["fleet", "observed_cells"], -1), "invalid integer observed_cells"),
    (_wave_set(1, ["fleet", "status_only_cells"], None), "invalid integer status_only_cells"),
    (_wave_set(1, ["fleet", "verified_source_archive_bytes"], 1.0),
     "invalid integer verified_source_archive_bytes"),
    (_wave_set(1, ["fleet", "status_only_cells"], 7), "cell geometry"),
    (_wave_set(2, ["fleet", "observed_cells"], 43), "cell geometry"),
    (_wave_set(2, ["fleet", "observed_cells"], 5), "observation regression"),
    (_wave_set(1, ["tests"], None), "incompatible test discovery"),
    (_wave_set(1, ["tests", "suite_id"], "OTHER"), "incompatible test discovery"),
    (_wave_set(1, ["tests", "failed"], None), "unknown counts"),
    (_wave_set(1, ["tests", "skipped"], -1), "unknown counts"),
    (_wave_set(1, ["tests"], dict(_tests(0))), "unsuccessful native test"),
    (_wave_set(1, ["tests", "passed"], 9), "unsuccessful native test"),
    (_wave_set(1, ["tests"], {**_tests(10), "passed": 9, "failed": 1}), "unsuccessful native test"),
    (_wave_set(0, ["focused"], _focused()), "native test/coverage lineage"),
    (_wave_set(1, ["focused", "tool"], "pytest-cov"), "native test/coverage lineage"),
    (_wave_set(1, ["focused", "source_file"], "x.py"), "unexpected focused module"),
    (_wave_set(1, ["focused", "source_file_sha256"], "short"), "source-file bytes"),
    (lambda d: d["waves"][1]["focused"].pop("source_file_sha256"), "source-file bytes"),
    (_wave_set(1, ["focused", "tool_version"], "7.0"), "unmatched coverage"),
    (_wave_set(1, ["focused", "statements"], None), "missing coverage dimension"),
    (_wave_set(1, ["focused", "branches"], [1]), "missing coverage dimension"),
    (_wave_set(1, ["focused", "statements", "covered"], -1), "statements covered"),
    (_wave_set(1, ["focused", "branches", "eligible"], 0), "branches eligible"),
    (_wave_set(1, ["focused", "statements", "covered"], 21), "impossible coverage ratio"),
    (_wave_set(1, ["root_predicates_recovered"], -2), "recovered first-red"),
    (_wave_set(0, ["root_predicates_recovered"], 1), "requires a subsequent wave"),
    (_wave_set(1, ["scope_notes"], None), "missing scope"),
    (_wave_set(1, ["scope_notes"], "   "), "missing scope"),
]


@pytest.mark.parametrize("mutate,msg", WAVE_CASES)
def test_validate_wave_rejections(mutate, msg):
    d = ledger()
    mutate(d)
    with pytest.raises(ValueError, match=msg):
        m.validate(d)


def test_timestamp_value_error_chained():
    d = ledger()
    d["waves"][1]["observed_at_utc"] = "notatimeZ"
    with pytest.raises(ValueError) as info:
        m.validate(d)
    assert isinstance(info.value.__cause__, ValueError)


def test_non_utc_offset_rejected_via_patched_datetime(monkeypatch):
    class FakeDT:
        @staticmethod
        def fromisoformat(text):
            return real_datetime.fromisoformat(text.replace("+00:00", "+02:00"))

    monkeypatch.setattr(m, "datetime", FakeDT)
    with pytest.raises(ValueError, match="invalid UTC wave evidence") as info:
        m.validate(ledger())
    assert "non-UTC" in str(info.value.__cause__)


def test_previous_valid_prefix():
    d = ledger()
    prev = ledger()
    prev["waves"] = prev["waves"][:2]
    assert m.validate(d, previous=prev) is True


def test_previous_invalid_itself():
    prev = ledger()
    prev["schema"] = "bad"
    with pytest.raises(ValueError, match="unsupported"):
        m.validate(ledger(), previous=prev)


def test_previous_not_shorter():
    with pytest.raises(ValueError, match="append-only"):
        m.validate(ledger(), previous=ledger())


def test_previous_catalog_rewritten():
    prev = ledger()
    prev["waves"] = prev["waves"][:2]
    d = ledger()
    d["catalog"][0]["sha"] = "f" * 40
    with pytest.raises(ValueError, match="catalog or comparability"):
        m.validate(d, previous=prev)


def test_previous_rules_rewritten():
    prev = ledger()
    prev["waves"] = prev["waves"][:2]
    d = ledger()
    d["measurement_rules"] = {"other": True}
    with pytest.raises(ValueError, match="catalog or comparability"):
        m.validate(d, previous=prev)


def test_previous_tampered_prefix():
    prev = ledger()
    prev["waves"] = prev["waves"][:2]
    d = ledger()
    d["waves"][1]["scope_notes"] = "rewritten"
    with pytest.raises(ValueError, match="tampered"):
        m.validate(d, previous=prev)


def test_percent():
    assert m._percent(1, 3) == 33.3333
    assert m._percent(42, 42) == 100.0


def test_coverage_delta_variants():
    a = {"focused": _focused(10, 20)}
    b = {"focused": _focused(15, 20)}
    assert m._coverage_delta(a, b, "statements") == 25.0
    assert m._coverage_delta(a, b, "branches") == 0.0
    assert m._coverage_delta({"focused": None}, b, "statements") is None
    assert m._coverage_delta(a, {"focused": None}, "statements") is None
    assert m._coverage_delta(a, {"focused": _focused(digest="e" * 64)}, "statements") is None
    assert m._coverage_delta(a, {"focused": _focused(10, 21)}, "statements") is None


def test_build_rejects_bad_source_sha():
    with pytest.raises(ValueError, match="current native head SHA"):
        m.build(ledger(), source_sha="C" * 40)


def test_build_rejects_invalid_ledger():
    d = ledger()
    d["qps_disposition"] = "GO"
    with pytest.raises(ValueError, match="QPS"):
        m.build(d, source_sha=CURRENT)


def test_build_report_and_deltas():
    r = m.build(ledger(), source_sha=CURRENT)
    assert r["schema"] == "gogreen.rolling-wave-report.v1"
    assert r["producer_source_sha"] == CURRENT
    assert r["source_catalog_repo_count"] == 6
    assert r["source_catalog_target_cells"] == 42
    assert r["future"] == {"next_wave": "G3", "status": "WAIT_FOR_NATIVE_EVIDENCE"}
    w0, w1, w2 = r["waves"]
    assert all(v is None for v in w0["delta"].values())
    assert w1["delta"]["observed_cells"] == 5
    assert w1["delta"]["native_tests"] is None
    assert w1["delta"]["focused_statement_coverage_pp"] is None
    assert w1["delta"]["recovered_roots"] is None
    assert w1["evidence_breadth_pct"] == round(100 * 6 / 42, 4)
    assert w2["delta"]["observed_cells"] == 15
    assert w2["delta"]["breadth_percentage_points"] == round(
        m._percent(21, 42) - m._percent(6, 42), 4)
    assert w2["delta"]["native_tests"] == 4
    assert w2["delta"]["focused_statement_coverage_pp"] == 25.0
    assert w2["delta"]["focused_branch_coverage_pp"] == 0.0
    assert w2["delta"]["recovered_roots"] == 2
    assert w2["artifact_id"] == 3002
    assert w2["artifact_digest"].startswith("sha256:")
    claims = r["improvement_claims"]
    assert claims["fleet_breadth_gain_last_wave_pp"] == w2["delta"]["breadth_percentage_points"]
    assert claims["native_test_gain_last_wave"] == 4
    assert claims["PCA_eligible"] is False
    assert r["admission"] == "HOLD" and r["merge_authorized"] is False


def test_num():
    assert m._num(None) == "UNKNOWN"
    assert m._num(3, " pp", signed=True) == "+3 pp"
    assert m._num(0, signed=True) == "0"
    assert m._num(-2, signed=True) == "-2"
    assert m._num(5) == "5"


def test_render_markdown_rows():
    text = m.render_markdown(m.build(ledger(), source_sha=CURRENT))
    assert text.endswith("\n")
    assert f"https://github.com/{REPO}/actions/runs/1002" in text
    assert "15/20" in text and "4/8" in text
    assert "5 PR-head predicates (not global roots)" in text
    assert "| UNKNOWN | UNKNOWN | UNKNOWN |" in text  # G0 has no focused / roots
    assert "+15 |" in text
    assert "Next: G3 — WAIT_FOR_NATIVE_EVIDENCE." in text
    assert f"Producer exact SHA: {CURRENT}." in text


def test_render_html_with_roots_and_focused():
    d = ledger()
    d["waves"][2]["scope_notes"] = "<b>x</b>"
    markup = m.render_html(m.build(d, source_sha=CURRENT))
    assert "<b>x</b>" not in markup and "&lt;b&gt;x&lt;/b&gt;" in markup
    assert "5 PR-head fingerprints" in markup
    assert "G2 scope; not current-wave or global root closure" in markup
    assert "21/42" in markup and "50.00%" in markup
    assert "15/20" in markup
    assert CURRENT in markup
    assert markup.startswith("<!doctype html>")


def test_render_html_unknowns():
    d = ledger()
    for w in d["waves"]:
        w["root_predicates_recovered"] = None
    d["waves"][2]["focused"] = None
    d["waves"][1]["focused"] = None
    markup = m.render_html(m.build(d, source_sha=CURRENT))
    assert "No comparable causal evidence" in markup
    assert "PR-head fingerprints" not in markup
    assert "UNKNOWN" in markup


def test_render_html_last_root_wave_not_newest():
    d = ledger()
    d["waves"][2]["root_predicates_recovered"] = None
    markup = m.render_html(m.build(d, source_sha=CURRENT))
    assert "G1 scope; not current-wave" in markup
    assert "3 PR-head fingerprints" in markup


def test_emit_writes_four_outputs(tmp_path):
    r = m.build(ledger(), source_sha=CURRENT)
    out = tmp_path / "nested" / "out"
    digest = m.emit(r, out)
    import hashlib
    payload = (out / "wave_timeline.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == digest
    assert (out / "wave_timeline.sha256").read_text(encoding="ascii") == digest + "\n"
    assert json.loads(payload)["future"]["next_wave"] == "G3"
    assert (out / "wave_timeline.md").read_text(encoding="utf-8").startswith("# MissionControl")
    assert "<html" in (out / "wave_timeline.html").read_text(encoding="utf-8")
    assert m.emit(r, out) == digest


def _write_inputs(tmp_path, with_previous):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(ledger()), encoding="utf-8")
    argv = ["wave_timeline.py", "--input", str(inp), "--out", str(tmp_path / "out"),
            "--source-sha", CURRENT]
    if with_previous:
        prev = ledger()
        prev["waves"] = prev["waves"][:2]
        pp = tmp_path / "prev.json"
        pp.write_text(json.dumps(prev), encoding="utf-8")
        argv += ["--previous", str(pp)]
    return argv


@pytest.mark.parametrize("with_previous", [False, True])
def test_main_cli(tmp_path, monkeypatch, capsys, with_previous):
    monkeypatch.setattr(sys, "argv", _write_inputs(tmp_path, with_previous))
    m.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["waves"] == 3 and payload["latest"] == "G2" and payload["next"] == "G3"
    assert payload["merge_authorized"] is False
    assert (tmp_path / "out" / "wave_timeline.sha256").read_text().strip() == payload["digest"]


def test_main_cli_previous_tampered(tmp_path, monkeypatch):
    argv = _write_inputs(tmp_path, True)
    prev = json.loads((tmp_path / "prev.json").read_text(encoding="utf-8"))
    prev["waves"][0]["scope_notes"] = "edited"
    (tmp_path / "prev.json").write_text(json.dumps(prev), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError, match="tampered"):
        m.main()
    assert not (tmp_path / "out").exists()


def test_dunder_main(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", _write_inputs(tmp_path, False))
    runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["latest"] == "G2"


def test_real_sample_structural():
    sample = MODULE_PATH.parent / "samples" / "wave_timeline.json"
    if not sample.exists():
        pytest.skip("sample absent")
    r = m.build(copy.deepcopy(json.loads(sample.read_text(encoding="utf-8"))), source_sha=CURRENT)
    assert isinstance(r["waves"], list)
    assert {"wave", "delta", "focused"} <= set(r["waves"][0])
    assert isinstance(m.render_markdown(r), str) and isinstance(m.render_html(r), str)
