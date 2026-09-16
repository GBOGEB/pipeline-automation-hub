#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os
from datetime import UTC, datetime
from pathlib import Path

CLOCKS = ["k","t","a","wave","pulse","pr","run","release"]
FEATURES = [("T_K","K"),("p_Pa","Pa"),("h_J_kg","J/kg"),("s_J_kgK","J/(kg*K)"),("rho_kg_m3","kg/m^3"),("cp_J_kgK","J/(kg*K)")]

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",",":")).encode()).hexdigest()

def main():
    p=argparse.ArgumentParser(); p.add_argument("--contract",type=Path,required=True); p.add_argument("--atom",type=Path,required=True); p.add_argument("--out",type=Path,required=True); a=p.parse_args()
    c=json.loads(a.contract.read_text()); atom=json.loads(a.atom.read_text()); ts={x["id"]:x for x in c["propagation_targets"]}; s=c["semantic_invariants"]; r=c["generalisation_rules"]; k=c["kpi_contract"]
    checks={
      "cycle3": c["mission"]=="GM-I-B" and c["cycle"]==3 and c["cycle_ordinal"]=="3P#3",
      "atom": atom["keb_item_id"]=="KEB-ITEM-0002" and atom["object_type"]=="KEB_KNOWLEDGE_ATOM",
      "digest": atom["source_digest"]==c["source_atom"]["source_digest"]=="sha256:876c55c759de33392985f693f1735cdc0d38dda7d7b7a6c80ee80aee33fd8405",
      "authority_cap": atom["authority_cap"]==c["source_atom"]["authority_cap"]=="A3_SYNTHETIC_ONLY",
      "cycle2": atom["independent_numeric_reproduction"]["receipt_sha256"]==c["source_atom"]["cycle2_independent_receipt_sha256"] and atom["independent_numeric_reproduction"]["result"]=="PASS_INDEPENDENT_C01_C07_7_OF_7",
      "semantics": len(s)==6 and s["named_clocks"]==CLOCKS,
      "targets": set(ts)=={"T1_MISSIONCONTROL","T2_COOLPROP","T3_QPS_TRIAGE"},
      "feature_schema": ts["T2_COOLPROP"]["required_feature_dimension"]==6 and [(x["name"],x["unit"]) for x in ts["T2_COOLPROP"]["required_feature_schema"]]==FEATURES,
      "reuse_only": all(x["new_independent_math_implementation_allowed"] is False for x in ts.values()) and r["consumer_may_implement_duplicate_pca_kernel"] is False,
      "interpretation_guards": r["consumer_may_change_mathematical_semantics"] is False and r["feature_dimension_is_not_display_dimension"] is True and r["schema_mapping_alone_is_not_a_pca_result"] is True,
      "kpis": k["propagation_targets_total"]==3 and k["semantic_invariants_total"]==6 and k["child_targets_total"]==2 and k["propagation_coverage_target"]==1.0 and k["semantic_parity_target"]==1.0 and k["reuse_ratio_target"]==1.0 and k["duplicate_implementation_count_target"]==0 and k["authority_inversion_count_target"]==0 and k["propagation_depth_target"]==2,
      "authority": c["authority_transfer"] is False and c["formal_credit_delta"]==0 and c["hard_gate_compensation_allowed"] is False and atom["authority_guards"]["authority_transfer"] is False
    }
    ok=all(checks.values())
    out={"schema":"missioncontrol.gm_i_b.3p_ral_cycle3_contract_selfcheck_receipt.v1","created_utc":datetime.now(UTC).replace(microsecond=0).isoformat(),"status":"PASS_CONTRACT_SELF_CHECK" if ok else "DEFER_CONTRACT_SELF_CHECK","source_head":os.environ.get("GITHUB_SHA","LOCAL_UNBOUND"),"checks":checks,"kpi":{"propagation_targets_total":3,"propagation_targets_reached":1 if ok else 0,"propagation_coverage":1/3 if ok else 0.0,"semantic_parity":1.0 if ok else 0.0,"reuse_ratio":1.0 if ok else 0.0,"duplicate_implementation_count":0,"child_disposition_coverage":0.0,"propagation_depth":0,"authority_inversion_count":0 if checks["authority"] else 1},"authority_transfer":False,"formal_credit_delta":0,"next_action":"PROPAGATE_TO_T2_COOLPROP" if ok else "REPAIR_FIRST_RED"}
    out["contract_sha256"]=digest(c); out["atom_sha256"]=digest(atom); out["receipt_sha256"]=digest(out); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); print(json.dumps(out,indent=2,sort_keys=True)); return 0 if ok else 1
if __name__=="__main__": raise SystemExit(main())
