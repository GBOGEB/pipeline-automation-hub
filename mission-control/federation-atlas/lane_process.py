#!/usr/bin/env python3
"""Offline, read-only granular federation/SIPOC process projection.

Uses the existing atlas registry and a pinned historical G4 evidence sample.
Never retrieves live data, dispatches workers, or writes authority states.
"""
import argparse
import html
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SCHEMA = "missioncontrol.federation_atlas.process_lanes.v1"
KNOWN = ("SUPPLY", "TRUST", "CENSUS", "DMAIC", "3P*", "MIP", "LDAB", "STAT", "REX", "GATE")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def esc(value):
    return html.escape(str(value), quote=True)


def verify(doc, registry):
    if doc.get("schema") != SCHEMA or doc.get("observer_authority") != "READ_ONLY":
        raise ValueError("Invalid readonly lane schema")
    lanes = doc.get("lanes", [])
    if not isinstance(lanes, list) or tuple(x.get("id") for x in lanes) != KNOWN:
        raise ValueError("Missing or duplicated lanes")
    ids = set()
    methods = {m["id"]: m for m in registry["methods"]}
    if set(methods) != {"SIPOC", "DAG", "DMAIC", "3P*", "MIP", "PCA", "BT", "LDAB"}:
        raise ValueError("Canonical atlas registry drift")
    for lane in lanes:
        if not lane.get("owner") or not lane.get("label"):
            raise ValueError("Unowned lane")
        stages = lane.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError("Empty lane")
        names = []
        for stage in stages:
            if not isinstance(stage, list) or len(stage) != 6 or not all(
                isinstance(v, str) and v for v in stage
            ):
                raise ValueError("Invalid node contract")
            node_id = lane["id"] + "__" + stage[0]
            if node_id in ids:
                raise ValueError("Duplicate node")
            ids.add(node_id)
            names.append(stage[0])
        if lane["id"] in ("DMAIC", "3P*", "MIP", "LDAB"):
            if lane["kind"] != "canonical" or names != methods[lane["id"]]["stages"]:
                raise ValueError("Registry stage mismatch")
        elif lane["kind"] == "canonical":
            raise ValueError("Projection promoted to canonical method")
    if len(doc.get("sipoc", [])) != 5 or [x.get("key") for x in doc["sipoc"]] != list("SIPOC"):
        raise ValueError("SIPOC contract mismatch")
    if doc.get("gates") != ["P5", "P6", "P7", "P8", "P9"]:
        raise ValueError("Gate sequence drift")
    o = doc["observation"]
    if not HEX40.fullmatch(o.get("head_sha", "")):
        raise ValueError("No exact source SHA")
    if not HEX64.fullmatch(o.get("focused_source_sha256", "")):
        raise ValueError("No focused source hash")
    if not HEX64.fullmatch(o.get("upload_zip_sha256", "")):
        raise ValueError("No archive upload hash")
    if (o["classification"] != "NATIVE_JOB_PASSED_ARTIFACT_UPLOAD_LOG_ONLY"
            or o["archive_bytes_independently_verified"] is not False):
        raise ValueError("Unproven artifact bytes promoted")
    if o["merge_admission"] != "HOLD" or o["authority_transfer"] is not False:
        raise ValueError("Authority assertion")
    if o["root_closure_credited"] != 0 or o["security_waiver"] is not False:
        raise ValueError("Unauthorized closure/security credit")
    eligible = o["eligible_cells"]
    if (type(eligible) is not int or eligible <= 0 or
            not (0 <= o["g0_observed_cells"] <= o["g1_observed_cells"] <= eligible)):
        raise ValueError("Bad fleet denominator")
    for axis in ("statements", "branches"):
        item = o[axis]
        if not all(type(item[k]) is int for k in ("before", "after", "eligible")):
            raise ValueError("Coverage count must be integer")
        if not 0 <= item["before"] <= item["eligible"] or not 0 <= item["after"] <= item["eligible"]:
            raise ValueError("Coverage numerator outside population")
    t = o["tests"]
    if not (0 < t["baseline"] <= t["candidate"] and t["passed_candidate"] <= t["candidate"]):
        raise ValueError("Invalid tests")
    for item in doc["sipoc"]:
        if not all(isinstance(item.get(k), str) and item[k] for k in ("name", "detail", "constraint")):
            raise ValueError("SIPOC missing fields")
    return len(ids)


def pct(n, d):
    return round(100 * n / d, 2)


def summary(doc):
    o = doc["observation"]
    return {
        "schema": "missioncontrol.federation_atlas.process_lane_metrics.v1",
        "source_repo": o["repository"], "source_sha": o["head_sha"],
        "run_id": o["run_id"], "job_id": o["job_id"], "artifact_id": o["artifact_id"],
        "evidence_class": o["classification"],
        "byte_verified": False,
        "node_count": sum(len(l["stages"]) for l in doc["lanes"]),
        "lane_count": len(doc["lanes"]),
        "observability": {
            "before": o["g0_observed_cells"], "after": o["g1_observed_cells"],
            "eligible": o["eligible_cells"],
            "before_pct": pct(o["g0_observed_cells"], o["eligible_cells"]),
            "after_pct": pct(o["g1_observed_cells"], o["eligible_cells"]),
            "gain_pp": round(100 * (o["g1_observed_cells"] - o["g0_observed_cells"]) / o["eligible_cells"], 2),
            "unobserved": o["eligible_cells"] - o["g1_observed_cells"],
            "archive_bytes_verified": 0,
        },
        "focused_depth": {
            axis: {
                "before": o[axis]["before"], "after": o[axis]["after"],
                "eligible": o[axis]["eligible"],
                "delta_pp": round(100 * (o[axis]["after"] - o[axis]["before"]) /
                                  o[axis]["eligible"], 4),
            }
            for axis in ("statements", "branches")
        },
        "tests": o["tests"],
        "planned_packets": o["scaled_scouts_planned"],
        "maximum_concurrency": o["scout_concurrency_max"],
        "packets_per_repo": o["packets_per_repo_max"],
        "actual_worker_hours": None,
        "runtime_sessions_verified": None,
        "m2_stability": "HOLD", "m3_capability": "HOLD",
        "pca": "NOT_ASSESSABLE", "bradley_terry": "NOT_ASSESSABLE",
        "root_closure_credited": 0,
        "merge_admission": "HOLD", "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
        "authority_transfer": False,
    }


def mermaid(doc):
    parts = ["flowchart LR", '  START["Control input / root + source SHA"]']
    for lane in doc["lanes"]:
        parts.append('  subgraph L_' + re.sub(r"\W", "_", lane["id"]) +
                     '["' + lane["label"].replace('"', "'") + '"]')
        stages = lane["stages"]
        for row in stages:
            key = re.sub(r"\W", "_", lane["id"] + "_" + row[0])
            title = (row[0] + " · " + row[1]).replace('"', "'")
            parts.append('    ' + key + '["' + title + '"]')
        parts.append("  end")
        for left, right in zip(stages, stages[1:]):
            a = re.sub(r"\W", "_", lane["id"] + "_" + left[0])
            b = re.sub(r"\W", "_", lane["id"] + "_" + right[0])
            parts.append("  " + a + " --> " + b)
    lane_order = ("SUPPLY", "TRUST", "CENSUS", "DMAIC", "3P*", "MIP", "LDAB", "STAT", "REX", "GATE")
    first = lambda lid: re.sub(r"\W", "_", lid + "_" + next(l["stages"][0][0] for l in doc["lanes"] if l["id"] == lid))
    last = lambda lid: re.sub(r"\W", "_", lid + "_" + next(l["stages"][-1][0] for l in doc["lanes"] if l["id"] == lid))
    parts.append("  START --> " + first("SUPPLY"))
    for a, b in zip(lane_order, lane_order[1:]):
        parts.append("  " + last(a) + " --> " + first(b))
    parts.append('  ' + last("GATE") + ' -. "next pulse, never same-wave cycle" .-> START')
    parts.append("  classDef caution fill:#41331d,stroke:#edb866,color:#f8ead1")
    parts.append("  class " + first("STAT") + "," + first("GATE") + " caution")
    return "\n".join(parts) + "\n"


def svg(doc):
    step_w, step_gap, left, top, rh = 180, 12, 230, 50, 96
    width = left + 6 * (step_w + step_gap) + 24
    height = top + len(doc["lanes"]) * rh + 20
    pieces = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ten federation process swimlanes with thirty-nine stages">'
              '<defs><marker id="lp-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="none" stroke="#8b9cd1"/></marker></defs>']
    for row_index, lane in enumerate(doc["lanes"]):
        y = top + row_index * rh
        pieces.append(f'<rect x="1" y="{y-8}" width="{width-2}" height="{rh-6}" rx="13" fill="{"#151e31" if row_index%2==0 else "#101927"}"/>')
        pieces.append(f'<text x="16" y="{y+25}" fill="#f6f8ff" font-size="17" font-weight="700">{esc(lane["id"])}</text>')
        pieces.append(f'<text x="16" y="{y+45}" fill="#9fb0cb" font-size="12">{esc(lane["kind"])}</text>')
        for j, node in enumerate(lane["stages"]):
            x = left + j * (step_w + step_gap)
            color = "#f0b779" if lane["id"] in ("STAT", "GATE") else "#58cbbb"
            pieces.append(f'<rect x="{x}" y="{y}" width="{step_w}" height="66" rx="10" fill="#202b42" stroke="{color}"/>')
            pieces.append(f'<text x="{x+9}" y="{y+22}" fill="#f5f7ff" font-size="12" font-weight="700">{esc(node[0])}</text>')
            title = node[1]
            short = title[:24] + ("…" if len(title)>24 else "")
            pieces.append(f'<text x="{x+9}" y="{y+45}" fill="#b4c6dd" font-size="11">{esc(short)}</text>')
            if j:
                pieces.append(f'<path d="M{x-step_gap+1} {y+32}H{x-3}" stroke="#849ab5" stroke-width="2" marker-end="url(#lp-arrow)"/>')
    pieces.append("</svg>")
    return "\n".join(pieces)


def build(out, contract_path=None, registry_path=None):
    doc = read_json(contract_path or HERE / "PROCESS_LANES_v1.json")
    registry = read_json(registry_path or HERE / "METHOD_OBSERVABILITY_v1.json")
    verify(doc, registry)
    metrics = summary(doc)
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    (target / "lane-process.mmd").write_text(mermaid(doc), encoding="utf-8")
    (target / "lane-process.json").write_text(
        json.dumps({"contract": doc, "metrics": metrics}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    kpi = metrics["observability"]
    cards = [
        ("Observed breadth", f'{kpi["after"]}/{kpi["eligible"]}', f'{kpi["after_pct"]}% · +{kpi["gain_pp"]} pp over G0'),
        ("Still UNKNOWN", str(kpi["unobserved"]), "Eligible repo × KPI-family cells"),
        ("Focused statements", f'{doc["observation"]["statements"]["after"]}/93',
         f'+{metrics["focused_depth"]["statements"]["delta_pp"]:.2f} pp; same source'),
        ("Focused branches", f'{doc["observation"]["branches"]["after"]}/26',
         f'+{metrics["focused_depth"]["branches"]["delta_pp"]:.2f} pp; same source'),
        ("Expanded native tests", str(metrics["tests"]["passed_candidate"]) + "/" + str(metrics["tests"]["candidate"]),
         "Narrow G4 only · no fleet coverage claim"),
        ("Archive-byte verified", "0", "Upload digest exists; ZIP bytes not independently examined"),
    ]
    cards_html = "".join(
        f'<article class="card"><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></article>'
        for label, value, note in cards
    )
    sipoc_html = "".join(
        f'<article class="sipoc"><b>{esc(x["key"])} · {esc(x["name"])}</b>'
        f'<p>{esc(x["detail"])}</p><small>{esc(x["constraint"])}</small></article>'
        for x in doc["sipoc"]
    )
    leaves = []
    for lane in doc["lanes"]:
        detail = "".join(
            f'<details class="leaf"><summary><b>{esc(s[0])}</b> · {esc(s[1])}</summary>'
            f'<dl><dt>Input</dt><dd>{esc(s[2])}</dd><dt>Output</dt><dd>{esc(s[3])}</dd>'
            f'<dt>KPI / pressure</dt><dd><code>{esc(s[4])}</code></dd>'
            f'<dt>Stop / HOLD</dt><dd>{esc(s[5])}</dd></dl></details>'
            for s in lane["stages"]
        )
        leaves.append(
            f'<section class="lane" data-lane="{esc(lane["id"])}"><h3>{esc(lane["id"])} · {esc(lane["label"])}</h3>'
            f'<p class="owner">Owner: {esc(lane["owner"])} · {esc(lane["kind"])} · '
            f'{len(lane["stages"])} nodes</p>{detail}</section>'
        )
    options = '<option value="ALL">All lanes</option>' + "".join(
        f'<option value="{esc(l["id"])}">{esc(l["id"])} · {esc(l["label"])}</option>'
        for l in doc["lanes"]
    )
    style = """
:root{color-scheme:dark;font-family:system-ui,Segoe UI,Arial,sans-serif;background:#0b1220;color:#e8f0fb}
*{box-sizing:border-box}body{margin:auto;max-width:1680px;padding:30px}
h1{font-size:clamp(26px,3vw,42px);margin:8px 0}h2{margin-top:36px}p{line-height:1.55}
a{color:#9fcbfa}a:focus-visible,button:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #e7bd70}
.kicker,.small,.owner{color:#aebcd0;font-size:13px}
.links{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.links a{border:1px solid #3b546f;padding:9px 12px;border-radius:9px;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:12px}
.card,.sipoc,.lane,.call{background:#162337;border:1px solid #354961;border-radius:13px;padding:18px}
.card span,.card small{display:block;color:#acbed2;font-size:13px}.card strong{display:block;font-size:30px;color:#7be0d2;margin:9px 0}
.sipoc b{color:#d2e3fb}.sipoc p{font-size:13px}.sipoc small{color:#f2bd76}
.scroll{overflow:auto;background:#0e1a2b;border:1px solid #33475d;border-radius:12px;padding:10px}
svg{width:100%;min-width:1150px;height:auto}select{padding:10px;background:#243750;color:#fff;border-radius:8px;border:1px solid #6a86a6}
.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px;margin-top:18px}
.lane{padding:16px}.lane h3{margin:0}.leaf{border-top:1px solid #34465b;padding:9px 0}
.leaf summary{cursor:pointer;line-height:1.5}.leaf dl{display:grid;grid-template-columns:110px 1fr;gap:6px;margin:10px 0}
dt{color:#9cb0c7}dd{margin:0;overflow-wrap:anywhere;font-size:13px}
code{color:#bce3f6}.call{border-color:#745f47;background:#211e25}
table{border-collapse:collapse;width:100%;margin-top:14px}th,td{padding:11px;border-bottom:1px solid #3d4c60;text-align:left}
footer{border-top:1px solid #364861;margin-top:35px;padding-top:20px;color:#acbed2}
@media(max-width:720px){body{padding:14px}.lanes{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""
    gates = [
        ("P5", "ABACUS #1998", "Native repaired-head tests + scope proof", "HOLD / latest source readback required"),
        ("P6", "Mission Control #530/#531", "ZIP member bytes + native receipt join", "HOLD / upload metadata only"),
        ("P7", "Six-repository scout scale", "6 packets, ≤2 concurrent, 1 per repo", "PLANNED / no authenticated worker census"),
        ("P8", "Statistical maturity", "M1 validity → M2 control → M3 capability", "HOLD / PCA and BT unassessable"),
        ("P9", "REX exact-main recurrence", "Root control + required checks + qualified owner", "HOLD / zero formal closure"),
    ]
    gates_html = "".join(f'<tr><th>{esc(g[0])}</th><td>{esc(g[1])}</td><td>{esc(g[2])}</td><td>{esc(g[3])}</td></tr>' for g in gates)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mission Control — SIPOC and granular lane control</title><style>{style}</style></head>
<body><div class="kicker">CODE PURPLE · Mission Control · READ-ONLY / HISTORICAL EVIDENCE</div>
<h1>Federation process · SIPOC to exact-main CONTROL</h1>
<p>This is a source-bound process projection, not a live engineering acceptance dashboard.
Canonical methods remain in METHOD_OBSERVABILITY_v1.json; REX/Census and statistics are overlays.
Dotted next-pulse feedback does not create a same-pulse dependency cycle.</p>
<nav class="links" aria-label="Related publications"><a href="index.html">Federation atlas</a>
<a href="code-purple.html">CODE PURPLE queue</a>
<a href="phase02-temporal.html">Temporal statistics</a>
<a href="federation.svg">Existing topology</a><a href="lane-process.mmd">Mermaid source</a>
<a href="lane-process.json">Machine-readable contract</a></nav>
<h2>Observed pulse KPIs · G4 exact PR-head sample</h2><div class="grid">{cards_html}</div>
<p class="small">Source: {esc(metrics["source_repo"])} @ {esc(metrics["source_sha"])} ·
native run {esc(metrics["run_id"])} / job {esc(metrics["job_id"])} · artifact {esc(metrics["artifact_id"])}.
Source-reported count and terminal native test log; uploaded ZIP checksum is NOT a downloaded-byte attestation.
No effective cross-repo admission.</p>
<h2>SIPOC · what flows into which decision</h2><div class="grid">{sipoc_html}</div>
<h2>Granular lane execution map</h2><p class="small">{metrics["lane_count"]} lanes ·
{metrics["node_count"]} named nodes. Each row runs left to right; downstream lanes consume receipts,
never inherited green statuses.</p><div class="scroll">{svg(doc)}</div>
<h2>Node / leaf evidence and control pressures</h2><label for="lane-select">Show process lane:
</label> <select id="lane-select">{options}</select><div class="lanes">{''.join(leaves)}</div>
<h2>Next controlled pulse gates</h2><div class="scroll"><table>
<thead><tr><th>Gate</th><th>Owner</th><th>Evidence required</th><th>Disposition</th></tr></thead>
<tbody>{gates_html}</tbody></table></div>
<section class="call"><h2>Pressure and statistical constraints</h2>
<p><b>Depth</b>: same source SHA, tool version and eligible statements/branches;
not comparable with full-repository coverage.
<b>Breadth</b>: 42 eligible repo-family cells, 6 status/metadata observations; 36 UNKNOWN.
<b>Convergence</b>: root transitions and repeated fingerprint pairs, not raw-count subtraction.
<b>Throughput</b>: actual worker-hours and queue timestamps required; both currently UNKNOWN.
<b>M2/M3</b>: independent control windows and defensible limits before stability/capability claims.
<b>PCA</b> requires matched numeric vectors. <b>Bradley–Terry</b> requires observed comparable
pairwise wins/losses. <b>3P*</b> remains advisory until the native admission transaction.
<b>REX</b> closes only after exact-main post-control recurrence evidence.</p></section>
<footer>Historical source-bound sample. Formal credit 0 · engineering credit 0 ·
security waiver false · authority transfer false · merge admission HOLD.
No new dispatch, signed attestation, merge, or GitHub Pages deployment.</footer>
<script>
const select=document.getElementById("lane-select");
select.addEventListener("change",()=>{{
  document.querySelectorAll(".lane").forEach(item=>{{
    item.hidden=select.value!=="ALL" && item.dataset.lane!==select.value;
  }});
}});
</script></body></html>"""
    (target / "lane-process.html").write_text(page, encoding="utf-8")
    return metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args()
    print(json.dumps(build(args.out), sort_keys=True))


if __name__ == "__main__":
    main()
