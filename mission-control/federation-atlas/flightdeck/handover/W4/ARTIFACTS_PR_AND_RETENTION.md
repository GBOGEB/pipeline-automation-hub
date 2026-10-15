# Artifact provenance and storage responsibilities

**Answer to “are all artifacts, diagrams and schemas updated via PR?” — No.** GitHub PRs carry source code, governed JSON/YAML, Markdown, `.mmd` and schema definitions. GitHub Actions may produce HTML/SVG/JSON/ZIP artifacts and office binaries but they do **not** automatically commit or permanently retain them. Nor does an existing Jekyll Pages PASS prove the Flight Deck is hosted. The W1/W2/W3 binaries are preserved in the *original* archives embedded in this W4 package.

| Artifact type | Authority | Persistent handover | Update trigger and path |
|---|---|---|---|
| Canonical SSOT YAML/JSON/schema, methods, generator `.py` / `.js` | Git `master` after governed PR | Full 40-character Git commit SHA + blob identity | User/owner accepts source delta → PR + exact-head CI |
| Mermaid `.mmd`, SIPOC and authoring Markdown | Source-controlled authoring files proposed here | Commit path + SHA / signed release copy | Change in process contract or BD root → regenerate projections; do not overwrite historical |
| Generated HTML / SVG / JSON | Derived review projection | CI artifact with SHA manifest, durable release mirror; Pages only if approved | Same frozen source SHA and generation tool lock |
| XLSX / DOCX / PPTX / PDF | Derived binaries | Content-addressed artifact ZIP or official doc manager; never assume PR stores them | Source/format changes → rebuild, structural+visual QA, corporate control remains external |
| User-supplied corporate files | External authoritative originals | Source path/document ID/version, approved hash and bytes where permitted; keep unmodified | New controlled revision → new lineage, no binary round-trip mutation |
| GitHub Actions logs/jobs | Native execution evidence | Run ID, attempt, job, exact SHA, original downloaded ZIP, internal SHA | Workflow run; retention finite — mirror important proof |
| This handover | Local append-only checkpoint | Four immutable ZIP ancestors, per-file content manifest, final ZIP SHA receipt | New recursive pulse consumes old ZIP as *one unchanged parent* |

## Per-artifact custody matrix

| Artifact | Authority | State | Example path | Caution |
|---|---|---|---|---|
| SRC-W1W2 | GITHUB_SOURCE | MERGED | mission-control/federation-atlas/flightdeck/{*.py,*.json,*.md} | Source, not a published binary |
| SRC-W3 | GITHUB_SOURCE | MERGED_WITH_CI_RED | .github/workflows/code-purple-method-atlas.yml; build_atlas.py | Earlier W3 PR head 077391d..., newer f9f branch contains overlay preservation not incorporated until W4 staged |
| SRC-HOOK | GITHUB_SOURCE | MERGED_WITH_PRODUCER_RED | mission-control/golden-thread/session_hook/ | No full raw chat export; 19 tests passed, post-test HTML assertion failed |
| SRC-DOV | GITHUB_SOURCE | MERGED | mission-control/federation-atlas/flightdeck/global_dov_*.py/json | Historical QPS product metrics remain separate from fleet |
| SRC-W4 | GITHUB_BRANCH | STAGED_NOT_PR | test_federation_latest_overlay.py; code-purple-session-hook.yml; code-purple-method-atlas.yml; build_atlas.py; W4_EVERRED_RECOVERY.md | Two first-red assertion fixes and N+2 overlay restoration |
| SSOT-G4 | GITHUB_SOURCE | HISTORICAL_SOURCE | mission-control/gogreen/samples/fleet_g1.json | Original 6/42 observations and 36 UNKNOWN remain frozen |
| VIEW-HTML | DERIVED_L3 | LOCAL_VERIFIED_NOT_HOSTED | qualification_out/index.html | In W3 frozen ZIP, not independently read back at Pages URL |
| VIEW-SVG | DERIVED_L3 | LOCAL_VERIFIED | qualification_out/flightdeck.svg | Generated projection, source schema/coordinates controlled in repo |
| VIEW-XLSX | DERIVED_BINARY | LOCAL_VERIFIED | qualification_out/evidence_register.xlsx | Inside immutable W3 parent ZIP; not committed to Git history |
| VIEW-DOCX | DERIVED_BINARY | LOCAL_VERIFIED | qualification_out/federation_report.docx | Inside W3 parent ZIP; corporate doc-control approval external |
| VIEW-PPTX | DERIVED_BINARY | LOCAL_VERIFIED | qualification_out/mission_brief.pptx | Inside W3 parent ZIP, not tracked as canonical source |
| VIEW-PDF | DERIVED_BINARY | LOCAL_VERIFIED | qualification_out/linked_evidence_book.pdf | Linked PDF projection, not live HTML nor authorized original |
| HOSTED-PAGES | DEPLOYMENT | PAGES_JEKYLL_PASS_FLIGHTDECK_UNKNOWN | https://gbogeb.github.io/pipeline-automation-hub/ | No exact hosted Flight Deck content-hash readback |
| MANIFEST-W3 | LOCAL_QA | HISTORICAL_LOCAL_ONLY | parents/MISSIONCONTROL_W3_CONVERGENCE_LOCAL_GATE_20261015.zip | W3 parent frozen source SHA f9f7..., not a GitHub PR541 terminal PASS |
| HANDOVER-W4 | NEW_LOCAL_PACKAGE | LOCAL_REPRODUCIBILITY | MANIFEST.json + parents/*.zip + state/ + site/ + tools/ | Current W4 zip is a lossless handover, not a GitHub release artifact |

**Release lock:** At a new exact main SHA, compute a source digest from canonical inputs; generate all derivative formats; verify count/digest consistency; check mandatory admission; publish via a single authorized publisher; read back served bytes and compare to immutable receipt. If a source or output differs, HOLD and recensus. Never let review HTML mutate engineering L1 truth.