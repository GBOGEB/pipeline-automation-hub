#!/usr/bin/env python3
"""Render the P process home page (site/index.html) and its 16:9 companion deck (site/P-process-deck.pdf).

The page and the deck come from the same sections: Code Purple (acute) x EVERRED (recursive), mode per repo,
escalation and handoff, scenarios, rulesets and drift, root register summary, method links.
Data: site/data/p_state.json (p_decide.py), everred.json, census.json, rulesets/manifest.json + drift.json, p_process.yaml.
Usage: python build_p_process.py [--no-pdf]
"""
import argparse
import html
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
esc = html.escape


def first(*c):
    return next(Path(x) for x in c if x and Path(x).is_file())


def load():
    return {
        "state": json.loads((SITE / "data/p_state.json").read_text()),
        "ev": json.loads(first(ROOT / "everred/out/everred.json", SITE / "everred/data/everred.json").read_text()),
        "cp": json.loads(first(ROOT / "kit/out/census.json", SITE / "code-purple/kit/census.json").read_text()),
        "man": json.loads((ROOT / "rulesets/manifest.json").read_text()),
        "drift": json.loads((ROOT / "rulesets/drift.json").read_text()),
        "spec": yaml.safe_load((ROOT / "p_process.yaml").read_text()),
    }


GOOD = {"CONFIRMED", "PRODUCER_VERIFIED", "EXACT_HEAD_PASSED", "EFFECTIVE", "ADMITTED", "NA", "PASS"}
BAD = {"UNRESOLVED", "NONE", "RED", "INEFFECTIVE", "HOLD", "UNCONTROLLED"}


def chip(v, cls=None):
    cls = cls or ("g" if v in GOOD else "r" if v in BAD else "u")
    return f'<span class="chip {cls}">{esc(str(v).replace("_", " ").lower())}</span>'


LOOP_SVG = """<svg viewBox="0 0 1000 380" role="img" aria-label="EVERRED recursive loop with escalation to and handoff from Code Purple" class="loops">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ah"/></marker></defs>
<text x="230" y="26" class="lt">EVERRED · recursive health monitor</text>
<text x="770" y="26" class="lt cp">CODE PURPLE · acute burndown</text>
<g class="ev">
 <circle cx="230" cy="200" r="132" class="ring"/>
 {ev_nodes}
 <text x="230" y="196" class="mid">RECURSE</text><text x="230" y="218" class="mids">every pulse · every schedule</text>
</g>
<g class="cpg">
 <rect x="610" y="56" width="320" height="300" rx="16" class="box"/>
 {cp_nodes}
</g>
<path d="M372,150 C470,110 520,110 600,120" class="esc" marker-end="url(#ar)"/><text x="486" y="100" class="el">E1 · E2 · E3 escalate</text>
<path d="M600,300 C520,320 470,320 372,260" class="hand" marker-end="url(#ar)"/><text x="486" y="342" class="el">H1 · H2 · H3 hand off roots</text>
</svg>"""


def loops_svg():
    import math
    steps = ["Harvest", "Classify", "Root", "Repair lane", "Verify P0–P7", "Admit", "Control"]
    ev = ""
    for i, s in enumerate(steps):
        a = -math.pi / 2 + i * 2 * math.pi / len(steps)
        x, y = 230 + 132 * math.cos(a), 200 + 132 * math.sin(a)
        ev += f'<g><rect x="{x-58:.0f}" y="{y-15:.0f}" width="116" height="30" rx="15" class="pn"/><text x="{x:.0f}" y="{y+5:.0f}" class="pt">{i+1} {s}</text></g>'
    cps = ["0 Declare", "1 Read back", "2 Classify every red", "3 Find the unblocker", "4 Repair source defects", "5 Admit or break glass", "6 Lift check", "7 Close out"]
    cp = "".join(f'<text x="636" y="{92+i*34}" class="ct"><tspan class="cn">{c.split(" ",1)[0]}</tspan> {c.split(" ",1)[1]}</text>' for i, c in enumerate(cps))
    return LOOP_SVG.replace("{ev_nodes}", ev).replace("{cp_nodes}", cp)


def sections(d):
    st, ev, cp, man, drift, spec = d["state"], d["ev"], d["cp"], d["man"], d["drift"], d["spec"]
    S = []
    met = sum(1 for x in cp["lift"] if x["ok"])
    m = ev["metrics"]
    # 1 overview
    modes = "".join(f"""<tr><td class="mono">{esc(r.split('/')[1])}</td><td>{chip(v['mode'], 'cp' if v['mode']=='CODE_PURPLE' else 'ev')}</td>
      <td>{chip(v['ruleset'], 'r' if v['ruleset']=='RED' else 'g' if v['ruleset']=='GREEN' else 'u')}</td><td class="num">{v['open_roots']}</td><td>{esc(v['worst'] or '—')}</td>
      <td class="small">{esc('; '.join(v['reasons']) or 'standing monitor')}</td></tr>""" for r, v in st["repos"].items())
    S.append(("overview", "1", "Where each repository is now", f"""
<div class="kpis">
 <div class="kpi cpk"><span>Code Purple {esc(st.get('incident',''))}</span><b>{'LIFTED' if cp['lifted'] else 'NOT LIFTED'}</b><small>{met} of {len(cp['lift'])} lift criteria · census {esc(cp['generated_at'][:16].replace('T',' '))} UTC</small></div>
 <div class="kpi"><span>Ungated ABACUS merges since #1858</span><b>{cp.get('admission_audit',{}).get('ungated','?')}</b><small>{cp.get('admission_audit',{}).get('with_red_checks','?')} merged with red checks</small></div>
 <div class="kpi"><span>Ruleset probe</span><b>{m.get('control_plane_red','?')} / {m.get('control_plane_probed','?')} red</b><small>expected BASIC rules missing</small></div>
 <div class="kpi"><span>EVERRED roots</span><b>{m['roots_independent']}</b><small>closure {m['root_closure_rate']} · replay {m['consumer_replay_coverage']}</small></div>
</div>
<table><thead><tr><th>Repository</th><th>Mode</th><th>Ruleset</th><th class="num">Open roots</th><th>Worst</th><th>Why</th></tr></thead><tbody>{modes}</tbody></table>"""))
    # 2 two modes
    cpm, evm = spec["modes"]["CODE_PURPLE"], spec["modes"]["EVERRED"]
    S.append(("modes", "2", "One process, two modes", f"""
<div class="two"><div class="card cpc"><h3>Code Purple · acute</h3><p>{esc(cpm['intent'])}.</p><dl><dt>Entry</dt><dd>{esc(cpm['entry'])}</dd><dt>Exit</dt><dd>{esc(cpm['exit'])}</dd><dt>Break glass</dt><dd>{esc(cpm['break_glass'])}</dd></dl><p><a href="code-purple/index.html">Code Purple page</a> · <a href="code-purple/Code-Purple-deck.pdf">deck PDF</a></p></div>
<div class="card evc"><h3>EVERRED · recursive</h3><p>{esc(evm['intent'])}.</p><dl><dt>Loop</dt><dd>{esc(' → '.join(evm['loop']))}</dd><dt>Cadence</dt><dd>{esc(evm['cadence'])}</dd><dt>Rule</dt><dd>one root → one owner → one repair → consumers revalidated</dd></dl><p><a href="everred/index.html">EVERRED register</a></p></div></div>
<div class="svgw">{loops_svg()}</div>"""))
    # 3 escalation / handoff / scenarios
    tr = lambda rows: "".join(f'<tr><td class="mono b">{esc(x["id"])}</td><td>{esc(x["when"])}</td></tr>' for x in rows)
    sc = "".join(f'<tr><td class="b">{esc(x["case"])}</td><td>{esc(x["mode"])}</td><td>{esc(x["first"])}; {esc(x["then"])}</td></tr>' for x in spec["scenarios"])
    S.append(("switch", "3", "When the mode switches", f"""
<div class="two"><div><h3>Escalate · EVERRED → Code Purple</h3><table><tbody>{tr(spec['escalation'])}</tbody></table></div>
<div><h3>Hand off · Code Purple → EVERRED</h3><table><tbody>{tr(spec['handoff'])}</tbody></table></div></div>
<h3 style="margin-top:22px">Per case</h3><table><thead><tr><th>Scenario</th><th>Mode</th><th>First step, then</th></tr></thead><tbody>{sc}</tbody></table>"""))
    # 4 rulesets
    rr = ""
    for repo, v in man.items():
        dv = drift["repos"].get(repo, {})
        gaps = dv.get("gaps", ["not probed"])
        rr += f"""<tr><td class="mono">{esc(repo.split('/')[1])}</td><td class="small">{esc(', '.join(v['checks']))}</td>
        <td class="small">{esc(', '.join(dv.get('effective_rules') or []) or 'none')}</td><td>{chip('RED' if dv.get('red', True) else 'GREEN', 'r' if dv.get('red', True) else 'g')} <span class="small">{esc('; '.join(gaps + dv.get('untargeted_rulesets', [])))}</span></td>
        <td><a href="rulesets/{esc(v['file'])}">{esc(v['file'])}</a>{f' · <a href="rulesets/{esc(v["hard_file"])}">{esc(v["hard_file"])}</a>' if v.get('hard_file') else ''}</td></tr>"""
    S.append(("rulesets", "4", "BASIC rulesets and drift", f"""
<p class="lead">Each BASIC ruleset: no deletion, no force-push, PRs with review threads resolved, and required checks that ran green on every recent PR and are not path-filtered. Bypass list empty: break glass by adding a bypass actor for one merge, never by deleting rules. <b>The owner imports these; agents never apply rulesets.</b> Drift probe at {esc(drift['generated_at'][:16].replace('T',' '))} UTC.</p>
<table><thead><tr><th>Repo</th><th>Required checks</th><th>Effective rules now</th><th>Drift</th><th>Import file</th></tr></thead><tbody>{rr}</tbody></table>"""))
    # 5 roots
    sev = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    roots = sorted([r for r in ev["roots"] if r["state"] not in ("VERIFIED_FIXED", "CLOSED")], key=lambda r: (sev.get(r.get("severity"), 9), r["id"]))
    rows = "".join(f"""<tr class="{'extra' if i >= 8 else ''}"><td class="mono"><a href="everred/index.html#{r['id'].lower()}">{r['id']}</a></td><td>{esc(r.get('severity',''))}</td><td><b>{esc(r['title'])}</b><div class="dims">{''.join(chip(v) for v in (r.get('dims') or {}).values())}</div></td><td>{chip(r['state'])}</td><td class="num">{r['occurrences']}</td></tr>""" for i, r in enumerate(roots))
    if len(roots) > 8:
        rows += f'<tr class="deckonly"><td colspan="5" class="small">+{len(roots) - 8} more open roots (P2–P3) on the <a href="everred/index.html">EVERRED register</a></td></tr>'
    S.append(("roots", "5", "Open roots by severity", f"""
<p class="lead">Seven dimension chips per root, in order: diagnosis, repair, integration, security, governance, admission, control. UNKNOWN never counts as green; derived reds (aggregators) are not roots. {m['occurrences_total']} occurrences, {m['distinct_signatures']} signatures, {m['unmatched_signatures']} not yet linked to a root.</p>
<table><thead><tr><th>Root</th><th>Sev</th><th>Title and dimensions</th><th>State</th><th class="num">Occ.</th></tr></thead><tbody>{rows}</tbody></table>"""))
    # 6 build & refresh
    S.append(("build", "6", "Build, refresh, verify", """
<div class="two"><div class="card"><h3>Refresh (needs a GitHub token with read access)</h3><pre>python refresh.py            # readback, drift probe, harvest, decide, pages, PDFs
python refresh.py --offline  # rebuild pages and PDFs from the committed data</pre>
<p>Pages re-read <span class="mono">data/*.json</span> every 5 minutes while open; a new census appears once refresh.py republishes it.</p></div>
<div class="card"><h3>Verify</h3><pre>python -m unittest discover -s tests -v
node tools/check_model.mts   # model integrity (TypeScript)
npx -y -p typescript@6.0.3 tsc -p tsconfig.json</pre><p>CI: <span class="mono">.github/workflows/p-process.yml</span>, offline, no secrets.</p></div></div>
<p class="small">Sources: <a href="data/p_state.json">p_state.json</a> · <a href="everred/data/everred.json">everred.json</a> · <a href="code-purple/kit/census.json">census.json</a> · <a href="rulesets/drift.json">drift.json</a> · <a href="data/p_process.yaml">p_process.yaml</a></p>"""))
    return S


CSS = """
:root{--bg:#f6f5f8;--surface:#fff;--ink:#1c1626;--muted:#625a70;--line:#dcd6e4;--accent:#5a2a86;--accent-soft:#ece3f6;
--r:#c9405f;--rb:#fce7ec;--ri:#8f2747;--a:#c98f2e;--ab:#fff2db;--ai:#7c5118;--g:#3f9b6c;--gb:#e0f4e9;--gi:#145c43;--t:#2f8f95;--tb:#dff1f2;--ti:#135458;
--f-body:"Aptos","IBM Plex Sans",system-ui,sans-serif;--f-display:"Archivo","Aptos Display",Arial,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121017;--surface:#1a1722;--ink:#ece8f3;--muted:#a69db4;--line:#322c3d;--accent:#b98ce6;--accent-soft:#2c2240;
--rb:#3a1c26;--ri:#f5b8c9;--ab:#35280f;--ai:#f1d39d;--gb:#15301f;--gi:#a8e2c2;--tb:#11302f;--ti:#a2dfe2;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#121017;--surface:#1a1722;--ink:#ece8f3;--muted:#a69db4;--line:#322c3d;--accent:#b98ce6;--accent-soft:#2c2240;--rb:#3a1c26;--ri:#f5b8c9;--ab:#35280f;--ai:#f1d39d;--gb:#15301f;--gi:#a8e2c2;--tb:#11302f;--ti:#a2dfe2;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--f-body)}
.wrap{max-width:1180px;margin:auto;padding:28px 16px 60px}a{color:var(--accent)}
h1,h2,h3{font-family:var(--f-display);margin:0;text-wrap:balance}h1{font-size:clamp(30px,4.4vw,46px);font-weight:800}h3{font-size:16px;margin-bottom:8px}
.eyebrow{font-family:var(--f-mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
nav.toc{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 6px}nav.toc a{text-decoration:none;font-size:13px;padding:5px 10px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink)}
section.s{margin-top:38px}.sh{display:flex;align-items:baseline;gap:14px;border-bottom:2px solid var(--accent);padding-bottom:6px;margin-bottom:14px}
.sn{font-family:var(--f-display);font-weight:800;font-size:44px;line-height:1;color:var(--accent)}.sh h2{font-size:24px}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}@media(max-width:800px){.kpis,.two{grid-template-columns:1fr!important}}
.kpi,.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.kpi span{font-family:var(--f-mono);font-size:11px;text-transform:uppercase;color:var(--muted);display:block}
.kpi b{font-family:var(--f-display);font-size:26px;display:block}.kpi small{color:var(--muted);font-size:12.5px}.kpi.cpk{border-color:var(--accent);background:var(--accent-soft)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.cpc{border-top:4px solid var(--accent)}.evc{border-top:4px solid var(--t)}
dl{display:grid;grid-template-columns:96px 1fr;gap:4px 10px;font-size:14px}dt{color:var(--muted);font-family:var(--f-mono);font-size:12px}dd{margin:0}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}th{font:500 11px var(--f-mono);text-transform:uppercase;color:var(--muted);text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}.num{text-align:right}.mono{font-family:var(--f-mono);font-size:12.5px}.b{font-weight:600}.small{font-size:12.5px;color:var(--muted)}
.chip{font-family:var(--f-mono);font-size:11px;padding:1px 7px;border-radius:4px;white-space:nowrap;display:inline-block;margin:1px}
.chip.g{background:var(--gb);color:var(--gi)}.chip.r{background:var(--rb);color:var(--ri)}.chip.u{background:var(--ab);color:var(--ai)}.chip.cp{background:var(--accent);color:#fff}.chip.ev{background:var(--tb);color:var(--ti)}
.dims{margin-top:4px}.deckonly{display:none}.lead{max-width:92ch;color:var(--muted);margin:0 0 12px}pre{font:12.5px var(--f-mono);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;overflow:auto}
.svgw{overflow-x:auto;margin-top:14px}.loops{width:100%;min-width:760px;height:auto}.ring{fill:none;stroke:var(--t);stroke-width:2;stroke-dasharray:4 5}
.pn{fill:var(--tb);stroke:var(--t)}.pt{font:600 12px var(--f-body);fill:var(--ti);text-anchor:middle}.mid{font:800 22px var(--f-display);fill:var(--t);text-anchor:middle}.mids{font:12px var(--f-body);fill:var(--muted);text-anchor:middle}
.box{fill:var(--accent-soft);stroke:var(--accent);stroke-width:2}.ct{font:13.5px var(--f-body);fill:var(--ink)}.cn{font:800 16px var(--f-display);fill:var(--accent)}
.lt{font:800 15px var(--f-display);fill:var(--t);text-anchor:middle}.lt.cp{fill:var(--accent)}.esc{fill:none;stroke:var(--r);stroke-width:2.5}.hand{fill:none;stroke:var(--g);stroke-width:2.5;stroke-dasharray:7 5}
.ah{fill:var(--muted)}.el{font:600 12.5px var(--f-mono);fill:var(--muted);text-anchor:middle}
#live{font-size:12.5px;color:var(--muted)}footer{margin-top:40px;font-size:12.5px;color:var(--muted)}
"""

DECK_CSS = """
@page{size:1920px 1080px;margin:0}body{background:#fff;font-size:21px}.wrap{max-width:none;padding:0}
nav.toc,#live,.web{display:none!important}
section.s,.cover{width:1920px;height:1080px;padding:64px 90px 50px;margin:0;break-after:page;overflow:hidden;position:relative}
.sn{font-size:96px}.sh h2{font-size:48px}.sh{gap:28px;margin-bottom:26px}h3{font-size:24px}
table{font-size:19px}td{padding:9px 10px}.mono{font-size:16px}.small{font-size:16px}.chip{font-size:14px}
.kpi b{font-size:40px}.kpi span{font-size:14px}.kpi small{font-size:16px}.lead{font-size:20px;max-width:none}pre{font-size:16px}
.loops{min-width:0;max-height:470px}tr.extra{display:none}tr.deckonly{display:table-row}.svgw{text-align:center}
.foot{position:absolute;left:90px;right:90px;bottom:22px;display:flex;justify-content:space-between;font:14px var(--f-mono);color:var(--muted)}
.cover h1{font-size:110px;margin-top:240px}.cover p{font-size:28px;color:var(--muted);max-width:1400px}
.cover ol{columns:2;font-size:30px;margin-top:60px}.cover ol a{text-decoration:none}
"""


def page(d, deck=False):
    S = sections(d)
    st = d["state"]
    toc = "".join(f'<a href="#{k}">{n} · {esc(t)}</a>' for k, n, t, _ in S)
    stamp = f"P process · census {esc(d['cp']['generated_at'][:16].replace('T', ' '))} UTC · EVERRED {esc(d['ev']['generated_at'][:16].replace('T', ' '))} UTC"
    body = "".join(f"""<section class="s" id="{k}"><div class="sh"><span class="sn">{n}</span><h2>{esc(t)}</h2></div>{c}
{'<div class="foot"><span>' + stamp + '</span><span><a href="#cover">contents</a></span><span>' + n + ' / ' + str(len(S)) + '</span></div>' if deck else ''}</section>""" for k, n, t, c in S)
    cover = ""
    if deck:
        cover = f"""<section class="cover" id="cover"><div class="eyebrow">QPS TRIAGE · {esc(st.get('incident',''))}</div><h1>P process</h1>
<p>Code Purple (acute PR and problem burndown) × EVERRED (recursive health monitor) across ABACUS, CODEX, cryoplant-project and the support repos.</p>
<ol>{''.join(f'<li><a href="#{k}">{esc(t)}</a></li>' for k, _, t, _ in S)}</ol><div class="foot"><span>{stamp}</span><span></span><span>companion to site/index.html</span></div></section>"""
    script = "" if deck else """<script>
(function(){const live=document.getElementById('live');
async function load(){try{const r=await fetch('data/p_state.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error(r.status);const s=await r.json();
const cp=Object.values(s.repos).filter(v=>v.mode==='CODE_PURPLE').length;live.textContent='State '+s.generated_at.replace('T',' ').slice(0,16)+' UTC · '+cp+' repo(s) in Code Purple · rechecks every 5 min';}
catch(e){live.textContent='Showing the built snapshot ('+e.message+').'}}
load();setInterval(()=>{if(!document.hidden)load()},300000);})();
</script>"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P Process</title><style>{FONTS if deck else ''}{CSS}{DECK_CSS if deck else ''}</style></head><body><div class="wrap">{cover}
{'' if deck else f'''<div class="eyebrow">QPS TRIAGE · P process · {esc(st.get('incident',''))}</div><h1>P process: Code Purple × EVERRED</h1>
<p class="lead" style="margin-top:8px">Code Purple is the acute mode: PR and problem burndown, highest priority, most resources on one blocker. EVERRED is the standing mode: health monitor, continuous root-cause repair, RECURSE every pulse. One loop, two speeds, explicit switch rules.</p>
<div id="live">{stamp}</div><nav class="toc">{toc}<a href="P-process-deck.pdf">16:9 PDF</a></nav>'''}
{body}
{'' if deck else '<footer>Read-only review projection: not merge admission, not a security waiver, not QPS engineering approval. UNKNOWN stays UNKNOWN.</footer>'}
</div>{script}</body></html>"""


FONTS = ""


def fonts_css():
    import base64
    F = ROOT / "fonts"
    spec = [("IBM Plex Sans", "ibm-plex-sans-latin-400-normal.woff2", 400), ("IBM Plex Sans", "ibm-plex-sans-latin-600-normal.woff2", 600),
            ("IBM Plex Mono", "ibm-plex-mono-latin-400-normal.woff2", 400), ("IBM Plex Mono", "ibm-plex-mono-latin-500-normal.woff2", 500),
            ("Archivo", "archivo-latin-600-normal.woff2", 600), ("Archivo", "archivo-latin-800-normal.woff2", 800)]
    return "".join(f'@font-face{{font-family:"{f}";font-weight:{w};src:url(data:font/woff2;base64,{base64.b64encode((F / n).read_bytes()).decode()}) format("woff2")}}' for f, n, w in spec)


def render_pdf(html_path: Path, pdf_path: Path, n_sections: int):
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(html_path.as_uri())
        pg.evaluate("document.fonts.ready")
        over = pg.evaluate("[...document.querySelectorAll('section')].map((s,i)=>s.scrollHeight>s.clientHeight+2?i:null).filter(x=>x!==null)")
        tmp = pdf_path.with_suffix(".tmp.pdf")
        pg.pdf(path=str(tmp), width="1920px", height="1080px", print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        b.close()
    w = PdfWriter(clone_from=str(tmp))
    w.add_metadata({"/Title": "P process: Code Purple x EVERRED", "/Author": "GBO (prepared with Claude)"})
    w.add_outline_item("Contents", 0)
    for i, (k, n, t, _) in enumerate(SECTS):
        w.add_outline_item(f"{n}  {t}", i + 1)
    w.page_mode = "/UseOutlines"
    with pdf_path.open("wb") as fh:
        w.write(fh)
    tmp.unlink()
    return len(PdfReader(str(pdf_path)).pages), over


SECTS = []


def main():
    global FONTS, SECTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    d = load()
    SECTS = sections(d)
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "data").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "p_process.yaml", SITE / "data/p_process.yaml")
    (SITE / "index.html").write_text(page(d), encoding="utf-8")
    out = {"index": str(SITE / "index.html")}
    if not a.no_pdf:
        FONTS = fonts_css()
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        dh = build / "p-process-deck.html"
        dh.write_text(page(d, deck=True), encoding="utf-8")
        n, over = render_pdf(dh, SITE / "P-process-deck.pdf", len(SECTS))
        out.update(pdf_pages=n, overflow_sections=over)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
