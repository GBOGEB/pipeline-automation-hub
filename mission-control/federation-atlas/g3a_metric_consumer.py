"""Read-only Mission Control consumer of source-bound gg_MATH G3A receipts.

Derived projection only; the existing Mission Control KPI taxonomy remains canonical.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

_SHA = re.compile(r"^[0-9a-f]{40}$")
_KPIS = frozenset({"QUEUE_P95", "EXACT_HEAD_PROOF_YIELD", "FIRST_RED_COUNT",
                    "ACCEPTED_RECEIPT_YIELD", "PREDICTION_VS_ACTUAL", "RUNNER_HEALTH"})

def canonical_sha(value):
    return isinstance(value, str) and _SHA.fullmatch(value) is not None

def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",",":"),
                                     allow_nan=False).encode()).hexdigest()

def consume(receipt: dict, taxonomy: dict, *, consumer_sha: str) -> dict:
    if not canonical_sha(consumer_sha):
        raise ValueError("consumer source SHA required")
    if taxonomy.get("schema") != "missioncontrol.phase02_kpi_taxonomy.v1":
        raise ValueError("unexpected canonical KPI registry")
    kpis = taxonomy.get("kpis", [])
    if frozenset(k.get("id") for k in kpis) != _KPIS or len(kpis) != 6:
        raise ValueError("six canonical KPI families must be preserved")
    if receipt.get("schema") != "gg_math.g3a_metric_bridge.v1":
        raise ValueError("unexpected gg_MATH receipt schema")
    if receipt.get("authority_transfer") is not False or receipt.get("merge_admission") != "HOLD":
        raise ValueError("provider authority boundary changed")
    if receipt.get("dispatch") != "NOT_LAUNCHED" or receipt.get("qps_acceptance") is not False:
        raise ValueError("dispatch or engineering authority cannot be claimed")
    if receipt.get("global_score") is not None or receipt.get("federation_coverage") is not None:
        raise ValueError("cross-repository scoring is unqualified")
    source = receipt.get("source_head")
    provider = receipt.get("provider_sha")
    if not canonical_sha(source) or not canonical_sha(provider):
        raise ValueError("unbound head")
    actual = digest({k:v for k,v in receipt.items() if k != "receipt_sha256"})
    if receipt.get("receipt_sha256") != actual:
        raise ValueError("altered or forged receipt digest")
    if receipt.get("source_repo") != "GBOGEB/ABACUS" or receipt.get("provider_repo") != "GBOGEB/gg_MATH":
        raise ValueError("unexpected producer repository")
    history = receipt.get("coverage_n_series")
    if not isinstance(history, list) or not history:
        raise ValueError("missing coverage history")
    if history[-1].get("head_sha") != source and receipt.get("current_coverage") is not None:
        raise ValueError("stale coverage promoted as current")
    out = {
      "schema": "missioncontrol.g3a_metric_view.v1",
      "owner": "GBOGEB/pipeline-automation-hub:mission-control",
      "read_only": True,
      "source_repo": receipt["source_repo"],
      "producer_repo": receipt["provider_repo"],
      "producer_sha": provider,
      "consumer_sha": consumer_sha,
      "upstream_receipt_sha256": receipt["receipt_sha256"],
      "taxonomy_semantic_sha256": digest(taxonomy),
      "canonical_kpi_count": 6,
      "new_kpi_registry_created": False,
      "historical_coverage": receipt["historical_coverage"],
      "current_coverage": receipt.get("current_coverage"),
      "forecast_error": None,
      "independent_root_closure": None,
      "dispatch": "NOT_LAUNCHED",
      "authority_transfer": False,
      "formal_credit_delta": 0,
      "qps_acceptance": False,
      "merge_admission": "HOLD"
    }
    out["view_sha256"] = digest(out)
    return out

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",required=True)
    p.add_argument("--taxonomy",required=True)
    p.add_argument("--consumer-sha",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    val=consume(json.loads(Path(a.receipt).read_text()),
                json.loads(Path(a.taxonomy).read_text()),
                consumer_sha=a.consumer_sha)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(val,indent=2,sort_keys=True)+"\n")
    print("G3A_READONLY_CONSUMER_PASS",val["view_sha256"])
if __name__ == "__main__":
    main()
