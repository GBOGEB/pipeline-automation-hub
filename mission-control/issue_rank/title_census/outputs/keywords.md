# Title taxonomy: keywords

Grammar: `<type>(<scope>[,<scope>][ <qualifier>...])[!]: <subject>`, e.g. `fix(jade devops N12): census fails closed`.

Pulse 2026-10-26T10:07:10Z, vocabulary sha256 `54a274e662c9`.

## Types

| type | family | aliases | spellings seen |
|---|---|---|---|
| `feat` | change | feature, features, add, new, enhancement, integrate, integration, ui | `feat` 612, `integrate` 3, `ui` 1 |
| `fix` | defect | bugfix, hotfix, bug, patch, repair, hardening, harden, fix-forward | `fix` 586, `Fix` 5, `repair` 3, `FIX` 2, `hardening` 1 |
| `docs` | knowledge | doc, documentation, readme | `docs` 222, `Docs` 3 |
| `ci` | pipeline | workflow, workflows, gha, actions, cd, infra | `ci` 261, `CI` 50, `infra` 1 |
| `build` | pipeline | deps, dependencies, release, packaging | `deps` 73, `release` 29, `build` 18, `Deps` 2, `Release` 1 |
| `test` | quality | tests, testing, qa, canary, testflight | `test` 193, `Test` 24, `qa` 3, `testflight` 1, `canary` 1 |
| `refactor` | quality | refactoring, restructure, migration, assimilate | `refactor` 4, `migration` 2, `assimilate` 1 |
| `perf` | quality | performance | `perf` 2 |
| `style` | quality | format, lint | `style` 10 |
| `chore` | maintenance | housekeeping, maint, cleanup, governance, gov, govern, revive, sync, merge | `chore` 91, `governance` 18, `SYNC` 11, `Governance` 7, `govern` 3, `revive` 1 |
| `revert` | maintenance | - | - |
| `plan` | planning | program, epic, tracker, rfi, wave, mission, triage | `triage` 70, `TRIAGE` 20, `RFI` 7, `plan` 6, `program` 2, `Wave` 1 |

## Families and scopes

Aliases in *italics* only match inside an explicit `type(scope)` or a label, never free text.

### handover (`handover`), 39 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `handover` | handover, handoff, hand-off, *checkpoint*, session-close, *closeout*, *close-out* | `handover (as type)` 17, `handover` 9, `Handover (as type)` 7, `handover-v2` 3, `HANDOVER (as type)` 3 | cryoplant-project 18, ABACUS 11, pipeline-automation-hub 9, CODEX 1 |

### gogreen (`gogreen`), 60 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `gogreen` | gogreen, go-green, gogreen-federation, *green* | `gogreen` 48, `GoGREEN` 2, `GoGREEN (as type)` 1 | pipeline-automation-hub 46, ABACUS 4, gg_MATH 1 |
| `gogreen-launcher` | gogreen-launcher, *launcher* | `gogreen-launcher` 6 | pipeline-automation-hub 6 |
| `scale-dock` | scale-dock, scale_dock, scaledock, *dock* | `scale-dock` 2 | pipeline-automation-hub 2 |
| `depth` | *depth* | `depth` 1 | pipeline-automation-hub 1 |

### jade devops (`jade-devops`), 56 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `jade-devops` | jade devops, jade-devops, jade, jade-temple, jade_temple, jade waves, jade-waves, devops | `jade` 36, `jade devops` 5, `DevOps (as type)` 2, `jade H01-H12` 2, `jade-temple W+1` 1, `jade-temple W+2` 1, `jade-temple` 1, `jade dag` 1, `jade waves` 1, `jade census` 1 | pipeline-automation-hub 45, DOCX_RTM_Automation 3, cryoplant-project 3 |
| `census` | census, token-census, devops-census, fleet-census | `census` 2, `token-census` 1 | ABACUS 2, pipeline-automation-hub 1 |
| `cicd-dag` | cicd-dag, cicd_dag, *dag*, *regen*, sipoc | - | - |
| `rolling5` | rolling5, rolling-5, nirvana, focus5, golden-thread | `golden-thread` 2 | pipeline-automation-hub 2 |

### watch (`watch`), 7 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `watch` | watch, watch-vnext, watcher, owner-edge | `watch` 7 | pipeline-automation-hub 7 |
| `flightdeck` | flightdeck, flight-deck | - | - |
| `outbox` | outbox | - | - |

### p-process (`p-process`), 28 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `p-process` | p-process, pprocess, p_process, p-decide, p_decide | `p-process` 4 | pipeline-automation-hub 4 |
| `everred` | everred, ever-red, *red-trace* | `everred` 18, `EVERRED` 2, `everred-ui` 1, `everred-ci` 1, `EVERRED (as type)` 1, `everred MYCELIUM` 1 | ABACUS 21, pipeline-automation-hub 3 |

### mission control (`mission-control`), 244 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `mission-control` | mission-control, mission control, missioncontrol, mc, mcc | `MissionControl (as type)` 134, `mc` 72, `missioncontrol` 17, `mission_control` 3, `mission-control` 2, `mcc` 2, `mc-m3` 2, `mc M4` 1, `missioncontrol (as type)` 1, `mc-hb-01` 1, `mc side mission 00` 1, `mc side mission 10` 1, `mc side mission 01` 1, `mc side mission 11` 1, `mc side mission` 1, `MC MACH-II` 1, `mc LDAB` 1, `mc-w2` 1, `MC-CREW-01 (as type)` 1 | pipeline-automation-hub 130, CODEX 107, cryoplant-project 5, ABACUS 2 |
| `g3` | g3a, g3c, g3p, g3-engine, g3_engine | - | - |

### code purple (`code-purple`), 54 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `code-purple` | code-purple, code purple, codepurple, *cp*, *purple*, cpq | `code-purple` 37, `cp` 5, `CODE PURPLE` 4, `code purple` 2, `codepurple` 2, `cpq` 2, `cp-live` 1, `cp-w10` 1 | pipeline-automation-hub 20, ABACUS 16, CODEX 11, cryoplant-project 6, gg_MATH 1 |

### qps (`qps`), 524 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `qps` | qps, qps triage, qps-triage, qps_deck, qps-deck, cool-down, cooldown | `qps` 370, `QPS (as type)` 30, `qps-roundtrip` 6, `qps CODE_BNB` 6, `qps BB JADE LKT` 6, `qps BB/JADE` 4, `qps-census` 3, `qps_line_s` 3, `qps-triage` 3, `QPS BNB JADE` 3, `qps QBD` 3, `qps-dow-keb` 2, `qps jade` 2, `qps-lb` 1, `QPS-LB (as type)` 1, `qps (as type)` 1, `qps-slide-system (as type)` 1, `qps-bt` 1, `qps-thermo` 1, `QPS GM-I MACH-II` 1, `qps B04-C1` 1, `QPS BREAD & BUTTER JADE` 1, `qps N1-A` 1, `qps B04-C2` 1, `QPS BNB LDAB` 1, `QPS BNB` 1, `qps N1E` 1, `qps POWER Share` 1, `qps B04-C3` 1, `QPS BREAD BUTTER JADE` 1, `qps B&B` 1, `qps b04c5` 1, `cooldown` 1, `QPS-FED-W02 (as type)` 1, `QPS-FED-W03 (as type)` 1, `Cool-down (as type)` 1, `qps-n4` 1, `qps-n5` 1, `qps P-process` 1 | cryoplant-project 262, CODEX 99, ABACUS 97, pipeline-automation-hub 8, github_Documents 1 |
| `qplant` | qplant, cryoplant, *cryo* | `cryo` 6, `qplant` 3, `QPLANT-AI-AUTO (as type)` 1 | CODEX 5, ABACUS 3, DOCX_RTM_Automation 1, document-organization-system 1 |
| `keb` | keb, knowledge-exchange-bridge | `keb` 7, `KEB (as type)` 7 | CODEX 14 |
| `triage` | *triage*, qps-triage-ultra, lm-11 | `triage` 16 | cryoplant-project 10, ABACUS 3, CODEX 3 |
| `cost` | cost, qps-cost, cost-control | `cost` 10, `qps-cost` 5, `qps-cost-master` 2 | cryoplant-project 12, ABACUS 3, CODEX 2 |

### atlas (`atlas`), 48 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `atlas` | atlas, metric-atlas, federation-atlas, method-atlas | `atlas` 8, `metric-atlas` 7, `method-atlas` 4, `federation-atlas` 1 | pipeline-automation-hub 18, CODEX 2 |
| `metrics` | metrics, mcw, kpi-metrics | `metrics (as type)` 19, `metrics` 6, `mcw` 3 | ABACUS 22, cryoplant-project 4, CODEX 1, pipeline-automation-hub 1 |

### mycelium (`mycelium`), 44 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `mycelium` | mycelium | `mycelium` 35, `mycelium MIP` 1, `MYCELIUM (as type)` 1 | CODEX 37 |
| `mesh` | mesh | `mesh` 7 | CODEX 7 |

### governance (`governance`), 138 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `governance` | governance, *gov*, branch-hygiene, *policy*, house_style, house-style, licence, license, branches, branch | `governance` 17, `branches` 9, `licence` 8, `branch-hygiene` 5, `license` 2, `governance CBD!` 1, `governance-tests` 1, `branch-strategy` 1 | CODEX 13, ABACUS 11, pipeline-automation-hub 4, cryoplant-project 3, gg_MATH 3, DOCX_RTM_Automation 2, Q_engineering_tools 2, document-organization-system 2, CODESPACES_jyperter 1, cryo_leak_rate_dashboard 1, cryogenic-accelerator-workspace 1, github_Documents 1 |
| `security` | security, codeql, supply-chain, *secrets* | `security` 20, `security (as type)` 3, `Security (as type)` 3, `security-dashboard` 1, `SECURITY-DEFER (as type)` 1 | ABACUS 20, CODEX 6, pipeline-automation-hub 2 |
| `first-pass-closure` | first-pass-closure, fpc, w305, *gate*, *gates* | `gate` 3, `Gate (as type)` 2, `fpc` 1 | ABACUS 5, pipeline-automation-hub 1 |
| `control` | control, *cp.close* | `CONTROL (as type)` 26, `control (as type)` 20, `control` 4, `cp.close` 3, `Control (as type)` 1 | cryoplant-project 32, ABACUS 6, pipeline-automation-hub 5, CODEX 4, DOCX_RTM_Automation 4, GEMINI 2, CODESPACES_jyperter 1 |
| `evidence` | evidence, receipt, receipts, attestation, *proof* | `evidence (as type)` 6 | cryoplant-project 6 |

### dependencies (`deps`), 258 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `deps` | deps, deps-pip, deps-npm, deps-actions, dependabot, dependencies, *pip*, *npm* | `deps` 225, `deps-pip` 13, `deps-actions` 10, `deps-npm` 10 | ABACUS 200, pipeline-automation-hub 35, CODEX 16, cryoplant-project 6, cryo_leak_rate_dashboard 1 |

### ci / ops (`ci-ops`), 111 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `ci` | ci, *actions*, *workflows*, *runner*, *runners*, *runtime*, runner-economics, runtime-health, py310, py-matrix | `ci` 64, `runtime` 8, `ci-governance` 3, `py310` 2, `actions` 2, `py-matrix` 1, `CI` 1, `RUNTIME (as type)` 1, `RUNNER-ECONOMICS (as type)` 1 | ABACUS 57, CODEX 12, cryoplant-project 6, pipeline-automation-hub 6, DOCX_RTM_Automation 1, gg_MATH 1 |
| `pages` | *pages*, *site*, browser-qa | `pages` 7, `browser-qa` 4, `site` 1 | pipeline-automation-hub 7, CODEX 3, ABACUS 1, cryoplant-project 1 |
| `dashboard` | dashboard, health-check | `dashboard` 3 | ABACUS 3 |
| `release` | *release*, releases, versioning | `release` 9 | ABACUS 3, gg_MATH 3, cryoplant-project 2, document-organization-system 1 |
| `infra` | infra, docker, devcontainer, codespaces, *mcp* | `mcp` 2, `docker` 2 | ABACUS 2, CODEX 2 |

### issue burndown (`issue-burndown`), 113 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `issue-burndown` | bd, burndown, issue-bd, triway, issue-rank, issue-expedition | `bd` 10, `issue-rank` 7, `BD (as type)` 6, `issue expedition` 2, `bd-ldab` 1, `burndown` 1, `bd-queue` 1, `BD-REX-CONTROL (as type)` 1 | pipeline-automation-hub 13, ABACUS 11, cryoplant-project 3, CODEX 2 |
| `cbd` | cbd, char-bd, charter-bd, bdq | `cbd` 64, `CBD` 6, `bdq` 2, `char-bd` 1, `CBD (as type)` 1, `cbd wave5` 1, `cbd-n3` 1, `cbd W+3` 1, `cbd W+2` 1, `cbd W31/A` 1, `cbd W31/B` 1, `cbd W31/C` 1, `cbd W31/D` 1, `cbd W31/E` 1, `cbd W51-C1/C2/C3` 1 | ABACUS 76, pipeline-automation-hub 4, cryoplant-project 3, CODEX 1 |

### physics (`physics`), 19 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `physics` | physics, physics-pin, coolprop, *thermo*, math, gg-math | `physics` 7, `math` 5, `physics-pin` 2, `physics-review` 1, `coolprop` 1, `math (as type)` 1, `gg_MATH (as type)` 1, `gg_math` 1 | CODEX 10, gg_MATH 8, cryoplant-project 1 |

### fleet / federation (`fleet`), 90 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `fleet` | fleet, gm-fleet, *gm*, federation, *fed*, delta-1, orchestration | `GM-FLEET-03 (as type)` 49, `federation` 13, `Fleet (as type)` 9, `federation (as type)` 6, `GM-FLEET-03-H1 (as type)` 3, `fed-w44` 2, `GM-FLEET-02B (as type)` 2, `orchestration` 1, `fed-w44/p03a` 1, `fed-w44/p03c` 1, `gm-fleet03` 1, `gm-dmaic` 1, `GM-FLEET (as type)` 1 | pipeline-automation-hub 68, cryoplant-project 9, ABACUS 5, CODEX 4, gg_MATH 2, DOCX_RTM_Automation 1, document-organization-system 1 |

### dmaic (`dmaic`), 119 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `dmaic` | dmaic, dmaic-c3, dmaic-v3, gm14, gm-top7, testpilot, gm-iv, gm-v, gm-i | `GM-IV (as type)` 17, `GM-I-A (as type)` 14, `dmaic` 9, `GM-I-C (as type)` 9, `GM-V (as type)` 9, `dmaic (as type)` 6, `dmaic C3` 2, `testpilot` 2, `GM-I-B (as type)` 2, `dmaic C2` 1, `dmaic C4` 1, `dmaic C4B` 1, `dmaic C5` 1, `gm-i-a` 1, `gm-v` 1 | pipeline-automation-hub 44, ABACUS 24, CODEX 3, GEMINI 2, gg_MATH 2, cryoplant-project 1 |
| `dab` | dab, dab-hard, ldab | `DAB (as type)` 23, `DAB-G4 (as type)` 1, `dab` 1, `dab T2` 1, `DAB-BD8K (as type)` 1 | ABACUS 27 |
| `sut` | sut | `sut` 6 | ABACUS 6 |
| `mcl` | mcl | `mcl` 9, `mcl CBD!` 1 | ABACUS 10 |
| `g3cs` | g3cs | - | - |

### code quality (`quality`), 49 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `coverage` | coverage, cov, cov-p1 | `coverage` 3, `COV-01-TRIAGE (as type)` 1 | ABACUS 2, CODEX 1, cryoplant-project 1 |
| `lint` | *lint*, ruff, flake8, bandit, osv, house-style, e302, *style*, semgrep, safety | `style` 10, `osv` 3, `bandit` 2, `ruff` 2, `house_style` 2, `safety` 2, `semgrep` 2, `flake8` 1, `house-style (as type)` 1 | CODEX 9, DOCX_RTM_Automation 6, ABACUS 5, cryoplant-project 3, gg_MATH 2 |
| `tests` | *tests*, *test*, pytest, smoke, testflight, *quality* | `test` 9, `tests` 6, `quality` 5 | ABACUS 12, CODEX 6, cryoplant-project 1, pipeline-automation-hub 1 |

### dow / dov (`dow-dov`), 21 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `dow` | dow, definition-of-work | `dow` 16, `DOW (as type)` 4, `dow-ci` 1 | ABACUS 21 |
| `dov` | dov, dod, definition-of-verification | - | - |

### cryo engineering (`cryo-eng`), 75 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `lkt` | lkt | `lkt` 12 | cryoplant-project 12 |
| `alat` | alat | - | - |
| `pvps` | pvps | `PVPS (as type)` 6 | cryoplant-project 6 |
| `hepak` | hepak, helium, he-4, he4, vlp, qcell, rfcell, line-b, line-s | `Line-S (as type)` 2, `helium` 1, `line-s` 1, `helium_flow` 1, `hepak (as type)` 1 | ABACUS 4, CODESPACES_jyperter 1, cryoplant-project 1 |
| `offer` | offer, offer-eval, *eval*, nego, bidder, rfi | `nego` 21, `eval` 13, `RFI-QPS-WSH-01 (as type)` 1, `offer RFI-QPS-CC-01` 1, `RFI-QPS-HP-01 (as type)` 1, `RFI-QPS-PVPS-01 (as type)` 1, `offer RFI-QPS-TURB-01` 1, `RFI-QPS-RECOVERY-01 (as type)` 1, `offer RFI-QPS-3D-01` 1, `RFI-QPS-QRB-TS-01 (as type)` 1, `offer RFI-QPS-WCS-BL-01` 1, `RFI-QPS-LINEB-01 (as type)` 1, `RFI-ALAT-S03 (as type)` 1, `RFI-ALAT-WCS-SENS-01 (as type)` 1, `RFI-ALAT-DRYER-01 (as type)` 1, `RFI-ALAT-DEWAR-CIS-01 (as type)` 1, `RFI-ALAT-MJA-P0 (as type)` 1, `RFI-ALAT-OFFER12 (as type)` 1, `RFI-LKT-CYBER (as type)` 1 | cryoplant-project 51 |

### rtm / adr (`rtm-adr`), 49 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `rtm` | rtm, qps-rtm, docx-rtm, requirements, traceability | `qps-rtm` 36, `docx-rtm` 2 | ABACUS 36, document-organization-system 2 |
| `adr` | adr, ocd, ocd-adr | `adr` 7, `ADR_OCD (as type)` 2, `ocd` 1, `ocd-adr` 1 | cryoplant-project 8, DOCX_RTM_Automation 2, CODEX 1 |

### pca / bt (`pca`), 14 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `pca` | pca, pca-engine, *bt*, kpi, ariana | `pca (as type)` 6, `ariana` 5, `pca_engine` 2, `pca` 1 | ABACUS 5, CODEX 2, cryo_leak_rate_dashboard 2, CODESPACES_jyperter 1, DOCX_RTM_Automation 1, cryogenic-accelerator-workspace 1, cryoplant-project 1, github_Documents 1 |

### mip / 3p (`mip-3p`), 85 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `mip` | mip, 3pr, 3p, 3pc, 3pstar, 3p* | `mip` 42, `MIP (as type)` 30, `MIP` 5, `MIP-STABILIZE (as type)` 2, `mip C1` 2, `3p` 1, `mip CBD!` 1, `mip A` 1, `mip B` 1 | ABACUS 66, CODEX 5, cryoplant-project 3, pipeline-automation-hub 3, DOCX_RTM_Automation 2, gg_MATH 2, CODESPACES_jyperter 1, GEMINI 1, document-organization-system 1, github_Documents 1 |

### historian / lineage (`historian`), 57 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `historian` | historian, rex | `Historian (as type)` 38, `rex` 4, `REX-CM-005 (as type)` 1, `HISTORIAN-FLEET (as type)` 1 | pipeline-automation-hub 28, ABACUS 11, CODEX 4, cryoplant-project 1 |
| `lineage` | lineage, provenance, temporal | `Temporal (as type)` 6, `lineage` 4, `Lineage (as type)` 3 | cryoplant-project 7, pipeline-automation-hub 6 |

### knowledge / docs (`knowledge`), 45 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `docs` | *docs*, *readme*, slides, index.html, glossary, claude-md, book | `docs` 5, `slides` 4, `index.html` 2, `claude-md` 2, `glossary` 2, `README` 2, `book` 1, `slides (as type)` 1, `readme` 1, `GLOSSARY (as type)` 1 | CODEX 11, ABACUS 6, cryoplant-project 3, DOCX_RTM_Automation 1 |
| `gistau` | gistau, gistau-ch15 | `gistau` 14, `gistau-ch15` 2 | CODEX 16 |
| `semantic` | semantic, ssot, taxonomy | `ssot` 3, `semantic` 2, `semantic (as type)` 1 | CODEX 3, document-organization-system 2, cryoplant-project 1 |
| `office` | excel, xlsx, pptx, docx, word, *html*, presentation-engine | `presentation-engine` 1, `docx` 1 | ABACUS 1, DOCX_RTM_Automation 1 |

### minerva p&id (`minerva`), 7 explicit

| scope | aliases | spellings seen | by repo |
|---|---|---|---|
| `minerva` | minerva, minerva-pid, minerva_pid, p-id | `minerva` 4, `minerva-pid` 3 | ABACUS 5, MINERVA_PID 1, cryoplant-project 1 |

## Qualifier classes

`wave`, `pulse`, `jade-step`, `gate-phase`, `user-ticket`, `priority-phase`, `fleet-step`, `round`, `version`, `program`, `ticket`, `pr-ref`, `rank`

## Unmapped explicit scopes (add to a family or rename)

| scope | n | by repo |
|---|---|---|
| `review` | 7 | cryoplant-project 7 |
| `adapter` | 5 | document-organization-system 5 |
| `home` | 4 | ABACUS 1, CODEX 1, cryoplant-project 1, gg_MATH 1 |
| `graph` | 4 | cryoplant-project 4 |
| `a10` | 3 | ABACUS 3 |
| `α` | 3 | ABACUS 1, CODEX 1, cryoplant-project 1 |
| `relief` | 3 | CODEX 3 |
| `refresh` | 3 | cryoplant-project 3 |
| `asis` | 3 | cryoplant-project 3 |
| `aht` | 2 | ABACUS 1, CODEX 1 |
| `spine` | 2 | ABACUS 1, CODEX 1 |
| `pr` | 2 | ABACUS 2 |
| `integration` | 2 | ABACUS 2 |
| `bridge` | 2 | CODEX 2 |
| `incubator` | 2 | CODEX 2 |
| `portal` | 2 | CODEX 2 |
| `render` | 2 | CODEX 1, DOCX_RTM_Automation 1 |
| `registry` | 2 | CODEX 1, pipeline-automation-hub 1 |
| `manifest` | 2 | CODEX 2 |
| `build-control` | 2 | CODEX 2 |
| `nav` | 2 | cryoplant-project 2 |
| `program` | 2 | cryoplant-project 2 |
| `qa` | 2 | cryoplant-project 2 |
| `tender-library` | 2 | cryoplant-project 2 |
| `lanes` | 2 | cryoplant-project 2 |
| `wave-a` | 2 | cryoplant-project 2 |
| `bnb` | 2 | cryoplant-project 2 |
| `qbd` | 2 | pipeline-automation-hub 2 |
| `common.js` | 1 | ABACUS 1 |
| `w001.1` | 1 | ABACUS 1 |
| `repo` | 1 | ABACUS 1 |
| `api` | 1 | ABACUS 1 |
| `auth` | 1 | ABACUS 1 |
| `dormant` | 1 | ABACUS 1 |
| `config` | 1 | ABACUS 1 |
| `convergence` | 1 | ABACUS 1 |
| `diagnostics` | 1 | ABACUS 1 |
| `recovery` | 1 | ABACUS 1 |
| `mip/governance` | 1 | ABACUS 1 |
| `code-maroon` | 1 | ABACUS 1 |
| `acceptance` | 1 | ABACUS 1 |
| `cbd!` | 1 | ABACUS 1 |
| `b0` | 1 | ABACUS 1 |
| `w35/w81` | 1 | ABACUS 1 |
| `backbone` | 1 | ABACUS 1 |
| `p41-l1` | 1 | ABACUS 1 |
| `p41-l3` | 1 | ABACUS 1 |
| `recursive-build` | 1 | ABACUS 1 |
| `bd/ldab` | 1 | ABACUS 1 |
| `code-purple/mip` | 1 | ABACUS 1 |
| `cicd` | 1 | ABACUS 1 |
| `deploy` | 1 | ABACUS 1 |
| `p41-l5` | 1 | ABACUS 1 |
| `root-w1+w2` | 1 | ABACUS 1 |
| `root` | 1 | ABACUS 1 |
| `root-refactor` | 1 | ABACUS 1 |
| `abacus` | 1 | ABACUS 1 |
| `dashboards` | 1 | ABACUS 1 |
| `py-runtime` | 1 | ABACUS 1 |
| `draft` | 1 | CODEX 1 |
| `renderer` | 1 | CODEX 1 |
| `agentic` | 1 | CODEX 1 |
| `w003.2` | 1 | CODEX 1 |
| `w007.1` | 1 | CODEX 1 |
| `block-library` | 1 | CODEX 1 |
| `windows` | 1 | CODEX 1 |
| `pid-pipeline` | 1 | CODEX 1 |
| `tools` | 1 | CODEX 1 |
| `ch15` | 1 | CODEX 1 |
| `ubi9` | 1 | CODEX 1 |
| `browser` | 1 | CODEX 1 |
| `pyright` | 1 | CODEX 1 |
| `purplegrid` | 1 | CODEX 1 |
| `swift-roof` | 1 | CODEX 1 |
| `swift` | 1 | CODEX 1 |
| `a7` | 1 | CODEX 1 |
| `claude.md` | 1 | CODEX 1 |
| `bots` | 1 | CODEX 1 |
| `archive-incubate` | 1 | CODEX 1 |
| `telemetry` | 1 | cryoplant-project 1 |
| `reentry` | 1 | cryoplant-project 1 |
| `architecture` | 1 | cryoplant-project 1 |
| `architecture/eval` | 1 | cryoplant-project 1 |
| `qtg` | 1 | cryoplant-project 1 |
| `namespace` | 1 | cryoplant-project 1 |
| `offers-itt` | 1 | cryoplant-project 1 |
| `neg` | 1 | cryoplant-project 1 |
| `gloob` | 1 | cryoplant-project 1 |
| `graphs` | 1 | cryoplant-project 1 |
| `h08` | 1 | cryoplant-project 1 |
| `binaries` | 1 | cryoplant-project 1 |
| `nist` | 1 | document-organization-system 1 |
| `contract` | 1 | document-organization-system 1 |
| `mach-iii` | 1 | pipeline-automation-hub 1 |
| `live-census` | 1 | pipeline-automation-hub 1 |
| `pipeline` | 1 | pipeline-automation-hub 1 |
| `replay-lane` | 1 | pipeline-automation-hub 1 |
| `owner` | 1 | pipeline-automation-hub 1 |
| `agents` | 1 | pipeline-automation-hub 1 |
| `workstation` | 1 | pipeline-automation-hub 1 |
| `portability` | 1 | pipeline-automation-hub 1 |
| `master` | 1 | pipeline-automation-hub 1 |
| `ops` | 1 | pipeline-automation-hub 1 |

## Unknown types

| type | n | by repo |
|---|---|---|
| `feedback` | 14 | ABACUS 8, CODEX 6 |
| `review` | 9 | cryoplant-project 9 |
| `bridge` | 4 | ABACUS 1, CODEX 1, DOCX_RTM_Automation 1, cryoplant-project 1 |
| `draft` | 4 | cryoplant-project 4 |
| `adapter` | 2 | document-organization-system 2 |
| `PR-H` | 1 | CODEX 1 |

## Lint codes

| code | severity | rule | n |
|---|---|---|---|
| T001 | error | no type(scope): prefix | 4087 |
| T002 | error | unknown type | 34 |
| T003 | info | type alias, use the canonical type | 262 |
| T004 | warning | missing scope | 246 |
| T005 | warning | scope not in vocabulary | 150 |
| T006 | info | scope alias, use the canonical scope | 610 |
| T007 | warning | scope used as type (e.g. 'MissionControl: ...') | 806 |
| T008 | info | bracket tag outside the prefix, move it into the scope as a qualifier | 235 |
| T009 | info | subject longer than 100 characters | 63 |
| T011 | info | freeform lead label (e.g. 'W327: ...'), rewrite as type(scope qualifier): | 1909 |
