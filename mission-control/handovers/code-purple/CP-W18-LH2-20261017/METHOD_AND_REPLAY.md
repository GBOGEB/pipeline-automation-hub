# LOSSLESS_HANDOVER_V2 governed method (this cut)

**Canonical source:** [ABACUS tools/handover_v2/process_spec.json](https://github.com/GBOGEB/ABACUS/blob/19d0581e640f252f39984ef893d4fd4e9d236ad5/tools/handover_v2/process_spec.json), version `2.0.0`. This is a public-safe GitHub-first operational *index* conforming to the intent of the method. **It is NOT a generator/schema-validated or P7 replay-certified V2 capsule**, because that generator was inspected from GitHub but was not executed on an exact declared V2 `handover_input.json`. No full raw chat transcript or private native artifact archive was supplied.

| V2 stage | This cut | Next proof |
|---|---|---|
| P0_CAPTURE | GitHub exact refs, 141 issue identities, SHA and UTC captured | Repeat live readback on receive |
| P1_VALIDATE | 141 unique issue identities checked, consistent search pages | Run original V2 schema/semantic checks on a compliant input |
| P2_TRACE | `code_provenance.json` includes owner path/PR/run SHA | Authenticated artifact bytes/attempt jobs, especially #2182 |
| P3_COMPARE | `comparisons.json` separate issue/canonical vs test-union observations | Same-population B9/coverage diff not yet qualified |
| P4_DECIDE | `bd_queue.json` DAG and no promotion controls | Human/admin P0 disposition |
| P5_GENERATE | Markdown + JSON files source committed on new handover PR | Formal generator output differs and is unverified |
| P6_SEAL | Git blob object IDs available in `manifest.json` | Independently attest complete SHA-256 raw artifact bytes |
| P7_REPLAY_VERIFY | **NOT ATTESTED** | Run canonical `build_handover.py build/verify` with schema-validated input |
| P8_HANDOFF | Copy `dropin.md` + this PR URL into new chat | New session must refresh exact heads first |
| P9_ITERATE | Source-owner next wave in BD queue | Emit successor and compare scope-matched evidence |

**DoD (this documentation PR)**: files present, Git tree and exact committed paths verified, issue rows unique, YAML/JSON syntax tested where applicable, portable reference manifest. **DoV (global)**: HOLD; independent human review and protected branch controls do not presently satisfy required policy. No direct source bug closure, claimed merged security waiver, QPS acceptance or authenticated CODEX dispatch.

**Release integrity:** Git SHA-1 *blob IDs* are content identity under Git semantics; they are **not SHA-256** and do not constitute signed authenticity. In local portable ZIP, generate and verify SHA-256 manifest for byte integrity. The original V2 generator and independent remote signature would be stronger.
