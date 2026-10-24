"use strict";
/* Read-only; data.js is produced exclusively by tools/build_gate12_dov.py. */
(function () {
  const d = window.JADE_GATE12;
  const byId = id => document.getElementById(id);
  const create = (tag, cls, message) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (message !== undefined && message !== null) n.textContent = String(message);
    return n;
  };
  const attach = (target, ...nodes) => nodes.forEach(node => target.appendChild(node));
  const safeLink = (url, text) => {
    if (typeof url !== "string" ||
        !(url.startsWith("https://github.com/") || /^[a-z0-9][a-z0-9_.-]*$/.test(url))) {
      return create("span", "muted", text || "Not qualified");
    }
    const a = create("a", "", text || "Evidence");
    a.href = url;
    if (url.startsWith("https://")) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    return a;
  };
  const chip = (status, title) => create("span", "chip " + status, title || status);
  const format = x => String(x).replaceAll("_", " ");
  if (!d || d.schema !== "jade.temple.gate12.dov_projection.v1" ||
      !d.metrics || d.authority.merge_admission !== "HOLD" ||
      d.authority.formal_release_credit !== 0) {
    byId("source-warning").textContent =
      "JADE source/projection missing or unsafe. Run the source-bound generator; no gate is qualified.";
    return;
  }
  byId("readback-date").textContent = "FROZEN NON-ATOMIC · " + d.source.observed_date;
  const m = d.metrics;
  const scores = [
    [m.observed_repositories + "/" + m.top21_repositories, "Observed repos", "16 not qualified on this snapshot"],
    [m.observed_pass + "/" + m.observed_gate_denominator, "Historical gate PASS", "Only five-repo observed denominator"],
    [m.observed_fail + "/" + m.observed_gate_denominator, "Observed FAIL", "Failures do not disappear in aggregate"],
    [m.unassessed_gate_slots, "Unassessed gate slots", "16 unassessed repositories × 12"],
    ["HOLD", "Owner release", "No deployed or hosted status inferred"]
  ];
  for (const [value, label, sub] of scores) {
    const card = create("article", "kpi");
    attach(card, create("b", "", value), create("span", "", label), create("small", "", sub));
    byId("scoreboard").appendChild(card);
  }
  const facetMap = new Map();
  for (const p of d.pillars) {
    const card = create("article", "pillar");
    const heading = create("header");
    attach(heading, create("span", "gate-id", p.id),
           create("span", "minor", p.phase + " / " + p.facet + " / " + p.priority));
    attach(card, heading, create("h3", "", p.label));
    const s = create("div", "numbers");
    attach(s, create("span", "dot-pass", p.observed_counts.PASS + " PASS"),
           create("span", "dot-fail", p.observed_counts.FAIL + " FAIL"),
           create("span", "dot-unknown", p.observed_counts.UNKNOWN + " UNKNOWN"),
           create("span", "dot-unobserved", p.unassessed_repos + " unassessed"));
    attach(card, s, create("p", "", "Threshold proposal: " + p.threshold));
    const more = create("details");
    const summary = create("summary", "", "Read acceptance criteria and next action");
    attach(more, summary);
    const paragraphs = [
      ["Quality", p.quality], ["Owner", p.owner], ["Next action", p.action],
      ["Required proof", p.proof], ["Prerequisites", p.prerequisites.join(", ") || "Source gate"]
    ];
    paragraphs.forEach(([key, value]) => {
      const node = create("p");
      const strong = create("strong", "", key + ": ");
      attach(node, strong, document.createTextNode(value));
      more.appendChild(node);
    });
    card.appendChild(more);
    byId("pillar-grid").appendChild(card);
    if (!facetMap.has(p.facet)) facetMap.set(p.facet, []);
    facetMap.get(p.facet).push(p.id);
    const opt = create("option", "", p.id + " " + p.label);
    opt.value = p.id;
    byId("q-gate").appendChild(opt);
  }
  for (const [facet, gates] of facetMap.entries()) {
    const card = create("article", "facet");
    attach(card, create("h3", "", format(facet)),
           create("p", "", gates.length + " acceptance pillars; each retains independent proof."),
           create("div", "facet-pills", gates.join(" · ")));
    byId("quality-axes").appendChild(card);
  }
  const pri = {FIRST_RED: 0, READY: 1, WAIT_DEPENDENCY: 2, COMPLETE: 3};
  const ordered = d.queue.slice().sort((a, b) =>
    pri[a.readiness] - pri[b.readiness] || a.rank - b.rank ||
    a.pillar.localeCompare(b.pillar));
  const tbody = byId("q-body");
  const search = byId("q-search"), status = byId("q-status");
  const frontier = byId("q-frontier"), gate = byId("q-gate");
  const renderQueue = () => {
    const needle = search.value.trim().toLowerCase();
    const rows = ordered.filter(t =>
      (status.value === "ALL" || t.status === status.value) &&
      (frontier.value === "ALL" || t.readiness === frontier.value) &&
      (gate.value === "ALL" || t.pillar === gate.value) &&
      (needle === "" || [t.repository, t.pillar, t.owner, t.action, t.blocked_by]
        .join(" ").toLowerCase().includes(needle)));
    tbody.replaceChildren();
    const fragment = document.createDocumentFragment();
    rows.forEach(t => {
      const tr = create("tr"), td1 = create("td"), td2 = create("td", "code", t.pillar);
      const td3 = create("td"), td4 = create("td"), td5 = create("td"), td6 = create("td");
      attach(td1, create("strong", "", t.rank + " / " + t.repository));
      if (t.source_sha) attach(td1, create("div", "minor", t.source_sha.slice(0, 12)));
      else attach(td1, create("div", "minor", "No exact-head gate readback"));
      td3.appendChild(chip(t.status));
      attach(td4, chip(t.readiness), create("div", "minor", t.blocked_by || "No prerequisite veto"));
      attach(td5, create("strong", "", t.owner), create("div", "minor", t.action));
      td6.appendChild(safeLink(t.evidence, t.evidence ? "Source proof ↗" : "Unqualified"));
      attach(tr, td1, td2, td3, td4, td5, td6);
      fragment.appendChild(tr);
    });
    tbody.appendChild(fragment);
    byId("q-count").textContent = rows.length + " of " + d.queue.length +
      " gate rows shown · FIRST_RED/READY is a dependency frontier, not merge authorization";
  };
  [search, status, frontier, gate].forEach(n => n.addEventListener(
    n.tagName === "INPUT" ? "input" : "change", renderQueue));
  renderQueue();
  const operational = [
    ["Authored source", d.publication.source_authored],
    ["Static QA", d.publication.static_qa],
    ["Browser QA", d.publication.browser_qa],
    ["Single Pages staging", d.publication.staged_single_publisher],
    ["Deployment", d.publication.deployed],
    ["Hosted HTTP 200", d.publication.hosted_http_200],
    ["Served SHA parity", d.publication.served_sha_matches],
    ["Operational runtime health", d.publication.operational_health],
    ["Rollback drill", d.publication.rollback_drill],
    ["Owner release", d.publication.owner_release]
  ];
  for (const [name, state] of operational) {
    const article = create("article");
    attach(article, create("h3", "", name),
           create("strong", "", state === null ? "UNKNOWN / NOT PROVEN" : state),
           create("p", "", state === null ? "A source-matched native or owner receipt is required." :
             "This state is a source declaration, not hosted evidence."));
    byId("publication-status").appendChild(article);
  }
  d.acceptance_ladder.forEach((step, i) => {
    const li = create("li");
    attach(li, create("span", "n", String(i + 1).padStart(2, "0")),
           document.createTextNode(format(step)));
    byId("acceptance-ladder").appendChild(li);
  });
  d.assets.forEach(a => {
    const card = create("article", "asset");
    attach(card, safeLink(a.path, a.title + " ↗"),
           create("small", "", format(a.kind) + " / repository candidate"),
           create("small", "", "Hosted Pages: " + a.hosted_status));
    byId("asset-grid").appendChild(card);
  });
  for (const [name, oid] of Object.entries(d.source.git_blob_oids)) {
    const row = create("div");
    attach(row, create("dt", "", name), create("dd", "", oid));
    byId("source-oids").appendChild(row);
  }
})();
