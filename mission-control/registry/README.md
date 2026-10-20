# GBOGEB canonical registry (#529 G01)

**One SSOT.** `REPO_REGISTRY.yaml` covers every repository (90). Every other repo list (TOP21 roster, TOP7 census, live-census REPOS, red-trace core) is a legacy input or a derived view, and the registry reports their drift.

| File | What | Edit? |
|---|---|---|
| `REPO_REGISTRY.yaml` | Canonical: rank, score and its parts, class (CORE / SATELLITE / OWNED / UPSTREAM_FORK), memberships, JADE fields (priority, lane, owner role, MACH, technical need) | generated |
| `REPO_TIERS.yaml` | `all.*` and `owned.*` (non-fork) `top_3/7/14/21/50/100` + `bottom_3/7/14/21/50`, plus `legacy_list_drift` | generated |
| `BINARY_REGISTRY.yaml` | Binaries per core repo: count, bytes, by type, hierarchy (top dirs), depth spread, referenced/unreferenced, duplicate content groups | generated |
| `BINARY_TIERS.yaml` | `priority.*` and `size.*` top/bottom tiers over canonical contents (git O-ID) | generated |
| `BINARY_INDEX.json` | Every binary: repo, path, name, ext, **O-ID**, bytes, refs, copies, canonical, canonical_path | generated |
| `seed/ORG_LISTING_*.tsv` | Account listing the census ranks | input |

**Score (recomputable):** core federation 30 + TOP7 12 + TOP21 8 + JADE priority (P0 5, P1 3, P2 1) + recency (≤2 d 25, ≤7 d 20, ≤30 d 12, ≤90 d 6, ≤365 d 2) − fork 20 − archived 30.

**Binary priority:** 10 × min(text references, 10) + log2(bytes + 1). Rankings use only the canonical copy of each content (identical O-ID = identical bytes).

```bash
python mission-control/registry/census.py repos
python mission-control/registry/census.py binaries --repo pipeline-automation-hub=. --repo ABACUS=../abacus ...
python mission-control/registry/census.py get mission-control/registry/REPO_TIERS.yaml all.top_7
python mission-control/registry/census.py get mission-control/registry/BINARY_TIERS.yaml priority.top_14
```
