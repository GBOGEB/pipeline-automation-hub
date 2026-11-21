// Offline consumer projection of existing Kahn layers; no scheduling or admission.
function renderDevelopment(repo, parent) {
  const model = repo.development;
  if (!model) return;
  const box = detail('BIOS / pipeline scope / ADR development', parent);
  box.open = true;
  el('p', model.purpose, box);
  el('p', 'Lane: ' + model.lane + ' · Scope: ' + model.scope_state, box);
  link(model.purpose_source, box);
  for (const pipeline of model.pipelines) {
    const view = detail(pipeline.label, box);
    view.dataset.pipeline = pipeline.id;
    el('p', 'Entry-file LOC: ' + pipeline.entry_loc + ' · Explicit review scope, not transitive pipeline LOC.', view);
    table(['Supplier', 'Input', 'Process', 'Output', 'Customer'], [[pipeline.sipoc.supplier, pipeline.sipoc.input, pipeline.sipoc.process, pipeline.sipoc.output, pipeline.sipoc.customer]], view);
    const files = detail('Source scope and entry OIDs', view);
    pipeline.entry_files.forEach(row => link(row, files));
    if (pipeline.graph_error) el('p', 'Graph diagnostic: ' + pipeline.graph_error, view);
    else if (pipeline.layers && pipeline.layers.length) drawPipeline(pipeline, view);
    else el('p', 'No workflow DAG selected. Execution readiness: NOT_EVALUATED.', view);
    const context = detail('External calls and environment gates (context only)', view);
    table(['Job', 'Relation', 'Target'], pipeline.context_relations.map(r => [r.from_job, r.kind, r.target]), context);
    const decisions = detail('ADR / decision source crosswalk — ' + pipeline.adr_sources.length, view);
    for (const adr of pipeline.adr_sources) {
      const d = detail(adr.title, decisions);
      link(adr, d);
      el('p', 'Acceptance: NOT_EVALUATED · Review crosswalk; no hard dependency inferred.', d);
      table(['Field', 'Source declaration', 'Source line'], adr.declarations.map(r => [r.field, r.value, r.line]), d);
    }
  }
}

function drawPipeline(pipeline, parent) {
  const wrap = el('div', undefined, parent);
  wrap.className = 'scroll';
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  const positions = new Map();
  const width = Math.max(400, pipeline.layers.length * 210);
  const height = 80 + Math.max(...pipeline.layers.map(w => w.length)) * 100;
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', pipeline.label + ' declared workflow dependencies by Kahn wave');
  wrap.append(svg);
  const panel = el('div', undefined, parent);
  panel.setAttribute('aria-live', 'polite');
  el('p', 'Select a job to inspect prerequisites, consumers, observations and OIDs. Lines show declared needs only.', panel);
  function shape(tag, attrs, text) {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (text !== undefined) node.textContent = text;
    svg.append(node);
    return node;
  }
  pipeline.layers.forEach((wave, col) => {
    shape('text', {x: col * 210 + 14, y: 24, fill: '#e6edf6'}, 'Kahn wave ' + col);
    wave.forEach((id, row) => positions.set(id, {x: col * 210 + 12, y: row * 100 + 45}));
  });
  for (const job of pipeline.nodes) {
    const end = positions.get(job.id);
    for (const upstream of job.upstream) {
      const start = positions.get(upstream);
      if (start && end) shape('line', {x1: start.x + 175, y1: start.y + 30, x2: end.x, y2: end.y + 30, stroke: '#8195b5', 'stroke-width': 2});
    }
  }
  function inspect(job) {
    panel.replaceChildren();
    el('h4', job.id, panel);
    el('p', 'Reported observation: ' + job.evidence.state + ' · ' + job.evidence.reason, panel);
    el('p', 'Execution readiness: NOT_EVALUATED (conditions, artifacts and owner gates are separate).', panel);
    table(['Direct upstream', 'Direct downstream', 'Reported failed prerequisites', 'Unobserved prerequisites'], [[job.upstream.join(', ') || 'none declared', job.downstream.join(', ') || 'none declared', job.reported_failed_prerequisites.join(', ') || 'none reported', job.unobserved_prerequisites.join(', ') || 'none']], panel);
    el('pre', job.oid + '\nDefinition SHA256: ' + job.definition_sha256, panel);
    if (job.evidence.record) el('pre', JSON.stringify(job.evidence.record, null, 2), panel);
  }
  for (const job of pipeline.nodes) {
    const pos = positions.get(job.id);
    if (!pos) continue;
    const bad = job.evidence.state === 'REPORTED_FAILURE';
    const rect = shape('rect', {x: pos.x, y: pos.y, width: 175, height: 65, rx: 8, fill: bad ? '#732a3b' : '#23344f', stroke: '#a8ceff', tabindex: 0, role: 'button', 'aria-label': 'Inspect job ' + job.id});
    rect.style.cursor = 'pointer';
    rect.addEventListener('click', () => inspect(job));
    rect.addEventListener('keydown', event => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault();inspect(job);}});
    const label = shape('text', {x: pos.x + 8, y: pos.y + 24, fill: '#e6edf6', 'font-size': 12, 'pointer-events': 'none'}, job.id.length > 23 ? job.id.slice(0, 21) + '…' : job.id);
    const title = document.createElementNS(ns, 'title');title.textContent = job.id;label.append(title);
    shape('text', {x: pos.x + 8, y: pos.y + 47, fill: '#c2d4ef', 'font-size': 10, 'pointer-events': 'none'}, job.evidence.state);
  }
}
