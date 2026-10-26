#!/usr/bin/env python3
"""Render the EVERRED 3.0 register page from everred.json (harvest.py) and the Code Purple census.

Usage: python build_page.py [--report everred.json] [--census census.json] [--out site/everred/index.html]
Defaults resolve from this file: fresh out/ files first, then the committed site snapshot.
"""
import argparse
import html
import json
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parent
REPO_OF = {"ABACUS": "GBOGEB/ABACUS", "CODEX": "GBOGEB/CODEX", "CRYO": "GBOGEB/cryoplant-project", "GGMATH": "GBOGEB/gg_MATH",
           "PAH": "GBOGEB/pipeline-automation-hub", "QET": "GBOGEB/Q_engineering_tools", "EVR": "GBOGEB/ABACUS"}
DIMS = ["diagnosis", "repair", "integration", "security", "governance", "admission", "control"]
GOOD = {"CONFIRMED", "PRODUCER_VERIFIED", "CONSUMERS_VERIFIED", "EXACT_HEAD_PASSED", "GREEN", "EFFECTIVE", "ADMITTED", "CONTROLLED", "NA"}
BAD = {"UNRESOLVED", "NONE", "RED", "INEFFECTIVE", "HOLD", "UNCONTROLLED", "BLOCKED"}


def first(*cands):
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    raise SystemExit(f"none of {cands} exists: run harvest.py / readback.py first")


ap = argparse.ArgumentParser()
ap.add_argument("--report")
ap.add_argument("--census")
ap.add_argument("--out", default=str(ROOT / "site/everred/index.html"))
a = ap.parse_args()
rep = json.loads(first(a.report, D / "out/everred.json", ROOT / "site/everred/data/everred.json").read_text())
cp = json.loads(first(a.census, ROOT / "kit/out/census.json", ROOT / "site/code-purple/kit/census.json").read_text())
m = rep["metrics"]
aa = cp.get("admission_audit", {})
esc = html.escape

STATES = ["DISCOVERED", "TRIAGED", "OWNED", "FIX_COMMITTED", "PRODUCER_GREEN", "CONSUMERS_REPLAYED", "VERIFIED_FIXED", "CLOSED"]
SIDE = ["BLOCKED_AUTHORITY", "BLOCKED_INFRA", "BLOCKED_DEPENDENCY", "REOPENED"]
CLASS_LABEL = {"PRODUCT_DEFECT": "Product defect", "TEST_OR_MEASUREMENT_DEFECT": "Test / measurement", "GENERATED_ARTIFACT_DRIFT": "Generated drift",
               "INFRA_ENV_DEFECT": "Infra / env", "EXISTING_REPOSITORY_DEBT": "Repository debt", "SECURITY_OR_POLICY": "Security / policy",
               "CONTROL_PLANE_DRIFT": "Control-plane drift"}
indep = [r for r in rep["roots"] if not r.get("derived")]
count = {s: sum(1 for r in indep if r["state"] == s) for s in STATES + SIDE}


def state_cls(s):
    return {"VERIFIED_FIXED": "ok", "CLOSED": "ok", "PRODUCER_GREEN": "partial", "CONSUMERS_REPLAYED": "partial", "FIX_COMMITTED": "prog",
            "OWNED": "prog", "TRIAGED": "todo", "DISCOVERED": "todo", "BLOCKED_AUTHORITY": "block", "BLOCKED_INFRA": "block",
            "BLOCKED_DEPENDENCY": "block", "REOPENED": "block"}.get(s, "todo")


pipe = "".join(f'<li class="{"has" if count[s] else ""}"><b>{count[s]}</b><span>{s.replace("_", " ").title()}</span></li>' for s in STATES)
side = "".join(f'<span class="st {state_cls(s)}">{s.replace("_", " ").title()} · {count[s]}</span>' for s in SIDE if count[s])

rows = []
for r in rep["roots"]:
    repo = REPO_OF.get(r["id"].split("-")[0], "GBOGEB/ABACUS")
    prs = ", ".join(f'<a href="https://github.com/{repo}/pull/{n}">#{n}</a>' for n in r["affected_prs"][:10])
    dims = "".join(f'<span class="dim {"g" if v in GOOD else "r" if v in BAD else "u"}" title="{k}">{k[:3]} · {esc(v.replace("_", " ").lower())}</span>'
                   for k, v in (r.get("dims") or {}).items())
    more = f' +{len(r["affected_prs"]) - 10}' if len(r["affected_prs"]) > 10 else ""
    probe = r.get("probe")
    ev = "".join(f"<li>{esc(e)}</li>" for e in r.get("evidence", []))
    rows.append(f"""<tr id="{r['id'].lower()}" class="sev-{r.get('severity', 'P3').lower()}">
      <td class="id">{r['id']}{'<br><span class="tag">derived</span>' if r.get('derived') else ''}</td>
      <td><b>{esc(r['title'])}</b><div class="dims">{dims}</div><details><summary>Evidence, repair, contract</summary><ul>{ev}</ul>
        <p><i>Canonical repair:</i> {esc(r.get('canonical_repair') or '—')}</p><p><i>Regression contract:</i> {esc(r.get('regression_contract') or '—')}</p>{f"<p><i>Note:</i> {esc(r['note'])}</p>" if r.get('note') else ''}</details></td>
      <td><span class="sev">{r.get('severity', '—')}</span></td>
      <td>{CLASS_LABEL.get(r['class'], r['class'])}</td>
      <td><span class="st {state_cls(r['state'])}">{r['state'].replace('_', ' ').title()}</span></td>
      <td>{esc(r.get('owner') or 'unowned')}</td>
      <td class="num">{r['occurrences']}{f'<div class="probe {"red" if probe["red"] else "green"}">probe {"RED" if probe["red"] else "green"}</div>' if probe else ''}</td>
      <td class="prs">{prs}{more or ''}{'' if prs else '—'}</td></tr>""")

un = "".join(f"""<tr><td class="sig">{esc(u['signature'])}</td><td>{', '.join(x.split('/')[1] for x in u['repos'])}</td><td class="num">{u['occurrences']}</td>
  <td class="prs">{', '.join('#' + str(n) for n in u['prs'][:6]) or 'main'}</td><td><a href="{u['example_url']}">run</a></td></tr>""" for u in rep["unmatched"])


red_cp = [r for r in rep["roots"] if (r.get("probe") or {}).get("red")]
p0 = "".join(f'''<div class="p0"><b>{esc(r.get("severity", "P0"))} · <a href="#{r["id"].lower()}">{r["id"]}</a> · control-plane drift on {esc(REPO_OF.get(r["id"].split("-")[0], "?").split("/")[1])}</b>
<span>{esc(r["probe"]["detail"])}. {esc(r.get("canonical_repair") or "")}</span></div>''' for r in red_cp if r.get("severity") == "P0")
if red_cp:
    p0 += (f'<p class="muted" style="margin-top:8px;font-size:13.5px">{len(red_cp)} of {m.get("control_plane_probed", len(red_cp))} repositories fail the ruleset probe. '
           f'ABACUS admission since #1858: {aa.get("merged", "?")} merged, PR Feedback Gate green on {aa.get("gate_green", "?")}, {aa.get("with_red_checks", "?")} with red checks.</p>')
dimrows = "".join(f"<tr><th>{d}</th>" + "".join(f'<td><span class="dim {"g" if k in GOOD else "r" if k in BAD else "u"}">{esc(k.replace("_", " ").lower())}</span> <b>{v}</b></td>'
                  for k, v in sorted(m.get("dims", {}).get(d, {}).items(), key=lambda kv: -kv[1])) + "</tr>" for d in DIMS)


def mv(k):
    v = m[k]
    return "UNKNOWN" if v == "UNKNOWN" else v


page = f"""<title>EVERRED Register</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: register sheet. P0 banner, metric strip, root lifecycle pipeline, root ledger, candidate signatures, standard addendum. */
:root{{--bg:#f6f5f8;--surface:#fff;--surface-2:#efedf3;--ink:#1c1626;--muted:#625a70;--line:#dcd6e4;--line-2:#c5bcd2;
--accent:#5a2a86;--accent-soft:#ece3f6;--red:#c9405f;--red-bg:#fce7ec;--red-ink:#8f2747;--amber:#c98f2e;--amber-bg:#fff2db;--amber-ink:#7c5118;
--green:#3f9b6c;--green-bg:#e0f4e9;--green-ink:#145c43;--teal:#2f8f95;--teal-bg:#dff1f2;--teal-ink:#135458;
--f-body:"Aptos","IBM Plex Sans",system-ui,sans-serif;--f-display:"Archivo","Aptos Display",Arial,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#121017;--surface:#1a1722;--surface-2:#231f2d;--ink:#ece8f3;--muted:#a69db4;--line:#322c3d;--line-2:#463e54;
--accent:#b98ce6;--accent-soft:#2c2240;--red:#e0718f;--red-bg:#3a1c26;--red-ink:#f5b8c9;--amber:#d9a24a;--amber-bg:#35280f;--amber-ink:#f1d39d;
--green:#55b383;--green-bg:#15301f;--green-ink:#a8e2c2;--teal:#45a9ae;--teal-bg:#11302f;--teal-ink:#a2dfe2;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#121017;--surface:#1a1722;--surface-2:#231f2d;--ink:#ece8f3;--muted:#a69db4;--line:#322c3d;--line-2:#463e54;
--accent:#b98ce6;--accent-soft:#2c2240;--red:#e0718f;--red-bg:#3a1c26;--red-ink:#f5b8c9;--amber:#d9a24a;--amber-bg:#35280f;--amber-ink:#f1d39d;
--green:#55b383;--green-bg:#15301f;--green-ink:#a8e2c2;--teal:#45a9ae;--teal-bg:#11302f;--teal-ink:#a2dfe2;color-scheme:dark}}
*{{box-sizing:border-box}} body{{background:var(--bg);color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.55}}
.wrap{{max-width:1320px;margin:0 auto;padding-inline:20px;padding-block:26px 60px}}
h1,h2{{font-family:var(--f-display);margin:0;text-wrap:balance}} h1{{font-size:clamp(28px,4vw,40px);font-weight:800}} h2{{font-size:21px;font-weight:800;margin:30px 0 10px}}
.eyebrow{{font-family:var(--f-mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}}
a{{color:var(--accent)}} p{{margin:0}} .muted{{color:var(--muted)}} .mono{{font-family:var(--f-mono);font-size:.9em}}
.p0{{margin:16px 0;border:2px solid var(--red);background:var(--red-bg);color:var(--red-ink);border-radius:10px;padding:14px 18px;display:grid;gap:6px}}
.p0 b{{font-size:17px}}
.kpis{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-top:16px}}
@media (max-width:900px){{.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
.kpi{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:0}}
.kpi b{{display:block;font-family:var(--f-display);font-size:26px;font-weight:800;font-variant-numeric:tabular-nums}}
.kpi small{{color:var(--muted);font-size:12px}}
.pipe{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:4px}}
@media (max-width:900px){{.pipe{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}
.pipe li{{background:var(--surface);border:1px solid var(--line);padding:10px;display:grid;gap:2px;clip-path:polygon(0 0,92% 0,100% 50%,92% 100%,0 100%,6% 50%)}}
.pipe li b{{font-family:var(--f-display);font-size:24px;color:var(--muted)}} .pipe li.has b{{color:var(--accent)}} .pipe li span{{font-size:12px;color:var(--muted)}}
.side{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:10px}} .tbl{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}
th{{font-family:var(--f-mono);font-size:11px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line-2);white-space:nowrap}}
td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
td.id{{font-family:var(--f-mono);font-size:12.5px;color:var(--accent);white-space:nowrap}} td.num{{text-align:right}} td.sig{{font-family:var(--f-mono);font-size:12px;overflow-wrap:anywhere}}
td.prs{{font-size:12.5px;max-width:240px}}
tr.sev-p0 td.id{{box-shadow:inset 4px 0 var(--red)}} tr.sev-p1 td.id{{box-shadow:inset 4px 0 var(--amber)}}
.sev{{font-family:var(--f-mono);font-size:12px}}
.st{{font-family:var(--f-mono);font-size:11px;padding:1px 8px;border-radius:999px;border:1px solid;white-space:nowrap;display:inline-block}}
.st.ok{{background:var(--green-bg);border-color:var(--green);color:var(--green-ink)}} .st.partial{{background:var(--teal-bg);border-color:var(--teal);color:var(--teal-ink)}}
.st.prog{{background:var(--accent-soft);border-color:var(--accent);color:var(--accent)}} .st.todo{{background:var(--surface);border-color:var(--line-2);color:var(--muted)}}
.st.block{{background:var(--red-bg);border-color:var(--red);color:var(--red-ink)}}
.tag{{font-family:var(--f-mono);font-size:10.5px;color:var(--muted)}}
.probe{{font-family:var(--f-mono);font-size:10.5px;margin-top:3px}} .probe.red{{color:var(--red)}} .probe.green{{color:var(--green)}}
details summary{{cursor:pointer;color:var(--muted);font-size:12.5px;margin-top:3px}} details ul{{margin:6px 0;padding-left:18px;font-size:13px}} details p{{font-size:13px;margin-top:4px}}
.add{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}} @media (max-width:900px){{.add{{grid-template-columns:minmax(0,1fr)}}}}
.add .card{{padding:14px 16px}} .add h3{{margin:0 0 6px;font-size:15px}} .add p,.add li{{font-size:13.5px}} .add ul{{margin:4px 0 0;padding-left:18px}}
.add .num-h{{font-family:var(--f-mono);color:var(--accent);margin-right:6px}}
.bar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}}
.btn{{all:unset;cursor:pointer;font-size:13px;padding:5px 11px;border:1px solid var(--line-2);border-radius:6px;background:var(--surface)}} .btn:focus-visible{{outline:2px solid var(--accent)}}
input[type=search]{{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line-2);border-radius:6px;background:var(--surface);color:var(--ink)}}
footer{{margin-top:30px;font-size:12.5px;color:var(--muted)}}
.dims{{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}} .dim{{font-family:var(--f-mono);font-size:10.5px;padding:1px 6px;border-radius:4px;border:1px solid var(--line-2);color:var(--muted)}}
.dim.g{{background:var(--green-bg);color:var(--green-ink);border-color:transparent}} .dim.r{{background:var(--red-bg);color:var(--red-ink);border-color:transparent}} .dim.u{{background:var(--amber-bg);color:var(--amber-ink);border-color:transparent}}
table.dimt td,table.dimt th{{padding:6px 8px}} table.dimt td b{{font-family:var(--f-mono);font-size:12px;font-weight:500}}
</style>
<div class="wrap">
<div class="eyebrow">EVERRED 3.0 · root-cause register · ABACUS · CODEX · cryoplant-project · census {esc(rep['generated_at'])}</div>
<h1>EVERRED Register</h1>
<p class="muted" style="max-width:80ch;margin-top:6px">One verified root cause, one canonical repair owner, one controlled repair, all affected consumers revalidated. Occurrences are harvested from GitHub; roots are triaged by people. Primary register: <a href="https://github.com/GBOGEB/ABACUS/issues/1860">ABACUS #1860</a>.</p>

{p0}

<div class="kpis">
 <div class="kpi"><span class="eyebrow">Occurrences</span><b>{m['occurrences_total']}</b><small>main head + nightly, open PRs, last 20 merged</small></div>
 <div class="kpi"><span class="eyebrow">Signatures</span><b>{m['distinct_signatures']}</b><small>{m['unmatched_signatures']} not yet linked to a root</small></div>
 <div class="kpi"><span class="eyebrow">Independent roots</span><b>{m['roots_independent']}</b><small>{m['roots_triaged_or_later']} triaged or later</small></div>
 <div class="kpi"><span class="eyebrow">Failure amplification</span><b>{mv('failure_amplification')}</b><small>occurrences per triaged root</small></div>
 <div class="kpi"><span class="eyebrow">Root closure rate</span><b>{mv('root_closure_rate')}</b><small>verified or closed / independent</small></div>
 <div class="kpi"><span class="eyebrow">Consumer replay</span><b>{mv('consumer_replay_coverage')}</b><small>no replay outcomes recorded</small></div>
</div>

<h2>Seven dimensions · independent roots</h2>
<div class="card"><div class="tbl"><table class="dimt"><tbody>{dimrows}</tbody></table></div></div>
<p class="muted" style="font-size:13px;margin-top:6px">A root is done only when every dimension is green or not applicable: diagnosis confirmed, repair verified at the producer, consumers integrated on exact heads, security and governance effective, admission granted, control in place. UNKNOWN is never counted as green.</p>

<h2>Root lifecycle</h2>
<ol class="pipe">{pipe}</ol>
<div class="side">{side}</div>

<h2>Root ledger</h2>
<div class="bar"><input type="search" id="q" placeholder="Filter roots, classes, PRs" aria-label="Filter roots"><span class="muted" id="qn" style="font-size:12.5px"></span></div>
<div class="card" style="margin-top:8px"><div class="tbl"><table id="roots"><thead><tr><th>Root</th><th>Title</th><th>Sev.</th><th>Class</th><th>State</th><th>Owner</th><th class="num">Occ.</th><th>Affected PRs</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div></div>

<h2>Unlinked signatures · candidate roots</h2>
<p class="muted" style="font-size:13.5px;max-width:84ch">Search this list and the ledger before repairing anything (EVERRED §5). A signature becomes a root only after triage establishes the cause; matching messages are candidates, not proof.</p>
<div class="card" style="margin-top:8px"><div class="tbl"><table><thead><tr><th>Signature (workflow :: job :: step)</th><th>Repo</th><th class="num">Occ.</th><th>PRs</th><th></th></tr></thead><tbody>{un}</tbody></table></div></div>

<h2>Addendum to the standard · where EVERRED 2.0 needed detail</h2>
<div class="add">
 <div class="card"><h3><span class="num-h">A1</span>Occurrence and signature</h3><p>An occurrence is one failed step in one job run: repo, SHA, PR, workflow, job, step, run ID and attempt, job ID, runner, completion time. The signature is <span class="mono">workflow :: job :: step</span> with OS and Python moved to the environment, hashes replaced by <span class="mono">&lt;sha&gt;</span> and worker sequence numbers by <span class="mono">*</span>. Upgrade path: JUnit test IDs and scanner rule IDs as a fourth signature level.</p></div>
 <div class="card"><h3><span class="num-h">A2</span>Root IDs and ledger</h3><p><span class="mono">&lt;REPO&gt;-RC-YYYY-NNNN</span> (V3; V2 <span class="mono">EVR-…</span> IDs stay as aliases), never reused; a split creates new IDs with <span class="mono">split_from</span>, a merge keeps the older ID. The ledger lives in the owning repo (proposed <span class="mono">governance/everred/roots.yaml</span>) and exports to CODEX as a REX return (<span class="mono">gbogeb-repo-rex-return/1.0</span>, merge key = signature), so the CODEX #989 rule "update the existing record before minting" applies unchanged.</p></div>
 <div class="card"><h3><span class="num-h">A3</span>New class: control-plane drift</h3><p>Rulesets, branch protection, required-check names or app IDs that differ from the declared policy. Detected by a probe each census, not by a failing job, because a missing gate produces no red at all. Fail-closed; owner-only repair. First instance: EVR-ABACUS-0001.</p></div>
 <div class="card"><h3><span class="num-h">A4</span>Aggregators and umbrella steps</h3><p>Jobs that only summarise other reds (Full Red Proof Summary) are <i>derived</i> and never counted as roots. Enforce steps that combine several tools (security: Bandit + Safety; quality: Black + isort + Flake8) are umbrella signatures; split them into one root per tool from the upstream step outcomes before assigning owners.</p></div>
 <div class="card"><h3><span class="num-h">A5</span>One lane per root</h3><ul><li>Branch <span class="mono">everred/&lt;root-id&gt;-&lt;slug&gt;</span>, draft PR labelled <span class="mono">everred:&lt;root-id&gt;</span>.</li><li>The ledger's <span class="mono">owner</span> plus the open lane PR is the lock.</li><li>A second worker whose failure matches the signature comments on the lane PR and links its occurrence; it does not open a competing fix.</li></ul></div>
 <div class="card"><h3><span class="num-h">A6</span>Who may move a root</h3><ul><li>Agent: DISCOVERED → TRIAGED → FIX_COMMITTED → PRODUCER_GREEN → CONSUMERS_REPLAYED, each with a linked run.</li><li>Owner: OWNED, any BLOCKED_AUTHORITY decision, policy dispositions.</li><li>Independent reviewer: VERIFIED_FIXED for security roots.</li><li>CLOSED only after the observation window passes with no matching occurrence.</li></ul></div>
 <div class="card"><h3><span class="num-h">A7</span>Metrics as implemented</h3><ul><li>Amplification = occurrences on triaged independent roots ÷ triaged independent roots.</li><li>Signature amplification (occurrences ÷ distinct signatures) is shown as an upper bound only.</li><li>Replay coverage stays UNKNOWN until replay outcomes are recorded per consumer.</li><li>No metric ever reports 0 for a missing denominator.</li></ul></div>
 <div class="card"><h3><span class="num-h">A8</span>EVERRED and Code Purple</h3><p>Code Purple is the acute response to an admission deadlock, with lift criteria. EVERRED is the standing root system. Code Purple's close-out hands its inherited reds to EVERRED as roots; EVERRED escalates to Code Purple when a root blocks all admission or a control-plane probe turns red. Lesson from this run: break glass with a bypass actor, never by deleting rules, and verify rule content in the lift check.</p></div>
 <div class="card"><h3><span class="num-h">A9</span>Cadence and receipts</h3><p>Run the harvest each pulse and on a schedule; keep every <span class="mono">everred.json</span> as a dated, immutable census row. A later occurrence matching a VERIFIED_FIXED or CLOSED root reopens it automatically as a candidate.</p></div>
 <div class="card"><h3><span class="num-h">A10</span>Known limits of this census</h3><ul><li>Job logs and artifacts sit on a blob host this session cannot read, so causes come from step outcomes, annotations and local reproduction. A harvest running inside GitHub Actions can read the logs.</li><li>Consumer replay outcomes are not yet recorded.</li></ul></div>
</div>
<footer>Census files: <a href="data/everred.json">everred.json</a> · <a href="data/rex_return.yaml">rex_return.yaml</a> · <a href="data/register.md">register.md</a> · <a href="data/roots.yaml">roots.yaml</a>. Snapshot of the census at {esc(rep['generated_at'])}; refresh.py rebuilds it. Part of the <a href="../index.html">P process</a>.</footer>
</div>
<script>
(function(){{const q=document.getElementById('q'),rows=[...document.querySelectorAll('#roots tbody tr')],n=document.getElementById('qn');
function f(){{const v=q.value.trim().toLowerCase();let k=0;rows.forEach(r=>{{const on=!v||r.textContent.toLowerCase().includes(v);r.hidden=!on;if(on)k++}});n.textContent=k+' of '+rows.length+' roots'}}
q.addEventListener('input',f);f();}})();
</script>
"""
out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8", newline="\n")
print("ok", len(page))
