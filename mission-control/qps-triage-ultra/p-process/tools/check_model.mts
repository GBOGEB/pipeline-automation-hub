// Referential-integrity check for the Code Purple model (TypeScript, run with Node >= 22.18
// type stripping:  node tools/check_model.mts  ·  type-check:  tsc -p tsconfig.json).
// Exit 1 with one line per problem; prints a JSON summary on success.
import { createRequire } from "node:module";
import type { CodePurpleModel, CPNode } from "../types/code-purple-model.d.ts";

const require = createRequire(import.meta.url);
const M = require(process.env.CP_MODEL_JS ?? "../code-purple/assets/model.js") as CodePurpleModel;

export function checkModel(m: CodePurpleModel): string[] {
  const errs: string[] = [];
  const ids = new Set<string>();
  const dup = (kind: string, id: string): void => {
    if (ids.has(id)) errs.push(`duplicate ${kind} id ${id}`);
    ids.add(id);
  };
  const nodes = new Map<string, CPNode>();
  for (const n of m.NODES) {
    dup("node", n.id);
    nodes.set(n.id, n);
    if (!/^N\d{2}$/.test(n.id)) errs.push(`node id ${n.id} is not Nnn`);
    if (!(n.kind in m.KIND)) errs.push(`${n.id}: unknown kind ${n.kind}`);
    if (!(n.phase in m.PH)) errs.push(`${n.id}: unknown phase ${n.phase}`);
    if (!(n.lane in m.LANE)) errs.push(`${n.id}: unknown lane ${n.lane}`);
    if (!(n.status in m.STATUS)) errs.push(`${n.id}: unknown status ${n.status}`);
    if (!n.actions?.length) errs.push(`${n.id}: no actions (hover card would be empty)`);
  }
  for (const e of m.EDGES) {
    dup("edge", e.id);
    if (!nodes.has(e.f)) errs.push(`${e.id}: from ${e.f} is not a node`);
    if (!nodes.has(e.t)) errs.push(`${e.id}: to ${e.t} is not a node`);
    if (!(e.k in m.EKIND)) errs.push(`${e.id}: unknown edge kind ${e.k}`);
  }
  const states = new Set(m.LSTATES.map(s => s.id));
  for (const t of m.TRIGGERS) {
    dup("trigger", t.id);
    if (!states.has(t.f)) errs.push(`${t.id}: from ${t.f} is not a lifecycle state`);
    if (!states.has(t.t)) errs.push(`${t.id}: to ${t.t} is not a lifecycle state`);
    if (!(t.w in m.WIRED)) errs.push(`${t.id}: unknown wiring ${t.w}`);
    for (const n of t.nodes) if (!nodes.has(n)) errs.push(`${t.id}: node ${n} missing`);
  }
  m.STAGES.forEach((s, i) => {
    if (s.n !== i + 1) errs.push(`stage ${s.name}: number ${s.n}, expected ${i + 1}`);
    for (const n of s.nodes) if (!nodes.has(n)) errs.push(`stage ${s.n}: node ${n} missing`);
  });
  const staged = new Set(m.STAGES.flatMap(s => s.nodes));
  for (const n of nodes.keys()) if (!staged.has(n)) errs.push(`${n} belongs to no stage`);
  return errs;
}

const errs = checkModel(M);
if (errs.length) {
  console.error(errs.join("\n"));
  process.exit(1);
}
console.log(JSON.stringify({ ok: true, nodes: M.NODES.length, edges: M.EDGES.length, stages: M.STAGES.length, triggers: M.TRIGGERS.length, states: M.LSTATES.length }));
