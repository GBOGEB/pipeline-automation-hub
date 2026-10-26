# H2 — Separate method backlog (not implemented by this H1 documentation PR)

| ID | Priority | Method evolution | Required DoV |
|---|---|---|---|
| MIP-01 | P0 | Append-only observation and transition ledger | Stable replay creates 0 new transitions |
| MIP-02 | P0 | Canonical root/occurrence registry | >=12 HTTP401 events stay one root |
| MIP-03 | P0 | Typed QPS dependency and authority graph | No accepted unlock without child + owner receipt |
| MIP-04 | P0 | Effective governed-admission veto | Missing independent review and blocked-RED proof veto |
| MIP-05 | P0 | Exact head/cohort/coverage comparator | Different source, config, test population, or denominator rejected |
| MIP-06 | P0 | Idempotent four-class alert reducer | Zero duplicate alerts on replay |
| MIP-07 | P1 | Source and binary successor integrity | Original/child member hashes and paths proven |
| MIP-08 | P1 | Queue, execution and acceptance clocks | Separate UTC times and measured population |
| MIP-09 | P1 | N-1/N/N+1 predictive REX | Forecast versus actual logged and bounded |
| MIP-10 | P1 | Adversarial/reverse-order tests | A->B->A, stale, cancelled, false green, wrong ZIP paths rejected |
| MIP-11 | P1 | Method Atlas/dashboard reader | One navigation spine, no shadow SSOT |
| MIP-12 | P2 | PCA/BT priority analytics | Comparable evidence; noncompensating safety and governance vetoes |

Required fixture negatives: parent merge without child receipt; green CI without eligible review; stale/cancelled/synthetic-merge head; duplicate HTTP 401; changed coverage denominator; #2091 merged with historical W163 failure; unmatched P0001/P0002; correct outer ZIP but wrong internal members; A→B→A; missing supplier originals/owner disposition. None should falsely produce QPS ACCEPTED.

Wave: N frozen history; N+1 replay; N+2 negative/adversarial; N+3 read-only live qualification; N+4 owner operational review. Current work is **H1 capture only**. Do not claim these implementation or test waves complete.
