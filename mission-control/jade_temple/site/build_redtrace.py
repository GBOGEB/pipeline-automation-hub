#!/usr/bin/env python3
"""JADE N+8 red-trace federation ledger: deterministic HTML page + 16:9 HTML slides.

Sources (committed, read-only): data/RED_TRACE_FEDERATION_N8.json, data/GAP_ANALYSIS_N8.json.
Outputs (generated; do not hand edit): site/redtrace.html, site/redtrace-slides.html,
site/redtrace-manifest.json. The interactive PDF is rendered from redtrace-slides.html by
tools/render_redtrace_pdf.py. Presentation reuses site/jade.css tokens and the JADE mast.
Colour is never the only status cue: every state also has a text label.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
FED = "data/RED_TRACE_FEDERATION_N8.json"
GAP = "data/GAP_ANALYSIS_N8.json"
OUTPUTS = ("redtrace.html", "redtrace-slides.html")
E = lambda s: html.escape("" if s is None else str(s), quote=True)
CLS = {"GREEN_TO_RED": ("red", "GREEN→RED"), "EVERRED": ("red", "EVERRED"), "FLAKY": ("amber", "FLAKY"),
       "RED_TO_GREEN": ("green", "RED→GREEN"), "STABLE_GREEN": ("green", "STABLE"),
       "UNKNOWN_NO_TERMINAL": ("amber", "UNKNOWN")}
GAPSTATE = {"FILLED": ("green", "FILLED"), "EXCEEDED": ("green", "EXCEEDED"), "FILLED_PARTIAL": ("amber", "PARTIAL"),
            "DETECTED": ("amber", "DETECTED"), "OPEN": ("red", "OPEN")}
ACTOR = {"AGENT": "Agent-executed (Claude session)", "OWNER": "Owner decision / action", "CI": "Native CI evidence"}


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def short(s):
    return (s or "")[:8]


def chip(kind, label):
    return f'<span class="rt-chip rt-{kind}">{E(label)}</span>'


def actor(a):
    return f'<span class="rt-actor rt-actor-{E(a.lower())}" title="{E(ACTOR.get(a, a))}">{E(a)}</span>'


def window_text(w, repo):
    t = w.get("window") or {}
    base = f"https://github.com/{repo}/actions/runs/"
    parts = []
    if t.get("last_green_sha"):
        parts.append(f'<code>{E(short(t["last_green_sha"]))}</code> → ')
    elif t.get("red_before_window"):
        parts.append("red at window start → ")
    if t.get("first_red_sha"):
        run = t.get("first_red_run")
        first = f'<code>{E(short(t["first_red_sha"]))}</code>'
        parts.append(f'<a href="{E(base + str(run))}">{first}</a>' if run else first)
    if t.get("recovery_sha"):
        parts.append(f' → ✓<a href="{E(base + str(t.get("recovery_run")))}"><code>{E(short(t["recovery_sha"]))}</code></a>'
                     f' <small>({E(t.get("red_hours"))} h red)</small>')
    elif t.get("red_streak_runs"):
        parts.append(f' <small>({E(t["red_streak_runs"])} red)</small>')
    return "".join(parts) or "—"


def flags(w):
    out = []
    if w["current"] == "RED":
        out.append(chip("red", "RED NOW"))
    if w["stale"]:
        out.append(chip("amber", f"STALE {w['age_days']} d"))
    if w["pinned"]:
        out.append(chip("violet", "📌 PINNED EVIDENCE"))
    if w["history_truncated"]:
        out.append(chip("quiet", "⁺ history truncated"))
    return " ".join(out)


MAST = """<header class="mast"><div class="brand"><span class="brand-logo" aria-hidden="true">JT</span><div>JADE_TEMPLE<small>N+8 · GOGREEN RED-TRACE FEDERATION LEDGER</small></div></div>
<div class="mast-right"><span class="timestamp">OBSERVED {obs}</span><span class="pill pill-hold">ADMISSION HOLD</span><span class="pill rt-pill-ro">READ-ONLY</span></div></header>"""

CSS = """
.rt-wrap{padding:22px 0 60px}.rt-h1{font-size:clamp(26px,3.4vw,40px);margin:18px 0 6px;letter-spacing:-.01em}.rt-lead{color:var(--muted);max-width:980px}
.rt-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}
.rt-kpi{background:var(--panel);border:1px solid var(--stroke);border-radius:14px;padding:14px 16px}.rt-kpi b{display:block;font-size:28px;line-height:1.1}.rt-kpi span{font-size:12px;color:var(--muted)}
.rt-sec{margin:34px 0 10px;font-size:20px}.rt-card{background:var(--panel);border:1px solid var(--stroke);border-radius:14px;padding:16px;margin:10px 0}
.rt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}
.rt-chip{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.06em;border:1px solid;border-radius:99px;padding:2px 8px;margin:1px 2px 1px 0;white-space:nowrap}
.rt-red{color:var(--red);border-color:#8e4b4b;background:#3a1b1b}.rt-green{color:var(--green);border-color:var(--green-dark);background:#123d2c}
.rt-amber{color:var(--amber);border-color:#8a6a3c;background:#3a2f1c}.rt-violet{color:#d9c2ff;border-color:#6d5a9a;background:#271f3d}.rt-quiet{color:var(--quiet);border-color:var(--stroke)}
.rt-actor{display:inline-block;font-size:10px;font-weight:900;letter-spacing:.12em;border-radius:6px;padding:2px 7px;margin-right:6px}
.rt-actor-agent{background:#cfe9ff;color:#0a2a44}.rt-actor-owner{background:#ffe2a8;color:#3d2a00}.rt-actor-ci{background:#c9f2dc;color:#0d3a24}
.rt-pill-ro{color:var(--green)}.rt-tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0}
.rt-tools select,.rt-tools input{background:var(--panel);color:var(--text);border:1px solid var(--stroke);border-radius:9px;padding:8px 10px}
.rt-tools input{flex:1;min-width:200px}.rt-tablewrap{overflow-x:auto;border:1px solid var(--stroke);border-radius:12px}
table.rt{border-collapse:collapse;width:100%;min-width:860px}table.rt th,table.rt td{padding:9px 11px;border-bottom:1px solid var(--stroke);text-align:left;vertical-align:top;font-size:13px}
table.rt th{background:var(--panel-hi);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);position:sticky;top:0}
table.rt td small{color:var(--quiet)}.rt-repo{font-weight:800}.rt-step{color:var(--muted);font-size:12px;overflow-wrap:anywhere}
.rt-bars{display:grid;gap:8px}.rt-bar{display:grid;grid-template-columns:170px 1fr 90px;gap:10px;align-items:center;font-size:13px}
.rt-track{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--panel-hi)}.rt-track i{display:block}
.rt-s-g{background:var(--green)}.rt-s-r{background:var(--red)}.rt-s-a{background:var(--amber)}.rt-s-s{background:#86c8a6}
.rt-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.rt-legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
footer.rt-foot{color:var(--quiet);font-size:12px;margin-top:40px;border-top:1px solid var(--stroke);padding-top:14px}
@media(max-width:620px){.app-shell{padding:0 16px}.rt-bar{grid-template-columns:1fr}.mast{flex-wrap:wrap}}
"""


def bars(fed):
    rows = []
    for r in fed["repositories"]:
        c = r["counts"]
        n = max(1, r["workflows_traced"])
        seg = [("rt-s-s", c.get("STABLE_GREEN", 0), "stable green"), ("rt-s-g", c.get("RED_TO_GREEN", 0), "recovered"),
               ("rt-s-a", c.get("FLAKY", 0) + c.get("UNKNOWN_NO_TERMINAL", 0), "flaky/unknown"),
               ("rt-s-r", c.get("GREEN_TO_RED", 0) + c.get("EVERRED", 0), "green→red / everred")]
        track = "".join(f'<i class="{k}" style="width:{v * 100 / n:.2f}%" title="{E(lbl)}: {v}"></i>' for k, v, lbl in seg if v)
        rows.append(f'<div class="rt-bar"><span class="rt-repo">{E(r["short"])}</span><span class="rt-track" role="img" '
                    f'aria-label="{E(r["short"])}: ' + ", ".join(f"{lbl} {v}" for _, v, lbl in seg) + f'">{track}</span>'
                    f'<span>{r["currently_red"]} red · {r["currently_red_stale"]} stale</span></div>')
    legend = ('<div class="rt-legend"><span><i class="rt-s-s"></i>stable green</span><span><i class="rt-s-g"></i>recovered (RED→GREEN)</span>'
              '<span><i class="rt-s-a"></i>flaky / unknown</span><span><i class="rt-s-r"></i>GREEN→RED + EVERRED</span></div>')
    return f'<div class="rt-bars">{"".join(rows)}</div>{legend}'


def kpis(fed, gap):
    t = fed["totals"]
    shared = sum(len(r["shared_break_roots"]) for r in fed["repositories"])
    filled = sum(1 for g in gap["gaps"] if g["state"] in ("FILLED", "EXCEEDED"))
    items = [(len(fed["repositories"]), "core repositories traced"), (t["workflows"], "workflows with history"),
             (f'{t["runs"]:,}', "runs read (GET only)"), (t["red_fresh"], "red now · fresh"),
             (t["red_stale"], "red · stale (replay first)"), (t["pinned_red"], "red on pinned evidence"),
             (shared, "shared break roots"), (f'{filled}/{len(gap["gaps"])}', "gaps filled / exceeded")]
    return '<div class="rt-kpis">' + "".join(f'<div class="rt-kpi"><b>{E(v)}</b><span>{E(k)}</span></div>' for v, k in items) + "</div>"


def ledger_rows(fed):
    rows = []
    for r in fed["repositories"]:
        for w in r["non_green"]:
            k, lbl = CLS.get(w["class"], ("quiet", w["class"]))
            step = "; ".join((w.get("window") or {}).get("failing", []))
            rows.append(f'<tr data-repo="{E(r["short"])}" data-class="{E(w["class"])}" data-red="{1 if w["current"] == "RED" else 0}">'
                        f'<td class="rt-repo">{E(r["short"])}</td><td>{E(w["name"])}<br><small>{E(w["path"])}</small></td>'
                        f'<td>{chip(k, lbl)}</td><td>{flags(w)}</td><td>{window_text(w, r["repository"])}</td>'
                        f'<td class="rt-step">{E(step) or "—"}</td></tr>')
    return "".join(rows)


def gap_cards(gap):
    out = []
    for g in gap["gaps"]:
        k, lbl = GAPSTATE.get(g["state"], ("quiet", g["state"]))
        out.append(f'<article class="rt-card" id="gap-{E(g["id"])}"><div>{actor(g["actor"])}{chip(k, lbl)} <b>{E(g["id"])} · {E(g["title"])}</b></div>'
                   f'<p>{E(g["finding"])}</p><p><small>Fill:</small> {E(g["fill"])}</p><p><small>Next:</small> {E(g["next"])}</p></article>')
    return '<div class="rt-grid">' + "".join(out) + "</div>"


def core_block(gap):
    c = gap["core"]
    core = "".join(f'<li><b>{E(x["repo"].split("/")[1])}</b>: {E(x["role"])}</li>' for x in c["federation_core"])
    return (f'<div class="rt-grid"><div class="rt-card"><h3>Pipeline</h3><p>{E(c["pipeline"]["answer"])}</p></div>'
            f'<div class="rt-card"><h3>Federation core (5)</h3><ul>{core}</ul></div>'
            f'<div class="rt-card"><h3>Satellites & cohort</h3><p>{E(", ".join(s.split("/")[1] for s in c["satellites"]))}</p><p>{E(c["cohort_note"])}</p></div></div>')


def actions_table(gap):
    rows = "".join(f'<tr><td>{E(a["date"])}</td><td>{actor(a["actor"])}</td><td>{E(a["action"])}</td><td>{E(a["ref"])}</td></tr>'
                   for a in gap["agent_actions"])
    return f'<div class="rt-tablewrap"><table class="rt" style="min-width:640px"><thead><tr><th>Date</th><th>Actor</th><th>Action</th><th>Reference</th></tr></thead><tbody>{rows}</tbody></table></div>'


JS = """(function(){var q=document.getElementById('rt-q'),repo=document.getElementById('rt-repo'),cls=document.getElementById('rt-cls'),red=document.getElementById('rt-red'),n=document.getElementById('rt-n');
function f(){var s=q.value.toLowerCase(),c=0;document.querySelectorAll('#rt-ledger tbody tr').forEach(function(tr){var ok=(!repo.value||tr.dataset.repo===repo.value)&&(!cls.value||tr.dataset.class===cls.value)&&(!red.checked||tr.dataset.red==='1')&&tr.textContent.toLowerCase().indexOf(s)>-1;tr.hidden=!ok;if(ok)c++});n.textContent=c+' rows';}
[q,repo,cls,red].forEach(function(e){e.addEventListener('input',f);e.addEventListener('change',f)});f();})();"""


def page(fed, gap):
    repos = "".join(f'<option value="{E(r["short"])}">{E(r["short"])}</option>' for r in fed["repositories"])
    classes = "".join(f'<option value="{k}">{E(v[1])}</option>' for k, v in CLS.items() if k != "STABLE_GREEN")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JADE N+8 · Red-trace federation ledger</title><link rel="stylesheet" href="jade.css"><style>{CSS}</style></head><body>
<a class="skip" href="#main">Skip to content</a><div class="app-shell">{MAST.format(obs=E(fed["observed_at_utc"]))}<main id="main" class="rt-wrap">
<h1 class="rt-h1">Which workflows are red, since when, and why?</h1>
<p class="rt-lead">Per-workflow EVERRED · GREEN→RED · RED→GREEN · FLAKY ledger for the five federation core repositories, from native Actions history (one outcome per head SHA, terminal results only). Break windows link to the first red run. <a href="redtrace-slides.html">Slides</a> · <a href="redtrace-slides.pdf">Interactive PDF</a> · <a href="../data/RED_TRACE_FEDERATION_N8.json">Data</a> · <a href="../data/GAP_ANALYSIS_N8.json">Gap analysis</a></p>
{kpis(fed, gap)}
<h2 class="rt-sec" id="core">Core repositories: pipeline and federation</h2>{core_block(gap)}
<h2 class="rt-sec" id="score">Federation scoreboard</h2><div class="rt-card">{bars(fed)}</div>
<h2 class="rt-sec" id="ledger">Non-green ledger</h2>
<div class="rt-tools"><input id="rt-q" type="search" placeholder="Search workflow, step, SHA…" aria-label="Search ledger"><select id="rt-repo" aria-label="Repository"><option value="">All repositories</option>{repos}</select>
<select id="rt-cls" aria-label="Class"><option value="">All classes</option>{classes}</select><label><input id="rt-red" type="checkbox" checked> red now only</label><span id="rt-n" aria-live="polite"></span></div>
<div class="rt-tablewrap"><table class="rt" id="rt-ledger"><thead><tr><th>Repo</th><th>Workflow</th><th>Class</th><th>Flags</th><th>Window (last green → first red → recovery)</th><th>First failing step</th></tr></thead><tbody>{ledger_rows(fed)}</tbody></table></div>
<h2 class="rt-sec" id="gaps">Gap analysis: using our own code to answer, what is missing?</h2><p class="rt-lead">{E(gap["question"])}</p>{gap_cards(gap)}
<h2 class="rt-sec" id="agents">Explicit agentic involvement</h2><p class="rt-lead">{actor("AGENT")} executed by a Claude session · {actor("OWNER")} decided or merged by the repository owner · {actor("CI")} native GitHub Actions evidence. Agents never merge, waive or confirm roots.</p>{actions_table(gap)}
<footer class="rt-foot">Source digest <code>{E(fed["digest_sha256"][:16])}</code> · generated by <code>site/build_redtrace.py</code> · suspects are not causal attribution · no root-closure credit · merge_authorized=false.</footer>
</main></div><script>{JS}</script></body></html>
"""


SLIDE_CSS = """
@page{size:1280px 720px;margin:0}html,body{margin:0;background:var(--bg)}
.deck{display:block}.slide{width:1280px;height:720px;box-sizing:border-box;padding:46px 60px;position:relative;overflow:hidden;
background:radial-gradient(circle at 92% 0,#164533 0,transparent 35%),var(--bg);border-bottom:1px solid var(--stroke);page-break-after:always;break-after:page}
.slide h1{font-size:46px;margin:90px 0 10px;letter-spacing:-.015em}.slide h2{font-size:30px;margin:0 0 18px}
.slide .kick{color:var(--green);font-size:13px;letter-spacing:.16em;font-weight:800}.slide p,.slide li{font-size:17px}
.slide .foot{position:absolute;left:60px;right:60px;bottom:22px;display:flex;justify-content:space-between;color:var(--quiet);font-size:12px}
.slide table.rt{min-width:0}.slide table.rt td,.slide table.rt th{font-size:12.5px;padding:6px 9px}
.slide .rt-card{padding:12px 14px}.slide .rt-card p{font-size:13.5px;margin:4px 0}.slide .rt-grid{grid-template-columns:repeat(3,1fr);gap:10px}
.slide .rt-kpis{grid-template-columns:repeat(4,1fr)}.slide .rt-kpi b{font-size:30px}.toc a{display:block;font-size:19px;margin:7px 0}
.nav-hint{position:fixed;right:14px;top:10px;color:var(--quiet);font-size:12px}@media print{.nav-hint{display:none}}
"""


def slides(fed, gap):
    obs = fed["observed_at_utc"]
    S = []

    def slide(sid, title, body, kick="JADE N+8 · RED-TRACE"):
        S.append((sid, title, f'<section class="slide" id="{sid}" aria-label="{E(title)}"><div class="kick">{E(kick)}</div>{body}'
                              f'<div class="foot"><span>GBOGEB federation · observed {E(obs)} · read-only · ADMISSION HOLD</span>'
                              f'<span><a href="#s-toc">Contents</a> · {{n}}/{{N}}</span></div></section>'))

    slide("s-title", "Red-trace federation ledger", f'<h1>Which workflows are red,<br>since when, and why?</h1>'
          f'<p class="rt-lead">EVERRED · GREEN→RED · RED→GREEN across the five federation core repositories, plus a gap analysis of what our own tooling can and cannot answer.</p>{kpis(fed, gap)}')
    slide("s-toc", "Contents", "<h2>Contents</h2><div class='toc'>{toc}</div>")
    slide("s-core", "Core repositories", f"<h2>What are the core repos? Pipeline vs federation</h2>{core_block(gap)}")
    slide("s-score", "Federation scoreboard", f'<h2>Federation scoreboard</h2><div class="rt-card">{bars(fed)}</div>'
          f'<p>Red now: <b>{fed["totals"]["red_fresh"]}</b> fresh, <b>{fed["totals"]["red_stale"]}</b> stale (replay before trusting), '
          f'<b>{fed["totals"]["pinned_red"]}</b> on pinned historical evidence.</p>')
    for r in fed["repositories"]:
        reds = [w for w in r["non_green"] if w["current"] == "RED"][:7]
        if not reds:
            body = '<p>No workflow red at last observation. Recovered episodes are listed on the HTML page.</p>'
        else:
            rows = "".join(f'<tr><td>{E(w["name"])}</td><td>{chip(*CLS.get(w["class"], ("quiet", w["class"])))}</td><td>{flags(w)}</td>'
                           f'<td>{window_text(w, r["repository"])}</td><td class="rt-step">{E("; ".join((w.get("window") or {}).get("failing", []))[:90])}</td></tr>' for w in reds)
            more = r["currently_red"] - len(reds)
            body = (f'<div class="rt-tablewrap"><table class="rt"><thead><tr><th>Workflow</th><th>Class</th><th>Flags</th><th>Window</th><th>First failing step</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table></div>' + (f'<p><small>+{more} more on the HTML page.</small></p>' if more > 0 else ""))
        slide(f"s-repo-{r['short']}", f"{r['short']} reds", f'<h2>{E(r["short"])}: {r["currently_red"]} red · {r["currently_red_stale"]} stale</h2>'
              f'<p class="rt-lead">{E(r["role"])}</p>{body}', kick=f"JADE N+8 · {r['short'].upper()}")
    g = gap["gaps"]
    for i in range(0, len(g), 6):
        part = {"gaps": g[i:i + 6]}
        slide(f"s-gaps-{i // 6 + 1}", f"Gap analysis {i // 6 + 1}", f'<h2>Gap analysis ({i // 6 + 1}/{(len(g) + 5) // 6}): what our own code could not answer</h2>{gap_cards(part)}')
    slide("s-agents", "Agentic involvement", f'<h2>Explicit agentic involvement</h2><p>{actor("AGENT")} executed · {actor("OWNER")} decided · {actor("CI")} evidence. Agents never merge, waive or confirm roots.</p>{actions_table(gap)}')
    owner = [x for x in g if x["actor"] == "OWNER" or x["state"] in ("DETECTED", "OPEN", "FILLED_PARTIAL")]
    slide("s-decide", "Owner decisions", '<h2>Owner decisions that unblock the rest</h2><ol>' +
          "".join(f'<li><b>{E(x["id"])}</b> {E(x["title"])}: {E(x["next"])}</li>' for x in owner) + "</ol>")
    slide("s-sources", "Sources", '<h2>Sources & replay</h2><ul>' + "".join(
        f'<li><a href="https://github.com/{E(r["repository"])}/actions">{E(r["repository"])}</a>: {r["workflows_traced"]} workflows, '
        f'{r["runs"]:,} runs, digest <code>{E(r["source_digest"][:12])}</code></li>' for r in fed["repositories"]) +
          '<li>Replay: <code>python mission-control/gogreen/red_trace/red_trace.py --repo … --root … --out …</code> then '
          '<code>tools/build_redtrace_data.py</code> and <code>site/build_redtrace.py</code></li></ul>')
    toc = "".join(f'<a href="#{sid}">{i + 1}. {E(t)}</a>' for i, (sid, t, _) in enumerate(S))
    N = len(S)
    body = "".join(h.replace("{toc}", toc).replace("{n}", str(i + 1)).replace("{N}", str(N)) for i, (_, _, h) in enumerate(S))
    nav = """(function(){var s=[].slice.call(document.querySelectorAll('.slide'));function go(d){var y=window.scrollY+1,i=s.findIndex(function(e){return e.offsetTop+e.offsetHeight>y});i=Math.max(0,Math.min(s.length-1,i+d));s[i].scrollIntoView();}
document.addEventListener('keydown',function(e){if(['ArrowRight','PageDown',' '].indexOf(e.key)>-1){e.preventDefault();go(1)}if(['ArrowLeft','PageUp'].indexOf(e.key)>-1){e.preventDefault();go(-1)}});})();"""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1280">'
            f'<title>JADE N+8 · Red-trace federation slides</title><link rel="stylesheet" href="jade.css"><style>{CSS}{SLIDE_CSS}</style></head>'
            f'<body><main class="deck">{body}</main><div class="nav-hint">← → to navigate · Print = PDF</div><script>{nav}</script></body></html>\n'), [(sid, t) for sid, t, _ in S]


def build():
    fed, gap = load(FED), load(GAP)
    for d, s in ((fed, "jade.temple.redtrace_federation.v1"), (gap, "jade.temple.gap_analysis.v1")):
        if d.get("schema") != s or d.get("authority", {}).get("merge_authorized") is not False:
            raise SystemExit(f"invalid source {s}")
    deck, outline = slides(fed, gap)
    files = {"redtrace.html": page(fed, gap).encode(), "redtrace-slides.html": deck.encode()}
    manifest = {"schema": "jade.temple.redtrace_manifest.v1", "iteration": "N+8",
                "sources_sha256": {r: hashlib.sha256((ROOT / r).read_bytes()).hexdigest() for r in (FED, GAP)},
                "public_files_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
                "slide_outline": [{"id": i, "title": t} for i, t in outline],
                "pdf": {"file": "redtrace-slides.pdf", "renderer": "tools/render_redtrace_pdf.py", "deterministic": False},
                "replay_command": "python mission-control/jade_temple/site/build_redtrace.py --check",
                "merge_authorized": False}
    files["redtrace-manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return files


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    files = build()
    if a.check:
        bad = [n for n, b in files.items() if not (SITE / n).exists() or (SITE / n).read_bytes() != b]
        if bad:
            raise SystemExit("REDTRACE_DRIFT: " + ", ".join(bad))
        print("REDTRACE_CHECK=PASS files=%d" % len(files))
        return
    for n, b in files.items():
        (SITE / n).write_bytes(b)
    print("REDTRACE_BUILD=PASS files=%d" % len(files))


if __name__ == "__main__":
    main()
