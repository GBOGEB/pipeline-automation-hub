# CODE PURPLE W+4 — SPINE / authority DAG / SIPOC / telemetry

**Purpose:** a separately navigable **architecture & governance control plane** alongside the G3C statistics, with explicit owners, legal transitions, telemetry transport and MYCELIUM handoff. This is a *read-only projection*, **not** a new Mission Control SSOT, CODEX SPINE-core, CODEX Mycelium control manifest, engineering-acceptance authority, or a dispatcher.

## 1. Canonical and candidate boundary

| Architecture concern | Canonical owner/source | W+4 consumer |
|---|---|---|
| Mission process, statuses, leases | Hub `mission-control/v2/MISSION_CONTROL_CURRENT_v2.json` | Control process labels, no replacements |
| Ten-beam graph / declared dependencies | Hub `mission-control/federation-atlas/CODE_PURPLE_BEAMS_DAG_v1.json` | Separate owner/admission *control-view*, not 11th canonical beam |
| Owner rule configuration | Hub `governance/branch_protection/policy.json` and live GitHub rulesets | Explicit admin-gate nodes, control-class HOLD |
| MYCELIUM receiver & typed graph | CODEX `mission_control/mycelium/control_manifest.yaml` | Distinct consumer node; acceptance WITHHELD |
| CODEX ADR-0002 SPINE-core | `governance/adr/ADR-0002-spine-core-public-backbone.md` (proposed) | References only: this W+4 deliverable is *not* SPINE-core publication |
| Coverage/statistical method | G3C #708 + gg_MATH separately governed | Telemetry consumers only, no causal/status promotion |
| QPS engineering truth | cryoplant-project engineering SSOT | No source mutations/acceptance |

## 2. Control SPINE and DAG

The generated `spine-control.mmd`, `spine-control.svg` and `spine-control.html` capture **20 nodes / 21 within-pulse directed dependency edges / 3 explicitly NEXT-PULSE feedback edges**. The feedforward graph is topologically sorted and stage monotonic; feedback is drawn dotted in Mermaid and never counted as a current-pulse dependency.

The independent strands are:

- **ABACUS owner:** effective reviewed rule #24494381 → failed RED canary → fresh control census. Historically the active rule permits 0 approvals, lacks mandatory CI, has six bypass actors. Owner/admin only.
- **Hub owner:** effective reviewed default rules + rejected RED canary + exact PR-head CI + independently eligible human approval → legal admission → main SHA run → controlled publication. Hub #336 remains blocked (master unprotected, #25252917 empty branch filter).
- **CODEX producer:** source repair #1093 → exact-head CI → owner protections plus independent review → legal admission → current-main proof → typed MYCELIUM reception. A consumer green test alone does not grant receiver ACCEPT or engineering truth.
- **Measurement:** six-repo CENSUS, source/job/attempt/receipt custody, first-red displacement, dedup roots → G3C/gg_MATH qualified analysis. Analysis never feeds a shortcut to the merge node. Only an N+1 feedback edge may seed another source repair.
- **Publication:** a review view requires matching source digest, post-main terminal CI and browser/asset QA; published HTML cannot change source-owned engineering truth.

## 3. Separate SIPOC

`spine-sipoc.md` binds six non-overlapping supplier/customer process contracts: owner protection, source repair, proof custody, typed federation, analytics, and controlled release. The SIPOC is intentionally **not** a statistical widget: it tells an operator *who supplies what evidence, what process is permitted, what output is controlled, and who may accept it*.

## 4. Telemetry contract (independent from governance)

Mandatory source identity: `repository, branch, source_sha, run_id, attempt, job_id, artifact_sha256, observed_at_utc`. Keep manifest failure occurrences distinct from independent causal roots and GitHub issue closures. A historical native green check is not a current-head receipt; missing jobs are UNKNOWN/QUEUED, not zero. Current counts in the frozen sample: 6 repositories inspected, 0 qualified owner controls, 0 accepted issue closures.

Track `first_red_manifestations, deduplicated_causal_roots, eligible_issue_closures, governed_merge_admissions, queue_p95_seconds, native_proof_yield, matched_coverage_(numerator|denominator), source_freshness` separately. Full-fleet worker hours, stable process capability, PCA/BT evidence and Six Sigma are **unsupported** until provider-designed comparable independent samples exist.

## 5. Separate admission route, DoD and DoV

Owner action: ABACUS #1860 and hub #336 administrator restores controls in the existing repo policy method; negative merge canary proves RED blocked, independently approved GREEN receives actual required checks. **Do not put a personal/repo admin token in Actions or bypass protections to prove the model.**

Source action: CODEX #1093 at `ae0913fbb6e2...` awaits fresh Mycelium/W003; hub current-main W2 & CP.CLOSE await terminal jobs; G3C #708 source changed beyond its prior green `a2af1b...`. Only native exact-head terminal results (and eligible approvals) enable progression. No merges/issue closures are authorized by this view.

Build locally, using Python standard library only:

```sh
python -m unittest discover -s mission-control/v2/spine_w4 -p test_spine_control.py -v
python mission-control/v2/spine_w4/spine_control.py --contract mission-control/v2/spine_w4/control_view.json --out /tmp/w4-spine
```

CI workflow: `.github/workflows/mission-control-w4-spine.yml` (Python 3.11 + 3.12, exact checkout and 19 negative/positive methods). It produces `spine-control.json`, `spine-control.html`, `spine-control.svg`, `spine-control.mmd`, `spine-sipoc.md`, and SHA-256 `manifest.json`. Native source/view QA is *not* authority to alter rulesets, merge a PR, close issues, declare B0/coverage improvement or accept QPS.

Visual QA requires desktop 1440×1000, laptop 1280×800 and mobile 390×844; check zero console/page errors, bounded horizontal body overflow (intentional graph-container horizontal pan permitted), SVG legibility, head/source digest and SIPOC table. Do not claim this browser test executed until a real browser receipt exists.

## 6. Next legal routing

`OWNER_CONTROL → RED_CANARY → PR_NATIVE_CI ∧ ELIGIBLE_REVIEW → GOVERNED_ADMISSION → MAIN_SHA_NATIVE_CI → TELEMETRY/REX → PUBLICATION`. CODEX MYCELIUM owner acceptance is a separate `DEFER / REJECT / ACCEPT` consumer disposition after typed artifact parity; remote dispatch and engineering compliance stay blocked.

**Current: OWNER_GATES_RED, ADMISSION=HOLD, ROOT_CLOSURES_CREDIT=0, SIX_SIGMA=NOT_QUALIFIED.**
