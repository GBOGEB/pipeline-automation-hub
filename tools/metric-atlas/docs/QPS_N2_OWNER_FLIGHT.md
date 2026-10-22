# QPS TRIAGE N2 — source-owned, bounded receiver flight

**State:** Operator-enabled tooling only; no remote dispatch or native receiver
success is claimed by this document.

The census has three eligible physical producers but only two admitted receivers:

| Lane | Repository | Current decision |
|---|---|---|
| ABACUS | `GBOGEB/ABACUS` | HOLD until #2126's effective gates pass and it merges |
| CODEX | `GBOGEB/CODEX` | Receiver merged in #1065/#1066 |
| QPS engineering | `GBOGEB/cryoplant-project` | Receiver merged in #1946/#1947 |

CODEX and the private QPS repository each expose two read-only routes:
`native_checks` and `coverage_catalog`. The N2 owner-flight launches at most
two repository events and four receiver jobs. It **never dispatches ABACUS**.
A future admitted three-repository wave may expand to six jobs, not before.

## Authenticated operator entry point

Use GitHub CLI with an account authorized to read and dispatch workflows
in CODEX and the private cryoplant-project. No token is stored in this code.
Install Python 3.9+ and initialize the Metric Atlas environment.

```powershell
# In tools/metric-atlas, after bootstrap.ps1:
.\qps_owner_flight.ps1                   # source read + dry-run only
.\qps_owner_flight.ps1 -Execute          # explicit operator opt-in
```

The Python equivalent is:

```bash
PYTHONPATH=tools/metric-atlas python -m metric_atlas.owner_flight \
  --output tools/metric-atlas/run/qps-owner-n2.json
```

To send source-owned receiver requests from the CLI (requires authorization):

```bash
PYTHONPATH=tools/metric-atlas python -m metric_atlas.owner_flight \
  --execute --confirm OWNER_APPROVED_N2_READONLY_CENSUS \
  --output tools/metric-atlas/run/qps-owner-n2.json
```

The operator entry point does not grant private-repository access. Its
`gh api` call must already succeed using locally authenticated credentials.
It reads both `main` source SHAs, constructs deterministic
`qps-metric-census/v1` request IDs and rereads both heads before enqueue.
Any unavailable private source or stale SHA prevents **all** dispatches.

A successful CLI invocation reports `REQUEST_SUBMITTED_NOT_RECEIVER_PROOF`.
Independent evidence must subsequently include receiver run ID, attempt,
job ID, exact source SHA, terminal conclusion and artifact ZIP/member bytes.
This metadata-only census does not execute functional tests or grant coverage,
engineering acceptance, security waiver or merge permission.

## Controller alternative

Central Mission Control fan-out remains separately owner-controlled.
It requires `QPS_FEDERATION_READ_TOKEN` for private-source reads and
`QPS_TRIAGE_DISPATCH_TOKEN` for authorized cross-repository dispatch.
These secrets are not provisioned, inferred or accepted from PR payloads.
Only an authorized operator can configure them in repository secrets.
The hub's `workflow_dispatch` launch with `dispatch_fanout=true` must
be explicitly selected on canonical `master` after source-head validation.

## Canonical roles and controls

- Mission Control #530 validates ZIPs; #531 produces six-repository breadth;
  #533 remains the viewer.
- ABACUS #2126 admission is independent of this N2 observer.
- Requests are capped at three repositories and six route jobs.
- Unknown tests, coverage, worker hours, and QPS authority remain UNKNOWN.
- A reobserved current SHA is required before any replay or N+1 expansion.
