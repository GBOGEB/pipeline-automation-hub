# MISSION CONTROL — federated SIPOC (read-only)

Input authority: source-owned GitHub. No engineering, release or merge credit.

| Stage | Evidence and process boundary | Canonical origin |
|---|---|---|
| S · Suppliers | Repository owners, immutable Git source, CODEX gate, gg_MATH methods | `mission-control/OFFICIAL_MISSION_REGISTER_v1.yaml` |
| I · Inputs | Exact source SHAs, authenticated native CI receipts, canonical root IDs, authorized path leases | `mission-control/v2/MC_MISSION_TELEMETRY_CONTRACT_v1.json` |
| P · Process | Discover → Classify → Stage proposal → Source-owner run → Evidence join → Governed review → Recensus | `mission-control/federation-atlas/PROCESS_LANES_v1.json` |
| O · Outputs | Qualified graph atoms, source-bound receipts, HTML/SVG/Mermaid projections and explicit HOLD | `mission-control/federation-atlas/pages_portal.py` |
| C · Customers | Repository owner/reviewer, next-wave worker, MissionControl viewer, QPS engineering owner | `mission-control/v2/MISSION_CONTROL_CURRENT_v2.json` |

## Workflow hierarchy

- 1. **Mission** — Registered purpose / source owner
- 2. **Sprint** — Bounded scope and review commitment
- 3. **Wave** — Coordinated disjoint delivery envelope
- 4. **Pulse** — One temporal measured disposition
- 5. **Run** — Source-owning native run/job/attempt

## Dispatch condition

All displayed worker/dispatch routes are **DECLARED** scheduling proposals. The existing CODEX execution gateway is STAGE_ONLY; actual mutation is disabled. A display button is not an authenticated runner.
