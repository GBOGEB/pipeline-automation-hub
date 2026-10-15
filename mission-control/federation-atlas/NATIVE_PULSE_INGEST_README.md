# CODE PURPLE — Native pulse intake (bounded implementation)

Scope: six named repositories in the existing G4 cohort; no new canonical SSOT, Pages publisher, or GitHub write authority. This adapter adds immutable event leaves alongside—not inside—the frozen QPS P0/P1/P2 and G4 G0/G1 histories. The existing `mission-control/gogreen/collect_readonly.py`, `verify_native_zip.py`, and `federation_pulse_rollup.py` remain upstream contracts and should be reused when their specific schemas apply.

## Native command (read-only GET)

From repository root:

```sh
python -m unittest discover -s mission-control/federation-atlas -p test_native_pulse_ingest.py -v
GITHUB_TOKEN="$GITHUB_TOKEN" python mission-control/federation-atlas/native_pulse_ingest.py \
  --repo GBOGEB/pipeline-automation-hub --run-id 38707835880 \
  --out /tmp/code-purple-native-pulses
```

The run ID above is an example historical G4 run, not evidence that this new adapter has executed on it. A nonexistent/mismatched/expired artifact is a hard error. To independently download and inspect a specifically contracted producer:

```sh
GITHUB_TOKEN="$GITHUB_TOKEN" python mission-control/federation-atlas/native_pulse_ingest.py \
  --repo GBOGEB/pipeline-automation-hub --run-id <actual-run-id> \
  --artifact-name pulse-measurement --expected-sha <exact-40-char-run-head> \
  --out /tmp/code-purple-native-pulses
```

The name `pulse-measurement` identifies an *opt-in future producer contract* containing `pulse_measurement.json`; existing G4 ZIP archives are **not asserted** to contain it. Existing incompatible native ZIP producers should be adapted explicitly via a separate schema-specific read-only parser, not relabeled or blindly accepted.

A recorded event includes source SHA, run ID, attempt, job census, archive ID and digest (if retrieved), and an evidence-depth classification. When no compatible ZIP receipt is observed, test counts and line/branch coverage are `null`. No cross-run coverage merging is performed. Root burndown, reviewer approval, federation acceptance and QPS engineering admission remain separate UNKNOWN/DEFER dimensions.

### Required receipt contract

Top-level ZIP entry: `pulse_measurement.json` with `schema=codepurple.pulse-measurement/v1`, `repository`, `head_sha`, `run_id`, `run_attempt`, `job_id`, `config_sha256`, `tool: {name, version}`, `selection`, `tests: {passed, failed, skipped}`, `line` and `branch` numerator/denominator, and `source_scope: [{path,sha256}]`.

The adapter verifies the source/run/job relationship using current GitHub REST run and job metadata, and performs a bounded ZIP member and payload check. The resulting coverage figure is still a **producer-reported observation**; this does not independently rerun coverage or prove the production source content. For offline `--offline` capture, input metadata is explicitly marked `CALLER_SUPPLIED_OFFLINE`; never promote such samples to an authenticated-native claim. GitHub's artifact `digest` field is not assumed to be present or sufficiently scoped; the adapter computes its own SHA-256 of downloaded ZIP bytes.

The output directory receives individual immutable `pulse-*.json` leaves, a rebuilt `native_pulse_ledger.json` and a static, responsive `native_pulse_index.html`. Re-reading the same event is idempotent. A changed result creates a new leaf; a mutated previous leaf is rejected. Generated review files may be replaced; historical event leaves may not. No GitHub issue, branch, PR, security policy or Pages surface is modified by running this utility.

## Admission and release

**Local regression proof is not a native run.** Initial state `LOCAL_REPRODUCIBILITY`; native exact-head workflow run and artifact validation are required for `EXACT_SHA_RECEIPT`. No `P3` or `N+3` is inferred from this tool. Before enabling unattended publication, add an owner-reviewed workflow with least-privilege, verify error handling for public/private cross-repo artifact access, and join receipt leaves through the existing GOGREEN/federation sources. Protected-main and eligible review remain independent gates.