/* Source-driven, offline Method Atlas. No requests, dispatches or token access. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const obj = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const list = (value) => Array.isArray(value) ? value : [];
  const text = (value, fallback = "UNKNOWN") => value === null || value === undefined || value === "" ? fallback : typeof value === "object" ? JSON.stringify(value) : String(value);
  const displayKey = (value) => text(value).replace(/_/g, " ");
  const NS = "http://www.w3.org/2000/svg";
  let model;
  try { model = JSON.parse($("source-model").textContent); }
  catch (error) { $("diagram-view").textContent = "Source model could not be read: " + error.message; return; }
  const source = obj(model.source);
  const blocks = list(model.blocks).filter((value) => value && typeof value === "object");
  const graphs = list(model.graphs).filter((value) => value && typeof value === "object");
  const programmes = list(obj(model.taxonomy).programmes);
  const inventory = obj(model.inventory);
  const coverage = obj(model.coverage);
  const coverageRows = list(coverage.rows);
  const sourceRecords = list(inventory.python_modules).map((record) => ({ ...record, family: "python" })).concat(list(inventory.workflows).map((record) => ({ ...record, family: "workflow" })));
  const sourceMap = new Map(sourceRecords.map((record) => [text(record.path), record]));
  const programmeNames = new Map(programmes.map((programme) => [text(programme.id), text(programme.label || programme.id)]));
  const blockMap = new Map(blocks.map((block) => [text(block.id), block]));
  const state = { graph: graphs[0] || null, selectedNode: null, selectedBlock: null, selectedSource: null, page: 0, sourcePage: 0, graphPage: 0, pageSize: 30, view: "diagram" };

  function element(tag, value, className) {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = text(value);
    if (className) node.className = className;
    return node;
  }
  function svgElement(tag, attributes = {}, value) {
    const node = document.createElementNS(NS, tag);
    for (const [key, item] of Object.entries(attributes)) node.setAttribute(key, text(item, ""));
    if (value !== undefined) node.textContent = text(value);
    return node;
  }
  function clear(node) { node.replaceChildren(); return node; }
  function button(label, handler, className) {
    const node = element("button", label, className);
    node.type = "button";
    node.addEventListener("click", handler);
    return node;
  }
  function number(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : "UNKNOWN";
  }
  function statusClass(value) {
    const valueText = text(value).toUpperCase();
    if (/UNKNOWN|UNVERIFIED|NOT[ _-]|MISSING|UNQUALIFIED/.test(valueText)) return "unknown";
    if (/FAIL|BLOCK|HOLD|DEFER|(^|_)RED($|_)/.test(valueText)) return "blocked";
    if (/PASS|DONE|CLOSED|VERIFIED|SUCCEEDED/.test(valueText)) return "passed";
    if (/PROPOS|DESIGN|DECLAR|ROLE|POLICY/.test(valueText)) return "declared";
    return "unknown";
  }
  function badge(value) { return element("span", text(value), "badge " + statusClass(value)); }
  function safeURL(value) {
    if (typeof value !== "string" || !value || /[\x00-\x1f\\]/.test(value)) return null;
    if (/^https?:\/\//i.test(value)) {
      try { return new URL(value).href; } catch (_error) { return null; }
    }
    return !value.startsWith("/") && !value.split("/")[0].includes(":") ? value : null;
  }
  function sourceURL(record) {
    const explicit = safeURL(record.source_url);
    if (explicit) return explicit;
    const repository = record.repo || source.repository;
    const head = record.head_sha || source.head_sha;
    if (typeof repository === "string" && /^[\w.-]+\/[\w.-]+$/.test(repository) && head && record.source_path) {
      return "https://github.com/" + repository + "/blob/" + encodeURIComponent(head) + "/" + String(record.source_path).split("/").map(encodeURIComponent).join("/");
    }
    return null;
  }
  function sourceLink(record) {
    const href = sourceURL(record);
    const node = element(href ? "a" : "span", text(record.source_path), "source-path");
    if (href) { node.href = href; node.target = "_blank"; node.rel = "noreferrer"; }
    return node;
  }
  function artifactLink(path, label) {
    const href = safeURL(path);
    if (!href) return null;
    const link = element("a", label, "artifact-link");
    link.href = href;
    return link;
  }
  function metadata(record) {
    const dl = element("dl", undefined, "metadata");
    for (const [key, value] of Object.entries(obj(record))) {
      const row = element("div");
      row.append(element("dt", displayKey(key)), element("dd", text(value)));
      dl.append(row);
    }
    return dl.childElementCount ? dl : element("p", "UNKNOWN · no source fields supplied.", "empty");
  }
  function addOptions(select, entries) {
    for (const [value, label] of entries) {
      const option = element("option", label);
      option.value = value;
      select.append(option);
    }
  }
  function searchable(record) { return JSON.stringify(record).toLowerCase(); }
  function programmeLabel(value) { return programmeNames.get(text(value)) || text(value); }
  function programmeTag(value) {
    const node = element("span", programmeLabel(value), "tag");
    node.dataset.programme = text(value);
    return node;
  }

  function contractTable(raw, label) {
    const section = element("section", undefined, "contract");
    section.append(element("h4", label));
    const values = list(raw);
    if (!values.length) {
      section.append(element("p", "UNKNOWN · no explicit " + label.toLowerCase() + " contract supplied.", "empty"));
      return section;
    }
    const table = element("table");
    const header = element("thead");
    const headRow = element("tr");
    ["Interface", "Type / requirement", "Validation / checking"].forEach((value) => headRow.append(element("th", value)));
    header.append(headRow);
    table.append(header);
    const body = element("tbody");
    for (const rawItem of values) {
      const item = typeof rawItem === "string" ? { name: rawItem } : obj(rawItem);
      const row = element("tr");
      const nameCell = element("td");
      nameCell.append(element("strong", text(item.name || item.label || item.id || item.path || item.artifact)));
      if (item.description || item.purpose) nameCell.append(element("p", item.description || item.purpose, "fine"));
      const typeCell = element("td");
      typeCell.append(element("span", text(item.type || item.kind || item.format || item.schema)));
      typeCell.append(element("p", "Required: " + text(item.required), "fine"));
      if (item.schema) typeCell.append(element("p", "Schema: " + text(item.schema), "fine"));
      const validation = item.validation || item.checks || item.check || item.validator || item.validation_rule;
      const checkCell = element("td", text(validation));
      if (item.evidence_class || item.status) checkCell.append(badge(item.evidence_class || item.status));
      row.append(nameCell, typeCell, checkCell);
      body.append(row);
    }
    table.append(body);
    const wrap = element("div", undefined, "table-scroll");
    wrap.append(table);
    section.append(wrap);
    return section;
  }

  function selectBlock(id, scroll = false) {
    const block = blockMap.get(text(id));
    if (!block) return;
    state.selectedBlock = text(id);
    const target = clear($("block-inspector"));
    target.append(element("div", block.id, "eyebrow"), element("h3", block.label || block.id), badge(block.status));
    target.append(element("p", block.purpose), sourceLink(block));
    target.append(metadata({ repository: block.repo || source.repository, entrypoint: block.entrypoint, role: block.role, programmes: list(block.programmes).map(programmeLabel) }));
    if (sourceMap.has(text(block.source_path))) target.append(button("Inspect Python source", () => selectSource(block.source_path, true), "small-button"));
    target.append(contractTable(block.inputs, "Inputs"), contractTable(block.outputs, "Outputs"));
    const deps = element("section", undefined, "contract");
    deps.append(element("h4", "Declared prerequisites"));
    if (list(block.needs).length) {
      const ul = element("ul", undefined, "dependency-list");
      for (const need of block.needs) {
        const needId = typeof need === "string" ? need : text(obj(need).id || obj(need).from);
        const li = element("li");
        const matched = blockMap.get(needId);
        li.append(matched ? button(matched.label || needId, () => selectBlock(needId), "text-button") : element("span", needId));
        ul.append(li);
      }
      deps.append(ul);
    } else deps.append(element("p", Array.isArray(block.needs) ? "No prerequisites declared in this source record." : "UNKNOWN · prerequisite inventory not supplied.", "fine"));
    target.append(deps);
    const attributes = element("details");
    attributes.append(element("summary", "Python / workflow attributes"), metadata(block.attributes));
    target.append(attributes);
    document.querySelectorAll("#block-rows tr[data-block]").forEach((row) => row.classList.toggle("selected", row.dataset.block === state.selectedBlock));
    if (scroll && window.innerWidth < 1100) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderBlocks() {
    const query = $("block-search").value.trim().toLowerCase();
    const programme = $("programme-filter").value;
    const role = $("role-filter").value;
    const filtered = blocks.filter((block) => (!query || searchable(block).includes(query)) && (programme === "all" || list(block.programmes).map((value) => text(value)).includes(programme)) && (role === "all" || text(block.role) === role));
    const maxPage = Math.max(0, Math.ceil(filtered.length / state.pageSize) - 1);
    state.page = Math.min(state.page, maxPage);
    const start = state.page * state.pageSize;
    const visible = filtered.slice(start, start + state.pageSize);
    const body = clear($("block-rows"));
    for (const block of visible) {
      const row = element("tr");
      row.dataset.block = text(block.id);
      row.classList.toggle("selected", row.dataset.block === state.selectedBlock);
      const title = element("td");
      title.append(element("strong", block.label || block.id), sourceLink(block));
      const purpose = element("td", block.purpose);
      const tags = element("td");
      tags.append(element("span", block.role, "role-label"));
      const tagList = element("div", undefined, "tag-list");
      list(block.programmes).forEach((value) => tagList.append(programmeTag(value)));
      tags.append(tagList);
      const contracts = element("td");
      contracts.append(element("div", "In: " + (Array.isArray(block.inputs) && block.inputs.length ? number(block.inputs.length) : "UNKNOWN")), element("div", "Out: " + (Array.isArray(block.outputs) && block.outputs.length ? number(block.outputs.length) : "UNKNOWN")));
      const action = element("td");
      action.append(button("Inspect", () => selectBlock(block.id, true), "small-button"));
      row.append(title, purpose, tags, contracts, action);
      body.append(row);
    }
    if (!visible.length) { const row = element("tr"); const cell = element("td", "No functional blocks match these filters.", "empty"); cell.colSpan = 5; row.append(cell); body.append(row); }
    $("block-count").textContent = number(filtered.length) + " / " + number(blocks.length) + " source blocks";
    $("block-page").textContent = filtered.length ? `${start + 1}–${Math.min(start + state.pageSize, filtered.length)} of ${filtered.length}` : "0 results";
    $("previous-blocks").disabled = state.page === 0;
    $("next-blocks").disabled = state.page === maxPage;
  }

  function openFunction(name) {
    for (const details of $("source-inspector").querySelectorAll("details[data-function]")) {
      if (details.dataset.function === name) { details.open = true; details.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
    }
  }
  function pythonSource(record, target) {
    target.append(element("p", record.docstring, "fine"));
    target.append(metadata({ entrypoints: record.entrypoints, static_call_count: list(record.static_calls).length, parse_error: record.parse_error || "None reported" }));
    if (!list(record.functions).length) { target.append(element("p", "No top-level functions recorded in this module.", "fine")); return; }
    for (const fn of list(record.functions)) {
      const details = element("details", undefined, "function-detail");
      details.dataset.function = text(fn.name);
      const summary = element("summary");
      summary.append(element("code", (fn.async ? "async " : "") + text(fn.name) + "(" + text(fn.signature, "") + ")"));
      details.append(summary);
      const reference = { source_path: record.path };
      const href = sourceURL(reference);
      if (href && fn.line) {
        const anchor = element("a", "Source line " + fn.line, "source-path");
        anchor.href = href + "#L" + encodeURIComponent(fn.line); anchor.target = "_blank"; anchor.rel = "noreferrer";
        details.append(anchor);
      }
      if (fn.docstring) details.append(element("p", fn.docstring, "fine"));
      details.append(element("p", "Declared local calls", "fine"));
      if (list(fn.calls).length) {
        const calls = element("div", undefined, "inline-actions");
        list(fn.calls).forEach((name) => calls.append(button(name, () => openFunction(text(name)), "text-button")));
        details.append(calls);
      } else details.append(element("p", "None recorded among top-level functions in this module.", "fine"));
      target.append(details);
    }
  }
  function workflowSource(record, target) {
    target.append(metadata({ triggers: record.triggers, concurrency: record.concurrency, permissions: record.permissions, dynamic_dependencies: record.dynamic_dependencies, parse_errors: list(record.errors).length ? record.errors : "None reported" }));
    if (Array.isArray(record.layers)) {
      const layers = element("ol", undefined, "layer-list");
      record.layers.forEach((layer, index) => layers.append(element("li", "Layer " + (index + 1) + ": " + list(layer).map((value) => text(value)).join(", "))));
      target.append(element("h4", "Declared job dependency layers"), layers);
    }
    for (const job of list(record.jobs)) {
      const details = element("details", undefined, "job-detail");
      details.dataset.job = text(job.id);
      details.open = list(record.jobs).length === 1;
      details.append(element("summary", text(job.label || job.id) + " · " + list(job.steps).length + " ordered steps"));
      details.append(metadata({ job_id: job.id, needs: job.needs, unresolved_needs: job.unresolved_needs, runs_on: job.runs_on, strategy: job.strategy, condition: job.if, concurrency: job.concurrency, reusable_workflow: job.uses }));
      if (!list(job.steps).length) details.append(element("p", "No steps recorded; this may be a reusable workflow job.", "fine"));
      const steps = element("ol", undefined, "step-list");
      for (const step of list(job.steps)) {
        const li = element("li");
        if (Number.isInteger(step.ordinal) && step.ordinal > 0) li.value = step.ordinal;
        li.append(element("strong", step.name || step.id));
        li.append(metadata({ step_id: step.id, uses: step.uses, condition: step.if, continue_on_error: step.continue_on_error, run_sha256: step.run_sha256 }));
        if (list(step.python_targets).length) {
          li.append(element("span", "Python targets", "fine"));
          const targets = element("div", undefined, "inline-actions");
          list(step.python_targets).forEach((path) => targets.append(sourceMap.has(text(path)) ? button(path, () => selectSource(path), "text-button") : element("code", path)));
          li.append(targets);
        }
        steps.append(li);
      }
      details.append(steps); target.append(details);
    }
    target.append(element("p", "Step order, conditions and continue-on-error are source declarations. A preceding step is not automatically a required-success edge. Shell bodies remain source-linked and hash identified.", "fine"));
  }
  function selectSource(path, scroll = false) {
    const record = sourceMap.get(text(path));
    if (!record) return;
    state.selectedSource = text(path);
    const target = clear($("source-inspector"));
    target.append(element("div", record.family === "python" ? "Python / static source" : "GitHub YAML / declared execution", "eyebrow"));
    target.append(element("h3", record.name || record.path), sourceLink({ source_path: record.path }), badge(record.evidence_class));
    target.append(metadata({ sha256: record.sha256 }));
    if (record.family === "python") pythonSource(record, target); else workflowSource(record, target);
    document.querySelectorAll("#source-rows tr[data-source]").forEach((row) => row.classList.toggle("selected", row.dataset.source === state.selectedSource));
    if (scroll) $("sources").scrollIntoView({ behavior: "smooth" });
  }
  function renderSources() {
    const query = $("source-search").value.trim().toLowerCase(), kind = $("source-kind").value;
    const filtered = sourceRecords.filter((record) => (!query || searchable(record).includes(query)) && (kind === "all" || record.family === kind));
    const maxPage = Math.max(0, Math.ceil(filtered.length / state.pageSize) - 1);
    state.sourcePage = Math.min(state.sourcePage, maxPage);
    const start = state.sourcePage * state.pageSize;
    const body = clear($("source-rows"));
    for (const record of filtered.slice(start, start + state.pageSize)) {
      const row = element("tr"), name = element("td"), action = element("td");
      row.dataset.source = text(record.path); row.classList.toggle("selected", row.dataset.source === state.selectedSource);
      name.append(element("strong", record.name || text(record.path).split("/").pop()), sourceLink({ source_path: record.path }));
      const count = record.family === "python" ? list(record.functions).length : list(record.jobs).length;
      action.append(button("Inspect", () => selectSource(record.path, window.innerWidth < 1200), "small-button"));
      row.append(name, element("td", record.family), element("td", count), action); body.append(row);
    }
    if (!body.childElementCount) { const row = element("tr"), cell = element("td", "No source files match these filters.", "empty"); cell.colSpan = 4; row.append(cell); body.append(row); }
    $("source-count").textContent = `${filtered.length} / ${sourceRecords.length} source files`;
    $("source-page").textContent = filtered.length ? `${start + 1}–${Math.min(start + state.pageSize, filtered.length)} of ${filtered.length}` : "0 results";
    $("previous-sources").disabled = state.sourcePage === 0;
    $("next-sources").disabled = state.sourcePage === maxPage;
  }

  function percentage(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100 ? value.toFixed(2) + "%" : "UNKNOWN";
  }
  function coverageMeasures(row) {
    const result = element("div", undefined, "coverage-measures");
    for (const [unit, label] of [["statements", "Statements"], ["branches", "Branches"], ["changed_lines", "Changed lines"]]) {
      const metric = obj(row[unit]);
      const panel = element("div", undefined, "coverage-measure");
      panel.append(element("span", label, "fine"));
      panel.append(element("strong", /NOT_APPLICABLE|NO_EXECUTABLE/.test(text(metric.classification)) ? "N/A" : percentage(metric.pct)));
      panel.append(element("span", number(metric.covered) + " / " + number(metric.eligible), "metric-ratio"));
      panel.append(element("small", metric.classification, "fine"));
      result.append(panel);
    }
    return result;
  }
  function selectCoverage(index) {
    const row = coverageRows[index];
    if (!row) return;
    const target = clear($("coverage-inspector"));
    target.append(element("div", row.id, "eyebrow"), element("h3", row.label || row.id), badge(row.qualification));
    target.append(element("p", ["Portfolio", row.repository, row.family, row.cohort_id].map((value) => text(value)).join(" › "), "selection-path"));
    target.append(coverageMeasures(row));
    const columns = element("div", undefined, "two-up");
    const population = element("section");
    population.append(element("h4", "Population, anchor and qualification"));
    population.append(metadata({
      observation_kind: row.observation_kind, scope: row.scope, comparison_key: row.comparison_key,
      eligible_modules: row.eligible_modules, instrumented_modules: row.instrumented_modules,
      zero_covered_modules: row.zero_covered_modules, unmeasured_modules: row.unmeasured_modules,
      unknown_module_identities: row.unknown_module_identity_count, worst_file_coverage_pct: row.worst_file_coverage_pct,
      inventory_completeness_qualified: row.inventory_completeness_qualified,
      additional_statements_to_75pct_in_this_population: row.additional_statements_to_75pct,
      independently_verified: row.independently_verified, current_head_freshness: row.current_head_freshness
    }));
    const proof = element("section");
    proof.append(element("h4", "Tests and native evidence"));
    proof.append(metadata(Object.keys(obj(row.tests)).length ? row.tests : { collected: null, passed: null, failed: null, skipped: null }));
    proof.append(metadata({ test_context: row.test_context, critical_behavior_verified: row.critical_behavior_verified, function_branch_identity: row.function_branch_identity, instrumentation_version: row.instrumentation_version, coverage_policy_id: row.coverage_policy_id }));
    proof.append(metadata(Object.keys(obj(row.native)).length ? row.native : { head_sha: null, run_id: null, attempt: null, job_id: null }));
    columns.append(population, proof); target.append(columns);
    if (row.note || row.notes) target.append(element("p", row.note || row.notes, "fine"));
    target.append(element("h4", "Module identities and deeper evidence"));
    if (list(row.modules).length) {
      for (const module of row.modules) {
        const details = element("details", undefined, "coverage-module");
        details.append(element("summary", module.name || module.path));
        details.append(coverageMeasures(module), metadata({ source_path: module.path, membership: module.membership, function_branch: module.function_branch, test_context: module.test_context, native_evidence: module.native_evidence }));
        target.append(details);
      }
    } else target.append(element("p", "UNKNOWN · no individually identified modules supplied in this cohort.", "empty"));
    const identity = element("details");
    identity.append(element("summary", "Immutable observation identity and source provenance"), metadata({ event_id: row.event_id, event_sha256: row.event_sha256, source_provenance: row.source_provenance }));
    target.append(identity);
    document.querySelectorAll("#coverage-rows [data-coverage]").forEach((item) => item.classList.toggle("selected", Number(item.dataset.coverage) === index));
    if (window.innerWidth < 860) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function filterCoverage() {
    const repository = $("coverage-repository").value, kind = $("coverage-kind").value;
    let visible = 0;
    document.querySelectorAll("#coverage-rows [data-coverage]").forEach((row) => {
      row.hidden = (repository !== "all" && row.dataset.repository !== repository) || (kind !== "all" && row.dataset.kind !== kind);
      if (!row.hidden) visible += 1;
    });
    $("coverage-count").textContent = `${visible} / ${coverageRows.length} independently scoped observations`;
  }

  function roleLabel(node) {
    const direct = node.role || node.kind || node.type;
    if (direct) return text(direct);
    const family = text(state.graph && state.graph.kind);
    if (family === "SIPOC") return ({ S: "supplier", I: "input", P: "process", O: "output", C: "customer" })[text(node.id)] || "role unknown";
    return ({ STATIC_CALLS: "Python function", WORKFLOW_JOBS: "workflow job", WORKFLOW_STEPS: "ordered step", METHOD_LANE: "method stage", EXECUTABLE_LOCAL: "local task adapter" })[family] || "role unknown";
  }
  function nodeRole(node) {
    if (["source", "qualified", "waiting", "blocked", "viewer", "neutral"].includes(node.visual_role)) return node.visual_role;
    // Keep this fallback identical to main.graph_role; programme hue cannot
    // establish qualification and descriptive role labels remain independent.
    const state = text(node.status === undefined ? node.state : node.status, "").toUpperCase();
    const role = text(node.role === undefined ? node.class : node.role, "").toLowerCase();
    if (["BLOCKED", "FAILED", "HOLD", "RETURN_OWNER"].includes(state) || ["blocked", "hold"].includes(role)) return "blocked";
    if (node.native_qualified === true) return "qualified";
    if (["WAITING", "PENDING", "QUEUED", "DEFERRED", "UNKNOWN_NEEDS_READER"].includes(state)) return "waiting";
    if (["viewer", "packager", "semantic", "control"].includes(role)) return "viewer";
    if (["neutral", "actor"].includes(role)) return "neutral";
    return "source";
  }
  function edgeEndpoints(edge) { return [text(edge.from || edge.source), text(edge.to || edge.target)]; }
  function isDashed(edge) { return !["LOCAL_CONTRACT", "RECEIPT", "NATIVE_RECEIPT"].includes(edge.binding); }
  function edgeColor(edge) {
    return ({ DEPENDENCY: "#4c9ad6", ARTIFACT_HANDOFF: "#169c87", FEEDBACK_NEXT_PULSE: "#d58924", ROLE_ONLY: "#8568bf", STATIC_CALL: "#64748b", STEP_ORDER: "#4c9ad6", SUPPLIES: "#4c9ad6", CONSUMES_INPUT: "#169c87", PRODUCES_OUTPUT: "#169c87", DELIVERS_TO: "#8568bf" })[edge.kind] || "#8568bf";
  }
  function labelLines(value, width = 25, limit = 3) {
    const words = text(value).replace(/[_/]/g, (value) => value + " ").split(/\s+/);
    const lines = [];
    let line = "";
    for (let word of words) {
      while (word.length > width) {
        if (line) { lines.push(line); line = ""; }
        lines.push(word.slice(0, width)); word = word.slice(width);
      }
      if (line.length + word.length + 1 > width) { lines.push(line); line = word; }
      else line += (line ? " " : "") + word;
    }
    if (line) lines.push(line);
    if (lines.length > limit) return lines.slice(0, limit - 1).concat(lines[limit - 1].slice(0, width - 1) + "…");
    return lines;
  }
  function layoutGraph(nodes, edges) {
    const byId = new Map(nodes.map((node) => [text(node.id), node]));
    const incoming = new Map(nodes.map((node) => [text(node.id), 0]));
    const outgoing = new Map(nodes.map((node) => [text(node.id), []]));
    const levels = new Map(nodes.map((node) => [text(node.id), 0]));
    for (const edge of edges) {
      const [from, to] = edgeEndpoints(edge);
      if (byId.has(from) && byId.has(to)) { incoming.set(to, incoming.get(to) + 1); outgoing.get(from).push(to); }
    }
    const queue = Array.from(incoming).filter((entry) => entry[1] === 0).map((entry) => entry[0]);
    let index = 0;
    while (index < queue.length) {
      const id = queue[index++];
      for (const next of outgoing.get(id)) {
        levels.set(next, Math.max(levels.get(next), levels.get(id) + 1));
        incoming.set(next, incoming.get(next) - 1);
        if (incoming.get(next) === 0) queue.push(next);
      }
    }
    const unresolved = nodes.filter((node) => incoming.get(text(node.id)) > 0);
    const rows = [];
    const processed = new Set(queue);
    const uniqueLevels = Array.from(new Set(queue.map((id) => levels.get(id)))).sort((a, b) => a - b);
    for (const level of uniqueLevels) {
      const layer = nodes.filter((node) => processed.has(text(node.id)) && levels.get(text(node.id)) === level);
      for (let start = 0; start < layer.length; start += 5) rows.push(layer.slice(start, start + 5));
    }
    for (let start = 0; start < unresolved.length; start += 5) rows.push(unresolved.slice(start, start + 5));
    const width = Math.max(660, Math.min(5, Math.max(1, nodes.length)) * 214 + 36);
    const positions = new Map();
    rows.forEach((row, rowIndex) => {
      const total = row.length * 190 + (row.length - 1) * 24;
      row.forEach((node, column) => positions.set(text(node.id), { x: (width - total) / 2 + column * 214, y: 42 + rowIndex * 146, width: 190, height: 90 }));
    });
    return { width, height: Math.max(195, rows.length * 146 + 42), positions, unresolved: unresolved.length };
  }

  function renderDiagram() {
    const target = clear($("diagram-view"));
    const graph = state.graph;
    if (!graph) { target.append(element("p", "UNKNOWN · no canonical graph supplied.", "empty")); return; }
    const allNodes = list(graph.nodes);
    const depth = $("graph-depth").value;
    const nodes = allNodes.filter((node) => depth === "all" || !Number.isFinite(Number(node.depth || node.level)) || Number(node.depth || node.level) <= Number(depth));
    const visibleIds = new Set(nodes.map((node) => text(node.id)));
    const edges = list(graph.edges).filter((edge) => { const [from, to] = edgeEndpoints(edge); return visibleIds.has(from) && visibleIds.has(to); });
    if (!nodes.length) {
      target.append(element("p", "No parsed nodes are supplied for this view. Inspect the Mermaid source or source file.", "empty"));
      $("graph-note").textContent = "Graph source: " + text(graph.source_path);
      return;
    }
    const layout = layoutGraph(nodes, edges);
    const svg = svgElement("svg", { viewBox: `0 0 ${layout.width} ${layout.height}`, width: layout.width, height: layout.height, role: "img", "aria-label": text(graph.label || graph.id) });
    const defs = svgElement("defs");
    const marker = svgElement("marker", { id: "atlas-arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" });
    marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "arrowhead" }));
    defs.append(marker); svg.append(defs);
    for (const edge of edges) {
      const [fromId, toId] = edgeEndpoints(edge);
      const from = layout.positions.get(fromId), to = layout.positions.get(toId);
      if (!from || !to) continue;
      const x1 = from.x + from.width / 2, x2 = to.x + to.width / 2;
      const y1 = from.y + (to.y > from.y ? from.height : 0), y2 = to.y;
      const route = to.y > from.y ? `M ${x1} ${y1} C ${x1} ${y1 + 31} ${x2} ${y2 - 31} ${x2} ${y2}` : `M ${x1} ${y1} C ${x1} ${y1 - 34} ${x2} ${y2 - 34} ${x2} ${y2}`;
      const path = svgElement("path", { d: route, class: "graph-edge" + (isDashed(edge) ? " declared" : ""), "data-from": fromId, "data-to": toId, "marker-end": "url(#atlas-arrow)" });
      path.style.setProperty("--edge-color", edgeColor(edge));
      path.append(svgElement("title", {}, `${fromId} → ${toId} · ${text(edge.kind)} · ${text(edge.binding)}`));
      svg.append(path);
    }
    for (const node of nodes) {
      const id = text(node.id), position = layout.positions.get(id);
      const group = svgElement("g", { class: "graph-node " + nodeRole(node), tabindex: 0, role: "button", "data-node": id, "aria-label": "Inspect " + text(node.label || id), "aria-pressed": id === state.selectedNode ? "true" : "false" });
      group.append(svgElement("rect", { x: position.x, y: position.y, width: position.width, height: position.height, rx: 10 }));
      group.append(svgElement("rect", { x: position.x, y: position.y + 14, width: 3, height: position.height - 28, rx: 1, class: "role-stripe" }));
      const lines = labelLines(node.label || id);
      lines.forEach((line, index) => group.append(svgElement("text", { x: position.x + 13, y: position.y + 24 + index * 16, class: "node-label" }, line)));
      const role = roleLabel(node);
      group.append(svgElement("text", { x: position.x + 13, y: position.y + 77, class: "node-role" }, role.length > 29 ? role.slice(0, 28) + "…" : role));
      group.append(svgElement("title", {}, `${text(node.label || id)}\nID: ${id}\nRole: ${role}\nStatus: ${text(node.status)}`));
      group.addEventListener("click", () => selectNode(id));
      group.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectNode(id); } });
      svg.append(group);
    }
    target.append(svg);
    const dangling = list(graph.edges).filter((edge) => { const [from, to] = edgeEndpoints(edge); return !allNodes.some((node) => text(node.id) === from) || !allNodes.some((node) => text(node.id) === to); }).length;
    $("graph-note").textContent = `${nodes.length} / ${allNodes.length} nodes visible · ${edges.length} visible edges · ${text(graph.kind)}. ` + (layout.unresolved ? `${layout.unresolved} nodes have cyclic or unresolved precedence; their placement follows source order. ` : "Layout follows declared dependency order. ") + (dangling ? `${dangling} edges reference endpoints outside the supplied node set. ` : "") + "Node colour shows role or an explicit blocked state; edges do not establish execution.";
    focusGraph();
  }

  function focusGraph() {
    const id = state.selectedNode;
    const related = new Set(id ? [id] : []);
    if (id && state.graph) {
      for (const edge of list(state.graph.edges)) {
        const [from, to] = edgeEndpoints(edge);
        if (from === id || to === id) { related.add(from); related.add(to); }
      }
    }
    document.querySelectorAll("#diagram-view .graph-node").forEach((node) => {
      node.classList.toggle("selected", node.dataset.node === id);
      node.classList.toggle("dim", Boolean(id) && !related.has(node.dataset.node));
      node.setAttribute("aria-pressed", String(node.dataset.node === id));
    });
    document.querySelectorAll("#diagram-view .graph-edge").forEach((edge) => {
      edge.classList.toggle("emphasis", edge.dataset.from === id || edge.dataset.to === id);
      edge.classList.toggle("dim", Boolean(id) && edge.dataset.from !== id && edge.dataset.to !== id);
    });
  }
  function graphSummary() {
    const target = clear($("graph-inspector"));
    const graph = state.graph;
    target.append(element("h3", graph ? graph.label || graph.id : "Graph inspector"));
    if (!graph) { target.append(element("p", "UNKNOWN · graph inventory unavailable.", "empty")); return; }
    target.append(element("p", text(graph.description || graph.purpose), "fine"), sourceLink(graph));
    if (sourceMap.has(text(graph.source_path))) target.append(button("Inspect source structure", () => selectSource(graph.source_path, true), "small-button"));
    const files = element("div", undefined, "inline-actions");
    const paths = obj(graph.paths);
    const svgFile = artifactLink(paths.svg_light || graph.svg_path, "Light SVG");
    const darkSvgFile = artifactLink(paths.svg_dark, "Dark SVG");
    const mermaidFile = artifactLink(paths.mermaid || graph.mermaid_path, "Mermaid file");
    if (svgFile) files.append(svgFile);
    if (darkSvgFile) files.append(darkSvgFile);
    if (mermaidFile) files.append(mermaidFile);
    if (files.childElementCount) target.append(files);
    target.append(metadata({ graph_id: graph.id, family: graph.kind, parent: graph.parent_id || graph.parent, level: graph.level, nodes: Array.isArray(graph.nodes) ? graph.nodes.length : null, edges: Array.isArray(graph.edges) ? graph.edges.length : null, evidence: graph.evidence_class || graph.binding }));
    target.append(element("p", "Choose a node for its source identity, input/output contract and immediate directional dependencies.", "fine"));
  }
  function selectNode(id) {
    const graph = state.graph;
    if (!graph) return;
    const node = list(graph.nodes).find((node) => text(node.id) === text(id));
    if (!node) return;
    state.selectedNode = text(id);
    const target = clear($("graph-inspector"));
    target.append(element("div", node.id, "eyebrow"), element("h3", node.label || node.id), badge(node.status));
    const block = blockMap.get(text(node.block_id || node.canonical_id || node.id));
    target.append(element("p", node.purpose || node.description || (block && block.purpose)));
    target.append(metadata({ source: node.source_path || (block && block.source_path) || graph.source_path, process: node.role || node.kind || node.type, identity: node.canonical_id || node.id, node: node.id, evidence: node.evidence_class || node.binding || graph.evidence_class }));
    if (node.source_path) target.append(sourceLink(node));
    if (sourceMap.has(text(node.source_path || graph.source_path))) target.append(button("Inspect source structure", () => selectSource(node.source_path || graph.source_path, true), "small-button"));
    if (block) {
      target.append(button("Inspect functional contract", () => { selectBlock(block.id); $("blocks").scrollIntoView({ behavior: "smooth" }); }));
      target.append(contractTable(block.inputs, "Inputs"), contractTable(block.outputs, "Outputs"));
    } else if (node.inputs || node.outputs) target.append(contractTable(node.inputs, "Inputs"), contractTable(node.outputs, "Outputs"));
    const edges = list(graph.edges).filter((edge) => { const [from, to] = edgeEndpoints(edge); return from === state.selectedNode || to === state.selectedNode; });
    target.append(element("h4", "Directional dependencies"));
    const ul = element("ul", undefined, "dependency-list");
    for (const edge of edges) {
      const [from, to] = edgeEndpoints(edge);
      const otherId = from === state.selectedNode ? to : from;
      const other = list(graph.nodes).find((candidate) => text(candidate.id) === otherId);
      const li = element("li");
      li.append(element("small", from === state.selectedNode ? "Produces / precedes →" : "← Requires / follows", "fine"));
      li.append(other ? button(other.label || otherId, () => selectNode(otherId), "text-button") : element("span", otherId));
      li.append(element("span", text(edge.kind) + " · " + text(edge.binding || edge.evidence_class), "fine"));
      if (edge.contract || edge.output || edge.input) li.append(element("span", edge.contract || { output: edge.output, input: edge.input }, "fine"));
      ul.append(li);
    }
    target.append(edges.length ? ul : element("p", "No incident edges supplied for this node.", "fine"));
    focusGraph();
  }
  function mermaid(graph) {
    if (!graph) return "No graph supplied.";
    if (typeof graph.mermaid === "string" && graph.mermaid.trim()) return graph.mermaid;
    const ids = new Map(list(graph.nodes).map((node, index) => [text(node.id), "n" + index]));
    const quote = (value) => text(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/[\r\n]/g, " ");
    const lines = ["flowchart TD", "  %% Generated from source graph IDs; relationships do not establish execution."];
    list(graph.nodes).forEach((node) => lines.push(`  ${ids.get(text(node.id))}["${quote(node.label || node.id)}"]`));
    list(graph.edges).forEach((edge) => {
      const [from, to] = edgeEndpoints(edge);
      if (ids.has(from) && ids.has(to)) lines.push(`  ${ids.get(from)} ${isDashed(edge) ? "-.->" : "-->"} ${ids.get(to)}`);
    });
    return lines.join("\n");
  }
  function graphEdges() {
    const body = clear($("edge-rows"));
    for (const edge of list(state.graph && state.graph.edges)) {
      const [from, to] = edgeEndpoints(edge);
      const row = element("tr");
      row.append(element("td", from), element("td", to), element("td", edge.kind), element("td", edge.binding || edge.evidence_class));
      body.append(row);
    }
    if (!body.childElementCount) { const row = element("tr"); const cell = element("td", "No edge contracts supplied.", "empty"); cell.colSpan = 4; row.append(cell); body.append(row); }
  }
  function chooseGraph(index, scroll = false) {
    state.graph = graphs[index] || null;
    state.selectedNode = null;
    $("graph-select").value = String(index);
    renderDiagram(); graphSummary(); graphEdges();
    $("mermaid-source").textContent = mermaid(state.graph);
    if (scroll) $("execution").scrollIntoView({ behavior: "smooth" });
  }
  function renderCatalog() {
    const query = $("graph-search").value.trim().toLowerCase(), kind = $("graph-kind").value;
    const filtered = graphs.map((graph, index) => ({ graph, index })).filter(({ graph }) => (!query || [graph.id, graph.label, graph.kind, graph.source_path].map((value) => text(value)).join(" ").toLowerCase().includes(query)) && (kind === "all" || text(graph.kind) === kind));
    const maxPage = Math.max(0, Math.ceil(filtered.length / state.pageSize) - 1);
    state.graphPage = Math.min(state.graphPage, maxPage);
    const start = state.graphPage * state.pageSize;
    const body = clear($("catalog-rows"));
    for (const { graph, index } of filtered.slice(start, start + state.pageSize)) {
      const row = element("tr"), name = element("td"), counts = element("td"), action = element("td");
      name.append(element("strong", graph.label || graph.id), sourceLink(graph));
      counts.textContent = (Array.isArray(graph.nodes) ? graph.nodes.length : "UNKNOWN") + " / " + (Array.isArray(graph.edges) ? graph.edges.length : "UNKNOWN");
      action.append(button("Open graph", () => chooseGraph(index, true), "small-button"));
      row.append(name, element("td", graph.kind), element("td", text(graph.parent_id || graph.parent) + " / " + text(graph.level)), counts, action);
      body.append(row);
    }
    if (!filtered.length) { const row = element("tr"); const cell = element("td", "No diagrams match these filters.", "empty"); cell.colSpan = 5; row.append(cell); body.append(row); }
    $("catalog-count").textContent = `${filtered.length} / ${graphs.length} diagram records · topology counts retain their original graph boundaries.`;
    $("graph-page").textContent = filtered.length ? `${start + 1}–${Math.min(start + state.pageSize, filtered.length)} of ${filtered.length}` : "0 results";
    $("previous-graphs").disabled = state.graphPage === 0;
    $("next-graphs").disabled = state.graphPage === maxPage;
  }
  async function copyText(value) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(value);
      else {
        const area = element("textarea", value);
        area.className = "clipboard-fallback";
        document.body.append(area); area.select();
        const copied = document.execCommand("copy"); area.remove();
        if (!copied) throw new Error("clipboard unavailable");
      }
      $("copy-status").textContent = "Copied to clipboard.";
      return true;
    } catch (_error) { $("copy-status").textContent = "Clipboard is unavailable here. Select the visible source text to copy it."; return false; }
  }
  function download(content, name, mime) {
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const anchor = element("a"); anchor.href = url; anchor.download = name;
    document.body.append(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const systemTheme = window.matchMedia("(prefers-color-scheme: light)");
  let themePreference = "system";
  function theme(value, persist = true) {
    themePreference = ["system", "light", "dark"].includes(value) ? value : "system";
    document.documentElement.dataset.themeMode = themePreference;
    document.documentElement.dataset.theme = themePreference === "system" ? (systemTheme.matches ? "light" : "dark") : themePreference;
    $("theme-mode").value = themePreference;
    if (persist) {
      try { localStorage.setItem("method-atlas-theme", themePreference); } catch (_error) { /* file/preview storage may be unavailable */ }
    }
  }
  let savedTheme;
  try { savedTheme = localStorage.getItem("method-atlas-theme"); } catch (_error) { savedTheme = null; }
  theme(savedTheme || "system", false);
  systemTheme.addEventListener("change", () => { if (themePreference === "system") theme("system", false); });
  $("theme-mode").addEventListener("change", () => theme($("theme-mode").value));
  const tags = Array.from(new Set(blocks.flatMap((block) => list(block.programmes).map((value) => text(value))))).sort();
  addOptions($("programme-filter"), tags.map((tag) => [tag, programmeLabel(tag)]));
  addOptions($("role-filter"), Array.from(new Set(blocks.map((block) => text(block.role)))).sort().map((role) => [role, role]));
  addOptions($("graph-kind"), Array.from(new Set(graphs.map((graph) => text(graph.kind)))).sort().map((kind) => [kind, kind]));
  addOptions($("graph-select"), graphs.map((graph, index) => [String(index), text(graph.label || graph.id) + " · " + text(graph.kind)]));
  addOptions($("coverage-repository"), Array.from(new Set(coverageRows.map((row) => text(row.repository)))).sort().map((value) => [value, value]));
  addOptions($("coverage-kind"), Array.from(new Set(coverageRows.map((row) => text(row.observation_kind)))).sort().map((value) => [value, value]));
  $("graph-count").textContent = graphs.length + " source graph records";
  ["block-search", "programme-filter", "role-filter"].forEach((id) => $(id).addEventListener(id === "block-search" ? "input" : "change", () => { state.page = 0; renderBlocks(); }));
  $("reset-filters").addEventListener("click", () => { $("block-search").value = ""; $("programme-filter").value = "all"; $("role-filter").value = "all"; state.page = 0; renderBlocks(); });
  $("previous-blocks").addEventListener("click", () => { state.page -= 1; renderBlocks(); });
  $("next-blocks").addEventListener("click", () => { state.page += 1; renderBlocks(); });
  $("graph-search").addEventListener("input", () => { state.graphPage = 0; renderCatalog(); });
  $("graph-kind").addEventListener("change", () => { state.graphPage = 0; renderCatalog(); });
  $("previous-graphs").addEventListener("click", () => { state.graphPage -= 1; renderCatalog(); });
  $("next-graphs").addEventListener("click", () => { state.graphPage += 1; renderCatalog(); });
  $("source-search").addEventListener("input", () => { state.sourcePage = 0; renderSources(); });
  $("source-kind").addEventListener("change", () => { state.sourcePage = 0; renderSources(); });
  $("previous-sources").addEventListener("click", () => { state.sourcePage -= 1; renderSources(); });
  $("next-sources").addEventListener("click", () => { state.sourcePage += 1; renderSources(); });
  $("coverage-repository").addEventListener("change", filterCoverage);
  $("coverage-kind").addEventListener("change", filterCoverage);
  document.querySelectorAll(".inspect-coverage").forEach((control) => control.addEventListener("click", () => selectCoverage(Number(control.dataset.index))));
  $("graph-select").addEventListener("change", () => chooseGraph(Number($("graph-select").value)));
  $("graph-depth").addEventListener("change", renderDiagram);
  $("clear-focus").addEventListener("click", () => { state.selectedNode = null; focusGraph(); graphSummary(); });
  document.querySelectorAll("[data-view]").forEach((control) => control.addEventListener("click", () => {
    state.view = control.dataset.view;
    ["diagram", "mermaid", "edges"].forEach((view) => $(view + "-view").hidden = view !== state.view);
    document.querySelectorAll("[data-view]").forEach((item) => item.setAttribute("aria-pressed", String(item.dataset.view === state.view)));
  }));
  $("copy-mermaid").addEventListener("click", async () => {
    const copied = await copyText(mermaid(state.graph));
    $("copy-mermaid").textContent = copied ? "Copied" : "Select text below";
  });
  $("download-mermaid").addEventListener("click", () => download(mermaid(state.graph) + "\n", text(state.graph && state.graph.id, "atlas").replace(/[^a-z0-9_-]/gi, "_") + ".mmd", "text/plain"));
  document.querySelectorAll(".copy-command").forEach((control) => control.addEventListener("click", async () => {
    const copied = await copyText($(control.dataset.command).textContent);
    control.textContent = copied ? "Copied" : "Select text below";
  }));
  $("download-model").addEventListener("click", () => download(JSON.stringify(model, null, 2) + "\n", "method-atlas-source-model.json", "application/json"));
  renderBlocks(); renderSources(); renderCatalog(); filterCoverage(); chooseGraph(0);
  document.documentElement.dataset.atlasReady = "true";
}());
