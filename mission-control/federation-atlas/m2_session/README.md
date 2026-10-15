# CODE PURPLE M2 — Source-bound recursive handover and HTML

The single controlled source is [M2_STATE.json](M2_STATE.json), Git blob `88380f1840bce1bc72008b5ee953e580bfe9d604` (15 user intent atoms, 20 owned actions, six repo profiles, nine independent release gates). The existing Golden Thread and Flight Deck remain owners; no raw ChatGPT transcript or original turn IDs are claimed.

Run `node mission-control/federation-atlas/m2_session/test_m2_portal.js` then `node mission-control/federation-atlas/m2_session/m2_portal.js --check`. On a GitHub exact-head runner use `node .../m2_portal.js --out /tmp/code-purple-atlas/session-m2 --source-sha "$EXACT_SHA"` to produce 12 HTML leaves plus an exact source SHA and SHA256 manifest under the same existing Method Atlas artifact. `--check` detects stale or hand-edited derived HTML.

Pages under `docs/mission-control/m2/` are **committed text/L3 source-bound renditions** but not confirmed hosted Pages; the existing owner publisher must separately deploy and verify URL/bytes. Browser file input stays on device and only returns local SHA256, never runs CLI or modifies GitHub. Outputs do not modify original user binary inputs. No ZIP or TAR handover.
