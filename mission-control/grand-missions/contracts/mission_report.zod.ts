import { z } from "zod";

export const ObservationClass = z.enum(["OBSERVED", "INFERRED", "PROPOSED"]);
export const EvidenceClass = z.enum([
  "EXACT_SHA_RUNTIME",
  "EXACT_SHA_SOURCE",
  "REPO_METADATA",
  "SEMANTIC_READ",
  "REFERENCE_ONLY",
]);

export const BreadthLevel = z.enum(["B0", "B1", "B2", "B3", "B4", "B5", "B6"]);
export const PenetrationLevel = z.enum(["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]);
export const RuntimeLevel = z.enum(["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"]);

export const LineageRelationship = z.enum([
  "PARENT_OF", "CHILD_OF", "CONTAINS", "DERIVED_FROM", "DEPENDS_ON", "BLOCKS",
  "IMPLEMENTS", "VERIFIES", "SUPERSEDES", "REVERTS", "MERGES", "BRANCHED_FROM",
  "PR_FOR", "COMMIT_IN", "EVIDENCE_FOR", "CREW_ASSIGNED_TO", "REX_LEARNED_FROM", "CROSS_FEEDS",
]);

export const LineageNode = z.object({
  id: z.string().min(1),
  type: z.enum(["MISSION", "REPO", "SUBREPO", "WORK_PACKAGE", "TASK", "CREW", "EVIDENCE", "COMMIT", "PR", "BRANCH", "REX", "GRAPH_NODE"]),
  state: z.string().min(1),
  authority: z.string().min(1),
  evidence_class: EvidenceClass,
  observed_at: z.string().min(1),
  parent_ids: z.array(z.string()).default([]),
  child_ids: z.array(z.string()).default([]),
  current_or_superseded: z.enum(["CURRENT", "SUPERSEDED"]).default("CURRENT"),
});

export const LineageEdge = z.object({
  parent_id: z.string().min(1),
  child_id: z.string().min(1),
  relationship: LineageRelationship,
  observation_class: ObservationClass,
  source_ref: z.string().min(1),
  authority_inherited: z.literal(false).default(false),
});

export const CrewDepth = z.object({
  crew_id: z.string().min(1),
  roles: z.array(z.string()).min(1),
  role_depth: z.number().min(0).max(1),
  repo_familiarity: z.number().min(0).max(1),
  mission_familiarity: z.number().min(0).max(1),
  runtime_proof_depth: z.number().min(0).max(1),
  evidence_depth: z.number().min(0).max(1),
  rex_depth: z.number().min(0).max(1),
  cross_mission_depth: z.number().min(0).max(1),
  tool_readiness: z.number().min(0).max(1),
  availability: z.number().min(0).max(1),
  effective_capacity: z.number().min(0),
  last_evidence_sha: z.string().nullable(),
  score_basis: z.enum(["OBSERVED", "EXPERT_SEEDED", "MIXED"]),
});

export const MissionReport = z.object({
  mission_id: z.string().min(1),
  mission_name: z.string().min(1),
  parent_mission_id: z.string().nullable(),
  child_mission_ids: z.array(z.string()).default([]),
  state: z.string().min(1),
  lifecycle_stage: z.string().min(1),
  authority_owner: z.string().min(1),
  report_sha: z.string().min(7),
  as_of: z.string().min(1),
  breadth_level_B: BreadthLevel,
  breadth_fraction_b: z.number().min(0).max(1),
  penetration_level_P: PenetrationLevel,
  depth_fraction_d: z.number().min(0).max(1),
  Pen_bxd: z.number().min(0).max(1),
  runtime_level_R: RuntimeLevel,
  runtime_paths_proven: z.number().int().nonnegative(),
  nodes: z.number().int().nonnegative(),
  edges: z.number().int().nonnegative(),
  atoms_or_modules: z.number().int().nonnegative(),
  crew: z.array(CrewDepth),
  team_effective_worker_capacity: z.number().min(0),
  mission_pressure: z.number().min(0),
  reinforcement_need: z.number().min(0),
  rex_in: z.array(z.string()),
  rex_learned: z.array(z.string()),
  rex_generated: z.array(z.string()),
  historian: z.object({
    commit_history_read: z.boolean(),
    pr_history_read: z.boolean(),
    lineage_decomposed: z.boolean(),
    commits_examined: z.number().int().nonnegative(),
    prs_examined: z.number().int().nonnegative(),
    reversions_or_supersessions: z.number().int().nonnegative(),
    unresolved_lineage_edges: z.number().int().nonnegative(),
  }),
  lineage_nodes: z.array(LineageNode),
  lineage_edges: z.array(LineageEdge),
  DoV_state: z.string().min(1),
  DoD_state: z.string().min(1),
  first_red: z.string().nullable(),
  next_bounded_action: z.string().min(1),
}).superRefine((r, ctx) => {
  const expectedPen = r.breadth_fraction_b * r.depth_fraction_d;
  if (Math.abs(r.Pen_bxd - expectedPen) > 1e-6) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["Pen_bxd"], message: "Pen_bxd must equal breadth_fraction_b * depth_fraction_d" });
  }
  if (r.runtime_level_R !== "R0" && r.runtime_paths_proven === 0 && !["R1", "R2"].includes(r.runtime_level_R)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["runtime_paths_proven"], message: "R3+ requires at least one proven runtime path" });
  }
});

export type MissionReportContract = z.infer<typeof MissionReport>;
