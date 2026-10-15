# Bounded response and session rollover template — M2

**When to checkpoint:** 3–5 substantial pulses; an exact-SHA or authority collision; unresolved native first-red needing long investigation; chat/UI slowdown reported by user; or an answer that cannot cover all actions and sources without becoming unwieldy. Consult QPS `controls/QPS_CHAT_SESSION_HEALTH_POLICY_v0.2.yaml` for H1–H5/hysteresis if applicable.

**Brief answer:** one narrative summary, no more than five short sections, three to five meaningful metrics, one small DAG, one GitHub source link set; avoid reproducing entire tables/logs in chat. Place full detail in versioned GitHub Markdown and JSON, not ZIP/TAR.

**Before terminating:** (1) confirm current exact repo heads, PR states and native run/job/attempt; (2) append new intent/action IDs with predecessor links; (3) publish every DONE/DEFER/HOLD/SUPERSEDED status with evidence, including negative evidence and noncompensating gates; (4) re-run deterministic generated HTML parity and capture the exact source/manifest hashes; (5) never transfer QPS engineering authority, self-review GitHub, fabricate chat message IDs or claim Pages deployed without readback; (6) emit a short copyable drop-in plus explicit next first-red/owner. The actual GitHub write must be acknowledged before claiming persisted.

**Restart:** read the M2 JSON/MD in GitHub, refresh live GitHub, recalc drift, continue earliest satisfiable P0. Reset chat-local experience/efficiency metrics and retain persistent source lineage. STOP the current answer when only repetitive detail remains and point to GitHub source.
