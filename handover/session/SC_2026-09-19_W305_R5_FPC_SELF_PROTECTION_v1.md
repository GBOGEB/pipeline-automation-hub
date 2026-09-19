# W305-R5 First-Pass Closure self-protection handover

Date: 2026-09-19
Tracking: pipeline-automation-hub#314
Parent: pipeline-automation-hub#304
Consumer held behind gate: cryoplant-project#1550
Authority transfer: false
Formal credit delta: 0

## Observed first-reds burned

1. Allowlisted proof workflow was trusted by repo/name/path while its implementation remained PR-mutable.
2. Auto-merge cleanup only ran when the evaluator step itself failed.
3. Missing/invalid policy could escape the normal machine-readable failure receipt path.

## R5 repair

- Proof workflow identity now requires the allowlisted workflow content at candidate head to equal the same path at PR base SHA.
- Cross-repo proof identity is withheld until an explicit trust contract exists.
- PR number is resolved before fallible proof steps.
- Checkout, unit tests and evaluator are individually observed.
- Missing evaluator output synthesizes a deterministic FAIL receipt.
- Auto-merge disable executes under always() whenever the gate has not proven success.
- Final workflow step fails closed unless PR resolution, checkout, tests and evaluator all succeed.
- Policy load errors and unexpected admission exceptions are normalized into FAIL receipts.

## Fault matrix

Required exact-head proof includes:
- clean canonical evaluation PASS;
- mutated allowlisted workflow FAIL;
- missing policy FAIL;
- invalid policy JSON FAIL;
- missing allowlist FAIL;
- failed proof run FAIL;
- wrong-head proof FAIL;
- stale PR receipt FAIL;
- spoofed/incomplete Codex review FAIL;
- exact-head Codex finding FAIL.

## Promotion rule

Do not merge the R5 PR until:
1. First-Pass Closure Proof is completed/success on exact head;
2. PR body binds that exact-head run;
3. Codex review summary is Completed on exact head;
4. no exact-head Codex COMMENTED finding remains;
5. First-Pass Closure Gate is PASS.

After merge:
- #314 may close as DONE;
- #304 may close only if the parent objective is satisfied by the merged R5 repair;
- cryoplant-project#1550 may transition BLOCKED_DEPENDENCY -> EXECUTE_NOW and pin the exact R5 merge SHA.

Owner-side required-status/ruleset remains defense in depth and is not claimed by repository code alone.
