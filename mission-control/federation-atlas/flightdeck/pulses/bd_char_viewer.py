#!/usr/bin/env python3
"""Generate a read-only BD/CHAR HTML projection from a dated GitHub census."""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
SCHEMA = "code-purple.bd-char.sfed-pulse.v1"
COUNT_KEYS = ("success", "failure", "cancelled", "nonterminal")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def validate(d):
    require(isinstance(d, dict) and d.get("schema") == SCHEMA, "invalid schema")
    a = d.get("authority", {})
    require(a.get("merge_admission") == "HOLD"
            and a.get("security_waiver") is False
            and a.get("authority_transfer") is False
            and a.get("dispatch") == "STAGED_NOT_LAUNCHED"
            and a.get("qps_decision") == "DEFER"
            and all(a.get(k) is None for k in (
                "accepted_root_open", "accepted_root_closed",
                "accepted_root_reopened", "accepted_rex",
                "hosted_publication_verified")), "authority inversion")
    for s in d.get("main_heads", {}).values():
        require(isinstance(s, str) and SHA.fullmatch(s), "invalid main SHA")
    rows = d.get("pr_rows")
    require(isinstance(rows, list) and rows, "missing PR census")
    ids = set()
    for r in rows:
        ident = (r.get("repo"), r.get("pr"))
        require(ident not in ids, "duplicate PR observation")
        ids.add(ident)
        require(r.get("repo") == "GBOGEB/ABACUS"
                and type(r.get("pr")) is int and r["pr"] > 0
                and isinstance(r.get("head_sha"), str)
                and SHA.fullmatch(r["head_sha"]), "invalid PR identity")
        require(r.get("scope") == "PR_HEAD_ASSOCIATED_NOT_CHECKOUT_VERIFIED"
                and r.get("status") in ("OPEN", "MERGED_FEATURE_ONLY")
                and r.get("url") ==
                f"https://github.com/GBOGEB/ABACUS/pull/{r['pr']}",
                "invalid PR provenance")
        c = r.get("counts")
        require(isinstance(c, dict) and set(c) == set(COUNT_KEYS)
                and all(type(c[k]) is int and c[k] >= 0 for k in COUNT_KEYS)
                and sum(c.values()) > 0, "invalid workflow counts")
    p = d.get("same_head_pulse", {})
    match = [r for r in rows if r["pr"] == p.get("pr")]
    require(len(match) == 1 and match[0]["head_sha"] == p.get("source_sha"),
            "temporal SHA drift")
    rr = p.get("run_ids", [])
    require(len(rr) == 8 and len(set(rr)) == 8
            and all(type(k) is int and k > 0 for k in rr),
            "run identity not paired")
    for moment in ("before", "after"):
        c = p.get(moment, {})
        require(set(c) == set(COUNT_KEYS)
                and all(type(c[k]) is int and c[k] >= 0 for k in COUNT_KEYS)
                and sum(c.values()) == len(rr),
                "unmatched temporal denominator")
    require(p["after"] == match[0]["counts"]
            and p["before"]["nonterminal"] == len(rr)
            and p["after"]["success"] == len(rr),
            "temporal run transition invalid")
    h = d.get("matched_historical_coverage", {})
    b, c = h.get("before", {}), h.get("after", {})
    require(h.get("scope") == "HISTORICAL_C2_PR_UBUNTU_SAME_CONFIG_NOT_MAIN"
            and b.get("eligible") == c.get("eligible")
            and type(b.get("covered")) is int
            and type(c.get("covered")) is int
            and 0 <= b["covered"] <= b["eligible"]
            and 0 <= c["covered"] <= c["eligible"]
            and h.get("current_main") is None
            and h.get("current_pr_diff") is None, "coverage population drift")
    root_ids = set()
    for f in d.get("candidate_families", []):
        require(f.get("id") not in root_ids, "duplicate root family")
        root_ids.add(f.get("id"))
        require(f.get("priority") in ("P0", "P1", "P2", "P3")
                and f.get("accepted_closure") is None
                and f.get("qualification") == "CANDIDATE_NOT_ADMITTED"
                and f.get("url", "").startswith("https://github.com/GBOGEB/"),
                "invented causal closure")
    require(d.get("statistical_admission", {}).get("process_stability") == "HOLD",
            "invalid statistical admission")
    return d


def _esc(value):
    return html.escape(str(value), quote=True)


def render(d, source_sha256):
    validate(d)
    rows = d["pr_rows"]
    totals = {k: sum(r["counts"][k] for r in rows) for k in COUNT_KEYS}
    observed = sum(totals.values())
    n, after = d["same_head_pulse"]["before"], d["same_head_pulse"]["after"]
    transitioned = after["success"] - n["success"]
    cov = d["matched_historical_coverage"]
    added = cov["after"]["covered"] - cov["before"]["covered"]
    pp = 100 * added / cov["before"]["eligible"]
    cards = "".join(
        '<div class="metric"><small>' + name + '</small><strong>' + val
        + '</strong><span>' + sub + '</span></div>'
        for name, val, sub in [
            ("Terminal successes", str(totals["success"]) + "/" + str(observed),
             "PR-associated workflow records, not independent trials"),
            ("Observed failure runs", str(totals["failure"]),
             "Distinct workflow runs, not deduplicated roots"),
            ("N to N+1, same SHA", "+" + str(transitioned),
             "Eight #2063 runs finished successfully"),
            ("Formal root open / closed", "UNKNOWN",
             "Authoritative denominator not established"),
        ]
    )
    row_html = []
    for r in rows:
        c = r["counts"]
        name = _esc(r["lane"])
        total = sum(c.values())
        fraction = 100 * c["success"] / total
        row_html.append(
            '<tr data-lane="' + name + '"><td><a href="' + _esc(r["url"])
            + '" target="_blank" rel="noopener noreferrer">#'
            + str(r["pr"]) + '</a><div class="muted">'
            + _esc(r["base"]) + '</div></td><td>' + name
            + '<div class="sha">' + _esc(r["head_sha"][:16])
            + '…</div></td><td><div class="bar"><i style="width:'
            + f"{fraction:.3f}%" + '"></i></div><small>'
            + f'{c["success"]}/{total} pass · {c["failure"]} fail · '
            + f'{c["cancelled"]} cancelled · {c["nonterminal"]} pending'
            + '</small></td><td>' + _esc(r["first_red"].replace("_", " "))
            + '</td><td>' + _esc(r["status"].replace("_", " ")) + '</td></tr>'
        )
    root_html = []
    for r in sorted(d["candidate_families"], key=lambda x: (x["priority"], x["id"])):
        root_html.append(
            '<tr><td><b>' + _esc(r["priority"]) + '</b></td><td>'
            + _esc(r["id"]) + '</td><td>' + _esc(r["owner"])
            + '</td><td>' + _esc(r["proof"].replace("_", " "))
            + '</td><td><a href="' + _esc(r["url"])
            + '" target="_blank" rel="noopener noreferrer">Source ↗</a>'
            + '</td></tr>'
        )
    options = "".join('<option value="' + _esc(s) + '">'
                      + _esc(s.replace("_", " ")) + '</option>'
                      for s in sorted({r["lane"] for r in rows}))
    actions = "".join('<li>' + _esc(s) + '</li>' for s in d["next_actions"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="bd-source-sha256" content="{source_sha256}">
<title>CODE PURPLE · BD / CHAR Pulse</title>
<style>
:root {{color-scheme:dark;--bg:#0b1220;--panel:#17233a;--line:#35455d;--ink:#eef5ff;--muted:#b2c2d7;--accent:#87e7c0;--warn:#ffca88;}}
* {{box-sizing:border-box}} body {{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif;}}
main {{max-width:1380px;margin:0 auto;padding:24px}} h1 {{font-size:clamp(26px,4vw,44px);letter-spacing:-.035em;margin:10px 0}}
h2 {{margin:0 0 14px;font-size:21px}} a {{color:#9fc8ff}} .muted,small {{color:var(--muted)}} .sha {{font:12px monospace;color:var(--muted);overflow-wrap:anywhere}}
.deck {{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:24px 0}} .metric,section {{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}
.metric strong {{display:block;font-size:clamp(26px,3vw,36px);color:var(--accent)}} .metric span {{display:block;font-size:12px;color:var(--muted)}}
section {{margin:14px 0}} .note {{color:var(--warn)}} table {{border-collapse:collapse;width:100%;min-width:720px}}
th,td {{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} th {{color:var(--muted);font-size:12px}}
.scroll {{overflow-x:auto}} .bar {{background:#31425c;height:9px;border-radius:10px;overflow:hidden;width:160px;max-width:100%;margin-bottom:6px}}
.bar i {{display:block;background:var(--accent);height:100%;}} select,input {{padding:9px 11px;border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:8px}}
nav {{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:15px 0}} .pill {{color:var(--warn);border:1px solid #94734b;padding:5px 12px;border-radius:20px}}
@media(max-width:950px){{.deck{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:520px){{main{{padding:12px}}.deck{{grid-template-columns:1fr 1fr;gap:6px}}.metric{{padding:10px}}.metric strong{{font-size:23px}}}}
</style></head><body><main>
<nav><a href="../index.html">← Mission Control</a><span class="pill">P0 HOLD · QPS DEFER</span></nav>
<header><p class="muted">GBOGEB / MissionControl · 16 October 2026 · Supporting observation P2</p>
<h1>CODE PURPLE · BD / CHAR flight deck</h1>
<p>Central/disjoint census · measured temporal transitions · canonical owners · governed next actions</p>
<p class="note">This is an offline, date-bound read-only projection. GH Actions workflow records are not Crew launches, PR-associated runs are not exact-checkout proof, and formal causal closures remain UNKNOWN.</p>
</header>
<div class="deck">{cards}</div>
<section><h2>What actually improved?</h2>
<p>Same exact PR #2063 head, same eight native run IDs: <b>{n['nonterminal']}/8 nonterminal → {after['success']}/8 terminal successes</b>. Terminal resolution +{transitioned} workflows. The changed-docs lint workflow is absent from that triggered set; source repair is not yet independently certified.</p>
<p>Historical matched C2 PR broad coverage: {cov['before']['covered']:,}/{cov['before']['eligible']:,} → {cov['after']['covered']:,}/{cov['after']['eligible']:,}, <b>+{added} statements / +{pp:.2f} percentage points</b>. This is historical PR-only evidence; latest main and PR diff uplift UNKNOWN.</p>
</section>
<section><h2>Native PR workflow census</h2>
<nav><label for="filter">Lane:</label><select id="filter"><option value="">All lanes</option>{options}</select>
<label for="search">Search:</label><input id="search" type="search" placeholder="PR, root or SHA" aria-label="Filter evidence">
<small id="shown">{len(rows)} / {len(rows)} records</small></nav>
<div class="scroll"><table id="runs"><thead><tr><th>PR / base</th><th>Lane / head</th><th>Workflow outcomes</th><th>First-red / limitation</th><th>PR state</th></tr></thead>
<tbody>{''.join(row_html)}</tbody></table></div>
<p class="muted">Cohort = {len(rows)} explicitly selected PR heads; {observed} PR-associated workflow records. Not a complete GitHub fleet or independent reliability study. #2060 was merged to a feature branch, not ABACUS main.</p>
</section>
<section><h2>BD / CHAR — candidate root-family work order</h2>
<p class="muted">Eight attributable candidate families, not eight verified open engineering roots. No source row is authorized to close a root.</p>
<div class="scroll"><table><thead><tr><th>Priority</th><th>Candidate family</th><th>Owner</th><th>Definition of verification</th><th>Evidence</th></tr></thead><tbody>{''.join(root_html)}</tbody></table></div></section>
<section><h2>Next admissible CBD! / DMAIC / MIP pulses</h2><ol>{actions}</ol>
<p>Statistical qualification: M2 process stability HOLD, PCA NOT QUALIFIED, Bradley–Terry NOT QUALIFIED. N+2 forecast not issued without timestamped pre-outcome prediction.</p></section>
<section><h2>Evidence lineage</h2><p class="sha">Source JSON SHA-256: {source_sha256}</p>
<p class="sha">ABACUS main: {_esc(d['main_heads']['ABACUS'])}<br>
CODEX main: {_esc(d['main_heads']['CODEX'])}<br>
MissionControl parent: {_esc(d['main_heads']['MissionControl'])}</p>
<p><a href="snapshot.json">Open frozen read-only JSON</a> · <a href="manifest.json">View generation digests</a> · <a href="https://github.com/GBOGEB/ABACUS/issues/1929">Root/evidence authority #1929</a></p></section>
</main><script>
'use strict';
const sel=document.getElementById('filter'),q=document.getElementById('search'),rows=[...document.querySelectorAll('#runs tbody tr')];
function apply(){{let n=0;for(const row of rows){{const ok=(!sel.value||sel.value===row.dataset.lane)&&row.textContent.toLowerCase().includes(q.value.trim().toLowerCase());row.hidden=!ok;if(ok)n++}}document.getElementById('shown').textContent=n+' / '+rows.length+' records'}}
sel.addEventListener('change',apply);q.addEventListener('input',apply);
</script></body></html>"""


def produce(source, out):
    source, out = Path(source), Path(out)
    raw = source.read_bytes()
    d = validate(json.loads(raw))
    out.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    (out / "index.html").write_text(render(d, digest), encoding="utf-8")
    (out / "snapshot.json").write_bytes(raw)
    files = {n: hashlib.sha256((out / n).read_bytes()).hexdigest()
             for n in ("index.html", "snapshot.json")}
    receipt = {"schema": "code-purple.bd-char.view-receipt.v1",
               "source_sha256": digest, "artifacts": files,
               "qa_grade": "LOCAL_REPRODUCIBILITY_PENDING_BROWSER",
               "authority_transfer": False, "merge_admission": "HOLD",
               "native_source_acceptance": None}
    (out / "manifest.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(produce(a.source, a.out), sort_keys=True))


if __name__ == "__main__":
    main()
