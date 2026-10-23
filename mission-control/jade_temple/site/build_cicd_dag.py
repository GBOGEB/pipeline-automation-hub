#!/usr/bin/env python3
"""JADE CI/CD DAG + SIPOC page: deterministic HTML over tools/cicd_dag.py.

Source: the in-memory projection of tools/cicd_dag.py (same inputs, same hashes).
Output (generated; do not hand edit): site/cicd_dag.html. Offline, no external
requests: the DAG is inline SVG laid out here, and one switch flips every node
between the FUNCTION, SHA and OID lens. Colour is never the only status cue.
Validated JADE child, not staged into Pages (owner review first, as N+8).
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "site/cicd_dag.html"
_spec = importlib.util.spec_from_file_location("jade_cicd_dag", ROOT / "tools" / "cicd_dag.py")
dag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dag)

E = lambda s: html.escape("" if s is None else str(s), quote=True)
W, H, COL, ROW, PAD = 224, 60, 284, 76, 24
KIND_ORDER = {k: i for i, k in enumerate("SIPOC")}
COLOURS = {  # fill, stroke, text: dark JADE panel tints, one per evidence class
    "CODE_PURPLE": ("#2c1f47", "#b48cff", "#eadcff"),
    "ROOT_RED": ("#4a1d17", "#ff8a6b", "#ffd9cf"),
    "EVERRED": ("#3a1b1b", "#ff6b6b", "#ffd6d6"),
    "FAIL": ("#3a1b1b", "#ff9999", "#ffd6d6"),
    "UNKNOWN": ("#3a2f1c", "#ffcc83", "#ffe9c6"),
    "PASS": ("#123d2c", "#7be0ad", "#dbffec"),
    "P_PROCESS": ("#16284a", "#7fb2ff", "#dce9ff"),
    "ISSUE_BD": ("#3a2f1c", "#e6b35c", "#ffe9c6"),
    "CROSSWALK": ("#0f3340", "#6fd6e8", "#d6f6fb"),
    "NEUTRAL": ("#183a30", "#85ad9d", "#eefaf2"),
}
EDGE_STYLE = {"PREREQ": "e-pre", "FLOW": "e-flow", "FEDERATION": "e-fed", "CONTAINS": "e-flow",
              "CROSSWALK": "e-x", "TEMPORAL": "e-t"}


def clip(s, n):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def sid(scope):
    return scope.replace(":", "-").replace(".", "-").lower()


def positions(scope):
    cols = {}
    for n in scope["nodes"]:
        cols.setdefault(n["layer"], []).append(n)
    tallest = max(len(v) for v in cols.values())
    pos = {}
    for layer, members in cols.items():
        members.sort(key=lambda n: (KIND_ORDER[n["kind"]], n["type"], n["id"]))
        top = PAD + (tallest - len(members)) * ROW / 2
        for i, n in enumerate(members):
            pos[n["id"]] = (PAD + layer * COL, top + i * ROW)
    width = PAD * 2 + (max(cols) + 1) * COL - (COL - W)
    height = PAD * 2 + tallest * ROW + 40
    return pos, width, height


def edge_path(a, b, back):
    (x1, y1), (x2, y2) = a, b
    if back:  # temporal / same-column crosswalk: loop under both nodes
        sy, ty = y1 + H, y2 + H
        dip = max(sy, ty) + 34
        return f"M{x1 + W / 2:.0f},{sy:.0f} C{x1 + W / 2:.0f},{dip:.0f} {x2 + W / 2:.0f},{dip:.0f} {x2 + W / 2:.0f},{ty:.0f}"
    sx, sy, tx, ty = x1 + W, y1 + H / 2, x2, y2 + H / 2
    mid = (sx + tx) / 2
    return f"M{sx:.0f},{sy:.0f} C{mid:.0f},{sy:.0f} {mid:.0f},{ty:.0f} {tx:.0f},{ty:.0f}"


def svg(scope):
    pos, width, height = positions(scope)
    parts = [f'<svg class="dag" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" '
             f'role="img" aria-label="{E(scope["title"])}: {len(scope["nodes"])} nodes, {scope["dag"]["edges"]} edges">',
             '<defs><marker id="ah-' + sid(scope["scope"]) + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
             'markerHeight="7" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#8fb5a6"/></marker></defs>']
    for k in "SIPOC":
        xs = [pos[n["id"]][0] for n in scope["nodes"] if n["kind"] == k]
        if xs:
            parts.append(f'<text class="lane" x="{min(xs):.0f}" y="14">{k} · {E(dag.SIPOC_NAMES[k])}</text>')
    layer = {n["id"]: n["layer"] for n in scope["nodes"]}
    for e in scope["edges"]:
        back = e["type"] == "TEMPORAL" or layer[e["to"]] <= layer[e["from"]]
        title = f'{e["from"]} → {e["to"]} · {e["type"]}' + (f' · {e["label"]}' if e["label"] else "") + \
                (f' · {e["state"]}' if e.get("state") else "")
        parts.append(f'<path class="edge {EDGE_STYLE.get(e["type"], "e-flow")}" d="{edge_path(pos[e["from"]], pos[e["to"]], back)}" '
                     f'marker-end="url(#ah-{sid(scope["scope"])})"><title>{E(title)}</title></path>')
    for n in scope["nodes"]:
        x, y = pos[n["id"]]
        fill, stroke, ink = COLOURS[n["colour"]]
        badge = n["status"] or dag.colour_of({n["colour"]}, [], n["colour"])
        parts.append(f'<g class="node" tabindex="0" data-id="{E(n["id"])}" transform="translate({x:.0f},{y:.0f})">'
                     f'<title>{E(n["label"])} — {E(n["detail"])}</title>'
                     f'<rect width="{W}" height="{H}" rx="9" fill="{fill}" stroke="{stroke}"/>'
                     f'<rect width="5" height="{H}" rx="2" fill="{stroke}"/>'
                     f'<text x="13" y="20" fill="{ink}" class="t1">{E(clip(n["label"], 33))}</text>')
        for lens in dag.LENSES:
            txt = (f'{badge} · {clip(n["detail"], 24)}' if lens == "FUNCTION" and n["detail"]
                   else badge if lens == "FUNCTION" else dag.lens_text(n, lens))
            parts.append(f'<text x="13" y="40" class="t2 l l-{lens}" fill="{ink}">{E(clip(txt, 38))}</text>')
        parts.append(f'<text x="13" y="54" class="t3" fill="{stroke}">{E(n["kind"])} · {E(n["type"])}'
                     f'{" · " + E(n["phase"]) if n["phase"] else ""}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def chip(colour, text):
    return f'<span class="cd-chip c-{colour.lower()}">{E(text)}</span>'


def sipoc_table(scope, defs):
    by = {n["id"]: n for n in scope["nodes"]}
    cells = []
    for k in "SIPOC":
        items = "".join(f'<li>{chip(by[i]["colour"], by[i]["status"] or by[i]["colour"].replace("_", " "))} '
                        f'{E(by[i]["label"])}</li>' for i in scope["sipoc"][k])
        cells.append(f'<div class="sipoc-col"><h4>{k} · {E(dag.SIPOC_NAMES[k])}</h4><p class="cd-q">{E(defs[k].split(": ", 1)[-1])}</p>'
                     f'<ul>{items or "<li>—</li>"}</ul></div>')
    return f'<div class="sipoc">{"".join(cells)}</div>'


def kv(d, skip=()):
    rows = []
    for k, v in d.items():
        if k in skip:
            continue
        if isinstance(v, dict):
            v = " · ".join(f"{a} {b}" for a, b in v.items() if not isinstance(b, (dict, list)))
        elif isinstance(v, list):
            v = ", ".join(map(str, v)) or "—"
        rows.append(f"<tr><th>{E(k.replace('_', ' '))}</th><td>{E('—' if v is None else v)}</td></tr>")
    return f'<table class="cd-kv">{"".join(rows)}</table>'


def scope_metrics(scope):
    m = scope["metrics"]
    chips = " ".join(chip(c, c.replace("_", " ") + f" {v}") for c, v in scope["dag"]["by_colour"].items())
    blocks = [f'<div class="cd-card"><h4>DAG shape</h4>{kv(scope["dag"], skip=("by_sipoc", "by_colour"))}'
              f'<p class="cd-q">{chips}</p></div>']
    for key, val in m.items():
        if key == "repos":
            continue
        if isinstance(val, dict):
            blocks.append(f'<div class="cd-card"><h4>{E(key.replace("_", " "))}</h4>{kv(val, skip=("phase_yield", "per_repo"))}</div>')
        else:
            blocks.append(f'<div class="cd-card"><h4>{E(key.replace("_", " "))}</h4><p><b>{E(val)}</b></p></div>')
    return f'<div class="cd-grid">{"".join(blocks)}</div>'


def phase_bars(total):
    rows = []
    for ph, p in total["metrics"]["gates"]["phase_yield"].items():
        pct = 100 * (p["yield"] or 0)
        rows.append(f'<div class="cd-bar"><span><b>{E(ph)}</b> <small>{E(", ".join(p["gates"]))}</small></span>'
                    f'<span class="cd-track" role="img" aria-label="{E(ph)} yield {pct:.1f} percent"><i style="width:{pct:.1f}%"></i></span>'
                    f'<span>{p["pass"]}/{p["total"]} · {pct:.1f}%</span></div>')
    g = total["metrics"]["gates"]
    return (f'<div class="cd-card"><div class="cd-bars">{"".join(rows)}</div>'
            f'<p class="cd-q">Rolled throughput yield (product of phase yields) = <b>{g["rolled_throughput_yield"]}</b>. '
            f'Critical path {" → ".join(g["critical_path"]["gates"])}: mean PASS depth '
            f'<b>{g["critical_path"]["mean_pass_depth"]}/{g["critical_path"]["length"]}</b>.</p></div>')


def orch_table(orch):
    head = ("repo", "role", "in", "w-in", "out", "authority in", "mode", "ruleset", "open roots", "red now", "EVERRED")
    rows = []
    for repo, m in sorted(orch["metrics"]["repos"].items(), key=lambda kv: (-kv[1]["in_degree"], kv[0])):
        mode = m["mode"] or "n/a"
        mc = "CODE_PURPLE" if mode == "CODE_PURPLE" else "EVERRED" if mode == "EVERRED" else "NEUTRAL"
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in (
            f"<b>{E(dag._short(repo))}</b>", E(m["role"]), m["in_degree"], m["weighted_in"], m["out_degree"],
            m["authority_bound_in"], chip(mc, mode), E(m["ruleset"] or "n/a"), E(m["open_roots"] if m["open_roots"] is not None else "n/a"),
            E(m["red_now"] if m["red_now"] is not None else "n/a"), E(m["everred"] if m["everred"] is not None else "n/a"))) + "</tr>")
    return (f'<div class="cd-tablewrap"><table class="cd"><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def crosswalk_rows(model):
    rows = []
    for s in model["scopes"]:
        for n in s["nodes"]:
            shas = "<br>".join(f'<code>{E(b["value"][:12])}</code> <small>{E(b["label"])}</small>' for b in n["shas"]) or "—"
            oids = "<br>".join((f'<code>{E(b["oid"][:12])}</code> ' if b["oid"] else f'<small>{E(b["status"])}</small> ')
                               + f'<small>{E(b["path"])}{"::" + E(b["symbol"]) if b.get("symbol") else ""}'
                               + (f' @{E(b["at"][:7])}' if b.get("at") else "")
                               + (f'<br>{E(b["jade_oid"])}' if b.get("jade_oid") else "") + '</small>'
                               for b in n["oids"]) or "—"
            rows.append(f'<tr data-scope="{E(s["scope"])}"><td>{E(s["scope"])}</td><td><b>{E(n["label"])}</b><br><small>{E(n["id"])} · {E(n["detail"])}</small></td>'
                        f'<td>{E(n["kind"])}</td><td>{chip(n["colour"], n["status"] or n["colour"].replace("_", " "))}</td>'
                        f'<td>{shas}</td><td>{oids}</td></tr>')
    return "".join(rows)


def heatmap(model):
    lc = model.get("lifecycle")
    if not lc:
        return ""
    keys, names = lc["stages"], lc["level_names"]
    head = "".join(f"<th>{E(k.split('_', 1)[0])}<br><small>{E(k.split('_', 1)[1])}</small></th>" for k in keys)
    rows = []
    for r in lc["repos"]:
        cells = "".join(
            f'<td class="lv c-{r["status"][k].lower()}" title="{E(k)} L{r["levels"][k]} {E(names[str(r["levels"][k])])}'
            f' · blocked by {E(r["next_blocker"][k] or "nothing (L5)")} {E(r["status"][k]) if r["next_blocker"][k] else ""}">L{r["levels"][k]}'
            f'<small>{"blocker " + E(r["status"][k]) if r["next_blocker"][k] else "all PASS"}</small></td>'
            for k in keys)
        drift = (chip("CROSSWALK", "HEAD ≠ gate SHA") if r["sha_drift"] else
                 chip("PASS", "HEAD = gate SHA") if r["focus_sha"] else "")
        rows.append(f'<tr><td>{r["rank"]}</td><td><b>{E(dag._short(r["repo"]))}</b><br><small>{E(r["lane"])} · '
                    f'<code>{E((r["head_sha"] or "")[:10])}</code></small> {drift}</td>{cells}</tr>')
    fleet = "".join(f'<td class="lv">L{lc["fleet"][k]["median_level"]}<small>≥L3 {lc["fleet"][k]["repos_ge_L3"]}/21</small></td>' for k in keys)
    return (f'<h2 class="cd-sec" id="lifecycle">DevOps lifecycle maturity S0–S9 (21 repos, census N+9)</h2>'
            f'<p class="cd-lead">Level per stage on the census ladder (L0 ABSENT … L5 CONTROLLED); the cell text gives the level and the stage status '
            f'(the level is attainment, not a verdict; the label is the state of the next blocking probe above it, so an unobservable blocker stays UNKNOWN). Census <code>{E(lc["digest_sha256"][:12])}</code> '
            f'observed {E(lc["observed_at_utc"])}; HEADs can be newer than the gate SHAs.</p>'
            f'<div class="cd-tablewrap"><table class="cd"><thead><tr><th>#</th><th>Repo</th>{head}</tr></thead><tbody>{"".join(rows)}'
            f'<tr><td></td><td><b>Fleet median</b></td>{fleet}</tr></tbody></table></div>')


def objects_table(model):
    rows = "".join(f'<tr><td><code>{E(o["oid"])}</code></td><td>{E(o["path"])}{"<b>::" + E(o["symbol"]) + "</b>" if o.get("symbol") else ""}</td>'
                   f'<td>{E(o["kind"])}</td><td>{E(o["function"])}</td></tr>' for o in model["objects"])
    return (f'<div class="cd-tablewrap"><table class="cd"><thead><tr><th>Git blob OID</th><th>Object (path::symbol)</th>'
            f'<th>Kind</th><th>Function</th></tr></thead><tbody>{rows}</tbody></table></div>')


def legend(model):
    return '<div class="cd-legend">' + "".join(
        f'<div>{chip(k, v["label"])} <small>{E(v["meaning"])}</small></div>' for k, v in model["colour_classes"].items()) + \
        '<div><span class="ln e-pre"></span><small>prerequisite</small> <span class="ln e-fed"></span><small>federation edge</small> ' \
        '<span class="ln e-x"></span><small>crosswalk (declared join)</small> <span class="ln e-t"></span><small>temporal (next pulse / hand-off)</small></div></div>'


def kpis(total, orch):
    g, ev, p, bd = (total["metrics"][k] for k in ("gates", "everred", "p_process", "issue_bd"))
    items = [
        (f'{g["verified_completion_pct"]}%', "verified gate completion", "PASS"),
        (f'{g["measurement_debt_pct"]}%', "measurement debt (UNKNOWN)", "UNKNOWN"),
        (len(g["ready_frontier"]), "ready-frontier gate instances", "PASS"),
        (g["blocked_by_ancestor"], "blocked by an ancestor", "UNKNOWN"),
        (f'{g["critical_path"]["mean_pass_depth"]}/{g["critical_path"]["length"]}', "critical-path PASS depth", "CROSSWALK"),
        (total["metrics"]["source_red"]["core_focus"], "SOURCE_RED core focus", "ROOT_RED"),
        (f'{ev["everred_ratio"] * 100:.1f}%', f'EVERRED ratio ({ev["everred"]}/{ev["workflows_traced"]})', "EVERRED"),
        (f'{ev["recovery_rate"] * 100:.1f}%', "recovery rate (RED→GREEN)", "PASS"),
        (f'{ev["red_now"]}', f'red now · median {ev["red_now_median_age_days"]} d', "EVERRED"),
        (", ".join(p["code_purple_repos"]) or "none", f'Code Purple · lifted {p["lifted"]}', "CODE_PURPLE"),
        (p["control_plane_red"], "control-plane probes red", "CODE_PURPLE"),
        (f'{bd["bd_open"]}/{bd["bd_total"]}', f'BD open · {bd["open_issues_focus"]} issues', "ISSUE_BD"),
        (f'{total["dag"]["oid_coverage"] * 100:.0f}%', "nodes bound to a git OID", "CROSSWALK"),
        (f'{orch["metrics"]["hub_fan_in_share"] * 100:.0f}%', "hub share of federation edges", "P_PROCESS"),
    ]
    dv = total["metrics"].get("devops")
    if dv:
        items += [
            (dv["deploy_contract_core"], "deploy jobs passing DP1-DP10", "ROOT_RED"),
            (f'{dv["untested_module_pct"]}%', f'python modules untested ({dv["py_untested"]})', "FAIL"),
            (f'{dv["unguarded_test_job_pct"]}%', "CI test jobs without zero-test guard", "UNKNOWN"),
            (f'{dv["actions_pinned_pct"]}%', "third-party actions SHA-pinned", "UNKNOWN"),
            (f'{len(dv["census_sha_drift"])}/5', "focus repos: census HEAD ≠ gate SHA", "CROSSWALK"),
        ]
    return '<div class="cd-kpis">' + "".join(
        f'<div class="cd-kpi c-{c.lower()}-edge"><b>{E(v)}</b><span>{E(k)}</span></div>' for v, k, c in items) + "</div>"


CSS = """
.cd-wrap{padding:22px 0 60px}.cd-h1{font-size:clamp(26px,3.4vw,40px);margin:18px 0 6px;letter-spacing:-.01em}.cd-lead{color:var(--muted);max-width:1000px}
.cd-sec{margin:34px 0 10px;font-size:20px}.cd-q{color:var(--muted);font-size:13px}
.cd-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}
.cd-kpi{background:var(--panel);border:1px solid var(--stroke);border-top-width:3px;border-radius:14px;padding:12px 14px}.cd-kpi b{display:block;font-size:24px;line-height:1.15;overflow-wrap:anywhere}.cd-kpi span{font-size:12px;color:var(--muted)}
.cd-card{background:var(--panel);border:1px solid var(--stroke);border-radius:14px;padding:14px 16px;margin:10px 0;min-width:0}.cd-card h4{margin:0 0 8px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}
.cd-chip{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.05em;border:1px solid;border-radius:99px;padding:1px 8px;margin:1px 3px 1px 0;white-space:nowrap}
.c-code_purple{color:#eadcff;border-color:#b48cff;background:#2c1f47}.c-root_red{color:#ffd9cf;border-color:#ff8a6b;background:#4a1d17}
.c-everred,.c-fail{color:#ffd6d6;border-color:#ff6b6b;background:#3a1b1b}.c-unknown,.c-issue_bd{color:#ffe9c6;border-color:#e6b35c;background:#3a2f1c}
.c-pass{color:#dbffec;border-color:#7be0ad;background:#123d2c}.c-p_process{color:#dce9ff;border-color:#7fb2ff;background:#16284a}
.c-crosswalk{color:#d6f6fb;border-color:#6fd6e8;background:#0f3340}.c-neutral{color:var(--text);border-color:#85ad9d;background:#183a30}
.c-code_purple-edge{border-top-color:#b48cff}.c-root_red-edge{border-top-color:#ff8a6b}.c-everred-edge{border-top-color:#ff6b6b}.c-unknown-edge,.c-issue_bd-edge{border-top-color:#e6b35c}
.c-pass-edge{border-top-color:#7be0ad}.c-p_process-edge{border-top-color:#7fb2ff}.c-crosswalk-edge{border-top-color:#6fd6e8}
.cd-tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0}
.cd-tools select,.cd-tools input{background:var(--panel);color:var(--text);border:1px solid var(--stroke);border-radius:9px;padding:8px 10px;max-width:100%}
.cd-tools input{flex:1;min-width:180px}.cd-seg{display:inline-flex;border:1px solid var(--stroke);border-radius:10px;overflow:hidden}
.cd-seg button{background:var(--panel);color:var(--muted);border:0;padding:8px 14px;font-weight:700;font-size:13px}.cd-seg button[aria-pressed=true]{background:#214b3a;color:var(--green)}
.cd-stage{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:12px;align-items:start}.cd-stage>*{min-width:0}
.cd-canvas{overflow:auto;border:1px solid var(--stroke);border-radius:14px;background:#081d17;max-height:78vh}
.cd-panel{position:sticky;top:10px;max-height:78vh;overflow:auto}.cd-panel code{overflow-wrap:anywhere;font-size:11.5px}
svg.dag{display:block;font:12px var(--font)}svg.dag .lane{fill:var(--quiet);font-size:10.5px;letter-spacing:.14em;font-weight:800}
svg.dag .t1{font-weight:750;font-size:12.5px}svg.dag .t2{font-size:11.5px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}svg.dag .t3{font-size:9.5px;letter-spacing:.08em;font-weight:700}
svg.dag .node{cursor:pointer}svg.dag .node:focus{outline:none}svg.dag .node:focus rect:first-of-type,svg.dag .node.sel rect:first-of-type{stroke:var(--amber);stroke-width:3}
svg.dag .edge{fill:none;stroke:#5f8a7a;stroke-width:1.4;opacity:.85}svg.dag .e-pre{stroke:#8fb5a6}svg.dag .e-fed{stroke:#b6c9ff;stroke-width:2.2}
svg.dag .e-x{stroke:#6fd6e8;stroke-dasharray:5 4}svg.dag .e-t{stroke:#b48cff;stroke-dasharray:2 4;stroke-width:1.8}
.l{display:none}main[data-lens=FUNCTION] .l-FUNCTION,main[data-lens=SHA] .l-SHA,main[data-lens=OID] .l-OID{display:inline}
.cd-legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:6px 18px;margin:10px 0}
.ln{display:inline-block;width:28px;height:0;border-top:2px solid #8fb5a6;vertical-align:middle;margin:0 4px 0 10px}.ln.e-fed{border-top:3px solid #b6c9ff}.ln.e-x{border-top:2px dashed #6fd6e8}.ln.e-t{border-top:2px dotted #b48cff}
.sipoc{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.sipoc-col{background:var(--panel);border:1px solid var(--stroke);border-radius:12px;padding:10px 12px;min-width:0}
.sipoc-col h4{margin:0;font-size:13px}.sipoc-col ul{margin:6px 0 0;padding:0;list-style:none;font-size:12.5px}.sipoc-col li{margin:5px 0;overflow-wrap:anywhere}
.cd-tablewrap{overflow-x:auto;border:1px solid var(--stroke);border-radius:12px}table.cd{border-collapse:collapse;width:100%;min-width:760px}
table.cd th,table.cd td{padding:8px 10px;border-bottom:1px solid var(--stroke);text-align:left;vertical-align:top;font-size:12.5px}
table.cd th{background:var(--panel-hi);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);position:sticky;top:0}
table.cd small{color:var(--quiet)}table.cd code{font-size:11.5px}
table.cd-kv{border-collapse:collapse;width:100%;min-width:0;table-layout:fixed}table.cd-kv th{color:var(--muted);font-weight:600;text-align:left;padding:3px 10px 3px 0;font-size:12px;vertical-align:top;width:44%}table.cd-kv td{font-size:12.5px;padding:3px 0;overflow-wrap:anywhere;word-break:break-word}
.cd-bars{display:grid;gap:8px}.cd-bar{display:grid;grid-template-columns:200px 1fr 110px;gap:10px;align-items:center;font-size:13px}
.cd-track{display:block;height:14px;border-radius:7px;overflow:hidden;background:var(--panel-hi)}.cd-track i{display:block;height:100%;background:var(--green)}
.cd-scope[hidden]{display:none}table.cd td.lv{text-align:center;font-weight:800;white-space:nowrap}table.cd td.lv small{display:block;font-weight:600;font-size:10px;color:inherit;opacity:.85}
.lv.c-pass,.lv.c-fail,.lv.c-unknown{border-left:1px solid var(--stroke)}footer.cd-foot{color:var(--quiet);font-size:12px;margin-top:40px;border-top:1px solid var(--stroke);padding-top:14px;overflow-wrap:anywhere}
@media(max-width:980px){.cd-stage{grid-template-columns:1fr}.cd-panel{position:static;max-height:none}.sipoc{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.app-shell{padding:0 16px}.sipoc{grid-template-columns:1fr}.cd-bar{grid-template-columns:1fr}.mast{flex-wrap:wrap}}
"""

JS = """(function(){
var main=document.getElementById('main'),data=JSON.parse(document.getElementById('cd-data').textContent);
var sel=document.getElementById('cd-scope'),panel=document.getElementById('cd-panel');
function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=String(text);return e}
function add(p){for(var i=1;i<arguments.length;i++)if(arguments[i])p.appendChild(arguments[i]);return p}
function safeUrl(u){try{var x=new URL(u);return x.protocol==='https:'?x.href:null}catch(e){return null}}
function lens(l){main.dataset.lens=l;document.querySelectorAll('[data-lens-btn]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.lensBtn===l)});}
document.querySelectorAll('[data-lens-btn]').forEach(function(b){b.addEventListener('click',function(){lens(b.dataset.lensBtn)})});
function scope(s){document.querySelectorAll('.cd-scope').forEach(function(p){p.hidden=p.dataset.scope!==s});show(null);}
sel.addEventListener('change',function(){scope(sel.value)});
// The panel is built with DOM nodes and textContent only; evidence links must be https.
function show(id){document.querySelectorAll('svg.dag .node.sel').forEach(function(g){g.classList.remove('sel')});
 panel.replaceChildren();
 if(!id){add(panel,el('h4',null,'Node detail'),el('p','cd-q','Select a node (click or Enter) to see its function, every SHA and every git object OID bound to it.'));return}
 var n=(data[sel.value]||{})[id];if(!n)return;
 document.querySelectorAll('.cd-scope:not([hidden]) .node').forEach(function(g){if(g.dataset.id===id)g.classList.add('sel')});
 var chip=el('span','cd-chip c-'+String(n.colour).toLowerCase().replace(/[^a-z_]/g,''),n.status||n.colour);
 add(panel,el('h4',null,n.kind+' · '+n.type),add(el('p'),el('b',null,n.label)),
     add(el('p'),chip,n.phase?el('small',null,' '+n.phase):null),el('p','cd-q',n.detail));
 add(panel,el('h4',null,'SHA lens'));
 if(!n.shas.length)add(panel,el('p','cd-q','no SHA bound'));
 n.shas.forEach(function(b){add(panel,add(el('div'),el('small',null,b.label),el('br'),el('code',null,b.value)))});
 add(panel,el('h4',null,'OID lens'));
 if(!n.oids.length)add(panel,el('p','cd-q','no object bound'));
 n.oids.forEach(function(b){add(panel,add(el('div'),el('small',null,b.path+(b.symbol?'::'+b.symbol:'')),el('br'),el('code',null,b.oid||b.status),
   b.at?el('small',null,' @ census HEAD '+String(b.at).slice(0,10)):null,b.jade_oid?el('br'):null,b.jade_oid?el('small',null,b.jade_oid):null))});
 var u=n.url?safeUrl(n.url):null;
 if(u){var a=el('a',null,'evidence ↗');a.href=u;a.rel='noopener noreferrer';add(panel,add(el('p'),a))}}
document.querySelectorAll('svg.dag .node').forEach(function(g){g.addEventListener('click',function(){show(g.dataset.id)});g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();show(g.dataset.id)}})});
var q=document.getElementById('cd-q'),xs=document.getElementById('cd-xscope'),cnt=document.getElementById('cd-n');
function f(){var s=q.value.toLowerCase(),c=0;document.querySelectorAll('#cd-xwalk tbody tr').forEach(function(tr){var ok=(!xs.value||tr.dataset.scope===xs.value)&&tr.textContent.toLowerCase().indexOf(s)>-1;tr.hidden=!ok;if(ok)c++});cnt.textContent=c+' rows';}
[q,xs].forEach(function(e){e.addEventListener('input',f);e.addEventListener('change',f)});
lens('FUNCTION');scope(sel.value);f();})();"""

MAST = """<header class="mast"><div class="brand"><span class="brand-logo" aria-hidden="true">JT</span><div>JADE_TEMPLE<small>CI/CD DAG · SIPOC · SHA ⇄ OID CROSSWALK</small></div></div>
<div class="mast-right"><span class="timestamp">PULSE {pulse}</span><span class="pill pill-hold">ADMISSION HOLD</span><span class="pill" style="color:var(--green)">READ-ONLY</span></div></header>"""


def page(model):
    scopes = model["scopes"]
    total, orch = scopes[0], scopes[-1]
    opts = "".join(f'<option value="{E(s["scope"])}">{E(s["title"])}</option>' for s in scopes)
    canvases = "".join(f'<div class="cd-scope cd-canvas" data-scope="{E(s["scope"])}">{svg(s)}</div>' for s in scopes)
    panels = (f'<div class="cd-stage"><div>{canvases}</div>'
              '<aside class="cd-card cd-panel" id="cd-panel" aria-live="polite"></aside></div>'
              + "".join(f'<section class="cd-scope" data-scope="{E(s["scope"])}" aria-label="{E(s["title"])}">'
                        f'<h3 class="cd-sec">SIPOC · {E(s["title"])}</h3>{sipoc_table(s, model["sipoc_definitions"])}'
                        f'<h3 class="cd-sec">Metrics · {E(s["title"])}</h3>{scope_metrics(s)}</section>' for s in scopes))
    data = {s["scope"]: {n["id"]: {k: n[k] for k in ("kind", "type", "label", "status", "colour", "phase",
                                                     "detail", "shas", "oids", "url")} for n in s["nodes"]}
            for s in scopes}
    xopts = "".join(f'<option value="{E(s["scope"])}">{E(s["scope"])}</option>' for s in scopes)
    defs = "".join(f"<tr><th>{E(k.replace('_', ' '))}</th><td>{E(v)}</td></tr>" for k, v in model["metric_definitions"].items())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JADE CI/CD DAG</title><link rel="stylesheet" href="jade.css"><style>{CSS}</style></head><body>
<a class="skip" href="#main">Skip to content</a><div class="app-shell">{MAST.format(pulse=E(model["latest_pulse"]))}
<main id="main" class="cd-wrap" data-lens="FUNCTION">
<h1 class="cd-h1">How does CI/CD flow, where is it red, and which object produces each step?</h1>
<p class="cd-lead">One process model, seven views: the federation total, each JADE focus repo, and the orchestrating / federating assets. Every node carries three identities: <b>FUNCTION</b> (what the step means), <b>SHA</b> (the exact commit or sha256 snapshot it was observed on) and <b>OID</b> (the git blob of the Python, workflow or data object that produces it, with the function symbol). Read-only projection; UNKNOWN is never PASS. <a href="cicd_dag.json">JSON</a> · <a href="cicd_dag_crosswalk.csv">crosswalk CSV</a> · <a href="rolling5.json">rolling-5</a> · <a href="redtrace.html">red-trace</a></p>
{kpis(total, orch)}
<h2 class="cd-sec" id="dag">DAG / SIPOC</h2>
<div class="cd-tools"><label for="cd-scope" class="cd-q">View</label><select id="cd-scope">{opts}</select>
<span class="cd-seg" role="group" aria-label="Identity lens"><button type="button" data-lens-btn="FUNCTION" aria-pressed="true">Function</button><button type="button" data-lens-btn="SHA" aria-pressed="false">SHA</button><button type="button" data-lens-btn="OID" aria-pressed="false">Object-ID</button></span></div>
{legend(model)}
<div id="cd-views">{panels}</div>
<h2 class="cd-sec" id="yield">DMAIC phase yield (federation total)</h2>{phase_bars(total)}
{heatmap(model)}
<h2 class="cd-sec" id="orch">Orchestrating and federating repositories</h2><p class="cd-lead">In/out degree over typed federation edges; w-in weights inbound edges by state (AUTHORITY_BOUND 2, observation/evidence/provider 1, reference 0). {orch["metrics"]["causal_root_proof_edges"]} edges carry causal root proof.</p>{orch_table(orch)}
<h2 class="cd-sec" id="crosswalk">Crosswalk: function ⇄ SHA ⇄ OID</h2>
<div class="cd-tools"><input id="cd-q" type="search" placeholder="Search label, SHA, OID, path, symbol…" aria-label="Search crosswalk"><select id="cd-xscope" aria-label="Scope"><option value="">All scopes</option>{xopts}</select><span id="cd-n" aria-live="polite"></span></div>
<div class="cd-tablewrap"><table class="cd" id="cd-xwalk"><thead><tr><th>Scope</th><th>Node (function)</th><th>SIPOC</th><th>Status / class</th><th>SHA bindings</th><th>OID bindings (object::symbol)</th></tr></thead><tbody>{crosswalk_rows(model)}</tbody></table></div>
<h2 class="cd-sec" id="objects">Bound objects (git blob OIDs)</h2><p class="cd-lead">OIDs equal <code>git rev-parse HEAD:&lt;path&gt;</code> for committed files; symbols are verified to exist as <code>def</code> in the file, or the build fails closed.</p>{objects_table(model)}
<h2 class="cd-sec" id="defs">Metric definitions</h2><div class="cd-card"><table class="cd-kv">{defs}</table></div>
<footer class="cd-foot">Inputs: {" · ".join(f"<code>{E(k)}</code> {E(v[:12])}" for k, v in model["inputs"].items())}<br>Generated by <code>site/build_cicd_dag.py</code> over <code>tools/cicd_dag.py</code> · authority_transfer=false · release_credit=false · merge_admission=HOLD · not staged into Pages.</footer>
</main></div><script type="application/json" id="cd-data">{json.dumps(data, sort_keys=True, ensure_ascii=False).replace("</", "<\\/")}</script><script>{JS}</script></body></html>
"""


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    data = page(dag.project(root)).encode("utf-8")
    out = root / OUT
    if args.check:
        if not out.exists() or out.read_bytes() != data:
            print("CICD_DAG_PAGE_FIRST_RED: regenerate " + OUT)
            return 1
        print("CICD_DAG_PAGE_PARITY_OK")
        return 0
    out.write_bytes(data)
    print("CICD_DAG_PAGE_WROTE " + OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
