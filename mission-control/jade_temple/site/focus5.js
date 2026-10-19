/* JADE focus-five read-only view. Never calls GitHub or executes a job. */
(() => {
  'use strict';
  const D = JSON.parse(document.querySelector('#focus5-data').textContent);
  const $ = (id) => document.getElementById(id);
  const SVG = 'http://www.w3.org/2000/svg';
  const state = { view: 'parallel', repo: 'all', search: '' };
  const rows = [...D.rows]; // preserve QPS-first owner priority, not numeric rank
  const allowed = new Set(['PASS', 'FAIL', 'UNKNOWN']);
  if (D.workflow.merge_admission !== 'HOLD' || D.workflow.dispatch_performed !== false) {
    throw new Error('Unsafe dashboard authority input');
  }
  if (rows.length !== 5 || D.metrics.required_gate_total !== 60) {
    throw new Error('Invalid fixed denominator');
  }
  for (const row of rows) {
    if (row.gates.length !== 12 || row.gates.some(g => !allowed.has(g.status))) {
      throw new Error('Invalid twelve-gate cohort');
    }
  }
  const make = (tag, opts = {}) => {
    const node = document.createElement(tag);
    if (opts.text !== undefined) node.textContent = opts.text;
    if (opts.className) node.className = opts.className;
    return node;
  };
  const svg = (tag, attrs = {}) => {
    const node = document.createElementNS(SVG, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    return node;
  };
  const addText = (root, txt, x, y, cls, anchor = 'start') => {
    const t = svg('text', { x, y, 'text-anchor': anchor, 'class': cls || '' });
    t.textContent = txt;
    root.appendChild(t); return t;
  };
  const score = (n, d) => (100 * n / d).toFixed(2) + '%';
  const byName = (repo) => rows.find(r => r.repo === repo);
  const itemRepo = (r) => r.repo.split('/')[1];
  const selected = () => byName(state.repo) || rows.find(r => r.rank === 4) || rows[0];
  const match = (r) => {
    if (!state.search) return true;
    const q = state.search.toLowerCase();
    return [r.repo, r.role, ...r.blockers,
            ...r.gates.map(g => g.label + ' ' + g.reason)].join(' ').toLowerCase().includes(q);
  };
  function anchor(url, label) {
    const a = make('a', { text: label });
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  }
  function drawMetrics() {
    $('totalPct').textContent = score(D.metrics.passed, 60);
    $('totalBar').style.width = score(D.metrics.passed, 60);
    $('totalGateCount').textContent = D.metrics.passed + ' verified / 60 minimum gates';
    $('passCount').textContent = String(D.metrics.passed);
    $('failCount').textContent = String(D.metrics.failed);
    $('unknownCount').textContent = String(D.metrics.unknown);
    $('sourceEpoch').textContent = D.source.observed_date + ' · non-atomic readback';
  }
  function choose(repo) {
    if (repo !== 'all' && !byName(repo)) throw new Error('Unknown repository');
    state.repo = repo;
    $('repoSelect').value = repo;
    render();
  }
  function drawCards() {
    const root = $('repoCards'); root.replaceChildren();
    for (const r of rows.filter(match)) {
      const btn = make('button', { className: 'lane' + (selected().repo === r.repo ? ' active' : '') });
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Inspect ' + r.repo);
      const number = make('span', { text: String(r.rank).padStart(2, '0'), className: 'rank' });
      const name = make('div');
      name.appendChild(make('div', { text: itemRepo(r), className: 'repo-label' }));
      name.appendChild(make('div', { text: r.verified_complete + '/12 PASS · ' +
        r.verified_failed + ' FAIL · ' + r.unqualified + ' unknown', className: 'desc' }));
      const rate = make('div', { text: score(r.verified_complete, 12), className: 'rate' });
      rate.appendChild(make('small', { text: 'verified' }));
      btn.append(number, name, rate);
      btn.addEventListener('click', () => choose(r.repo));
      root.appendChild(btn);
    }
    if (!root.childElementCount) root.appendChild(make('p', { text: 'No matching repositories or gates.', className: 'muted' }));
  }
  function drawDetails() {
    const r = selected(), root = $('detail'); root.replaceChildren();
    root.appendChild(make('h3', { text: r.repo, className: 'detail-title' }));
    const line = make('div', { className: 'detail-sub' });
    line.appendChild(make('span', { text: 'JADE #' + r.rank + ' · ' +
      r.verified_complete + '/12 = ' + score(r.verified_complete, 12), className: 'detail-badge' }));
    line.appendChild(anchor('https://github.com/' + r.repo + '/actions', 'Native Actions ↗'));
    root.appendChild(line);
    root.appendChild(make('p', { text: 'main: ' + r.source_sha, className: 'detail-sha' }));
    root.appendChild(make('p', { text: r.role, className: 'muted' }));
    if (r.candidate_sha) {
      const line2 = make('p', { className: 'muted' });
      line2.appendChild(make('span', { text: 'Candidate branch (not admitted): ' }));
      line2.appendChild(anchor('https://github.com/' + r.repo + '/commit/' + r.candidate_sha,
                               r.candidate_sha.slice(0, 12) + ' ↗'));
      root.appendChild(line2);
    }
    const list = make('div', { className: 'gate-list' });
    for (const g of r.gates) {
      const block = make('div', { className: 'gate' });
      const header = make('div', { className: 'gate-head' });
      header.appendChild(make('span', { text: g.id, className: 'id' }));
      header.appendChild(make('strong', { text: g.label }));
      header.appendChild(make('span', { text: g.status, className: 'state ' + g.status }));
      block.appendChild(header);
      block.appendChild(make('p', { text: g.reason }));
      if (g.evidence) {
        const a = anchor(g.evidence, 'Open source evidence ↗');
        a.className = 'evidence';
        block.appendChild(a);
      }
      list.appendChild(block);
    }
    root.appendChild(list);
  }
  function line(x1, y1, x2, y2, extra = '') {
    return svg('path', { d: 'M ' + x1 + ' ' + y1 + ' L ' + x2 + ' ' + y2,
      class: 'edge ' + extra });
  }
  function circle(x, y, radius, status, titleText, onClick) {
    const n = svg('circle', { cx: x, cy: y, r: radius,
      class: 'neur ' + status + ' graph-click', tabindex: 0 });
    n.appendChild(svg('title')); n.firstChild.textContent = titleText;
    if (onClick) {
      n.addEventListener('click', onClick);
      n.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onClick(); }
      });
    }
    return n;
  }
  function drawParallel(root) {
    $('graphTitle').textContent = 'Parallel lanes · 60 gate neurons';
    $('graphLegend').textContent = 'Five independent 12-gate sequences; node color is evidence state';
    const names = D.requisites.map(x => x.id);
    names.forEach((id, i) => addText(root, id, 238 + i * 68, 29, 'note', 'middle'));
    rows.forEach((r, ri) => {
      const y = 72 + ri * 77;
      const name = itemRepo(r);
      addText(root, String(r.rank).padStart(2,'0') + ' · ' +
              (name.length > 20 ? name.slice(0, 19) + '…' : name), 7, y + 4, 'label');
      const gates = r.gates;
      for (let i = 0; i < gates.length - 1; i++) root.appendChild(line(238 + i * 68 + 10, y, 238 + (i + 1) * 68 - 10, y));
      gates.forEach((g, i) => {
        root.appendChild(circle(238 + i * 68, y, 9,
          g.status, r.repo + ' ' + g.id + ' ' + g.status + ': ' + g.reason,
          () => choose(r.repo)));
      });
      addText(root, score(r.verified_complete, 12), 1030, y + 4, 'note', 'end');
    });
    addText(root, 'Structural sequence. Passing upstream does NOT imply a passing downstream release gate.', 10, 434, 'note');
  }
  function drawDependencies(root) {
    $('graphTitle').textContent = 'Typed QPS TRIAGE dependency graph';
    $('graphLegend').textContent = 'Solid = declared owner interface; dashed = authority-bound observation only';
    const loc = {
      'GBOGEB/DOCX_RTM_Automation': [185, 84],
      'GBOGEB/yaml-grammar': [185, 198],
      'GBOGEB/gg_MATH': [185, 314],
      'GBOGEB/cryoplant-project': [535, 164],
      'GBOGEB/pipeline-automation-hub': [820, 310],
      'GBOGEB/ABACUS': [535, 53],
      'GBOGEB/CODEX': [820, 52]
    };
    for (const e of D.edges) {
      const a = loc[e.from], b = loc[e.to];
      if (a && b) root.appendChild(line(a[0], a[1], b[0], b[1],
        e.state === 'AUTHORITY_BOUND' ? 'external' : ''));
    }
    for (const [repo, coords] of Object.entries(loc)) {
      const r = byName(repo), status = r ? (r.verified_failed > 0 ? 'FAIL' : 'UNKNOWN') : 'UNKNOWN';
      root.appendChild(circle(coords[0], coords[1], r ? 31 : 23, status, repo +
        ' · ' + (r ? r.verified_complete + '/12 PASS' : 'external owner authority'), r ? () => choose(repo) : null));
      addText(root, repo.replace('GBOGEB/', ''), coords[0], coords[1] + 49, 'note', 'middle');
    }
    addText(root, 'DOCX candidate RTM input  ·  YAML grammar reference  ·  gg_MATH method provider', 14, 402, 'note');
    addText(root, 'QPS keeps engineering authority; ABACUS DOW and CODEX KEB have independent control gates.', 14, 426, 'note');
  }
  function drawGolden(root) {
    $('graphTitle').textContent = 'Golden thread · nine separate acceptance atoms';
    $('graphLegend').textContent = 'A visible connection is not a qualified merge, root closure or release';
    const labels = D.golden_thread.map(s => s.replaceAll('_', ' '));
    const x0 = 56, step = 115, y = 183;
    for (let i = 0; i < labels.length - 1; i++) root.appendChild(line(x0 + i * step + 20, y,
      x0 + (i + 1) * step - 20, y, 'external'));
    labels.forEach((label, i) => {
      const x = x0 + i * step;
      const status = i === 0 ? 'PASS' : 'UNKNOWN';
      root.appendChild(circle(x, y, 19, status,
        label + ': ' + (i === 0 ? 'source identity present' : 'independent owner proof required')));
      addText(root, '0' + (i + 1), x, y + 4, 'note', 'middle');
      const words = label.split(' ');
      words.forEach((word, j) => addText(root, word, x, y + 37 + j * 14, 'note', 'middle'));
    });
    addText(root, 'Not admitted: human review · security · rejected RED canary · postmerge SHA · owner tag and rollback.', 16, 391, 'note');
    addText(root, 'The sequence is a provenance architecture, not artificial neural weights or measured causal influence.', 16, 420, 'note');
  }
  function drawGraph() {
    const root = $('dag'); root.replaceChildren();
    if (state.view === 'dependencies') drawDependencies(root);
    else if (state.view === 'golden') drawGolden(root);
    else drawParallel(root);
  }
  function drawWaves() {
    const root = $('waveActions'); root.replaceChildren();
    rows.forEach((r, i) => {
      const card = make('div', { className: 'wave' });
      card.appendChild(make('div', { text: 'OWNER ' + String(i + 1).padStart(2, '0'), className: 'eyebrow' }));
      card.appendChild(make('h3', { text: itemRepo(r) }));
      card.appendChild(make('p', { text: r.owner_action }));
      root.appendChild(card);
    });
  }
  function render() { drawCards(); drawDetails(); drawGraph(); }
  for (const r of rows) {
    const opt = make('option', { text: String(r.rank).padStart(2, '0') + ' · ' + itemRepo(r) });
    opt.value = r.repo; $('repoSelect').appendChild(opt);
  }
  document.querySelectorAll('[data-view]').forEach(btn => btn.addEventListener('click', () => {
    state.view = btn.dataset.view;
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b === btn));
    drawGraph();
  }));
  $('search').addEventListener('input', event => {
    state.search = event.target.value.trim();
    drawCards();
  });
  $('repoSelect').addEventListener('change', event => choose(event.target.value));
  drawMetrics(); drawWaves(); choose(rows.find(r => r.rank === 4).repo);
})();
