# MC N12 — Recuperation, DoD/DoV, Top7→21 and recursive Golden Thread
**Control:** [Mission Control #604](https://github.com/GBOGEB/pipeline-automation-hub/issues/604) · [GM fleet #426](https://github.com/GBOGEB/pipeline-automation-hub/issues/426) · [Top7 #419](https://github.com/GBOGEB/pipeline-automation-hub/issues/419) · [BD #85](https://github.com/GBOGEB/pipeline-automation-hub/issues/85) · [Global #153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153).

## Recovered sources and previously forgotten obligations
Canonical 1→2→4→8→16 GM I–V registry with GM-IV **ACTIVE_8_OF_8** (eight named candidate slots, **zero** canonical child bindings), GM-V **HELD** (zero child and zero allocated crew). GM-I-A/B/C are *variants*, not new GM IDs. HM-01 is the QPS v6 horizontal release train; LM-10 and LM-11 remain local.

The older `GM_GENEALOGY.json` says GM-IV HELD: preserve as historical observation, precedence to source-bound current `GRAND_MISSION_REGISTRY.json`. Earlier QPS `#923` was a zero-step gate; owner issue is now **closed** with real runner-id/nonzero-step evidence. This improves the *habitat* predicate, not global QPS engineering DoV or GM-V governor admission. Recompute owner readiness separately.

Crew: 23 registry entries (8 U permanent + 7 S specialist + 8 C conceptual). Registered capacity is **not** live runnable capacity. Conceptual roles may not receive CONTROL/promotion authority. Skill scores in source are expert-seeded planning priors; measured allocation needs ≥2 accepted runs on distinct source SHAs and applicable REX guards. Exactly 10 archived crew ↔ MissionControl REX events are **recorded-at seed timestamps**, not original occurrence timestamps.

Source cohorts are different: Top7 source-first-red D1/D2/D3; Top14 shadow; Top21 original breadth promotion HOLD; independent N11 **21 repository/26,836 file** census; historical fleet **90 repository/4,486 PR** genealogy. Never add or substitute their denominators.

## Exact current native first-red and resource allocation
- Hub main baseline `0b6a6f1a062ecdcba4e532aa101735b54ab09911` contains [CODE PURPLE Live Census run 39062244840, job 117482412110, attempt 1](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39062244840/job/117482412110): **terminal FAIL / HTTP 404** on a cross-repository source read. Owner: source-access/credential boundary; not a missing file or application test failure. Existing legacy workflow remains red; N12 adapter is parallel fail-closed read-only evidence, **not** legacy root closure.
- [N12 #679](https://github.com/GBOGEB/pipeline-automation-hub/pull/679): read-only PR/default-head, check-run and native attempt/job collector; 31 tests **authored**; native tests/three-viewport Playwright await terminal exact-head proof.
- The earlier N11 (#671) and N10 (#664) landed on `master`. Merged source bytes do **not** demonstrate effective governance admission. Current main protection readback returned `protected=false`; owner review of effective rules needed.
- ABACUS focused #2161 source `6b89e0421fee000c4aa9bbdcffdc69b31f34d33c`: 3/3 focused native interpreter jobs PASS on 39060580597, **not full CI**. ABACUS #1860 admission and independent Safety/A10/review remain HOLD.
- Native runner workload is high: one successive PR-head commit can queue approximately eight hub workflows while cancelling previous N12 checks under concurrency. Do not advance head to reobserve unchanged deterministic failures; group path-disjoint source changes, freeze SHA, then wait for terminal native evidence.

## 3P* + DMAIC gated recovery
| Gate | DoD implementation | Required independent DoV | Disposition |
|---|---|---|---|
| P1 Source genealogy | GM/crew/REX exact-blob reader, DAG and adversarial tests | 15/15 source blob match + terminal exact-head unit receipts | Source committed; native pending |
| P2 GitHub readback | Bounded GET-only authenticated PR/run/job/attempt | Real job identity; explicit 404/403 unknown; no self-proving admission | Source committed; native pending |
| P3 Visual integration | Offline responsive six-tab Mission City; N11 link; exact model parity | Chromium desktop/laptop/mobile and screenshot SHA256 | Static 6/6 PASS; browser pending |
| P4 Recuperation | First-red routing, source-owner queue, crew return, REX and Golden Thread intent | Owner disposition and check head after correction; return-receipt chain | Proposed / no historical mutation |

**Per-repo repair rule:** at most one admitted source repair and one proof slot per repo; parallelize only path-disjoint repos. First-red sequence = classify `RUNNER_ZERO_STEP`→Dockmaster; `EXECUTED_GT0_APPLICATION`→Doctor/Engineer; `AUTHORITY`→Governor; `SEMANTIC`→KEB Reader/TM; `SOURCE_ACCESS`→owner-authenticated adapter. Deterministic unchanged SHA is *not rerun just to feel progress*. Enforce source/attempt/runner id, prior native first-red and comparable denominator before crediting improvements.

**Crew return hook:** `mission_id, task_id, crew_role, source_sha, run_id, attempt, job_id, evidence_class, REX_ids, DoD, DoV, BD_delta, owner_disposition, return_to_MissionControl`. Always preserve `semantic_generation_k` separately from `event_sequence_e`, real occurred-at versus known-at, native artifacts/digests, and negative/deferred evidence in Golden Thread. New projection neither mutates Golden Thread nor QPS/ABACUS/CODEX authorities.

## Nuanced stability decision
A file census (21/21) is **stable with respect to that frozen population**, but proves nothing about current issue closure. N12 has 31 negative/positive checks **authored** and 0 native proven on current SHA at latest queue readback — execution convergence is **UNKNOWN / QUEUE-CENSORED**, not divergent. The QPS #923 habitat transition is a material **unblocking step**; correct next action is to revalidate the downstream governor and current-QPS tests, not launch GM-V. Split P1/P2/P3 source owners to preserve disjointness; cap native fan-out until terminal work supplies useful signal.

### Operator commands
```powershell
python -m unittest discover -s mission-control/v2/recursive-recovery -p 'test_*.py' -v
python mission-control/v2/recursive-recovery/lineage.py --out .\out\N12_missions.json
$env:GITHUB_TOKEN = $env:GH_TOKEN
python mission-control/v2/recursive-recovery/native_readback.py --out .\out\N12_native.json
python -m pip install playwright
python -m playwright install chromium
python mission-control/v2/recursive-recovery/browser_qa.py .\out\N12_browser
```
No automatic import into `Golden Thread`; pass the reviewed crew-return intent through its existing replay/owner-control system. DoV and engineering acceptance remain separate.
