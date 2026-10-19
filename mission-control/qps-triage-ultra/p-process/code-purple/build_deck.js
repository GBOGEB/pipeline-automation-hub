// Builds the 16:9 Code Purple deck (HTML -> PDF) from the same model as index.html.
// Usage: node build_deck.js [--census FILE] [--out DIR]
//   -> OUT/deck.html, OUT/deck_landscape.pdf, OUT/deck_portrait.pdf, OUT/deck_sections.json, OUT/code-purple.md
// Paths resolve from this file, never from the working directory. Fonts are the vendored OFL files in ../fonts.
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const ROOT = path.resolve(DIR, '..');
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = path.resolve(arg('--out', process.env.CP_OUT || path.join(ROOT, 'build')));
fs.mkdirSync(OUT, { recursive: true });
const CENSUS = [arg('--census'), process.env.CP_CENSUS, path.join(ROOT, 'kit/out/census.json'), path.join(ROOT, 'site/code-purple/kit/census.json')]
  .filter(Boolean).find(f => fs.existsSync(f));
if (!CENSUS) throw new Error('no census.json: run kit/readback.py or pass --census');
function loadPlaywright() {
  for (const m of [process.env.PLAYWRIGHT_MODULE, 'playwright', '/opt/npm-tools/node_modules/playwright'].filter(Boolean)) {
    try { return require(m); } catch (e) { /* try next */ }
  }
  throw new Error('playwright not found: npm i playwright or set PLAYWRIGHT_MODULE');
}
const { chromium } = loadPlaywright();

const SRC = fs.readFileSync(path.join(DIR, 'index.html'), 'utf8');
const LIFT = JSON.parse(fs.readFileSync(CENSUS, 'utf8'));
const LIFT_MET = LIFT.lift.filter(x => x.ok).length;
const STAMP = `GitHub readback ${LIFT.generated_at.replace('T', ' ').slice(0, 16)} UTC · ${LIFT.lifted ? 'lifted' : `not lifted: ${LIFT_MET} of ${LIFT.lift.length} lift criteria met`}`;

// ---------- reuse model + page CSS ----------
const M = require('./assets/model.js');
const pageCSS = SRC.slice(SRC.indexOf('<style>') + 7, SRC.indexOf('</style>'));
const F = path.join(ROOT, 'fonts') + '/';
const ff = (fam, file, w) => `@font-face{font-family:"${fam}";font-weight:${w};src:url(data:font/woff2;base64,${fs.readFileSync(F + file).toString('base64')}) format("woff2")}`;
const fontCSS = [
  ff('IBM Plex Sans', 'ibm-plex-sans-latin-400-normal.woff2', 400),
  ff('IBM Plex Sans', 'ibm-plex-sans-latin-500-normal.woff2', 500),
  ff('IBM Plex Sans', 'ibm-plex-sans-latin-600-normal.woff2', 600),
  ff('IBM Plex Mono', 'ibm-plex-mono-latin-400-normal.woff2', 400),
  ff('IBM Plex Mono', 'ibm-plex-mono-latin-500-normal.woff2', 500),
  ff('Archivo', 'archivo-latin-600-normal.woff2', 600),
  ff('Archivo', 'archivo-latin-800-normal.woff2', 800),
].join('\n');

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const byId = Object.fromEntries(M.NODES.map(n => [n.id, n]));

// ---------- sections ----------
const SECTIONS = [
  { id: 'A', key: 'situation', name: 'Situation' },
  { id: 'B', key: 'read', name: 'How to read' },
  { id: 'C', key: 'protocol', name: 'Protocol' },
  { id: 'D', key: 'lifecycle', name: 'Lifecycle' },
  { id: 'E', key: 'admission', name: 'Admission' },
  { id: 'F', key: 'coverage', name: 'Coverage' },
  { id: 'G', key: 'evidence', name: 'Evidence & structure' },
  { id: 'H', key: 'method', name: 'Lift & method' },
];

(async () => {
  // ---------- grab rendered SVGs from the page ----------
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1400, height: 1200 } });
  await p.route('**/fonts.g*/**', r => r.abort());
  await p.goto('file://' + path.join(DIR, 'index.html'));
  await p.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  const svgs = await p.evaluate(() => ({
    pulse: document.querySelector('#canvas svg').outerHTML,
    life: document.querySelector('#lifeSvg svg').outerHTML,
    sipoc: document.querySelector('#sipoc svg').outerHTML,
  }));
  const strip = s => s.replace(/<path class="hitp"[^>]*>.*?<\/path>/g, '').replace(/ style="min-width:760px"/, '');

  // ---------- slide helpers ----------
  const slides = [];
  const add = (sec, html, opts = {}) => slides.push({ sec, html, ...opts });
  const pill = (cls, t) => `<span class="st-pill ${cls}">${esc(t)}</span>`;
  const kicker = t => `<div class="kick">${t}</div>`;
  const title = (t, sub) => `<h1>${t}</h1>${sub ? `<p class="lede">${sub}</p>` : ''}`;
  const swatchRole = k => `<span class="sw ${k === 'dec' ? 'dec' : k}"></span>`;

  // ===== A. SITUATION =====
  add('A', `
    <div class="cover">
      ${kicker('QPS TRIAGE · ABACUS · CODEX · FEDERATED DMAIC')}
      <div class="lifted" style="background:#c9405f">NOT LIFTED · GATE NOT RESTORED</div>
      <h1 class="big">Global Code Purple</h1>
      <p class="lede" style="max-width:1150px">A recursively self-testing execution protocol across repositories, agents, CI, PR admission and evidence. It builds on QPS TRIAGE, ABACUS, CODEX, KEB and DOW and adds no second authority.</p>
      <div class="cover-meta">
        <div><b>Status at</b><span>${STAMP}</span></div>
        <div><b>Seed</b><span class="mono">CODEX main · federation/mesh/CODE_PURPLE_EXECUTION_SEED_20261012.yaml</span></div>
        <div><b>Owner</b><span>GBO · Process Engineer, QPLANT System Owner, SCK CEN</span></div>
      </div>
    </div>`, { cover: true });

  add('A', `${title('Contents')}
    <div class="toc">${SECTIONS.map(s => `<a class="toc-i" href="#sec-${s.id}"><span class="toc-l">${s.id}</span><span class="toc-n">${s.name}</span><span class="toc-p" data-sec="${s.id}"></span></a>`).join('')}</div>
    <p class="note">Every slide has a section bar at the top; click a section to jump to its first slide. Slide numbers are bottom right.</p>`);

  add('A', `${kicker('Executive summary')}${title('ABACUS has merged nothing since 6 October; one PR unblocks it')}
    <div class="cols3">
      <div class="card"><div class="cap">What is blocked</div><p>All 20 open ABACUS PRs. The <b>Main Hard Gate</b> ruleset requires one check, <span class="mono">PR Feedback Gate</span>, which waits for an exact-head Codex code and security review. The Codex allowance is exhausted, so the gate never turns green.</p></div>
      <div class="card"><div class="cap">The fix in flight</div><p><b>ABACUS #1858</b> lets the owner attest the exact head when Codex cannot run. It cannot approve itself: the gate runs main's code. It needs a one-time owner <b>break-glass</b> on the ruleset to land.</p></div>
      <div class="card"><div class="cap">Already merged</div><p><b>CODEX #984</b> (this protocol's seed) merged at 12:16 with 4 red checks. CODEX main has no required-check ruleset, so nothing stopped it. CODEX main is green again on its current head.</p></div>
    </div>
    <div class="callbar"><b>Decisions needed from GBO:</b> (1) accept the 4 inherited reds under break-glass (they fail nightly on main) · (2) add the one-time bypass on ruleset 24494381. Done: threads resolved, #1878/#1879 opened, policy-and-inventory fixed (e7616e62).</div>`);

  const prRows = [
    ['ABACUS #1858', 'Owner-attested review fallback', 'e7616e62', 'open', '87 / 2 / 1', 'Code Quality, Security Scanning (Coverage, Full Red Proof still running) · policy-and-inventory now green', 'hold'],
    ['ABACUS #1859', 'PR-level new-debt ratchet', '6fac58cc', 'open', '61 / 4 / 1', 'Code Quality, Full Red Proof, Security Scanning, validate-scripts', 'block'],
    ['ABACUS #1857', 'Fix syntax error in diagnostic_kpi_probe.py', 'e7b45912', 'open', '60 / 4 / 1', 'Code Coverage, Code Quality, Full Red Proof, Security Scanning', 'block'],
    ['ABACUS #1856', 'Lossless branch hygiene burn-down', 'f11d8044', 'open', '91 / 3 / 1', 'Code Coverage, Code Quality, Full Red Proof', 'block'],
    ['CODEX #984', 'Code Purple execution seed', '90e3396a', 'merged 12:16', '55 / 4 / 0', 'ruff, governance-gate ×2, validate (at merge)', 'ok'],
    ['CODEX main', 'after #984 merge', '768c9e35', 'main', '38 / 2 / 0', 'validate (fixed on main at f9ae4676), osv-scan (fails on every main push since before #984)', 'block'],
    ['CODEX main', 'current head', 'cce9ce20', 'main', '—', 'MissionControl CI green; OSV-Scanner red (pre-existing)', 'hold'],
  ];
  add('A', `${kicker('Readback')}${title('Tracked heads at 17:55')}
    <table class="t"><thead><tr><th>Item</th><th>Subject</th><th>Head</th><th>State</th><th class="r">Pass / fail / neutral</th><th>Red checks</th></tr></thead><tbody>
    ${prRows.map(r => `<tr><td class="b">${r[0]}</td><td>${r[1]}</td><td class="mono">${r[2]}</td><td>${pill(r[6], r[3])}</td><td class="r mono">${r[4]}</td><td>${r[5]}</td></tr>`).join('')}
    </tbody></table>
    <p class="note">Counts exclude skipped and cancelled runs. ABACUS main's last merge is #1838 (2026-10-06).</p>`);

  // ===== B. HOW TO READ =====
  add('B', `${kicker('Taxonomy')}${title('Four kinds of reference, one model')}
    <div class="tax">
      <div class="tax-col"><div class="tax-h">Structure · what the protocol does</div>
        <div class="tx"><span class="idchip">1–8</span><b>Stages</b><span>The pulse written as a procedure. Each stage groups nodes and lists entry, actions and exit.</span></div>
        <div class="rel">contain ↓</div>
        <div class="tx"><span class="idchip">N01–N15</span><b>Nodes</b><span>One step of a pulse: who owns it, which artefact, what evidence it writes. Drawn on the pulse graph.</span></div>
        <div class="rel">are joined by ↓</div>
        <div class="tx"><span class="idchip">E01–E19</span><b>Edges</b><span>Typed connections: sequence, pass, red, hold, evidence, recursion.</span></div>
      </div>
      <div class="tax-col"><div class="tax-h">Lifecycle · what moves a work item</div>
        <div class="tx"><span class="idchip">12</span><b>States</b><span>Where a PR head or red finding is: test pending, set-up, run, debug, fix, integrate, admission, follow-up, hold, merged, federate.</span></div>
        <div class="rel">are changed by ↓</div>
        <div class="tx"><span class="idchip">T01–T16</span><b>Triggers</b><span>One event, one guard, one action. Each trigger names the nodes it acts at and whether it is wired today.</span></div>
        <div class="rel">act at → Nodes</div>
      </div>
      <div class="tax-col"><div class="tax-h">Evidence · what proves it</div>
        <div class="tx"><span class="idchip">per node</span><b>Telemetry</b><span>Preconfig (stage, test, debug), run attempts with pass / fail / neutral / pending, errors, logs.</span></div>
        <div class="rel">is kept as ↓</div>
        <div class="tx"><span class="idchip">sha</span><b>Receipts &amp; census</b><span>Exact-commit receipts per run; one census row per iteration N.</span></div>
        <div class="rel">is learned as ↓</div>
        <div class="tx"><span class="idchip">REX</span><b>Lessons</b><span>Recurring causes and reusable fixes, read back at the start of the next pulse.</span></div>
      </div>
    </div>
    <div class="callbar" style="background:var(--accent-soft);border-color:var(--accent);color:var(--ink)"><b>Worked example.</b> Trigger <b>T11</b> moved #1858 from <i>Admission</i> to <i>HOLD</i>. It acts at nodes <b>N10</b> (gate) and <b>N11</b> (hold), which belong to stages <b>6</b> and <b>7</b>. On the pulse graph that move is edge <b>E12</b>, and the hold record is evidence for REX.</div>
    <p class="note">Phase letters <b>D M A I C</b> (Define, Measure, Analyse, Improve, Control) tag every node and stage.</p>`);

  const roles = [['auth', 'Authority', 'Resolves or owns state: controller, allocation, output'], ['proc', 'Process', 'Checks and verification'], ['dec', 'Gate', 'A binary decision'], ['rep', 'Repair', 'Isolated change and retest'], ['pass', 'Admitted path', 'Merge and post-merge proof'], ['hold', 'Hold', 'Blocked, logged, retried'], ['evid', 'Evidence store', 'REX and KEB']];
  const edges = [['flow', 'Sequence', 'Normal next step'], ['yes', 'Pass', 'Admissible successor'], ['fail', 'Material red', 'Goes to repair'], ['hold', 'Hold', 'Deferred or blocked'], ['evid', 'Evidence', 'Receipts and lessons'], ['rec', '.self recursion', 'Output N becomes input N+1']];
  const stat = [['ok', 'Seeded / committed'], ['progress', 'In progress'], ['partial', 'Partial'], ['hold', 'On hold'], ['todo', 'Not implemented'], ['none', 'Not reached']];
  add('B', `${kicker('Legend')}${title('Colour, line and status vocabulary')}
    <div class="cols3 legend3">
      <div><div class="cap">Node roles (fill)</div>${roles.map(r => `<div class="lgr">${swatchRole(r[0])}<div><b>${r[1]}</b><span>${r[2]}</span></div></div>`).join('')}</div>
      <div><div class="cap">Edge types (line)</div>${edges.map(r => `<div class="lgr"><svg viewBox="0 0 60 14" class="lsv"><line x1="0" y1="7" x2="60" y2="7" class="e-${r[0]}"/></svg><div><b>${r[1]}</b><span>${r[2]}</span></div></div>`).join('')}
        <div class="cap" style="margin-top:22px">Markers</div>
        <div class="lgr"><svg viewBox="0 0 60 14" class="lsv"><circle cx="30" cy="7" r="6" class="rcpt"/></svg><div><b>Receipt</b><span>Step writes an exact-commit receipt</span></div></div>
        <div class="lgr"><svg viewBox="0 0 60 14" class="lsv"><rect x="0" y="5" width="34" height="4" class="seg-pass"/><rect x="34" y="5" width="10" height="4" class="seg-fail"/><rect x="44" y="5" width="16" height="4" class="seg-pend"/></svg><div><b>Run bar</b><span>pass · fail · pending share of attempts</span></div></div>
        <div class="lgr"><svg viewBox="0 0 60 14" class="lsv"><rect x="1" y="1" width="58" height="12" rx="4" class="ring"/></svg><div><b>Tracked PR</b><span>Where a live PR is now</span></div></div></div>
      <div><div class="cap">Implementation status</div>${stat.map(r => `<div class="lgr">${pill(r[0], r[1])}</div>`).join('')}
        <div class="cap" style="margin-top:22px">Trigger wiring</div>
        <div class="lgr">${pill('ok', 'Wired')}<div><span>Fires automatically today</span></div></div>
        <div class="lgr">${pill('partial', 'Partly wired')}<div><span>Detection automatic, response manual</span></div></div>
        <div class="lgr">${pill('hold', 'Manual')}<div><span>A person does it</span></div></div>
        <div class="lgr"><span class="wired proposed">Proposed</span><div><span>Not built yet</span></div></div></div>
    </div>`);

  const gloss = [
    ['DMAIC', 'Define, Measure, Analyse, Improve, Control: the phases each node belongs to.'],
    ['SIPOC', 'Supplier, Input, Process, Output, Customer. With .self, the customer of N supplies N+1.'],
    ['.self', 'The recursive interface: validated output N becomes input N+1 through governed reconciliation (⊕).'],
    ['Exact head', 'The one commit SHA under test. Evidence for any other SHA does not count.'],
    ['Material red', 'A completed failing check that blocks admission, as opposed to neutral or pending.'],
    ['Non-waivable gate', 'A required check or review that must be green on the same SHA before merge.'],
    ['Break-glass', 'A one-time, owner-only bypass of the ruleset, restored immediately and recorded in REX.'],
    ['Single-flight', 'One admitted PR merges at a time so no head goes stale behind another merge.'],
    ['Pre-match', 'Reusing a result already proven for the identical commit and inputs instead of re-running it.'],
    ['Receipt', 'A small record binding a result to an exact commit and input hash.'],
    ['REX · KEB', 'CODEX evidence stores: reusable lessons and recurrence (REX), evidence identity (KEB).'],
    ['DOW', 'ABACUS derived analysis: ranks findings and returns scoped dispositions.'],
    ['GLOB · MESH_DOCK', 'Global capability census and the producer/consumer contract between repos.'],
    ['Inherited debt', 'A red already present on main, as opposed to a defect the PR introduced.'],
  ];
  add('B', `${kicker('Glossary')}${title('Terms used in this deck')}
    <dl class="gloss">${gloss.map(g => `<div><dt>${g[0]}</dt><dd>${g[1]}</dd></div>`).join('')}</dl>`);

  // ===== C. PROTOCOL =====
  const steps = [['Reuse proven evidence', 'D→M'], ['Allocate, preconfigure, pretest', 'M'], ['Find the first material red', 'A'], ['Repair the smallest common cause', 'I'], ['Verify independently', 'I'], ['Publish exact-head evidence', 'C'], ['Advance only admissible successors', 'C']];
  add('C', `${kicker('The central rule')}${title('Seven steps, in order, every pulse')}
    <ol class="rule7">${steps.map((s, i) => `<li><span class="n">${String(i + 1).padStart(2, '0')}</span><b>${s[0]}</b><span class="ph">${s[1]}</span></li>`).join('')}</ol>
    <p class="lede" style="margin-top:40px">A passing local preflight raises confidence for the next iteration. Only exact-head GitHub checks and reviews move a PR through admission.</p>`);

  add('C', `<div class="split">
      <div class="split-l">${kicker('Execution pulse')}${title('One pulse, three lanes')}
        <p class="body">The admission spine runs down the centre. Reds go right into the repair loop; holds and evidence sit on the left. The dotted rings mark where the two tracked PRs are now.</p>
        <div class="mini-legend">${roles.map(r => `<span>${swatchRole(r[0])}${r[1]}</span>`).join('')}</div>
        <div class="callbar small"><b>#1858</b> waits at N10 (gate). <b>#984</b> reached N14 without passing N10.</div>
      </div>
      <div class="split-r">${strip(svgs.pulse)}</div></div>`, { pulse: true });

  // ---- cross-reference helpers (slugs shared with the markdown parent) ----
  const slugN = id => 'node-' + id.toLowerCase(), slugS = n => 'stage-' + n, slugT = id => 'trig-' + id.toLowerCase();
  const nref = id => `<a class="xr n" href="#${slugN(id)}">${id}</a>`;
  const sref = n => `<a class="xr s" href="#${slugS(n)}">${n}</a>`;
  const tref = id => `<a class="xr t" href="#${slugT(id)}">${id}</a>`;
  const stageOf = {}; M.STAGES.forEach(st => st.nodes.forEach(id => stageOf[id] = st.n));
  const trigOf = {}; M.TRIGGERS.forEach(t => t.nodes.forEach(id => (trigOf[id] = trigOf[id] || []).push(t.id)));

  const stageCard = st => `<div class="stg" id="${slugS(st.n)}"><div class="stg-badge"><span>${st.n}</span><i>${M.PH[st.ph]}</i></div><div class="stg-b"><div class="stg-h"><b>${esc(st.name)}</b><span class="ids">${st.nodes.map(id => `${nref(id)} <em>${esc(byId[id].label)}</em>`).join('')}</span></div>
    <div class="eae3"><div><i>Entry</i>${st.entry.map(esc).join('<br>')}</div><div><i>Actions</i>${st.acts.map(esc).join('<br>')}</div><div><i>Exit</i>${st.exit.map(esc).join('<br>')}</div></div></div></div>`;
  add('C', `${kicker('Process stages 1–4 · click a node ID for its reference row')}${title('From trigger to first red')}<div class="stgs">${M.STAGES.slice(0, 4).map(stageCard).join('')}</div>`);
  add('C', `${kicker('Process stages 5–8 · click a node ID for its reference row')}${title('From repair to the next pulse')}<div class="stgs">${M.STAGES.slice(4).map(stageCard).join('')}</div>`);

  const nodeRows = ns => ns.map(n => `<tr id="${slugN(n.id)}"><td class="idc">${n.id}</td><td><b>${esc(n.label)}</b><div class="sub">${esc(n.does)}</div></td><td class="nw">${swatchRole(n.kind)} ${M.KIND[n.kind]}</td><td class="c">${stageOf[n.id] ? sref(stageOf[n.id]) : '—'}</td><td>${(trigOf[n.id] || []).map(tref).join(' ') || '—'}</td><td class="small">${esc(n.artefact)}</td><td>${pill(n.status, M.STATUS[n.status])}</td></tr>`).join('');
  const nodeTable = ns => `<table class="t dense"><thead><tr><th>ID</th><th>Node · what it does</th><th>Role</th><th class="c">Stage</th><th>Triggers</th><th>Artefact</th><th>Status</th></tr></thead><tbody>${nodeRows(ns)}</tbody></table>`;
  add('C', `${kicker('Node reference 1 / 2 · stage and trigger IDs are links')}${title('Mobilise, measure, triage, repair')}${nodeTable(M.NODES.slice(0, 8))}`);
  add('C', `${kicker('Node reference 2 / 2 · stage and trigger IDs are links')}${title('Admit, hold, learn, merge, prove')}${nodeTable(M.NODES.slice(8))}`);

  // ===== D. LIFECYCLE =====
  add('D', `${kicker('Lifecycle')}${title('What moves a work item from state to state')}
    <div class="lifewrap">${svgs.life}</div>
    <div class="chipstrip">${M.TRIGGERS.map(t => tref(t.id)).join('')}</div>
    <p class="note">Each arrow is a trigger T01–T16: one event, one guard, one action. Tracked PRs: #1858 sits in HOLD (via T11), #984 in Merged (via T14 without a gate).</p>`);

  const wc = w => w === 'wired' ? 'ok' : w === 'partial' ? 'partial' : w === 'manual' ? 'hold' : 'proposed';
  const trigRows = ts => ts.map(t => {
    const F = M.LSTATES.find(x => x.id === t.f).label, T = M.LSTATES.find(x => x.id === t.t).label;
    const w = wc(t.w);
    return `<tr id="${slugT(t.id)}"><td class="idc">${t.id}</td><td class="nw">${esc(F)} → ${esc(T)}</td><td>${esc(t.ev)}</td><td>${esc(t.act)}</td><td class="nw">${t.nodes.map(nref).join(' ')}</td><td>${w === 'proposed' ? '<span class="wired proposed">Proposed</span>' : pill(w, M.WIRED[t.w])}<div class="sub">${esc(t.wn)}</div></td></tr>`;
  }).join('');
  const trigTable = ts => `<table class="t dense"><thead><tr><th>ID</th><th>From → to</th><th>Trigger event</th><th>Action</th><th>Nodes</th><th>Wired today</th></tr></thead><tbody>${trigRows(ts)}</tbody></table>`;
  add('D', `${kicker('Triggers 1 / 2')}${title('Set-up, run, debug, fix, integrate')}${trigTable(M.TRIGGERS.slice(0, 9))}`);
  add('D', `${kicker('Triggers 2 / 2')}${title('Admission, follow-up, hold, merge, federate')}${trigTable(M.TRIGGERS.slice(9))}`);

  const wcount = { wired: 0, partial: 0, manual: 0, proposed: 0 };
  M.TRIGGERS.forEach(t => wcount[t.w]++);
  const tot = M.TRIGGERS.length;
  const wbar = Object.entries(wcount).map(([k, v]) => {
    const lbl = { wired: 'Wired', partial: 'Partly wired', manual: 'Manual', proposed: 'Proposed' }[k];
    const ids = M.TRIGGERS.filter(t => t.w === k).map(t => t.id).join(' ');
    return `<div class="wrow"><span class="wl">${lbl}</span><div class="wtrack"><div class="wfill w-${k}" style="width:${(v / tot * 100).toFixed(1)}%"></div></div><span class="wv">${v}</span><span class="wids mono">${ids}</span></div>`;
  }).join('');
  add('D', `${kicker('Automation coverage')}${title(`Only ${wcount.wired} of ${tot} transitions fire on their own`)}
    <div class="wchart">${wbar}</div>
    <div class="cols2" style="margin-top:44px">
      <div class="card"><div class="cap">Automatic today</div><p>Fully automatic: a new head restarts the cycle (T07) and review events re-run the gate (T10). Partly automatic: CI starts on push and PR events but the gate does not reset on synchronize (T01), and thread detection is wired while the response is manual (T09).</p></div>
      <div class="card"><div class="cap">Next to wire</div><p>The <span class="mono">.self</span> harness (T02 set-up receipt), a scheduled readback pulse (T12), and debug-on-red using the existing CODEX LLDB and debugpy lanes (T04).</p></div>
    </div>`);

  // ===== E. ADMISSION =====
  const inv = [
    ['Exact-head Codex code review complete', 'no', 'Pending; Codex allowance exhausted'],
    ['Exact-head Codex security review complete', 'no', 'Pending; Codex allowance exhausted'],
    ['Zero unresolved review threads', 'yes', 'Both resolved 17:20 as owner residual risk → #1878, #1879'],
    ['Current-head GitHub Actions terminal and green', 'no', 'Code Quality and Security Scanning red; all inherited from main (see next slide)'],
    ['Current-head admission evidence terminal and green', 'wait', 'Gate re-running on e7616e62'],
    ['Known deferred warnings linked to open issues', 'yes', '#1736'],
  ];
  const mark = v => v === 'yes' ? '<span class="mk ok">✓</span>' : v === 'no' ? '<span class="mk no">✗</span>' : '<span class="mk wt">…</span>';
  add('E', `${kicker('ABACUS #1858 · head e7616e62')}${title('Gate invariants: 2 met, 3 failing, 1 running')}
    <table class="t inv"><tbody>${inv.map(r => `<tr><td class="c">${mark(r[1])}</td><td class="b">${r[0]}</td><td>${r[2]}</td></tr>`).join('')}</tbody></table>
    <p class="note">The gate checks out the default branch, so #1858's own fallback cannot admit #1858. The code reviews stay unmet until Codex is back or the owner uses break-glass.</p>`);

  const checks = ['Code Coverage', 'Code Quality Checks', 'Full Red Proof Summary', 'Security Scanning', 'policy-and-inventory', 'validate-scripts'];
  const mx = {
    'main nightly': ['r', 'r', 'r', 'r', '', ''],
    '#1858': ['…', 'r', '…', 'r', 'g', ''],
    '#1859': ['', 'r', 'r', 'r', '', 'r'],
    '#1857': ['r', 'r', 'r', 'r', '', ''],
    '#1856': ['r', 'r', 'r', '', '', ''],
  };
  const cls = ['Inherited debt · confirmed', 'Inherited debt · confirmed', 'Inherited debt · confirmed', 'Inherited debt · confirmed', 'Source defect · fixed in e7616e62', 'Unclassified'];
  const cell = v => v === 'r' ? '<td class="mx r">red</td>' : v === 'c' ? '<td class="mx c">cancelled</td>' : v === 'g' ? '<td class="mx g">green</td>' : v === '…' ? '<td class="mx c">running</td>' : '<td class="mx"></td>';
  add('E', `${kicker('Failure classification')}${title('Four reds fail on main every night: inherited, not caused by PRs')}
    <table class="t mxt"><thead><tr><th>Check</th>${Object.keys(mx).map(k => `<th class="c">${k}</th>`).join('')}<th>Class</th></tr></thead><tbody>
    ${checks.map((c, i) => `<tr><td class="b">${c}</td>${Object.values(mx).map(r => cell(r[i])).join('')}<td>${cls[i]}</td></tr>`).join('')}
    </tbody></table>
    <div class="cols2" style="margin-top:28px">
      <div class="card"><div class="cap">policy-and-inventory on #1858 · fixed</div><p><span class="mono">docs/ci/WORKFLOW_RATIONALIZATION.md</span> went stale after the one-line policy change. Regenerated and pushed as e7616e62; the check is green on the new head.</p></div>
      <div class="card"><div class="cap">Recurring reds · confirmed on main</div><p>ABACUS main (53688f26) fails Security Scanning, Code Quality, Code Coverage and Full Red Proof in every nightly CI/CD Test Suite run since at least 7 October. Each is an “Enforce … red roots / threshold” step: inherited debt. #1859 targets exactly this.</p></div>
    </div>`);

  const seq = [
    ['Claude', 'Done: threads resolved, #1878 #1879 opened and corrected', '17:20 · 17:55'],
    ['Claude', 'Done: regenerated rationalization doc pushed', 'e7616e62 · green'],
    ['GBO', 'Accept the 4 inherited reds under break-glass', 'they fail nightly on main'],
    ['GBO', 'Add yourself as bypass actor on ruleset 24494381', 'one-time'],
    ['Claude', 'Squash-merge #1858, read back ABACUS main CI', 'merge receipt'],
    ['GBO', 'Remove the bypass immediately', 'ruleset restored'],
    ['Claude', 'Write the REX entry; re-evaluate the 20 open PRs', 'owner attestation now available'],
  ];
  add('E', `${kicker('Landing #1858')}${title('Break-glass sequence, owner and Claude steps')}
    <ol class="seq">${seq.map((s, i) => `<li><span class="n">${i + 1}</span><span class="who ${s[0] === 'GBO' ? 'g' : 'c'}">${s[0]}</span><b>${s[1]}</b><span class="out">${s[2]}</span></li>`).join('')}</ol>
    <p class="note">#1878 and #1879 turned out to be fixed in the PR already (a7f623b5, 14430046); they stay open as post-merge checks. Ruleset at 17:55: active, 0 bypass actors.</p>`);

  add('E', `${kicker('CODEX #984')}${title('Merged, but the admission step was skipped')}
    <div class="cols2">
      <div class="card"><div class="cap">What happened</div><p>#984 merged at 12:16 with 4 red checks on head 90e3396a: ruff, governance-gate ×2, validate. CODEX main has no required-check ruleset, so the merge went through. After the merge, 768c9e35 had 38 pass and 2 fail. <b>validate</b> (deterministic materializations) was fixed on main at f9ae4676. <b>osv-scan</b> fails on every main push, including before #984: inherited.</p></div>
      <div class="card"><div class="cap">Why it matters for Code Purple</div><p>The protocol's own rule (advance only admissible successors) was not enforced on the repository that holds the protocol. ABACUS enforces a gate that is too strict to pass; CODEX enforces none.</p></div>
    </div>
    <div class="callbar">Decision for GBO by 14 October: give CODEX main a required-check ruleset like ABACUS, or record why not.</div>`);


  // ===== F. COVERAGE =====
  const kpi = (v, l, s2, cls) => `<div class="ktile ${cls || ''}"><span class="kl">${l}</span><b>${v}</b><span class="ks">${s2}</span></div>`;
  add('F', `${kicker('Coverage · measured on #1858 head 203d63af, 1,086 tests')}${title('Coverage is 37%: breadth × depth')}
    <div class="krow">${kpi('36.9%', 'Overall', 'line + branch, as the gate measures it', 'hold')}${kpi('38.2%', 'Lines', '10,686 of 27,998 statements')}${kpi('64.5%', 'Breadth', 'statements in files any test touches (155 of 269 files)')}${kpi('59.2%', 'Depth', 'lines covered inside those touched files')}</div>
    <div class="formula big" style="margin-top:34px">coverage = breadth × depth = 0.645 × 0.592 = 0.38 → target 0.90 × 0.84 ≈ 0.75</div>
    <div class="cols2"><div class="card"><div class="cap">Why it reads ~30%</div><p>CI recorded 37% on 1 October over a wider scope (41,408 statements). 114 files have no test at all; they hold 9,952 statements, 57% of the gap.</p></div>
    <div class="card"><div class="cap">What the gate does today</div><p><span class="mono">Enforce coverage threshold</span> fails at a fixed 75% on every PR, so the same red appears everywhere and steers nothing.</p></div></div>
    <p class="note">Local run with the CI command (<span class="mono">pytest --cov=.</span>, branch on). Docker integration tests deselected (no Docker here); CoolProp tests skip as in CI.</p>`);

  const areas = [['DMAIC_V3', 100, 12095, 25.3, 9036], ['repo root scripts', 41, 6105, 11.5, 5401], ['tools', 33, 3838, 75.6, 938], ['scripts', 18, 2231, 73.5, 591], ['models', 16, 1079, 77.4, 244], ['renderers', 4, 235, 0, 235], ['src/dmaic', 7, 305, 39.0, 186], ['rtm_integration', 1, 235, 23.0, 181], ['integration', 8, 135, 0, 135], ['src/qplant_presentation_engine', 12, 334, 65.9, 114]];
  const gap = 17312, AW = 860, AX = 470, rH = 64, maxM = 12095;
  let ab = `<svg viewBox="0 0 ${AX + AW + 330} ${areas.length * rH + 20}" class="barsvg">`;
  areas.forEach((a, i) => { const y = 8 + i * rH, w = a[4] / maxM * AW;
    ab += `<text x="${AX - 18}" y="${y + 24}" class="bl">${a[0]}</text><text x="${AX - 18}" y="${y + 46}" class="bv" text-anchor="end" style="text-anchor:end">${a[1]} files · ${a[3]}% covered</text>`;
    ab += `<rect x="${AX}" y="${y + 6}" width="${(a[2] / maxM * AW).toFixed(1)}" height="40" class="bk-skip" opacity=".45"/><rect x="${AX}" y="${y + 6}" width="${w.toFixed(1)}" height="40" class="bk-fail"/>`;
    ab += `<text x="${AX + Math.max(w, a[2] / maxM * AW) + 14}" y="${y + 33}" class="bv">${a[4].toLocaleString('en')} missing · ${(a[4] / gap * 100).toFixed(1)}% of gap</text>`; });
  ab += `</svg>`;
  add('F', `${kicker('Coverage hierarchy · repo → area → file')}${title('Two areas hold 83% of the 17,312 missing lines')}
    <div class="barkey"><span><i class="bk-fail"></i>missing lines</span><span><i class="bk-skip" style="opacity:.45"></i>area size (statements, where larger than missing)</span></div>${ab}`);

  add('F', `${kicker('Coverage · what is done today')}${title('Measured on every PR, but nothing ratchets it upward')}
    <div class="cols2">
      <div class="card"><div class="cap">In place</div><ul class="ul">
        <li><span class="mono">ci-cd-tests.yml</span> measures broad coverage on every PR and writes it to the job summary</li>
        <li>A ranked debt list per run (artifact <span class="mono">broad-coverage-ranking-&lt;sha&gt;</span>)</li>
        <li><span class="mono">governance/coverage/criticality_manifest.json</span>: user-directed high-criticality files (B10 cluster)</li>
        <li>Targeted tests in <span class="mono">tests/coverage/</span> for phase 1, 4, 8, execution tracker, debug pipeline</li>
        <li>MIP B0 canonical coverage evidence with per-test contexts (<span class="mono">dynamic_context = test_function</span>)</li>
        <li>#1859 proposes a PR-level new-debt ratchet</li></ul></div>
      <div class="card"><div class="cap">Missing</div><ul class="ul">
        <li>No floor that rises: the gate is a fixed 75%, red on every PR</li>
        <li>No diff coverage on new or changed lines</li>
        <li>No wave plan with owners and dates</li>
        <li>34 one-shot or legacy files sit in the denominator without a disposition</li>
        <li>Per-test contexts are recorded but not used to pick impacted tests (N05 pre-match)</li>
        <li>Coverage is not in the iteration census, so trends are invisible</li></ul></div>
    </div>`);

  const waves = [['W0', 'Baseline, ratchet on', 38.2, 'Floor = measured; new lines ≥ 80%', '16 Oct'], ['W1', 'Governed scope', 46.5, '34 legacy/one-shot files: keep+test, archive or omit', '20 Oct'], ['W2', 'DMAIC_V3 phases', 52.1, '10 phase modules to 80%', '27 Oct'], ['W3', 'Untested DMAIC_V3', 65.5, '53 zero-coverage modules to 70%', '6 Nov'], ['W4', 'Rest of DMAIC_V3', 72.1, '34 partly covered modules to 75%', '13 Nov'], ['W5', 'Tail', 80.2, 'tools, scripts, models, src to 80%', '20 Nov']];
  const WX = 120, WW = 1500, WH = 520, y0 = 590, sy = v => y0 - (v / 100) * WH, bw = 190;
  let wv = `<svg viewBox="0 0 1760 660" class="barsvg">`;
  [0, 25, 50, 75, 100].forEach(v => { wv += `<line x1="${WX}" y1="${sy(v)}" x2="${WX + WW}" y2="${sy(v)}" class="grid"/><text x="${WX - 14}" y="${sy(v) + 6}" class="ax" style="text-anchor:end">${v}%</text>`; });
  wv += `<line x1="${WX}" y1="${sy(75)}" x2="${WX + WW}" y2="${sy(75)}" stroke="var(--pass-s)" stroke-width="3" stroke-dasharray="10 6"/><text x="${WX + WW + 10}" y="${sy(75) + 6}" class="bv" style="fill:var(--pass-ink)">gate 75%</text>`;
  let prev = null;
  waves.forEach((w, i) => { const x = WX + 40 + i * 245, top = sy(w[2]);
    if (prev !== null) { wv += `<rect x="${x}" y="${top}" width="${bw}" height="${sy(prev) - top}" class="bk-pass"/><rect x="${x}" y="${sy(prev)}" width="${bw}" height="${y0 - sy(prev)}" class="bk-skip" opacity=".5"/>`; }
    else wv += `<rect x="${x}" y="${top}" width="${bw}" height="${y0 - top}" class="bk-fail" opacity=".85"/>`;
    wv += `<text x="${x + bw / 2}" y="${top - 12}" class="wvv">${w[2]}%</text><text x="${x + bw / 2}" y="${y0 + 30}" class="wvl">${w[0]} · ${w[4]}</text><text x="${x + bw / 2}" y="${y0 + 56}" class="wvs">${w[1]}</text>`;
    prev = w[2]; });
  wv += `</svg>`;
  add('F', `${kicker('Coverage · wave sequence (proposed)')}${title('Six waves from 38% to 80%, each one raising the floor')}${wv}
    <p class="note">Line coverage, simulated from today's per-file data: each wave raises its files to the stated level. The floor only moves up after exact-main CI confirms the new value (trigger T16). W1 changes the denominator, so it needs a written disposition per file.</p>`);

  const tgt = [
    ['W1', 'abacus_v21_* (17), deploy_* and run_* (6), demo, ci_monitor_local, clone_based_validator, _LEGACY_phase0_setup and others', '34 files · 5,017 statements', 'Each file gets keep+test, archive or omit, in writing. DOW_DEPLOYMENT_ORCHESTRATOR.py is a keep-and-test candidate'],
    ['W2', 'phase9 · phase4 · phase1 · phase8 · phase7 · phase6 · phase2 · phase3 · phase5 · phase0_init', '1,749 missing lines', 'Extend tests/coverage/ phase tests; they already exist for 1, 4, 8'],
    ['W3', 'agents/self_improvement_agent · convergence/maturity_tracker · core/canonical_index · core/link_tracker · generators/master_reconciliation · integrations/git_manager …', '53 modules · 4,382 missing', 'DMAIC_V3 root 1,842 · generators 646 · core 591 · convergence 504 · agents 385'],
    ['W4', 'Partly covered DMAIC_V3 modules (debug_pipeline, execution_tracker …)', '34 modules', 'Depth work: branches and error paths'],
    ['W5', 'tools, scripts, models, src/dmaic, src/qplant_presentation_engine, renderers, integration', '136 files', 'Mostly depth; renderers and integration have no tests yet'],
  ];
  add('F', `${kicker('Coverage · wave targets')}${title('Which files each wave works on')}
    <table class="t dense"><thead><tr><th>Wave</th><th>Files</th><th>Size</th><th>Note</th></tr></thead><tbody>${tgt.map(r => `<tr><td class="mono b">${r[0]}</td><td>${r[1]}</td><td class="nw">${r[2]}</td><td>${r[3]}</td></tr>`).join('')}</tbody></table>`);

  const mxA = ['DMAIC_V3', 'repo root', 'tools', 'scripts', 'models', 'src/*', 'renderers, integration'];
  const mxW = { W0: [1, 1, 1, 1, 1, 1, 1], W1: [1, 2, 0, 0, 0, 0, 0], W2: [2, 0, 0, 0, 0, 0, 0], W3: [2, 0, 0, 0, 0, 0, 0], W4: [2, 0, 0, 0, 0, 0, 0], W5: [0, 0, 2, 2, 2, 2, 2] };
  const mc = v => v === 2 ? '<td class="mx r" style="background:var(--pass);color:var(--pass-ink)">work</td>' : v === 1 ? '<td class="mx c">guard</td>' : '<td class="mx"></td>';
  add('F', `${kicker('Coverage in the protocol')}${title('Where coverage sits in the lanes, nodes and triggers')}
    <div class="cols2" style="grid-template-columns:1.05fr 1fr">
      <div><table class="t mxt"><thead><tr><th>Area \\ wave</th>${Object.keys(mxW).map(w => `<th class="c">${w}</th>`).join('')}</tr></thead><tbody>
        ${mxA.map((a, i) => `<tr><td class="b">${a}</td>${Object.values(mxW).map(r => mc(r[i])).join('')}</tr>`).join('')}</tbody></table>
        <p class="note" style="margin-top:12px">guard = ratchet and diff coverage protect the area; work = the wave adds tests or a disposition.</p></div>
      <div class="card"><div class="cap">Attachment points</div><dl class="kv2">
        <dt>Lane</dt><dd>New <b>Coverage</b> lane in tier Verify, owned by ABACUS <span class="mono">ci-cd-tests</span> and MIP B0</dd>
        <dt>N04</dt><dd>Worker lane measures line + branch per test</dd>
        <dt>N05</dt><dd>Pre-match uses per-test contexts to run only impacted tests</dd>
        <dt>N06</dt><dd>Fixed-threshold red = inherited debt; diff coverage below 80% = source defect</dd>
        <dt>N14</dt><dd>Exact-main CI records total, breadth, depth, per area</dd>
        <dt>N12 · census</dt><dd>One coverage row per iteration; trend read back each pulse</dd>
        <dt>T16 (new)</dt><dd>Main measured ≥ floor + 1 → raise the floor. Guard: exact-main CI green</dd></dl></div>
    </div>`);

  // ===== G. EVIDENCE & STRUCTURE =====
  const heads = [
    ['ABACUS #1858 · 10fdaaa5', 44, 1, 1, 3, 2],
    ['ABACUS #1858 · 203d63af', 87, 4, 1, 4, 3],
    ['ABACUS #1859 · 6fac58cc', 61, 4, 1, 4, 5],
    ['ABACUS #1857 · e7b45912', 60, 4, 1, 0, 3],
    ['ABACUS #1856 · f11d8044', 91, 3, 1, 0, 4],
    ['CODEX #984 · 90e3396a', 55, 4, 0, 1, 5],
    ['CODEX main · 768c9e35', 38, 2, 0, 3, 4],
    ['CODEX main · 6edf28b7', 9, 0, 0, 0, 8],
  ];
  const maxT = Math.max(...heads.map(h => h.slice(1).reduce((a, b) => a + b, 0)));
  const W = 980, rowH = 66, X0 = 360;
  let bars = `<svg viewBox="0 0 ${X0 + W + 140} ${heads.length * rowH + 60}" class="barsvg">`;
  [0, 25, 50, 75, 100].forEach(v => { const x = X0 + v / maxT * W; bars += `<line x1="${x}" y1="10" x2="${x}" y2="${heads.length * rowH + 10}" class="grid"/><text x="${x}" y="${heads.length * rowH + 38}" class="ax">${v}</text>`; });
  heads.forEach((h, i) => {
    const y = 18 + i * rowH; let x = X0;
    bars += `<text x="${X0 - 18}" y="${y + 26}" class="bl">${h[0]}</text>`;
    [['pass', h[1]], ['fail', h[2]], ['neu', h[3]], ['canc', h[4]], ['skip', h[5]]].forEach(([k, v]) => { if (!v) return; const w = v / maxT * W; bars += `<rect x="${x.toFixed(1)}" y="${y}" width="${w.toFixed(1)}" height="38" class="bk-${k}"/>`; x += w; });
    bars += `<text x="${x + 12}" y="${y + 26}" class="bv">${h[1]} ✓ · ${h[2]} ✗</text>`;
  });
  bars += `</svg>`;
  add('G', `${kicker('Census')}${title('Check outcomes per head, to scale')}
    <div class="barkey"><span><i class="bk-pass"></i>pass</span><span><i class="bk-fail"></i>fail</span><span><i class="bk-neu"></i>neutral</span><span><i class="bk-canc"></i>cancelled</span><span><i class="bk-skip"></i>skipped</span></div>
    ${bars}`);

  const rt = M.TEL_RECORDED.runtime;
  add('G', `${kicker('Runtime · version control · debug')}${title('What ran, where, on which commit')}
    <div class="cols2">
      <div class="card"><div class="cap">Version control</div><dl class="kv2">
        <dt>ABACUS #1858</dt><dd class="mono">fix/gate-owner-attestation-fallback @ 203d63af</dd>
        <dt>ABACUS main</dt><dd class="mono">53688f26 · #1838 · 2026-10-06</dd>
        <dt>CODEX main</dt><dd class="mono">6edf28b7 · 2026-10-12 14:40 CEST</dd>
        <dt>CODEX #984</dt><dd class="mono">merge 768c9e35 · 12 commits</dd>
        <dt>Ruleset</dt><dd class="mono">ABACUS 24494381 · active · 0 bypass</dd></dl></div>
      <div class="card"><div class="cap">Runtime and debug</div><dl class="kv2">
        <dt>Python</dt><dd>${esc(rt.python)}</dd>
        <dt>Runners</dt><dd>${esc(rt.implementation)} · ${esc(rt.platform)}</dd>
        <dt>Debug lanes</dt><dd>CODEX main: Docker real runtime LLDB, live lldb-dap + MCP, live debugpy + js-debug — all green</dd>
        <dt>Local check</dt><dd>Python 3.13: 61 governance tests pass; inventory check passes after regeneration</dd>
        <dt>Not yet</dt><dd>.self harness census, Docker smoke, live port probing</dd></dl></div>
    </div>`);

  add('G', `<div class="split">
      <div class="split-l">${kicker('Recursive SIPOC')}${title('The customer of N supplies N+1')}
        <div class="formula big">I<sub>N+1</sub> = O<sub>N</sub> ⊕ ΔE<sub>N</sub> ⊕ C<sub>N+1</sub></div>
        <dl class="kv2"><dt>O<sub>N</sub></dt><dd>last output: receipts, check states, ranked findings</dd><dt>ΔE<sub>N</sub></dt><dd>new evidence: completed checks, runner behaviour</dd><dt>C<sub>N+1</sub></dt><dd>new constraints: gates, policies, review rules</dd><dt>⊕</dt><dd>governed reconciliation, never plain concatenation</dd></dl>
      </div>
      <div class="split-r wide">${svgs.sipoc.replace(/ style="min-width:760px"/, '')}</div></div>`);

  const tiers = [
    ['Discover', [['Global lookup', 'GLOB.yaml · mesh census', 'CODEX'], ['Dock interface', '.mesh/MESH_DOCK.yaml', 'mesh']]],
    ['Verify', [['Runtime and self-test', 'scripts/testpilot_preflight.py', 'ABACUS'], ['Lint and configuration', 'pre-commit · Ruff · YAML/JSON/TOML', 'both'], ['Security', 'Bandit · Semgrep · SARIF', 'both']]],
    ['Analyse and remember', [['Derived analysis', 'DOW', 'ABACUS'], ['Semantic and provenance', 'KEB · REX', 'CODEX']]],
    ['Authorise and deliver', [['QPS domain', 'cryoplant-project sources', 'cryoplant-project'], ['Delivery', 'Actions · PR Feedback Gate · Pages', 'GitHub']]],
  ];
  add('G', `${kicker('Lanes')}${title('Nine lanes, four tiers, existing owners')}
    <div class="tree"><div class="root">Code Purple</div><div class="trow">${tiers.map(t => `<div class="tcol"><div class="th">${t[0]}</div>${t[1].map(l => `<div class="leaf2"><b>${l[0]}</b><span class="mono">${l[1]}</span><em>${l[2]}</em></div>`).join('')}</div>`).join('')}</div></div>
    <p class="note">Runtime dock ladder: ABACUS devcontainer ports 8000 · 8080 · 5000 and the CODEX compose validator are <b>configured</b>; listening, published and probed are unproven.</p>`);

  const burn = [
    ['1', 'Land ABACUS #1858', 'in progress', 'prog', 'GBO + Claude', '13 Oct'],
    ['2', 'Hardening #1878, #1879', 'fixed in PR', 'ok', 'verify after merge', 'post-merge'],
    ['3', 'CODEX post-merge reds', 'classified', 'ok', 'validate fixed · OSV inherited', 'done'],
    ['4', 'CODEX admission ruleset', 'decision', 'todo', 'GBO', '14 Oct'],
    ['5', 'Classify recurring reds', 'confirmed', 'ok', '4 inherited from main', 'done'],
    ['6', 'Runnable .self harness', 'todo', 'todo', 'Claude', '16 Oct'],
    ['7', 'Scheduled readback pulse (T12)', 'todo', 'todo', 'Claude', '16 Oct'],
    ['8', 'Docker smoke, port probing', 'not built', 'todo', 'Claude', '23 Oct'],
    ['9', 'Cross-repo adoption (T15)', 'gated on 1', 'todo', '—', 'after #1858'],
  ];
  add('G', `${kicker('Burndown')}${title('What is left, who owns it, by when')}
    <table class="t"><thead><tr><th>#</th><th>Item</th><th>Status</th><th>Owner</th><th>Target</th></tr></thead><tbody>
    ${burn.map(r => `<tr><td class="mono">${r[0]}</td><td class="b">${r[1]}</td><td>${pill(r[3], r[2])}</td><td>${r[4]}</td><td class="mono">${r[5]}</td></tr>`).join('')}</tbody></table>`);

  add('G', `${kicker('Appendix')}${title('Edge reference E01–E19')}
    <table class="t dense2"><thead><tr><th>ID</th><th>From → to</th><th>Type</th><th>Meaning</th></tr></thead><tbody>
    ${M.EDGES.map(e => `<tr><td class="mono b">${e.id}</td><td class="nw"><span class="mono">${e.f}→${e.t}</span> ${esc(byId[e.f].label)} → ${esc(byId[e.t].label)}</td><td class="nw"><svg viewBox="0 0 40 10" class="lsv sm"><line x1="0" y1="5" x2="40" y2="5" class="e-${e.k}"/></svg> ${M.EKIND[e.k]}</td><td>${esc(e.m)}</td></tr>`).join('')}</tbody></table>`);

  add('G', `${kicker('Sources')}${title('Where the figures come from')}
    <ul class="src">
      <li><a href="https://github.com/GBOGEB/ABACUS/pull/1858">ABACUS #1858</a> · checks, gate output, review threads (GitHub API, 17:27)</li>
      <li><a href="https://github.com/GBOGEB/ABACUS/issues/1878">ABACUS #1878</a> and <a href="https://github.com/GBOGEB/ABACUS/issues/1879">#1879</a> · follow-up hardening issues</li>
      <li><a href="https://github.com/GBOGEB/ABACUS/pull/1859">#1859</a>, <a href="https://github.com/GBOGEB/ABACUS/pull/1857">#1857</a>, <a href="https://github.com/GBOGEB/ABACUS/pull/1856">#1856</a> · check-run tallies</li>
      <li><a href="https://github.com/GBOGEB/CODEX/pull/984">CODEX #984</a> · merge record and check runs; CODEX main 768c9e35 and 6edf28b7</li>
      <li>ABACUS ruleset 24494381 (Main Hard Gate) · <span class="mono">.github/workflows/pr-feedback-gate.yml</span>, <span class="mono">ci/governance/pr_feedback_gate.py</span></li>
      <li>Code Purple execution seed · <span class="mono">federation/mesh/CODE_PURPLE_EXECUTION_SEED_20261012.yaml</span></li>
    </ul>`);


  // ===== H. LIFT & METHOD =====
  const lift = LIFT;
  add('H', `${kicker('Lift · ' + lift.generated_at.replace('T', ' ').slice(0, 16) + ' UTC readback')}${title(`Not lifted: ${lift.lift.filter(x => x.ok).length} of ${lift.lift.length} criteria met`)}
    <div class="krow">${kpi('20 → ' + lift.repos['GBOGEB/ABACUS'].open_prs, 'Open ABACUS PRs', 'baseline at declaration → now', '')}${kpi(String(lift.admission_audit.merged), 'Merges since #1858', `gate green on ${lift.admission_audit.gate_green}; ${lift.admission_audit.with_red_checks} with red checks`, 'hold')}${kpi('42.6%', 'Coverage (line + branch)', 'recorded 15 Oct on main 803700a3; from 36.9%', '')}${kpi((lift.lift.find(x => x.id === 'L2') || {}).ok ? 'restored' : 'incomplete', 'Ruleset 24494381', esc(((lift.lift.find(x => x.id === 'L2') || {}).evidence || '').replace(/^active, /, '')), (lift.lift.find(x => x.id === 'L2') || {}).ok ? '' : 'hold')}</div>
    <table class="t" style="margin-top:30px"><thead><tr><th>ID</th><th>Lift criterion</th><th class="c">Met</th><th>Evidence</th></tr></thead><tbody>
    ${lift.lift.map(x => `<tr><td class="idc">${x.id}</td><td class="b">${esc(x.text)}</td><td class="c">${x.ok ? '<span class="mk ok">✓</span>' : '<span class="mk no">✗</span>'}</td><td>${esc(x.evidence)}</td></tr>`).join('')}</tbody></table>
    <p class="note">The 13 Oct check passed L2 falsely: it read enforcement and bypass actors but not rule content. Fixed (EVR-ABACUS-0001). Follow-ups #1878 and #1879 verified on main. Red nightly on main: ${lift.repos['GBOGEB/ABACUS'].nightly.reds.join(', ')}.</p>`);

  add('H', `${kicker('After-action')}${title('What worked, what to change next time')}
    <div class="cols2">
      <div class="card"><div class="cap">Worked</div><ul class="ul">
        <li><b>Readback before action.</b> It showed #1858 could not admit itself (the gate runs main's code) and that #984 had merged red.</li>
        <li><b>Classify against main.</b> Four reds were red in main's nightly run, so accepting them under break-glass rested on evidence.</li>
        <li><b>Smallest fix.</b> A 3-line regenerated doc cleared the only red the PR caused.</li>
        <li><b>Owner / agent split.</b> Owner: bypass, merge, restore. Agent: threads, issues, fix, readback.</li>
        <li><b>Measurable lift.</b> Criteria read from GitHub; one of them was too weak (below).</li></ul></div>
      <div class="card"><div class="cap">Change</div><ul class="ul">
        <li><b>Break-glass deleted the rules instead of adding a bypass, and the lift check did not read rule content.</b> 61 PRs merged ungated. Use a bypass actor; L2 now compares rules; L5 audits every merge.</li>
        <li><b>Snapshots went stale twice in an hour.</b> Run the readback every pulse and on a schedule.</li>
        <li><b>A decision was written against an old head.</b> Threads were resolved as "residual risk" minutes after fixes were pushed. Re-read the head before writing any decision.</li>
        <li><b>The seed repo has no gate.</b> CODEX #984 merged with 4 reds. Decide on a CODEX ruleset.</li>
        <li><b>One reviewer was a single point of failure.</b> The owner-attested fallback is now on main; test it on the next outage.</li>
        <li><b>Inherited reds stay red.</b> Coverage W0 floor and diff coverage due 16 Oct.</li></ul></div>
    </div>`);

  const method = [
    ['0', 'Declare', 'Merge flow stalled, the same checks red across PRs, or a required reviewer unavailable', 'Write incident.yaml: repos, gate, tracked PRs, owner, lift criteria', 'Owner'],
    ['1', 'Read back', 'incident.yaml exists', 'Run readback.py; no action before the first census', 'Agent'],
    ['2', 'Classify every red', 'Census on exact heads', 'Inherited (also red on main nightly) · source defect · review capacity · runner or infra', 'Agent'],
    ['3', 'Find the unblocker', 'Classes known', 'Smallest change that lets the gate admit again; prove it cannot admit itself', 'Agent + owner'],
    ['4', 'Repair source defects only', 'Unblocker chosen', 'Fix on the unblocker branch, impacted retest, exact-head readback', 'Agent'],
    ['5', 'Admit or break glass', 'Only inherited or capacity reds left', 'Owner writes residual risk, adds a one-time bypass actor (never deletes rules), merges, removes the bypass, re-reads rule content', 'Owner'],
    ['6', 'Lift check', 'Unblocker merged', 'readback.py evaluates L-criteria; census row saved', 'Agent'],
    ['7', 'Close out', 'Lifted', 'Verify follow-ups on main and close; REX lesson; inherited reds become dated burn-down items', 'Agent + owner'],
  ];
  add('H', `${kicker('Reusable method')}${title('Code Purple in eight steps')}
    <table class="t dense"><thead><tr><th>Step</th><th>Name</th><th>Entry</th><th>Action</th><th>Who</th></tr></thead><tbody>
    ${method.map(m => `<tr><td><span class="stepb">${m[0]}</span></td><td class="b nw">${m[1]}</td><td>${m[2]}</td><td>${m[3]}</td><td class="nw">${m[4]}</td></tr>`).join('')}</tbody></table>
    <p class="note">Rule that never bends: the owner alone breaks glass, once, in writing, and restores the gate immediately. Nothing that changes a gate approves itself.</p>`);

  const knobs = [
    ['repos[].ruleset_id, gate_check', 'Which gate is blocked and which single check it requires'],
    ['repos[].nightly_workflow', 'The scheduled run on the default branch that defines the inherited set'],
    ['tracked_prs[].role', 'unblocker · debt-ratchet · queued · seed: decides lift and report order'],
    ['lift_criteria[]', 'pr_merged · ruleset_clean · merges_since · open_prs_at_most, with thresholds'],
    ['follow_up_issues[].check', 'What to verify on main before closing each follow-up'],
    ['baseline', 'Numbers at declaration, for the before/after census'],
  ];
  const adapt = [
    ['Gate', 'Required CI check', 'Approval signature on a controlled document', 'Validation step before a dataset is published'],
    ['Inherited red', 'Red on main nightly', 'Finding already open in the register', 'Check already failing on the last good release'],
    ['Unblocker', 'PR that restores admission', 'Revision that restores reviewability', 'Fix that lets validation run again'],
    ['Break-glass', 'One-time ruleset bypass', 'Documented concession, owner-signed', 'Manual release with sign-off'],
    ['Lift', 'Merges flow, backlog down', 'Reviews close, queue down', 'Releases resume'],
  ];
  add('H', `${kicker('Adapting it')}${title('One file to adapt; the same steps elsewhere')}
    <div class="cols2" style="grid-template-columns:1fr 1.25fr">
      <div class="card"><div class="cap">incident.yaml knobs</div><dl class="kv2" style="grid-template-columns:270px 1fr;font-size:18px">${knobs.map(k => `<dt style="text-transform:none;letter-spacing:0">${k[0]}</dt><dd>${k[1]}</dd>`).join('')}</dl></div>
      <div><table class="t dense"><thead><tr><th>Concept</th><th>Code (this case)</th><th>Engineering documents</th><th>Data pipeline</th></tr></thead><tbody>
        ${adapt.map(a => `<tr><td class="b">${a[0]}</td><td>${a[1]}</td><td>${a[2]}</td><td>${a[3]}</td></tr>`).join('')}</tbody></table>
        <p class="note" style="margin-top:12px">Only the code column has a working readback today; the other two are mappings for reuse.</p></div>
    </div>`);

  add('H', `${kicker('Toolkit')}${title('What runs the method')}
    <table class="t"><thead><tr><th>File</th><th>Does</th></tr></thead><tbody>
      <tr><td class="mono b">kit/incident.yaml</td><td>The instance: repos, gate, tracked PRs, owner, baseline, lift criteria. The only file to edit.</td></tr>
      <tr><td class="mono b">kit/readback.py</td><td>Reads GitHub through <span class="mono">gh</span>; classifies reds against the main nightly run; checks lift criteria; writes <span class="mono">census.json</span> and <span class="mono">after_action.md</span>.</td></tr>
      <tr><td class="mono b">index.html</td><td>The interactive page: pulse graph, lifecycle triggers, census, admission board.</td></tr>
      <tr><td class="mono b">build_deck.js · merge_deck.py</td><td>This 16:9 deck and its bookmarks, from the same model.</td></tr>
      <tr><td class="mono b">code-purple.md</td><td>Markdown parent with the same anchors as the PDF links.</td></tr>
    </tbody></table>
    <div class="callbar">Run: <span class="mono">python kit/readback.py kit/incident.yaml</span> → <span class="mono">kit/out/census.json</span>, <span class="mono">kit/out/after_action.md</span>. Lifted when every L-criterion is met.</div>`);
  // ---------- assemble ----------
  const firstOf = {};
  slides.forEach((s, i) => { if (!(s.sec in firstOf)) firstOf[s.sec] = i; });
  const N = slides.length + 1; // +1 portrait detail page inserted after slide 9
  const num = i => i + 1 + (i >= 9 ? 1 : 0);
  const nav = cur => `<nav class="snav"><span class="brand">GLOBAL CODE PURPLE</span>${SECTIONS.map(s => `<a href="#sec-${s.id}" class="${s.id === cur ? 'on' : ''}"><i>${s.id}</i>${s.name}</a>`).join('')}</nav>`;
  const body = slides.map((s, i) => {
    const id = firstOf[s.sec] === i ? ` id="sec-${s.sec}"` : '';
    const secName = SECTIONS.find(x => x.id === s.sec).name;
    return `<section class="slide${s.cover ? ' is-cover' : ''}${s.pulse ? ' is-pulse' : ''}"${id}>
      ${s.cover ? '' : nav(s.sec)}
      <div class="sbody">${s.html}</div>
      <footer class="sfoot"><span>${STAMP}</span><span>${s.sec} · ${secName}</span><span class="pg">${String(num(i)).padStart(2, '0')} / ${N}</span></footer>
    </section>`;
  }).join('\n');
  const tocFill = SECTIONS.map(s => `document.querySelectorAll('.toc-p[data-sec="${s.id}"]').forEach(e=>e.textContent='slide ${num(firstOf[s.id])}');`).join('');

  const deckCSS = `
  :root{--f-body:"Aptos","Aptos Display","IBM Plex Sans",system-ui,sans-serif}
  @page{size:1920px 1080px;margin:0}
  html,body{margin:0;padding:0;background:#fff}
  body{font-family:var(--f-body);color:var(--ink);font-size:24px;line-height:1.45}
  .slide{width:1920px;height:1080px;box-sizing:border-box;position:relative;overflow:hidden;break-after:page;background:var(--bg);display:flex;flex-direction:column}
  .snav{height:64px;flex:none;display:flex;align-items:center;gap:6px;padding:0 64px;border-bottom:1px solid var(--line);background:var(--surface)}
  .snav .brand{font-family:var(--f-mono);font-size:15px;letter-spacing:.14em;color:var(--accent);margin-right:auto;font-weight:500}
  .snav a{font-size:16px;color:var(--muted);text-decoration:none;padding:7px 14px;border-radius:999px;display:flex;gap:8px;align-items:center}
  .snav a i{font-style:normal;font-family:var(--f-mono);font-size:13px;width:22px;height:22px;border-radius:50%;display:inline-grid;place-items:center;border:1px solid var(--line-2)}
  .snav a.on{background:var(--accent);color:#fff}
  .snav a.on i{border-color:rgba(255,255,255,.6)}
  .sbody{flex:1;padding:44px 80px 20px;display:flex;flex-direction:column;min-height:0}
  .sfoot{max-width:none;margin:0;height:48px;flex:none;display:grid;grid-template-columns:1fr auto auto;gap:40px;align-items:center;padding:0 64px;font-family:var(--f-mono);font-size:14px;color:var(--muted);border-top:1px solid var(--line)}
  .sfoot .pg{color:var(--ink);font-weight:500}
  .kick{font-family:var(--f-mono);font-size:17px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
  h1{font-family:var(--f-display);font-weight:800;font-size:52px;line-height:1.08;letter-spacing:-.01em;margin:0 0 26px;text-wrap:balance;max-width:1600px}
  h1.big{font-size:120px;margin-bottom:28px}
  .lede{font-size:28px;color:var(--muted);max-width:1500px;margin:0 0 24px}
  .body{font-size:23px;color:var(--ink);margin:0 0 20px}
  .note{font-size:19px;color:var(--muted);margin-top:auto;padding-top:16px}
  .mono{font-family:var(--f-mono)}
  .cap{font-family:var(--f-mono);font-size:15px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
  .card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:26px 30px}
  .card p{margin:0;font-size:22px}
  .cols3{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
  .cols2{display:grid;grid-template-columns:1fr 1fr;gap:28px}
  .callbar{margin-top:30px;background:var(--hold);border:1px solid var(--hold-s);color:var(--hold-ink);border-radius:12px;padding:20px 28px;font-size:23px}
  .callbar.small{font-size:20px;padding:16px 20px}
  /* cover */
  .is-cover{background:var(--auth);color:#fff}
  .is-cover .sbody{justify-content:center;padding:80px 120px}
  .is-cover .kick{color:#e3cff7}
  .is-cover .lede{color:#e9def5}
  .is-cover .sfoot{color:#d9c6ef;border-top-color:rgba(255,255,255,.2)} .is-cover .sfoot .pg{color:#fff}
  .cover-meta{display:grid;gap:12px;margin-top:40px;font-size:22px}
  .cover-meta div{display:grid;grid-template-columns:140px 1fr;gap:20px}
  .cover-meta b{font-family:var(--f-mono);font-weight:500;font-size:16px;letter-spacing:.08em;text-transform:uppercase;color:#d9c6ef;padding-top:4px}
  /* toc */
  .toc{display:grid;grid-template-columns:1fr 1fr;gap:18px 40px;margin-top:10px}
  .toc-i{display:grid;grid-template-columns:72px 1fr auto;align-items:center;gap:20px;padding:22px 26px;border:1px solid var(--line);border-radius:14px;background:var(--surface);text-decoration:none;color:var(--ink)}
  .toc-l{font-family:var(--f-display);font-weight:800;font-size:44px;color:var(--accent)}
  .toc-n{font-size:30px;font-weight:600}
  .toc-p{font-family:var(--f-mono);font-size:18px;color:var(--muted)}
  /* tables */
  table.t{width:100%;border-collapse:collapse;font-size:20px;font-variant-numeric:tabular-nums}
  table.t th{font-family:var(--f-mono);font-size:14px;font-weight:500;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);text-align:left;padding:10px 14px;border-bottom:2px solid var(--line-2)}
  table.t td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}
  table.t .r{text-align:right} table.t .c{text-align:center} table.t .b{font-weight:600} table.t .nw{white-space:nowrap}
  table.t .small{font-size:15px}
  table.t .sub{font-size:15.5px;color:var(--muted);margin-top:3px;line-height:1.35}
  table.dense td{padding:8px 12px;font-size:18px} table.dense th{padding:8px 12px}
  table.dense2 td{padding:5px 12px;font-size:16px} table.dense2 th{padding:6px 12px}
  .st-pill{font-size:15px;padding:2px 12px}
  .wired{font-size:15px;padding:2px 12px}
  .sw{display:inline-block;width:30px;height:20px;vertical-align:-3px;border-radius:5px}
  .sw.dec{width:18px;height:18px;margin:0 6px;transform:rotate(45deg)}
  /* taxonomy */
  .tax{display:grid;grid-template-columns:repeat(3,1fr);gap:30px}
  .tax-col{display:flex;flex-direction:column;align-items:stretch}
  .tax-h{font-family:var(--f-mono);font-size:16px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:12px}
  .tx{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 20px;display:grid;grid-template-columns:auto 1fr;gap:4px 14px;align-items:baseline}
  .tx b{font-size:24px} .tx span:last-child{grid-column:1/-1;font-size:18px;color:var(--muted);line-height:1.4}
  .idchip{font-family:var(--f-mono);font-size:15px;background:var(--accent-soft);color:var(--accent);border-radius:6px;padding:2px 9px}
  .rel{font-family:var(--f-mono);font-size:15px;color:var(--muted);text-align:center;padding:8px 0}
  /* legend */
  .legend3 .lgr{display:grid;grid-template-columns:72px 1fr;gap:14px;align-items:center;margin-bottom:12px;font-size:19px}
  .legend3 .lgr b{display:block;font-size:20px} .legend3 .lgr span{color:var(--muted)}
  .lsv{width:64px;height:16px;overflow:visible} .lsv.sm{width:40px;height:10px;vertical-align:middle}
  /* glossary */
  .gloss{display:grid;grid-template-columns:1fr 1fr;gap:12px 48px;margin:0}
  .gloss div{display:grid;grid-template-columns:230px 1fr;gap:16px;padding:9px 0;border-bottom:1px solid var(--line)}
  .gloss dt{font-family:var(--f-mono);font-size:18px;font-weight:500;color:var(--accent);padding-top:2px}
  .gloss dd{margin:0;font-size:19px}
  /* rule */
  .rule7{list-style:none;margin:20px 0 0;padding:0;display:grid;grid-template-columns:repeat(7,1fr);gap:14px}
  .rule7 li{background:var(--surface);border:1px solid var(--line);border-top:6px solid var(--accent);border-radius:12px;padding:22px 20px;display:flex;flex-direction:column;gap:12px;min-height:260px}
  .rule7 .n{font-family:var(--f-display);font-weight:800;font-size:44px;color:var(--accent)}
  .rule7 b{font-size:25px;line-height:1.2} .rule7 .ph{font-family:var(--f-mono);font-size:16px;color:var(--muted);margin-top:auto}
  /* split */
  .split{display:grid;grid-template-columns:560px 1fr;gap:40px;height:100%;min-height:0}
  .split-l{display:flex;flex-direction:column}
  .split-r{display:flex;align-items:center;justify-content:center;min-height:0}
  .is-pulse .sbody{padding-top:20px;padding-bottom:10px}
  .is-pulse .split-r svg{height:935px;width:auto}
  .is-pulse .split{grid-template-columns:500px 1fr}
  .split-r.wide svg{width:100%;height:auto}
  .mini-legend{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px;font-size:18px;margin:10px 0 20px}
  .mini-legend span{display:flex;gap:10px;align-items:center}
  /* stages */
  .stgs{display:grid;gap:16px}
  .stg{display:grid;grid-template-columns:96px 1fr;gap:20px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 22px}
  .stg-n{font-family:var(--f-display);font-weight:800;font-size:48px;color:var(--accent);line-height:1}
  .stg-h{display:flex;gap:18px;align-items:baseline;margin-bottom:8px}
  .stg-h b{font-size:25px} .stg-h .ph{font-family:var(--f-mono);font-size:15px;color:var(--muted)} .stg-h .ids{font-family:var(--f-mono);font-size:15px;color:var(--accent);margin-left:auto}
  .eae3{display:grid;grid-template-columns:1fr 1.4fr 1fr;gap:24px;font-size:17.5px;line-height:1.4}
  .eae3 i{display:block;font-style:normal;font-family:var(--f-mono);font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:3px}
  /* lifecycle */
  .lifewrap{flex:1;display:flex;align-items:center;justify-content:center;min-height:0}
  .lifewrap svg{width:100%;height:auto;max-height:720px}
  .wchart{display:grid;gap:22px;margin-top:14px}
  .wrow{display:grid;grid-template-columns:220px 1fr 60px 520px;gap:20px;align-items:center;font-size:22px}
  .wtrack{height:40px;background:var(--surface-2);border-radius:6px;overflow:hidden}
  .wfill{height:100%} .w-wired{background:var(--pass-s)} .w-partial{background:var(--evid-s)} .w-manual{background:var(--hold-s)} .w-proposed{background:var(--line-2)}
  .wv{font-family:var(--f-display);font-weight:800;font-size:34px}
  .wids{font-size:16px;color:var(--muted)}
  /* invariants, matrix */
  .inv td{font-size:22px;padding:16px 14px}
  .mk{display:inline-grid;place-items:center;width:40px;height:40px;border-radius:50%;font-weight:700;font-size:22px}
  .mk.ok{background:var(--pass);color:var(--pass-ink);border:2px solid var(--pass-s)}
  .mk.no{background:var(--rep);color:var(--rep-ink);border:2px solid var(--rep-s)}
  .mk.wt{background:var(--hold);color:var(--hold-ink);border:2px solid var(--hold-s)}
  .mxt td.mx{text-align:center;font-family:var(--f-mono);font-size:16px;width:150px}
  .mxt td.mx.r{background:var(--rep);color:var(--rep-ink);border:3px solid var(--bg)}
  .mxt td.mx.g{background:var(--pass);color:var(--pass-ink);border:3px solid var(--bg)}
  .mxt td.mx.c{background:var(--surface-2);color:var(--muted);border:3px solid var(--bg)}
  /* sequence */
  .seq{list-style:none;margin:0;padding:0;display:grid;gap:12px}
  .seq li{display:grid;grid-template-columns:56px 120px 1fr 420px;gap:18px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 22px;font-size:23px}
  .seq .n{font-family:var(--f-display);font-weight:800;font-size:32px;color:var(--accent)}
  .seq .who{font-family:var(--f-mono);font-size:16px;text-align:center;border-radius:999px;padding:4px 0}
  .seq .who.g{background:var(--auth);color:#fff} .seq .who.c{background:var(--accent-soft);color:var(--accent)}
  .seq .out{font-size:18px;color:var(--muted);text-align:right}
  /* bars */
  .barsvg{width:100%;height:auto;max-height:740px}
  .barsvg .grid{stroke:var(--line);stroke-width:1}
  .barsvg .ax{font-family:var(--f-mono);font-size:16px;fill:var(--muted);text-anchor:middle}
  .barsvg .bl{font-size:20px;fill:var(--ink);text-anchor:end;font-family:var(--f-mono)}
  .barsvg .bv{font-size:18px;fill:var(--muted);font-family:var(--f-mono)}
  .bk-pass{fill:var(--pass-s);background:var(--pass-s)} .bk-fail{fill:var(--rep-s);background:var(--rep-s)} .bk-neu{fill:var(--e-flow);background:var(--e-flow)} .bk-canc{fill:var(--hold-s);background:var(--hold-s)} .bk-skip{fill:var(--line-2);background:var(--line-2)}
  .barkey{display:flex;gap:28px;font-size:19px;margin-bottom:10px}
  .barkey i{display:inline-block;width:20px;height:20px;border-radius:4px;vertical-align:-3px;margin-right:8px}
  /* kv */
  .kv2{display:grid;grid-template-columns:190px 1fr;gap:12px 20px;margin:0;font-size:20px}
  .kv2 dt{font-family:var(--f-mono);font-size:15px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding-top:3px}
  .kv2 dd{margin:0}
  .formula.big{font-size:40px;padding:22px 26px;margin:6px 0 26px;white-space:normal}
  /* tree */
  .tree{display:flex;flex-direction:column;align-items:center}
  .tree .root{background:var(--auth);color:#fff;font-family:var(--f-display);font-weight:800;font-size:28px;padding:12px 32px;border-radius:10px}
  .trow{display:grid;grid-template-columns:repeat(4,1fr);gap:22px;width:100%;margin-top:30px;position:relative;padding-top:26px;border-top:2px solid var(--line-2)}
  .tcol{display:flex;flex-direction:column;gap:12px}
  .th{background:var(--surface-2);border:1px solid var(--line-2);border-radius:10px;padding:10px;text-align:center;font-weight:600;font-size:22px}
  .leaf2{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 16px;display:grid;gap:4px;font-size:19px}
  .leaf2 .mono{font-size:15px;color:var(--muted)} .leaf2 em{font-style:normal;font-family:var(--f-mono);font-size:14px;color:var(--accent)}
  table.t td,table.t td.mono,table.t td.r{font-family:var(--f-body)}
  .idc{font-family:var(--f-mono)!important;font-weight:500;color:var(--accent);white-space:nowrap}
  a.xr{font-family:var(--f-mono);font-size:.82em;font-weight:500;text-decoration:none;border-radius:6px;padding:1px 8px;margin:0 3px 3px 0;display:inline-block;white-space:nowrap}
  a.xr.n{background:var(--accent-soft);color:var(--accent);border:1px solid var(--accent)}
  a.xr.s{background:var(--accent);color:#fff;border:1px solid var(--accent);min-width:1.6em;text-align:center}
  a.xr.t{background:var(--surface);color:var(--ink);border:1px solid var(--line-2)}
  .chipstrip{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:6px;font-size:20px}
  .stg-badge{width:96px;height:96px;border-radius:14px;background:var(--accent);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center}
  .stg-badge span{font-family:var(--f-display);font-weight:800;font-size:56px;line-height:1}
  .stg-badge i{font-style:normal;font-family:var(--f-mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;opacity:.85;margin-top:4px}
  .stg-h .ids{margin-left:auto;display:flex;flex-wrap:wrap;gap:4px 14px;justify-content:flex-end;font-size:20px}
  .stg-h .ids em{font-style:normal;font-size:15px;color:var(--muted)}
  .lifted{display:inline-block;background:var(--pass-s);color:#fff;font-family:var(--f-mono);font-size:22px;letter-spacing:.08em;padding:8px 18px;border-radius:8px;margin-bottom:20px}
  .stepb{display:inline-grid;place-items:center;width:44px;height:44px;border-radius:10px;background:var(--accent);color:#fff;font-family:var(--f-display);font-weight:800;font-size:24px}
  .krow{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}
  .ktile{background:var(--surface);border:1px solid var(--line);border-left:6px solid var(--accent);border-radius:12px;padding:18px 24px;display:grid;gap:4px}
  .ktile.hold{border-left-color:var(--hold-s)}
  .ktile .kl{font-family:var(--f-mono);font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
  .ktile b{font-family:var(--f-display);font-weight:800;font-size:64px;line-height:1.05;font-variant-numeric:tabular-nums}
  .ktile .ks{font-size:18px;color:var(--muted)}
  .ul{margin:0;padding-left:24px;font-size:20px;display:grid;gap:8px}
  .barsvg .wvv{font-family:var(--f-display);font-weight:800;font-size:30px;fill:var(--ink);text-anchor:middle}
  .barsvg .wvl{font-family:var(--f-mono);font-size:18px;fill:var(--accent);text-anchor:middle}
  .barsvg .wvs{font-size:17px;fill:var(--muted);text-anchor:middle}
  .src{font-size:23px;line-height:1.6;padding-left:28px} .src a{color:var(--accent)}
  `;

  const html = `<!doctype html><html data-theme="light"><head><meta charset="utf-8"><title>Global Code Purple — deck</title>
  <style>${fontCSS}\n${pageCSS}\n${deckCSS}</style></head><body>${body}<script>${tocFill}</script></body></html>`;

  // ---------- markdown parent with the same slugs ----------
  const L = [];
  L.push('# Global Code Purple', '', `_${STAMP}. Generated from the same model as the page and the deck; anchors match the PDF links._`, '');
  L.push('## Contents', '', ...SECTIONS.map(x => `- ${x.id} · ${x.name}`), '- [Process stages](#process-stages) · [Nodes](#nodes) · [Triggers](#triggers) · [Edges](#edges)', '');
  L.push('## Process stages', '');
  M.STAGES.forEach(st => { L.push(`<a id="${slugS(st.n)}"></a>`, `### Stage ${st.n} · ${st.name} (${M.PH[st.ph]})`, '',
    `Nodes: ${st.nodes.map(id => `[${id}](#${slugN(id)}) ${byId[id].label}`).join(' · ')}`, '',
    `- **Entry:** ${st.entry.join('; ')}`, `- **Actions:** ${st.acts.join('; ')}`, `- **Exit:** ${st.exit.join('; ')}`, ''); });
  L.push('## Nodes', '', '| ID | Node | Role | Phase | Stage | Triggers | Artefact | Status |', '|---|---|---|---|---|---|---|---|');
  M.NODES.forEach(n => L.push(`| <a id="${slugN(n.id)}"></a>${n.id} | **${n.label}**: ${n.does} | ${M.KIND[n.kind]} | ${M.PH[n.phase]} | ${stageOf[n.id] ? `[${stageOf[n.id]}](#${slugS(stageOf[n.id])})` : '—'} | ${(trigOf[n.id] || []).map(t => `[${t}](#${slugT(t)})`).join(' ') || '—'} | \`${n.artefact}\` | ${M.STATUS[n.status]} |`));
  L.push('', '## Triggers', '', '| ID | From → to | Event | Guard | Action | Nodes | Wired today |', '|---|---|---|---|---|---|---|');
  M.TRIGGERS.forEach(t => { const F = M.LSTATES.find(x => x.id === t.f).label, T = M.LSTATES.find(x => x.id === t.t).label;
    L.push(`| <a id="${slugT(t.id)}"></a>${t.id} | ${F} → ${T} | ${t.ev} | ${t.guard} | ${t.act} | ${t.nodes.map(id => `[${id}](#${slugN(id)})`).join(' ')} | ${M.WIRED[t.w]}: ${t.wn} |`); });
  L.push('', '## Edges', '', '| ID | From → to | Type | Meaning |', '|---|---|---|---|');
  M.EDGES.forEach(e => L.push(`| ${e.id} | [${e.f}](#${slugN(e.f)}) → [${e.t}](#${slugN(e.t)}) | ${M.EKIND[e.k]} | ${e.m} |`));
  fs.writeFileSync(path.join(OUT, 'code-purple.md'), L.join('\n') + '\n');
  fs.writeFileSync(path.join(OUT, 'deck.html'), html);
  fs.writeFileSync(path.join(OUT, 'deck_sections.json'), JSON.stringify(SECTIONS.map(x => [x.id + '  ' + x.name, num(firstOf[x.id]) - 1])));

  const d = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  const errs = []; d.on('pageerror', e => errs.push(e.message));
  await d.goto('file://' + path.join(OUT, 'deck.html'));
  await d.evaluate(() => document.fonts.ready);
  // overflow check
  const over = await d.evaluate(() => [...document.querySelectorAll('.slide')].map((s, i) => { const b = s.querySelector('.sbody'); return b.scrollHeight > b.clientHeight + 2 ? `${i + 1}:+${b.scrollHeight - b.clientHeight}px` : null; }).filter(Boolean));
  await d.pdf({ path: path.join(OUT, 'deck_landscape.pdf'), width: '1920px', height: '1080px', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });

  // ---------- portrait detail page for the tall pulse graph ----------
  const legendRows = roles.map(r => `<span>${swatchRole(r[0])}${r[1]}</span>`).join('') +
    edges.map(r => `<span><svg viewBox="0 0 60 14" class="lsv"><line x1="0" y1="7" x2="60" y2="7" class="e-${r[0]}"/></svg>${r[1]}</span>`).join('');
  const phtml = `<!doctype html><html data-theme="light"><head><meta charset="utf-8"><style>${fontCSS}\n${pageCSS}\n${deckCSS}
  @page{size:1080px 1920px;margin:0}
  .slide.portrait{width:1080px;height:1920px}
  .portrait .snav{padding:0 40px;gap:2px} .portrait .snav a{font-size:13px;padding:6px 8px} .portrait .snav .brand{font-size:12px}
  .portrait .sbody{padding:36px 48px 16px}
  .portrait .psvg svg{width:984px;height:auto;display:block}
  .portrait .plg{display:grid;grid-template-columns:repeat(4,1fr);gap:10px 18px;font-size:17px;margin-top:18px}
  .portrait .plg span{display:flex;align-items:center;gap:10px}
  .portrait .sfoot{padding:0 40px;font-size:13px}
  .portrait .pidx{display:grid;grid-template-columns:1fr 1fr;gap:6px 30px;margin-top:22px;padding-top:16px;border-top:1px solid var(--line);font-size:17px}
  .portrait .pidx div{display:grid;grid-template-columns:52px 40px 1fr auto;align-items:center}
  .portrait .pidx .mono{font-size:14px;color:var(--accent)} .portrait .pidx i{font-style:normal;font-family:var(--f-mono);font-size:13px;color:var(--muted)}
  </style></head><body><section class="slide portrait">${nav('C')}
  <div class="sbody">${kicker('Execution pulse · portrait detail of slide 09')}<h1 style="font-size:44px;margin-bottom:14px">One pulse, three lanes</h1>
  <div class="psvg">${strip(svgs.pulse)}</div><div class="plg">${legendRows}</div><div class="pidx">${M.NODES.map(n => `<div><span class="mono">${n.id}</span>${swatchRole(n.kind)}<b>${esc(n.label)}</b><i>${M.PH[n.phase]}</i></div>`).join('')}</div></div>
  <footer class="sfoot"><span>${STAMP}</span><span>C · Protocol</span><span class="pg">10 / ${N}</span></footer></section></body></html>`;
  fs.writeFileSync(path.join(OUT, 'deck_portrait.html'), phtml);
  const pp = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await pp.goto('file://' + path.join(OUT, 'deck_portrait.html'));
  await pp.evaluate(() => document.fonts.ready);
  const pover = await pp.evaluate(() => { const b = document.querySelector('.sbody'); return b.scrollHeight - b.clientHeight; });
  await pp.pdf({ path: path.join(OUT, 'deck_portrait.pdf'), width: '1080px', height: '1920px', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  console.log('portrait overflow px', pover);
  console.log('slides', N, 'overflow', JSON.stringify(over), errs.join('|') || 'NO_ERRORS');
  await b.close();
})();
