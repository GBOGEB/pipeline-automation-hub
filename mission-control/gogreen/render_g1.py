"""Monochrome G1 federation dashboard from a *frozen* source-bound rollup.

No GitHub API access, no mutation, no claim that SOURCE_DISCOVERED is NATIVE.
Generated HTML is an L3 presentation of rollup.json; it is never an SSOT.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
SCHEMA = "gogreen.federation.rollup.v1"


def verify(report, source_sha):
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise ValueError("wrong source rollup schema")
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ValueError("exact producer source SHA required")
    if report.get("admission") != "HOLD" or report.get("merge_authorized") is not False:
        raise ValueError("presentation cannot promote admission")
    if report.get("authority_transfer") is not False or report.get("worker_dispatches") != 0:
        raise ValueError("untrusted owner/worker authority")
    stats = report.get("breadth_depth")
    if not isinstance(stats, dict) or stats.get("repositories") != 6:
        raise ValueError("six-repository G1 snapshot required")
    dimension = ("target_repo_surface_cells", "source_discovered_cells",
                 "native_status_verified_cells", "artifact_bytes_verified_cells",
                 "unknown_cells")
    if any(type(stats.get(k)) is not int for k in dimension):
        raise ValueError("numeric counts required, unknown must not become zero")
    total, discovered, native, byte_proof, unknown = [stats[k] for k in dimension]
    if total != 66 or not (0 <= byte_proof <= native <= discovered <= total) or unknown != total-discovered:
        raise ValueError("66-cell cohort or nested evidence dimensions invalid")
    surface = report.get("surfaces")
    if not isinstance(surface, dict) or len(surface) != 11:
        raise ValueError("11 named surface families required")
    for key, row in surface.items():
        if not isinstance(key, str) or not isinstance(row, dict):
            raise ValueError("invalid surface group")
        if any(type(row.get(c)) is not int for c in (
            "target_cells", "source_discovered", "native_status_verified",
            "artifact_bytes_verified", "unknown")):
            raise ValueError("invalid grouped denominator")
        if row["target_cells"] != 6 or row["source_discovered"]+row["unknown"] != 6:
            raise ValueError("grouped census mismatch")
    return stats


def render(report, source_sha, rollup_sha256):
    stats = verify(report, source_sha)
    if not re.fullmatch(r"[0-9a-f]{64}", rollup_sha256):
        raise ValueError("invalid source report digest")
    escape = lambda v: html.escape(str(v), quote=True)
    total = stats["target_repo_surface_cells"]
    measures = [
        ("Source discovered", stats["source_discovered_cells"]),
        ("Native status", stats["native_status_verified_cells"]),
        ("Verified artifact bytes", stats["artifact_bytes_verified_cells"]),
    ]
    cards, bars = [], []
    for title, value in measures:
        pct = round(value*100/total, 2)
        cards.append(f'<section class="card"><p class="dim">{escape(title)}</p><strong>{value}/{total}</strong><p class="dim">{pct:.2f}%</p></section>')
        bars.append(f'<section class="metric"><div class="flex"><b>{escape(title)}</b><span>{value}/{total} ({pct:.2f}%)</span></div><div class="track" role="img" aria-label="{escape(title)} {value} of {total}"><div class="fill" style="width:{pct:.2f}%"></div></div></section>')
    rows = []
    for name, row in sorted(report["surfaces"].items()):
        rows.append(f'<tr><th scope="row">{escape(name)}</th><td>{row["source_discovered"]}/6</td><td>{row["native_status_verified"]}/6</td><td>{row["artifact_bytes_verified"]}/6</td><td>{row["unknown"]}/6</td></tr>')
    return ("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><title>MissionControl — G1 federation evidence</title>
<style>:root{color-scheme:dark;--bg:#0c0c0c;--fg:#fafafa;--dim:#b9b9b9;--edge:#484848;--track:#292929}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0}
main{max-width:1120px;margin:auto;padding:24px}h1{font-size:1.6rem}h2{font-size:1.1rem;margin-top:28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px}.card{border:1px solid var(--edge);border-radius:8px;padding:12px}
.card strong{font-size:1.65rem}.dim,footer{color:var(--dim);font-size:.86rem}.metric{margin:18px 0}.flex{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.track{height:11px;background:var(--track);border-radius:12px;overflow:hidden}.fill{height:100%;background:#aaa}
.scroller{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:600px}th,td{border-bottom:1px solid var(--edge);padding:10px;text-align:right}th:first-child{text-align:left}
footer{border-top:1px solid var(--edge);padding-top:14px;overflow-wrap:anywhere}
@media (prefers-color-scheme:light){:root{--bg:white;--fg:#111;--dim:#555;--edge:#ddd;--track:#eee}.fill{background:#555}}
</style></head><body><main><h1>MissionControl — G1 source-bound federation census</h1>
<p>Six repositories × eleven fixed surfaces. Source discovery, native status and independent artifact bytes are <b>different measurement layers</b>.</p>
<div class="grid">""" + "".join(cards) + """</div><h2>Coverage depth and breadth</h2>""" + "".join(bars) + """
<h2>Source surface groups</h2><div class="scroller"><table><thead><tr><th>Surface</th><th>Discovered</th><th>Native</th><th>Byte proof</th><th>Unknown</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table></div>
<h2>Decision</h2><p>HOLD — source discoveries are not authenticated runs; a producer artifact is not a consumer acceptance or an independent reviewer.</p>
<footer>Source pulse: """ + escape(report["pulse_id"]) + """ · Report observed UTC: """ + escape(report["observed_at_utc"]) +
"""<p>Producer exact SHA: <code>""" + escape(source_sha) + """</code> · Canonical rollup SHA-256: <code>""" + escape(rollup_sha256) + """</code></p>
<p>QPS disposition: DEFER · Worker launch: 0 · Authority transfer: false</p></footer></main></body></html>""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollup", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    a = ap.parse_args()
    raw = a.rollup.read_bytes()
    report = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    output = render(report, a.source_sha, digest)
    a.out.write_text(output, encoding="utf-8")
    print(json.dumps({"schema": "gogreen.g1.html-render.v1",
                      "source_sha": a.source_sha, "rollup_sha256": digest,
                      "generated_html_sha256": hashlib.sha256(output.encode()).hexdigest(),
                      "merge_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
