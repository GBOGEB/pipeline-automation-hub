#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def fail(m): raise SystemExit("W285_3PR_FAIL: "+m)
def main():
  ap=argparse.ArgumentParser(); ap.add_argument("--receipt",required=True); ap.add_argument("--out"); a=ap.parse_args()
  d=json.loads(Path(a.receipt).read_text())
  r=d["rank"]; p=d["probe"]; g=d["guards"]
  checks={
    "schema":d.get("schema")=="missioncontrol.hm01.r3.dmaic_w285_3pr_refresh.v1",
    "authority":d.get("authority_transfer") is False and d.get("formal_credit_delta")==0,
    "rank_order":[x["order"] for x in r]==[1,2,3,4,5],
    "unique_findings":len({x["id"] for x in r})==5,
    "canonical_schema":p["exact_capsule_schema_authoritative"]=="gmi.r3_successor.exact_env_capsule.v2",
    "producer_ready":p["producer_state"]=="PASS_MERGED",
    "physical_wait":p["physical_bundle_state"]=="WAIT_RETURN" and p["first_red"]=="PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C",
    "release_hold":p["r3_release_production_dov"]=="WITHHELD" and p["r4"]=="BLOCKED_NOT_NEXT",
    "noncomp":g=={"issue_923":"RED_OWNER_ACTION","gt_bdq_0":"RED_BLOCKED_ON_923_INFRA_PREEXECUTION","runtime_gold":"WITHHELD","canonical_gt_credit":"NONE","r3_release_3p3_authorized":False}
  }
  if not all(checks.values()): fail(json.dumps({k:v for k,v in checks.items() if not v},sort_keys=True))
  out={"schema":"missioncontrol.hm01.r3.dmaic_w285_3pr_receipt.v1","status":"PASS_3PR_REFRESH_PROBE_RANK","checks":checks,"rank":r,"next":d["next"],"authority_transfer":False,"formal_credit_delta":0}
  payload=json.dumps(out,indent=2,sort_keys=True)+"\n"
  if a.out: Path(a.out).write_text(payload)
  print(payload,end="")
if __name__=="__main__": main()
