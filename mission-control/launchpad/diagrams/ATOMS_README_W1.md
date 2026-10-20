# MissionControl — W1 atom / graph / DAG interpretation

**Scope:** six pinned source-owned repos, 13 graph-node atoms and 19 edge atoms. This is a metadata graph of system roles and declared/evidence routes; it is **not** a scan of all 90 GBOGEB repositories nor an enumeration of global causal BD roots.

- **GRAPH_NODE**: an HMI/root/system component with a role and source authority reference. Does not imply an active worker.
- **GRAPH_EDGE**: a relationship between two nodes, typed `DEPENDS_ON`, `DECLARED_ROUTE`, `EVIDENCE`, `ASSOCIATION` or `FEEDBACK`.
- **RECEIPT**: three historical source-bound run citations inherited from the canonical federation graph; no present-day runner status/merge rights implied.
- **DECLARED**: all other sixteen relationships; intended routes and/or noncausal associations with no effective execution proof.
- **Executable DAG**: seven dependency relations (`DEPENDS_ON`) in deterministic topological order. Excludes feedback and associations; no edge has dispatch permission.
- **Universal graph**: 13 nodes / 19 edges; can include feedback to a *later pulse*. Graph cycles are not native-run deadlocks.

**Receipts remain one level away from engineering approval.** Any future growth to 90-repo fleet must separately prove source access, no restricted material publication, typed run/job/attempt provenance, own-role dispatch and independent review.

Source [input crosswalk](../MISSIONCONTROL_NAV_SOURCES_v1.json), [graph atoms](../GRAPH_ATOMS_W1_v1.json), [Mermaid](MC_FEDERATION_ARCHITECTURE_W1.mmd), [SIPOC](SIPOC_W1.md). Publisher is the existing [Pages portal](../../federation-atlas/pages_portal.py). `MERGE_ADMISSION=HOLD` until the PR/head/hosted proof ladder succeeds.
