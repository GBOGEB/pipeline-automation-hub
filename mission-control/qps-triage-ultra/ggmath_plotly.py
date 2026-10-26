#!/usr/bin/env python3
"""Deterministic Plotly figure JSON for the QPS / gg_MATH bridge receipt.

Figures are plain Plotly ``{"data", "layout"}`` dictionaries built from
``ggmath_bridge_receipt.json`` without importing plotly, so the committed JSON is
byte-stable across plotly versions.  ``plotly`` (pinned 7.0.0 in gg_MATH
``requirements-release.txt``) is only used to validate figures, to write the
offline plotly.js bundle for the Jekyll site and to emit an optional
self-contained HTML page.  No CDN script is ever referenced.

Every figure carries its status, evidence class and threshold kind; DEFER and
SYNTHETIC_REFERENCE states are stated in the title, never hidden.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RECEIPT_PATH = HERE / "ggmath_bridge_receipt.json"
SITE_DATA_PATH = HERE / "site" / "_data" / "ggmath_bridge_figures.json"
SCHEMA = "qps-ggmath-plotly-figures/v1"
SIGNIFICANT = 6
CRLF, LF = bytes([13, 10]), bytes([10])
REMOTE_SCRIPT = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']https?://", re.I)

# Categorical slots 1-3 of the validated reference palette (light mode), plus neutral ink.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#52514e", "#8a8984", "rgba(127,127,127,0.25)"
SEQUENTIAL = [[0.0, "#eef4fc"], [0.5, "#7fb0ea"], [1.0, "#174a8c"]]


def canon(value: Any) -> Any:
    """Round floats to fixed significant digits so the JSON is platform-stable."""
    if isinstance(value, dict):
        return {str(k): canon(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canon(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        rounded = float(f"{value:.{SIGNIFICANT}g}")
        return 0.0 if rounded == 0 else rounded
    return value


def dumps(doc: dict) -> str:
    return json.dumps(canon(doc), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def _layout(title: str, xaxis: dict, yaxis: dict, **extra) -> dict:
    layout = {
        "title": {"text": title, "x": 0, "xanchor": "left", "font": {"size": 15, "color": INK}},
        "font": {"family": "IBM Plex Sans, system-ui, sans-serif", "size": 12, "color": INK},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 72, "r": 24, "t": 64, "b": 56},
        "xaxis": {"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": MUTED, **xaxis},
        "yaxis": {"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": MUTED, **yaxis},
        "legend": {"orientation": "h", "y": -0.22, "x": 0},
        "hovermode": "closest",
    }
    layout.update(extra)
    return layout


def _entry(fig_id: str, env: dict, figure: dict, evidence_class: str, headline: str, outputs: list[str]) -> dict:
    kinds = env.get("threshold_kind", {})
    return {
        "id": fig_id,
        "status": env["status"],
        "evidence_class": evidence_class,
        "threshold_kind": {k: kinds[k] for k in outputs if k in kinds},
        "headline": headline,
        "figure": figure,
    }


def scree(env: dict, fig_id: str) -> dict:
    res = env["result"]
    sc = res.get("scree")
    title = f"Scree with MP edge and PA95 - {env['status']}"
    if not sc:
        fig = {"data": [], "layout": _layout(title, {"title": {"text": "Component"}},
                                             {"title": {"text": "Eigenvalue"}})}
        return _entry(fig_id, env, fig, "MEASURED", f"n={res.get('n')} below registry minimum; no scree",
                      ["pca_mp_edge", "pca_pa95"])
    eig = sc["observed_eigenvalues"]
    labels = [f"PC{i + 1}" for i in range(len(eig))]
    data = [
        {"type": "scatter", "mode": "lines+markers", "name": "Observed eigenvalue", "x": labels, "y": eig,
         "line": {"color": BLUE, "width": 2}, "marker": {"size": 8, "color": BLUE},
         "hovertemplate": "%{x}: %{y:.3f}<extra>observed</extra>"},
        {"type": "scatter", "mode": "lines+markers", "name": "PA95 null threshold", "x": labels,
         "y": sc["pa95_component_thresholds"], "line": {"color": ORANGE, "width": 2, "dash": "dash"},
         "marker": {"size": 8, "color": ORANGE, "symbol": "diamond"},
         "hovertemplate": "%{x}: %{y:.3f}<extra>PA95</extra>"},
        {"type": "scatter", "mode": "lines", "name": "MP upper edge (asymptotic)", "x": [labels[0], labels[-1]],
         "y": [sc["mp_upper_asymptotic"]] * 2, "line": {"color": MUTED, "width": 2, "dash": "dot"},
         "hovertemplate": "MP upper edge: %{y:.3f}<extra></extra>"},
    ]
    layout = _layout(title, {"title": {"text": "Component"}}, {"title": {"text": "Eigenvalue (standardised)"},
                                                               "rangemode": "tozero"})
    headline = (f"n={res['n']}, p={res['p']}; {sc['leading_retained_candidates']} PA95 retention candidate(s); "
                f"sample adequate={res['sample_adequate']}")
    return _entry(fig_id, env, {"data": data, "layout": layout}, "MEASURED", headline,
                  ["pca_mp_edge", "pca_pa95", "pca_eigengap_guard"])


def bt_strength(env: dict, fig_id: str) -> dict:
    res = env["result"]
    iv = res["log_strength_intervals"]["intervals"]
    names = sorted(iv, key=lambda n: (iv[n]["estimate"], n))
    est = [iv[n]["estimate"] for n in names]
    data = [{
        "type": "scatter", "mode": "markers", "name": f"log-strength, {int(res['log_strength_intervals']['level'] * 100)}% Wald",
        "x": est, "y": names, "marker": {"size": 10, "color": BLUE},
        "error_x": {"type": "data", "symmetric": False, "color": BLUE, "thickness": 2, "width": 6,
                    "array": [iv[n]["interval"][1] - iv[n]["estimate"] for n in names],
                    "arrayminus": [iv[n]["estimate"] - iv[n]["interval"][0] for n in names]},
        "hovertemplate": "%{y}: %{x:.3f}<extra></extra>",
    }]
    fit_kind = res["reported_fit"]["fit_kind"]
    title = f"Bradley-Terry strength ({fit_kind}) - {env['status']}"
    layout = _layout(title, {"title": {"text": "log-strength (sum-to-zero)"}, "zeroline": True},
                     {"title": {"text": ""}, "automargin": True}, showlegend=False)
    headline = (f"{res['comparisons']} measured comparisons; classical MLE "
                f"{'available' if res['reported_fit_is_classical_mle'] else 'withheld (graph not strongly connected)'}")
    return _entry(fig_id, env, {"data": data, "layout": layout}, "MEASURED", headline,
                  ["bt_finite_mle_guard", "bt_log_strength_intervals"])


def bt_rank_frequency(env: dict, fig_id: str) -> dict:
    rf = env["result"]["rank_frequency"]
    table = rf["rank_frequency"]
    names = sorted(table)
    ranks = sorted({int(r) for n in names for r in table[n]})
    z = [[table[n][str(r)] for r in ranks] for n in names]
    data = [{
        "type": "heatmap", "x": [f"rank {r}" for r in ranks], "y": names, "z": z, "zmin": 0, "zmax": 1,
        "colorscale": SEQUENTIAL, "texttemplate": "%{z:.2f}", "showscale": True,
        "colorbar": {"title": {"text": "share"}},
        "hovertemplate": "%{y} at %{x}: %{z:.3f}<extra></extra>",
    }]
    title = (f"Bootstrap rank frequency (L2 penalty {rf['penalty']}, {rf['valid_resamples']} resamples) "
             f"- {env['status']}")
    layout = _layout(title, {"title": {"text": "Rank"}, "side": "bottom"}, {"automargin": True})
    return _entry(fig_id, env, {"data": data, "layout": layout}, "MEASURED",
                  f"seed {rf['seed']}; ties share fractional rank mass", ["bt_rank_frequency"])


def principal_angles(env: dict, fig_id: str) -> dict:
    trace = env["result"]["trace"]
    adj = trace["adjacent"]
    x = [f"k{a['from_k']}->k{a['to_k']}" for a in adj]
    data = [{
        "type": "scatter", "mode": "lines+markers", "name": "max principal angle", "x": x,
        "y": [max(a["principal_angles_degrees"]) for a in adj], "line": {"color": BLUE, "width": 2},
        "marker": {"size": 8, "color": BLUE}, "hovertemplate": "%{x}: %{y:.2f} deg<extra></extra>",
    }]
    title = f"Adjacent principal angle - {env['result']['evidence_class']} - {env['status']}"
    layout = _layout(title, {"title": {"text": "Transition (event index)"}},
                     {"title": {"text": "theta max (degrees)"}, "rangemode": "tozero"}, showlegend=False)
    return _entry(fig_id, env, {"data": data, "layout": layout}, env["result"]["evidence_class"],
                  f"rank {trace['retained_rank']} in R^{trace['ambient_dimension']}; {trace['states']} states",
                  ["temporal_subspace_trace"])


def grassmann_history(env: dict, fig_id: str) -> dict:
    trace = env["result"]["trace"]
    adj = trace["adjacent"]
    ks = [adj[0]["from_k"]] + [a["to_k"] for a in adj]
    cumulative = [0.0]
    for a in adj:
        cumulative.append(cumulative[-1] + a["grassmann_geodesic_distance"])
    data = [
        {"type": "scatter", "mode": "lines+markers", "name": "cumulative geodesic path", "x": ks, "y": cumulative,
         "line": {"color": BLUE, "width": 2}, "marker": {"size": 8, "color": BLUE},
         "hovertemplate": "k=%{x}: %{y:.3f} rad<extra>path</extra>"},
        {"type": "scatter", "mode": "lines+markers", "name": "per-step geodesic distance", "x": ks[1:],
         "y": [a["grassmann_geodesic_distance"] for a in adj], "line": {"color": ORANGE, "width": 2, "dash": "dash"},
         "marker": {"size": 8, "color": ORANGE, "symbol": "diamond"},
         "hovertemplate": "k=%{x}: %{y:.3f} rad<extra>step</extra>"},
    ]
    title = f"Grassmann history - {env['result']['evidence_class']} - {env['status']}"
    layout = _layout(title, {"title": {"text": "Event index k"}, "dtick": 1},
                     {"title": {"text": "Grassmann geodesic (radians)"}, "rangemode": "tozero"})
    headline = (f"path {trace['cumulative_grassmann_path_length']:.3f} rad vs net displacement "
                f"{trace['net_grassmann_displacement_from_reference']:.3f} rad")
    return _entry(fig_id, env, {"data": data, "layout": layout}, env["result"]["evidence_class"], headline,
                  ["temporal_subspace_trace"])


def convergence_velocity(env: dict, fig_id: str) -> dict:
    rec = env["result"]["receipt"]
    vel = env["result"]["velocity_series"]
    tol = rec["tolerance_pp"]
    x = [v["to_n"] for v in vel]
    data = [
        {"type": "scatter", "mode": "lines", "name": f"plateau band (+/-{tol} pp)", "x": x + x[::-1],
         "y": [tol] * len(x) + [-tol] * len(x), "fill": "toself", "fillcolor": "rgba(138,137,132,0.18)",
         "line": {"width": 0}, "hoverinfo": "skip"},
        {"type": "scatter", "mode": "lines+markers", "name": "coverage velocity", "x": x,
         "y": [v["velocity_pp_per_pulse"] for v in vel], "line": {"color": BLUE, "width": 2},
         "marker": {"size": 8, "color": BLUE}, "hovertemplate": "pulse %{x}: %{y:.2f} pp/pulse<extra></extra>"},
    ]
    title = f"Convergence velocity - {rec['evidence_class']} - {rec['classification']}"
    layout = _layout(title, {"title": {"text": "Pulse index (not wall time)"}, "dtick": 1},
                     {"title": {"text": "Velocity (pp per pulse)"}})
    headline = (f"{rec['classification']}; plateau last three steps={rec['plateau_last_three_steps']}; "
                f"cap distance {rec['cap_distance_pp']:.1f} pp")
    return _entry(fig_id, env, {"data": data, "layout": layout}, rec["evidence_class"], headline,
                  ["convergence_classification"])


def flow_efficiency(kpi: dict, fig_id: str, title_source: str) -> dict:
    lanes = kpi["lanes"]
    names = sorted(lanes, key=lambda n: (lanes[n]["flow_efficiency"] if lanes[n]["flow_efficiency"] is not None else -1, n))
    text = [f"{100 * lanes[n]['flow_efficiency']:.1f}% flow eff." if lanes[n]["flow_efficiency"] is not None else "n/a"
            for n in names]
    data = [
        {"type": "bar", "orientation": "h", "name": "queue (admission wait)", "y": names,
         "x": [lanes[n]["queue_seconds"] for n in names], "marker": {"color": ORANGE, "line": {"width": 2, "color": "#ffffff"}},
         "hovertemplate": "%{y}: %{x:.0f} s queue<extra></extra>"},
        {"type": "bar", "orientation": "h", "name": "execute", "y": names, "text": text, "textposition": "outside",
         "cliponaxis": False,
         "x": [lanes[n]["execute_seconds"] for n in names], "marker": {"color": BLUE, "line": {"width": 2, "color": "#ffffff"}},
         "hovertemplate": "%{y}: %{x:.0f} s execute<extra></extra>"},
    ]
    fleet = kpi["fleet"]
    title = f"Queue vs execute time - {title_source} - {kpi['status']}"
    layout = _layout(title, {"title": {"text": "Seconds (measured)"}}, {"automargin": True}, barmode="stack")
    layout["margin"]["r"] = 110
    headline = (f"pooled flow efficiency {100 * fleet['flow_efficiency']:.1f}%, queue/execute "
                f"{fleet['queue_execute_ratio']:.2f}; dominant: {fleet['dominant_component']}")
    entry = {
        "id": fig_id, "status": kpi["status"], "evidence_class": "MEASURED",
        "threshold_kind": kpi["threshold_kind"], "headline": headline,
        "figure": {"data": data, "layout": layout},
    }
    return entry


def build_figures(receipt: dict, receipt_bytes: bytes) -> dict:
    m, ref = receipt["measured"], receipt["reference_challenges"]
    figures = []
    if "scree" in m["pca_retention_w3_fleet"].get("result", {}):
        figures.append(scree(m["pca_retention_w3_fleet"], "scree_w3_fleet"))
    bt = m["bt_strength_w3_current_frontier"]
    if "result" in bt:
        figures.append(bt_strength(bt, "bt_strength_w3_current_frontier"))
        figures.append(bt_rank_frequency(bt, "bt_rank_frequency_w3_current_frontier"))
    if ref["temporal_trace_rank3_r4"]["status"].startswith("PASS"):
        figures.append(principal_angles(ref["temporal_trace_rank3_r4"], "principal_angles_reference"))
        figures.append(grassmann_history(ref["temporal_trace_rank3_r4"], "grassmann_history_reference"))
    if ref["convergence_reference_cohort"]["status"].startswith("PASS"):
        figures.append(convergence_velocity(ref["convergence_reference_cohort"], "convergence_velocity_reference"))
    figures.append(flow_efficiency(m["flow_kpi_gm_i_a"], "flow_gm_i_a", "GM-I-A pulse P001"))
    figures.append(flow_efficiency(m["flow_kpi_fleet_ledger"], "flow_fleet_ledger", "QPS fleet ledger"))
    deferred = [{"adapter": k, "status": v["status"]} for k, v in sorted(m.items())
                if not str(v.get("status", "")).startswith("PASS")]
    return {
        "schema": SCHEMA,
        "provider": receipt["provider"],
        "receipt": "ggmath_bridge_receipt.json",
        "receipt_sha256": hashlib.sha256(receipt_bytes.replace(CRLF, LF)).hexdigest(),
        "plotly_python_pin": "plotly==7.0.0",
        "figures": figures,
        "deferred_measured_adapters": deferred,
        "authority_transfer": False,
    }


def compare_figure_docs(committed: Any, fresh: Any, *, rel: float = 1e-6, abs_tol: float = 0.02,
                        where: str = "$") -> list[str]:
    """Differences between a committed and a freshly regenerated figure document.

    Statuses, labels and structure must match exactly; numbers may drift within
    ``abs_tol``/``rel`` (cross-platform LAPACK/BFGS last-digit noise).  The receipt
    digest is excluded because it binds bytes, not meaning.
    """
    if isinstance(committed, dict) and isinstance(fresh, dict):
        keys = (set(committed) | set(fresh)) - {"receipt_sha256"}
        out = []
        for k in sorted(keys):
            if k not in committed or k not in fresh:
                out.append(f"{where}.{k}: missing on one side")
            else:
                out += compare_figure_docs(committed[k], fresh[k], rel=rel, abs_tol=abs_tol, where=f"{where}.{k}")
        return out
    if isinstance(committed, list) and isinstance(fresh, list):
        if len(committed) != len(fresh):
            return [f"{where}: length {len(committed)} != {len(fresh)}"]
        return [d for i, (a, b) in enumerate(zip(committed, fresh))
                for d in compare_figure_docs(a, b, rel=rel, abs_tol=abs_tol, where=f"{where}[{i}]")]
    numeric = (int, float)
    if (isinstance(committed, numeric) and isinstance(fresh, numeric)
            and not isinstance(committed, bool) and not isinstance(fresh, bool)):
        return [] if math.isclose(committed, fresh, rel_tol=rel, abs_tol=abs_tol) else [f"{where}: {committed} != {fresh}"]
    return [] if committed == fresh else [f"{where}: {committed!r} != {fresh!r}"]


def validate_with_plotly(doc: dict) -> int:
    """Validate each figure with plotly.graph_objects; returns the count validated."""
    import plotly.graph_objects as go

    for entry in doc["figures"]:
        go.Figure(entry["figure"])
    return len(doc["figures"])


def write_html(doc: dict, out: Path) -> None:
    """Self-contained offline HTML (one embedded plotly.js, no CDN)."""
    import plotly.io as pio
    import plotly.graph_objects as go

    parts = []
    for i, entry in enumerate(doc["figures"]):
        parts.append(f"<section><p>{entry['headline']} [{entry['evidence_class']}; "
                     f"{', '.join(f'{k}={v}' for k, v in sorted(entry['threshold_kind'].items()))}]</p>")
        parts.append(pio.to_html(go.Figure(entry["figure"]), include_plotlyjs=(i == 0), full_html=False,
                                 config={"displaylogo": False, "responsive": True}))
        parts.append("</section>")
    html = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>QPS gg_MATH bridge</title></head>"
            f"<body data-ggmath-provider-sha=\"{doc['provider']['sha']}\">" + "".join(parts) + "</body></html>")
    if REMOTE_SCRIPT.search(html):
        raise ValueError("REMOTE_JS_DEPENDENCY")
    out.write_text(html, encoding="utf-8")


def vendor_plotlyjs(directory: Path) -> Path:
    from plotly.offline import get_plotlyjs

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "plotly.min.js"
    target.write_text(get_plotlyjs(), encoding="utf-8")
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--receipt", type=Path, default=RECEIPT_PATH)
    ap.add_argument("--out", type=Path, default=SITE_DATA_PATH)
    ap.add_argument("--check", action="store_true", help="fail if --out differs from a fresh build")
    ap.add_argument("--validate", action="store_true", help="validate every figure with plotly")
    ap.add_argument("--html", type=Path, help="also write a self-contained offline HTML page")
    ap.add_argument("--vendor-plotlyjs", type=Path, help="write plotly.min.js from the installed plotly")
    ap.add_argument("--compare-fresh", type=Path, help="compare --out with figures from a freshly built receipt")
    args = ap.parse_args(argv)
    if args.vendor_plotlyjs:
        print(f"wrote {vendor_plotlyjs(args.vendor_plotlyjs)}")
        return 0
    if args.compare_fresh:
        raw = args.compare_fresh.read_bytes()
        fresh = json.loads(dumps(build_figures(json.loads(raw), raw)))
        diffs = compare_figure_docs(json.loads(args.out.read_text(encoding="utf-8")), fresh)
        for d in diffs[:40]:
            print(d)
        print(f"fresh-vs-committed differences: {len(diffs)}")
        return 2 if diffs else 0
    raw = args.receipt.read_bytes()
    doc = build_figures(json.loads(raw), raw)
    text = dumps(doc)
    if args.validate:
        print(f"plotly validated {validate_with_plotly(json.loads(text))} figures")
    if args.html:
        write_html(json.loads(text), args.html)
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(f"STALE: {args.out} differs from a fresh deterministic build")
            return 2
        print(f"deterministic: {args.out} matches ({len(doc['figures'])} figures)")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out} ({len(doc['figures'])} figures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
