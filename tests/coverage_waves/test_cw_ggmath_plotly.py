"""Behavioural tests for mission-control/qps-triage-ultra/ggmath_plotly.py.

The existing suite (test_ggmath_bridge.py) drives the committed receipt.  These
tests use a small synthetic receipt to reach the gated/deferred branches,
compare_figure_docs edge cases, the offline HTML guard and the CLI.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "qps-triage-ultra" / "ggmath_plotly.py"


@pytest.fixture
def gp(tmp_path):
    spec = importlib.util.spec_from_file_location("cw_ggmath_plotly_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Default paths derive from __file__; point them at a sandbox, never the repo.
    mod.__file__ = str(tmp_path / "sandbox" / "cw_ggmath_alias.py")
    spec.loader.exec_module(mod)
    assert mod.RECEIPT_PATH == tmp_path / "sandbox" / "ggmath_bridge_receipt.json"
    return mod


def _flow(status="PASS_MEASURED", effs=(0.25, None)):
    lanes = {}
    for i, eff in enumerate(effs):
        lanes[f"lane{i}"] = {"flow_efficiency": eff, "queue_seconds": 30.0 + i, "execute_seconds": 10.0 + i}
    return {"status": status, "threshold_kind": {"flow": "MEASURED"}, "lanes": lanes,
            "fleet": {"flow_efficiency": 0.2, "queue_execute_ratio": 3.0, "dominant_component": "queue"}}


def receipt(full=True):
    pca = {"status": "PASS_MEASURED", "threshold_kind": {"pca_mp_edge": "ANALYTIC", "pca_pa95": "NULL_MODEL",
                                                      "other": "ignored"},
           "result": {"n": 40, "p": 3, "sample_adequate": True,
                      "scree": {"observed_eigenvalues": [2.0, 0.6, 0.4], "pa95_component_thresholds": [1.3, 1.1, 0.9],
                                "mp_upper_asymptotic": 1.6, "leading_retained_candidates": 1}}}
    bt = {"status": "PASS_MEASURED", "threshold_kind": {"bt_rank_frequency": "BOOTSTRAP"},
          "result": {"comparisons": 12, "reported_fit_is_classical_mle": False,
                     "reported_fit": {"fit_kind": "penalised"},
                     "log_strength_intervals": {"level": 0.95, "intervals": {
                         "b": {"estimate": 0.5, "interval": [0.1, 0.9]},
                         "a": {"estimate": -0.5, "interval": [-1.0, 0.0]}}},
                     "rank_frequency": {"penalty": 0.01, "valid_resamples": 200, "seed": 7,
                                        "rank_frequency": {"a": {"1": 0.1, "2": 0.9}, "b": {"1": 0.9, "2": 0.1}}}}}
    trace = {"status": "PASS_REFERENCE", "threshold_kind": {},
             "result": {"evidence_class": "SYNTHETIC_REFERENCE", "trace": {
                 "retained_rank": 3, "ambient_dimension": 4, "states": 3,
                 "cumulative_grassmann_path_length": 0.5, "net_grassmann_displacement_from_reference": 0.3,
                 "adjacent": [
                     {"from_k": 0, "to_k": 1, "principal_angles_degrees": [1.0, 5.0], "grassmann_geodesic_distance": 0.2},
                     {"from_k": 1, "to_k": 2, "principal_angles_degrees": [3.0, 2.0], "grassmann_geodesic_distance": 0.3}]}}}
    conv = {"status": "PASS_REFERENCE", "threshold_kind": {},
            "result": {"receipt": {"tolerance_pp": 0.5, "evidence_class": "SYNTHETIC_REFERENCE",
                                   "classification": "PLATEAU", "plateau_last_three_steps": True,
                                   "cap_distance_pp": 2.25},
                       "velocity_series": [{"to_n": 1, "velocity_pp_per_pulse": 1.0},
                                           {"to_n": 2, "velocity_pp_per_pulse": 0.2}]}}
    doc = {"provider": {"sha": "f" * 40, "repo": "GBOGEB/gg_MATH"},
           "measured": {"pca_retention_w3_fleet": pca, "bt_strength_w3_current_frontier": bt,
                        "flow_kpi_gm_i_a": _flow(), "flow_kpi_fleet_ledger": _flow("DEFER_NO_DATA", (None, 0.5))},
           "reference_challenges": {"temporal_trace_rank3_r4": trace, "convergence_reference_cohort": conv}}
    if not full:
        doc["measured"]["pca_retention_w3_fleet"] = {"status": "DEFER_SMALL_N", "result": {"n": 4}}
        doc["measured"]["bt_strength_w3_current_frontier"] = {"status": "DEFER_NO_PAIRS"}
        doc["reference_challenges"]["temporal_trace_rank3_r4"]["status"] = "DEFER_TRACE"
        doc["reference_challenges"]["convergence_reference_cohort"]["status"] = "FAIL_REFERENCE"
    return doc


def raw_of(doc, crlf=False):
    text = json.dumps(doc, indent=1)
    return (text.replace("\n", "\r\n") if crlf else text).encode()


# ---------------------------------------------------------------- figures
def test_full_receipt_builds_every_figure_in_gate_order(gp):
    doc = receipt()
    out = gp.build_figures(doc, raw_of(doc))
    assert [f["id"] for f in out["figures"]] == [
        "scree_w3_fleet", "bt_strength_w3_current_frontier", "bt_rank_frequency_w3_current_frontier",
        "principal_angles_reference", "grassmann_history_reference", "convergence_velocity_reference",
        "flow_gm_i_a", "flow_fleet_ledger"]
    # Only the flow ledger adapter is not PASS; references are not measured adapters.
    assert out["deferred_measured_adapters"] == [{"adapter": "flow_kpi_fleet_ledger", "status": "DEFER_NO_DATA"}]
    assert out["authority_transfer"] is False and out["schema"] == gp.SCHEMA


def test_deferred_receipt_omits_gated_figures_but_keeps_flow(gp):
    doc = receipt(full=False)
    out = gp.build_figures(doc, raw_of(doc))
    assert [f["id"] for f in out["figures"]] == ["flow_gm_i_a", "flow_fleet_ledger"]
    assert [d["adapter"] for d in out["deferred_measured_adapters"]] == [
        "bt_strength_w3_current_frontier", "flow_kpi_fleet_ledger", "pca_retention_w3_fleet"]


def test_receipt_digest_is_line_ending_neutral(gp):
    doc = receipt()
    lf, crlf = raw_of(doc), raw_of(doc, crlf=True)
    assert lf != crlf
    a = gp.build_figures(doc, lf)["receipt_sha256"]
    assert a == gp.build_figures(doc, crlf)["receipt_sha256"] == hashlib.sha256(lf).hexdigest()


def test_scree_without_eigenvalues_is_an_empty_measured_figure(gp):
    env = {"status": "DEFER_SMALL_N", "threshold_kind": {"pca_pa95": "NULL_MODEL"}, "result": {"n": 4, "scree": None}}
    entry = gp.scree(env, "s")
    assert entry["figure"]["data"] == []
    assert entry["headline"] == "n=4 below registry minimum; no scree"
    assert entry["threshold_kind"] == {"pca_pa95": "NULL_MODEL"}
    assert entry["figure"]["layout"]["title"]["text"] == "Scree with MP edge and PA95 - DEFER_SMALL_N"


def test_scree_traces_and_threshold_kind_filtering(gp):
    entry = gp.scree(receipt()["measured"]["pca_retention_w3_fleet"], "s")
    data = entry["figure"]["data"]
    assert data[0]["x"] == ["PC1", "PC2", "PC3"]
    assert data[2]["x"] == ["PC1", "PC3"] and data[2]["y"] == [1.6, 1.6]
    assert entry["threshold_kind"] == {"pca_mp_edge": "ANALYTIC", "pca_pa95": "NULL_MODEL"}
    assert entry["headline"] == "n=40, p=3; 1 PA95 retention candidate(s); sample adequate=True"


def test_bt_strength_sorts_by_estimate_and_asymmetric_errors(gp):
    entry = gp.bt_strength(receipt()["measured"]["bt_strength_w3_current_frontier"], "bt")
    trace = entry["figure"]["data"][0]
    assert trace["y"] == ["a", "b"]
    assert trace["error_x"]["array"] == pytest.approx([0.5, 0.4])
    assert trace["error_x"]["arrayminus"] == pytest.approx([0.5, 0.4])
    assert trace["name"] == "log-strength, 95% Wald"
    assert entry["headline"] == "12 measured comparisons; classical MLE withheld (graph not strongly connected)"
    env = receipt()["measured"]["bt_strength_w3_current_frontier"]
    env["result"]["reported_fit_is_classical_mle"] = True
    assert gp.bt_strength(env, "bt")["headline"].endswith("classical MLE available")


def test_rank_frequency_heatmap_matrix(gp):
    entry = gp.bt_rank_frequency(receipt()["measured"]["bt_strength_w3_current_frontier"], "rf")
    trace = entry["figure"]["data"][0]
    assert trace["x"] == ["rank 1", "rank 2"]
    assert trace["z"] == [[0.1, 0.9], [0.9, 0.1]]
    assert entry["headline"] == "seed 7; ties share fractional rank mass"
    assert entry["threshold_kind"] == {"bt_rank_frequency": "BOOTSTRAP"}


def test_reference_trace_figures_use_reference_evidence_class(gp):
    env = receipt()["reference_challenges"]["temporal_trace_rank3_r4"]
    pa = gp.principal_angles(env, "pa")
    assert pa["evidence_class"] == "SYNTHETIC_REFERENCE"
    assert pa["figure"]["data"][0]["x"] == ["k0->k1", "k1->k2"]
    assert pa["figure"]["data"][0]["y"] == [5.0, 3.0]
    assert pa["headline"] == "rank 3 in R^4; 3 states"
    gh = gp.grassmann_history(env, "gh")
    assert gh["figure"]["data"][0]["x"] == [0, 1, 2]
    assert gh["figure"]["data"][0]["y"] == pytest.approx([0.0, 0.2, 0.5])
    assert gh["headline"] == "path 0.500 rad vs net displacement 0.300 rad"


def test_convergence_band_is_closed_polygon(gp):
    entry = gp.convergence_velocity(receipt()["reference_challenges"]["convergence_reference_cohort"], "cv")
    band = entry["figure"]["data"][0]
    assert band["x"] == [1, 2, 2, 1] and band["y"] == [0.5, 0.5, -0.5, -0.5]
    assert entry["headline"] == "PLATEAU; plateau last three steps=True; cap distance 2.2 pp"


def test_flow_efficiency_orders_unknown_first_and_labels_na(gp):
    entry = gp.flow_efficiency(_flow(effs=(0.5, None, 0.1)), "f", "Src")
    execute = entry["figure"]["data"][1]
    assert execute["y"] == ["lane1", "lane2", "lane0"]
    assert execute["text"] == ["n/a", "10.0% flow eff.", "50.0% flow eff."]
    assert entry["figure"]["layout"]["margin"]["r"] == 110
    assert entry["figure"]["layout"]["title"]["text"] == "Queue vs execute time - Src - PASS_MEASURED"
    assert entry["headline"] == "pooled flow efficiency 20.0%, queue/execute 3.00; dominant: queue"


# ---------------------------------------------------------------- compare
def test_compare_reports_missing_keys_and_ignores_receipt_digest(gp):
    a = {"receipt_sha256": "x", "only_a": 1, "same": "s"}
    b = {"receipt_sha256": "y", "only_b": 2, "same": "s"}
    assert gp.compare_figure_docs(a, b) == ["$.only_a: missing on one side", "$.only_b: missing on one side"]


def test_compare_reports_list_length_and_nested_path(gp):
    assert gp.compare_figure_docs([1, 2], [1]) == ["$: length 2 != 1"]
    assert gp.compare_figure_docs({"f": [{"v": 1.0}]}, {"f": [{"v": 1.5}]}) == ["$.f[0].v: 1.0 != 1.5"]
    assert gp.compare_figure_docs({"f": [{"v": 1.0}]}, {"f": [{"v": 1.01}]}) == []


def test_compare_does_not_treat_bools_as_numbers(gp):
    assert gp.compare_figure_docs(True, 1) == []  # True == 1 in Python equality fallback
    assert gp.compare_figure_docs(True, 1.01) == ["$: True != 1.01"]
    assert gp.compare_figure_docs("a", "b") == ["$: 'a' != 'b'"]


# ---------------------------------------------------------------- plotly-backed helpers
def test_write_html_is_offline_and_labels_threshold_kinds(gp, tmp_path):
    pytest.importorskip("plotly")
    doc = json.loads(gp.dumps(gp.build_figures(receipt(), raw_of(receipt()))))
    out = tmp_path / "page.html"
    gp.write_html(doc, out)
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert 'data-ggmath-provider-sha="' + "f" * 40 + '"' in html
    assert "pca_mp_edge=ANALYTIC, pca_pa95=NULL_MODEL" in html
    assert html.count("<section>") == len(doc["figures"])
    assert gp.REMOTE_SCRIPT.search(html) is None


def test_write_html_rejects_remote_script(gp, tmp_path):
    pytest.importorskip("plotly")
    doc = json.loads(gp.dumps(gp.build_figures(receipt(full=False), raw_of(receipt(full=False)))))
    doc["figures"] = doc["figures"][:1]
    doc["figures"][0]["headline"] = '<script src="https://cdn.example/x.js"></script>'
    out = tmp_path / "page.html"
    with pytest.raises(ValueError, match="REMOTE_JS_DEPENDENCY"):
        gp.write_html(doc, out)
    assert not out.exists()


def test_vendor_plotlyjs_writes_bundle(gp, tmp_path):
    pytest.importorskip("plotly")
    target = gp.vendor_plotlyjs(tmp_path / "assets" / "js")
    assert target == tmp_path / "assets" / "js" / "plotly.min.js"
    assert target.stat().st_size > 100_000


def test_validate_with_plotly_rejects_bad_trace(gp):
    pytest.importorskip("plotly")
    doc = {"figures": [{"figure": {"data": [{"type": "scatter", "not_a_property": 1}], "layout": {}}}]}
    with pytest.raises(ValueError):
        gp.validate_with_plotly(doc)


# ---------------------------------------------------------------- CLI
@pytest.fixture
def receipt_file(tmp_path):
    p = tmp_path / "receipt.json"
    p.write_bytes(raw_of(receipt()))
    return p


def test_main_writes_then_check_is_deterministic(gp, tmp_path, receipt_file, capsys):
    out = tmp_path / "site" / "_data" / "figs.json"
    assert gp.main(["--receipt", str(receipt_file), "--out", str(out)]) == 0
    assert f"wrote {out} (8 figures)" in capsys.readouterr().out
    assert b"\r\n" not in out.read_bytes()
    assert gp.main(["--receipt", str(receipt_file), "--out", str(out), "--check"]) == 0
    assert "deterministic:" in capsys.readouterr().out


def test_main_check_flags_stale_and_missing_output(gp, tmp_path, receipt_file, capsys):
    out = tmp_path / "figs.json"
    assert gp.main(["--receipt", str(receipt_file), "--out", str(out), "--check"]) == 2
    assert f"STALE: {out} differs" in capsys.readouterr().out
    assert not out.exists()
    out.write_text("{}\n", encoding="utf-8")
    assert gp.main(["--receipt", str(receipt_file), "--out", str(out), "--check"]) == 2


def test_main_default_paths_resolve_beside_module(gp, tmp_path, capsys):
    gp.RECEIPT_PATH.parent.mkdir(parents=True)
    gp.RECEIPT_PATH.write_bytes(raw_of(receipt(full=False)))
    import sys
    argv = sys.argv
    sys.argv = ["ggmath_plotly.py"]
    try:
        # Defaults are bound at parser construction, from the sandboxed module paths.
        assert gp.main() == 0
    finally:
        sys.argv = argv
    assert json.loads(gp.SITE_DATA_PATH.read_text(encoding="utf-8"))["figures"][0]["id"] == "flow_gm_i_a"


def test_main_compare_fresh_reports_differences(gp, tmp_path, receipt_file, capsys):
    out = tmp_path / "figs.json"
    gp.main(["--receipt", str(receipt_file), "--out", str(out)])
    capsys.readouterr()
    assert gp.main(["--out", str(out), "--compare-fresh", str(receipt_file)]) == 0
    assert capsys.readouterr().out.strip() == "fresh-vs-committed differences: 0"
    changed = receipt()
    changed["measured"]["flow_kpi_gm_i_a"]["status"] = "DEFER_CHANGED"
    fresh = tmp_path / "fresh.json"
    fresh.write_bytes(raw_of(changed))
    assert gp.main(["--out", str(out), "--compare-fresh", str(fresh)]) == 2
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1].startswith("fresh-vs-committed differences: ")
    assert int(lines[-1].rsplit(" ", 1)[1]) == len(lines) - 1 >= 2
    assert any("'PASS_MEASURED' != 'DEFER_CHANGED'" in line for line in lines)


def test_main_compare_fresh_caps_printed_lines_at_forty(gp, tmp_path, capsys):
    many = receipt()
    many["measured"]["flow_kpi_gm_i_a"]["lanes"] = {
        f"l{i:02d}": {"flow_efficiency": 0.5, "queue_seconds": 1.0, "execute_seconds": 1.0} for i in range(50)}
    base = tmp_path / "base.json"
    base.write_bytes(raw_of(many))
    out = tmp_path / "figs.json"
    gp.main(["--receipt", str(base), "--out", str(out)])
    for lane in many["measured"]["flow_kpi_gm_i_a"]["lanes"].values():
        lane["queue_seconds"] = 100.0
    fresh = tmp_path / "fresh.json"
    fresh.write_bytes(raw_of(many))
    capsys.readouterr()
    assert gp.main(["--out", str(out), "--compare-fresh", str(fresh)]) == 2
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 41
    assert int(lines[-1].rsplit(" ", 1)[1]) > 40


def test_main_validate_and_html(gp, tmp_path, receipt_file, capsys):
    pytest.importorskip("plotly")
    out, page = tmp_path / "figs.json", tmp_path / "page.html"
    assert gp.main(["--receipt", str(receipt_file), "--out", str(out), "--validate", "--html", str(page)]) == 0
    assert "plotly validated 8 figures" in capsys.readouterr().out
    assert page.is_file() and out.is_file()


def test_main_vendor_short_circuits(gp, tmp_path, capsys):
    pytest.importorskip("plotly")
    target = tmp_path / "js"
    assert gp.main(["--vendor-plotlyjs", str(target), "--receipt", str(tmp_path / "absent.json")]) == 0
    assert capsys.readouterr().out.strip() == f"wrote {target / 'plotly.min.js'}"


def test_dumps_is_canonical_and_copy_safe(gp):
    doc = receipt()
    before = copy.deepcopy(doc)
    text = gp.dumps({"b": 1 / 3, "a": float("nan")})
    assert text == '{\n "a": null,\n "b": 0.333333\n}\n'
    gp.build_figures(doc, raw_of(doc))
    assert doc == before
