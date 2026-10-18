// Types for code-purple/assets/model.js (the single Code Purple model used by the page,
// the 16:9 deck builder and tools/check_model.ts). Keep in step with model.js.

export type Phase = "D" | "M" | "A" | "I" | "C";
export type NodeKind = "auth" | "proc" | "dec" | "rep" | "pass" | "hold" | "evid";
export type LaneId = "spine" | "ev" | "rep";
export type StatusId = "ok" | "progress" | "hold" | "partial" | "todo" | "none";
export type EdgeKind = "flow" | "yes" | "fail" | "hold" | "evid" | "rec";
export type WiredId = "wired" | "partial" | "manual" | "proposed";

/** Process node N01..Nnn on the execution pulse. */
export interface CPNode {
  id: string;
  label: string;
  sub?: string[];
  kind: NodeKind;
  phase: Phase;
  lane: LaneId;
  status: StatusId;
  owner: string;
  artefact: string;
  does: string;
  evidence: string;
  state: string;
  actions: string[];
  chips?: string[];
  note?: string;
  receipt?: boolean;
  lines?: string[];
  shape?: string;
  x?: number; y?: number; w?: number; h?: number;
  cx?: number; cy?: number; hw?: number; hh?: number; ty?: number;
}

/** Directed edge E01..Enn between two nodes. */
export interface CPEdge {
  id: string;
  f: string;
  t: string;
  k: EdgeKind;
  d: string;
  m: string;
  lab?: string[];
  lx?: number; ly?: number; rot?: number;
}

/** Numbered process stage (big purple numerals in page and deck). */
export interface CPStage {
  n: number;
  name: string;
  ph: Phase;
  nodes: string[];
  entry: string[];
  acts: string[];
  exit: string[];
}

/** Lifecycle state (Test pending, Setup, Debug, ... Merged). */
export interface CPLifecycleState {
  id: string;
  label: string;
  sub: string;
  k: string;
  x: number;
  y: number;
}

/** Lifecycle trigger T01..Tnn: one event, one guard, one action. */
export interface CPTrigger {
  id: string;
  f: string;
  t: string;
  k: EdgeKind;
  d: string;
  ev: string;
  guard: string;
  act: string;
  nodes: string[];
  w: WiredId;
  wn: string;
  lab?: string;
  lx?: number; ly?: number;
}

export interface CPTelemetry {
  schema: "code-purple.census/v1";
  source: "recorded" | "example" | string;
  iteration: number;
  generated_at: string;
  vcs: Record<string, string | null>;
  runtime: Record<string, string>;
  rex: unknown;
  nodes: Record<string, unknown>;
}

export interface CodePurpleModel {
  PH: Record<Phase, string>;
  KIND: Record<NodeKind, string>;
  LANE: Record<LaneId, string>;
  STATUS: Record<StatusId, string>;
  EKIND: Record<EdgeKind, string>;
  NODES: CPNode[];
  EDGES: CPEdge[];
  STAGES: CPStage[];
  LSTATES: CPLifecycleState[];
  TRIGGERS: CPTrigger[];
  WIRED: Record<WiredId, string>;
  TEL_RECORDED: CPTelemetry;
  TEL_EXAMPLE: CPTelemetry;
}

/** kit/census.json written by kit/readback.py (lift status consumed by the page and decks). */
export interface LiftCriterion { id: string; text: string; ok: boolean; evidence: string }
export interface Census {
  generated_at: string;
  lifted: boolean;
  lift: LiftCriterion[];
  merges_since_unblock?: number;
  repos: Record<string, { open_prs: number; nightly?: { reds: string[] } } & Record<string, unknown>>;
  prs?: Array<{ repo: string; number: number; role: string; merged: boolean; state: string }>;
  admission_audit?: { merged: number; gate_green: number; ungated: number; with_red_checks: number };
}
