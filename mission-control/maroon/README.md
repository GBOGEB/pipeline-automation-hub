# CODE MAROON runner

CODE_MAROON is the review- and security-debt programme declared in
`mission-control/federation-atlas/superstitch/SUPERSTITCH_TAXONOMY_v1.json`. The
2026-10-16 samples (`SEC-CODE-MAROON`, `P-CODE-MAROON` / `MAROON-FIRSTRED`) ask for a receipt that:
- deduplicates manifestations to roots;
- records closed, deferred and outstanding counts;
- keeps each scanner's provenance;
- closes nothing and has no merge authority.

`maroon.py` writes that receipt from GitHub's own alert APIs.

```bash
python mission-control/maroon/maroon.py fetch --owner GBOGEB --out <private dir>
python mission-control/maroon/maroon.py build --raw <private dir>/raw.json --out <private dir>
python -m unittest discover -s mission-control/maroon -p "test_*.py"
```

## What it reads

For every non-archived source repository of the owner (forks are skipped), the runner reads three
GitHub sources:

| Source | States read | How each state counts |
|---|---|---|
| Dependabot | open, fixed, dismissed, auto-dismissed | outstanding, closed, deferred, deferred |
| Code scanning (CodeQL, Bandit, Ruff, Semgrep, Trivy, ...) | open, fixed, dismissed | outstanding, closed, deferred |
| Secret scanning | open, resolved | outstanding; closed if revoked, otherwise deferred |

If a source can't be read, the runner records a coverage gap instead of a count:
- `not_enabled`: the scanner is switched off for that repository.
- `not_readable`: the caller's token can't read it.

Either way it is a gap, never zero.

## What it writes

| File | What | Where it may live |
|---|---|---|
| `raw.json` | Every alert as fetched | Private only |
| `MAROON_RECEIPT.json` | Coverage, totals, every root and every lane | Private only: names packages, rules, advisories and paths |
| `MAROON_FIXLIST.csv` | Outstanding roots, worst first, with the fix (for example `upgrade pillow to >= 11.0.0`) | Private only |
| `MAROON_LANES.md` | Lanes, worst first | Private only |
| `MAROON_PUBLIC.json` | Counts per repository: coverage, outstanding roots by severity, and manifestation dispositions | Safe to commit to a public repository |

## Roots

A root is one fix:
- **Dependabot:** one package, in one ecosystem, in one repository. Every advisory on it is a
  manifestation. The fix is to upgrade it to the highest first-patched version among its open
  advisories.
- **Code scanning:** one scanner rule in one repository. Every alert is a manifestation.
- **Secret scanning:** one secret type in one repository.

A root's severity is its worst outstanding manifestation.

## Lanes

A lane is one repository plus one source family:
- Dependabot: per ecosystem, for example `codex:deps-pip`.
- Code scanning: per tool, for example `codex:code-codeql`.
- Secrets: `codex:secrets`.

Two Dependabot lanes never edit the same manifest, so separate workers can take them in parallel.
Code-scanning lanes in one repository can touch the same source file; a lane's `shared_paths` names
those files so the work can be sequenced.

## Storage split

The public hub holds this runner and `MAROON_PUBLIC.json` only. The full receipt, fix list and lanes
go to a private repository, because they name vulnerable packages and file paths, including for private
repositories.
