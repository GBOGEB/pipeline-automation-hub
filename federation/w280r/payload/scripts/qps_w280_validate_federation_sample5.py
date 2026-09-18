#!/usr/bin/env python3
"""Fail-closed validator for W280R Federation Sample #5 authoritative return."""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTROL=ROOT/"controls/QPS_W280_FEDERATION_SAMPLE5_CURRENT_v0.1.json"
MATRIX=ROOT/"triage/w280/QPS_W280_SAMPLE5_FEATURE_MATRIX_ACCEPTED_v0.2.json"
RUNTIME=ROOT/"triage/w280/QPS_W280_FEDERATION_RUNTIME_CONTROL_v0.2.json"
BT=ROOT/"triage/w280/QPS_W280_BT_COUNTEROUTCOME_SEARCH_v0.2.json"
CENSUS=ROOT/"triage/w280/QPS_W280_GOVERNED_SURFACE_CENSUS_v0.2.json"

def load(p): return json.loads(p.read_text(encoding="utf-8"))

def validate():
    c,m,r,b,f=map(load,[CONTROL,MATRIX,RUNTIME,BT,CENSUS])
    assert c["wave"]=="W280R"
    assert c["state"]=="AUTHORITATIVE_RETURN_ACCEPTED"
    assert c["measurement"]=={
      "breadth":{"numerator":15,"denominator":15,"value":1},
      "depth":{"numerator":8,"denominator":8,"value":1},
      "penetration":1
    }
    assert c["accepted_bounded_samples"]==5
    assert c["known_sample_set_denominator"]==5
    assert len(m["rows"])==5 and all(x["accepted_sample"]==1 for x in m["rows"])
    assert m["measured_n5"]["state"]=="MEASURED_SMALL_N_N5_PC1_PERSISTS_PC2_UNSTABLE"
    ev=m["measured_n5"]["explained_variance_ratio"]
    assert abs(ev[0]-0.618903181)<1e-9
    assert abs(ev[1]-0.307076472)<1e-9
    assert abs(m["measured_n5"]["pc1_loading_congruence_abs_n4_to_n5"]-0.972259128)<1e-9
    assert abs(m["measured_n5"]["pc2_loading_congruence_abs_n4_to_n5"]-0.257532074)<1e-9

    q=r["exact_consumer"]
    assert q["pr"]==48
    assert q["pr_head_run"]["run_id"]==35341670931
    assert q["pr_head_run"]["result"]=="PASS_EXACT_6_OF_6_VALIDATOR_TESTS"
    assert q["merge"]=="107602529e5f31e4efc63e0cbf81a46752bc98f3"
    assert q["main_repeat"]["run_id"]==35342972343
    assert q["main_repeat"]["job_id"]==105592900839
    assert q["main_repeat"]["hosted_runner"] is True
    assert q["main_repeat"]["result"]=="PASS_EXACT_6_OF_6_VALIDATOR_TESTS_DISTINCT_MAIN_REPEAT"
    assert r["native_source_runtime"]["state"]=="WITHHELD_INFRA_PREEXECUTION_REX_006"
    assert r["native_source_runtime"]["compensated"] is False

    assert b["repair_component"]["reverse_or_tie_or_direct_cross_repair_found"] is False
    assert b["repair_component"]["finite_unregularized_mle"] is False
    assert b["separate_allocation_component"]["observed_pairs"]==12
    assert b["separate_allocation_component"]["single_cell_wins"]==8
    assert b["separate_allocation_component"]["paired_cell_wins"]==4
    assert b["separate_allocation_component"]["finite_two_node_unregularized_mle"] is True
    assert abs(b["separate_allocation_component"]["mle_strength_ratio_single_to_paired"]-2.0)<1e-12
    assert b["separate_allocation_component"]["bridge_to_repair_component"] is False
    assert b["global_state"]=="WITHHELD_DISCONNECTED_HETEROGENEOUS_COMPARISON_GRAPH"

    assert f["accessible_repository_universe_total"]==83
    assert f["classification_complete"] is True
    assert len(f["rows"])==83
    assert len({x["repo"] for x in f["rows"]})==83
    assert f["denominator"]["governed_surface_denominator"]==12
    credited=[x for x in f["rows"] if x["denominator_credit"]==1]
    assert len(credited)==12
    assert len({x["surface"] for x in credited})==12
    assert f["global_fleet_penetration"] is None
    assert c["fleet_census"]["governed_surface_denominator"]==12
    assert c["fleet_census"]["global_fleet_penetration"] is None
    assert all(v==0 for v in c["formal_credit_delta"].values())
    assert c["authority_transfer"] is False
    return {
      "schema":"qps-w280r-authoritative-return-validation/v0.2",
      "wave":"W280R",
      "result":"PASS_AUTHORITATIVE_RETURN_PAYLOAD",
      "sample5_accepted":True,
      "accepted_bounded_samples":5,
      "breadth":1.0,"depth":1.0,"penetration":1.0,
      "pca_state":m["measured_n5"]["state"],
      "repair_bt":b["repair_component"]["state"],
      "allocation_bt":b["separate_allocation_component"]["state"],
      "global_bt":b["global_state"],
      "accessible_repositories":83,
      "governed_surface_denominator":12,
      "global_fleet_penetration":None,
      "formal_credit_delta":0,
      "authority_transfer":False
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out"); a=ap.parse_args()
    r=validate(); t=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.out: Path(a.out).write_text(t,encoding="utf-8")
    print(t,end=""); return 0

if __name__=="__main__": raise SystemExit(main())
