# GoGREEN governed task execution - local-pilot v1

**Owner:** Mission Control / GoGREEN #529. **Authority:** `LOCAL_PILOT_ONLY`.
This is an execution consumer of `sipoc_instances.plan_instances()` and the
Method Atlas, not a replacement for either or a second work-queue SSOT.

## Execution contract

* Exact source commit: every operator-supplied manifest, policy, Python worker
  and input fixture is Git-tracked and verified against `HEAD:<path>`.
* Eligibility: all six READY instances must be present in the canonical
  plan receipt. `BLOCKED`, `PROOF_PENDING`, mutation proposals, foreign source
  SHAs and undeclared inputs fail closed. Only fixed operations are executable.
* Fixed operations: `SOURCE_DIGEST`, `JSON_INDEX`, `JSON_CANONICAL`,
  `GOLDEN_THREAD_CONE`, `OUTPUT_FANIN`, `AUDIT_GATE`. No arbitrary shell,
  user-configurable executable, GitHub mutation, credential or network API.
* Worker: fixed `sys.executable`/script argv, no shell, sanitized environment;
  single-writer output leases, finite deadline, output set enforcement, no
  writes to repository paths. Scratch generated files are atomic per file.
* Wave execution: bounded `asyncio` concurrency plus actual subprocess I/O.
  Wave n+1 waits for earlier waves. On a failure, downstream waves do not run.
* Idempotency: SQLite journal keys include input/task/policy/plan source hashes;
  repeat runs verify output bytes, then reuse without re-execution.
* Recovery: expired lease enters `RECOVERY_HOLD`; an explicit separate
  `--recover-id <journal-key> --allow-pilot-recovery` is needed to release a
  local retry, within the declared budget. An active lease cannot be stolen.
* Cancellation: a scratch-scoped `cancel.requested` marker prevents new wave
  launches and kills an active worker within polling bounds. Timeout kills
  the worker, marks retryable failure, and never grants closure.
* Proof: every output SHA-256 is recorded. Final receipt is signed with an
  ephemeral Ed25519 private key, and immediately verified. **Self-signature is
  not owner authentication**; trusted production key identity is absent.

## Native runner use

Use an exact trusted checkout, from the repository root:

```sh
python -m pip install cryptography==46.0.4
python -m unittest discover -s mission-control/gogreen/tests -p test_execution_adapter.py -v
python mission-control/gogreen/execution_adapter.py \
  --repo . \
  --plan mission-control/gogreen/samples/execution_plan_pilot_v1.json \
  --atlas mission-control/federation-atlas/PROCESS_LANES_v1.json \
  --tasks mission-control/gogreen/samples/task_bindings_pilot_v1.json \
  --policy mission-control/gogreen/samples/execution_policy_pilot_v1.json \
  --source-sha "$(git rev-parse HEAD)" --out /tmp/gogreen-executor \
  --allow-local-pilot
```

Repeat the same command against the same output directory to measure verified
idempotent reuse. To verify the receipt, add `--verify-receipt` while retaining
required CLI arguments; it verifies the ephemeral Ed25519 signature and does
not assert independent signature-trust or approval.

## Promotion gates (all held)

* Authentic owner-approved dispatch policy, independent identity binding,
  trusted external signer/public-key registry and key rotation.
* Shared distributed lease service with fencing tokens; SQLite leases only
  coordinate processes using the same runner filesystem.
* Permissioned remote agent/REX transport with hardened runtime sandbox,
  external network isolation, immutable artifact custody and cancellation.
* Independent security, governance/A10, rollback, PR head/main parity and
  control admission. QPS engineering approval remains wholly separate.

**Never infer:** a local pilot SUCCESS is a Crew dispatch, authorized GitHub
mutation, accepted root closure, or merge authorization. Production may not
inherit the pilot's `pilot_enabled` flag as permission to act remotely.
