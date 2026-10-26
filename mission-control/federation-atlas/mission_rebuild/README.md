# MISSION CONTROL · Federation Makeover W1

Additive source-model projection, consuming the existing canonical `PROCESS_LANES_v1.json`, `CODE_PURPLE_BEAMS_DAG_v1.json` and historical SIPOC instance sample. No competing SSOT, publisher, scheduler, dispatch authorization or merge gate.

Run: `python -m unittest discover -s mission-control/federation-atlas/mission_rebuild -p 'test_*.py' -v`. Build: `python mission-control/federation-atlas/mission_rebuild/build.py --source-sha "$(git rev-parse HEAD)" --out /tmp/code-purple-atlas/mission-rebuild`.

The static launch page contains five source-repository links, 39 stage atoms, beam graph edges, next-pulse feedback, SIPOC and a historical worker lease view. Source input digests, generated member digests and exact checkout SHA are in `manifest.json`.

W1/P1: source-graph and adversarial tests. W1/P2: existing Pages portal adapter with hash parity. W1/P3: native CI and browser QA. These are separate from authenticated worker execution, current-head green, QPS owner acceptance, security, reviewer and merge admission.
