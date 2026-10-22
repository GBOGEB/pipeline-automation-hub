# MissionControl Makeover — W1 P1 source-bound architecture

Moniker: `MC.MAKEOVER.G3P(N,N+3)`. This is a ChatGPT instruction, not a runner command or background scheduler.

Canonical source authority remains the **MissionControl v2 operating model** and **CODEX Mycelium** for its own control/gateway; this launchpad is only a read-only navigation and diagram projection. Source snapshot is date-only, pinned/non-atomic. Native worker count, active dispatch, live queue latency, proof yield, accepted N, hosted HTTP and Six Sigma are **UNKNOWN**, never inferred.

## Source order
1. [MC v2 pointer](../v2/MISSION_CONTROL_CURRENT_v2.json), [official mission register](../OFFICIAL_MISSION_REGISTER_v1.yaml), [MC status](../v2/MC_MISSION_STATUS_CURRENT_v1.json).
2. [Canonical root/BD register](../federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json), [federation ATLAS graph](../federation-atlas/ATLAS_GRAPH_v1.yaml) and [SIPOC lanes](../federation-atlas/PROCESS_LANES_v1.json).
3. [CODEX Mycelium](https://github.com/GBOGEB/CODEX/blob/f8a179f8bf67bba4264364b5742c7c271f4041a6/mission_control/mycelium/control_manifest.yaml) and [execution gateway](https://github.com/GBOGEB/CODEX/blob/f8a179f8bf67bba4264364b5742c7c271f4041a6/mission_control/mycelium/execution_gateway_contract.yaml) — STAGE_ONLY, mutation disabled, remote mutation disallowed.
4. This versioned registry `MISSIONCONTROL_NAV_SOURCES_v1.json` (metadata-only) is the view's input crosswalk, not a second truth or a worker scheduler.

## G3P wave / disjoint file ownership
- **P1 / Graph crew**: `mission-control/launchpad/MISSIONCONTROL_NAV_SOURCES_v1.json`, `nav_model.py`, tests and generated DAG/SIPOC. Source and graph invariants.
- **P2 / HMI crew**: `mission-control/launchpad/launchpad_template.html`, `render_launchpad.py`, client QA. Accessible searchable/filterable repo launch and multi-panel graph. Consumes P1 output.
- **P3 / Publication/QA crew**: existing `federation-atlas/pages_portal.py` + native `.github/workflows` + browser QA. Only the existing Pages publisher may package the generated view.

P2 depends on P1, P3 depends on P2. **Distinct paths do not imply concurrent source ancestry, native runner allocation or independent human review.** Disjoint changes are stacked and admitted serially. Do not claim parallel Actions dispatch without job/run evidence.

## Graph semantics and scheduling
- Universal graph contains evidence, declared intended routes, and next-pulse feedback. It may contain cycles.
- Executable dependency projection uses only typed `DEPENDS_ON` edges and is validated acyclic; it does not grant executor permission.
- `RECEIPT` edges refer to *historical source-owned run evidence* in `ATLAS_GRAPH_v1.yaml`. They are not fresh current-head CI or source authorization.
- Scheduler board maps EXECUTE_NOW / PROVE / RETURN / CONTROL / READ / HOLD from #372. One source repair and one proof WIP lease per repository, *advisory only*.
- Workers are logical roles. Active crew count, queue p95, dispatched-run count remain null.
- Release / Pages / engineering / security gates remain non-compensating; HTML is a materialized view.

## DoV
`python mission-control/launchpad/nav_model.py --out /tmp/mc-nav`;
`python -m unittest discover -s mission-control/launchpad -p 'test_nav_model.py' -v`.
Native exact SHA job ID/attempt and source hash are required for acceptance. Never infer a published URL from committed HTML.
