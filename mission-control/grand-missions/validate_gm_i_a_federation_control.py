#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
CONTROL=ROOT/"mission-control"/"grand-missions"/"GM-I-A_FAST_HEAVY_FEDERATION_CONTROL_v0.1.yaml"
TOPOLOGY=ROOT/"mission-control"/"grand-missions"/"GM-I-A_FAST_HEAVY_FEDERATION_TOPOLOGY_v0.1.json"
OUT=ROOT/"mission-control"/"grand-missions"/"receipts"/"GM_I_A_FEDERATION_SENTINEL_RECEIPT.json"

EXPECTED_PROVIDER="47cc8dced9278d50714ac39ef0a2edab7458c6a0"
EXPECTED_ATTESTATION="132ff84a3502f5ce39d4698fa772e98f7e8fba8e52587e698e8ea419197e1398"

def main():
    c=yaml.safe_load(CONTROL.read_text())
    t=json.loads(TOPOLOGY.read_text())
    assert c["authority_transfer"] is False
    assert c["formal_credit_delta"]==0
    assert c["provider"]["source_head_sha"]==EXPECTED_PROVIDER
    assert c["attestation"]["content_sha256"]==EXPECTED_ATTESTATION
    assert t["provider"]["attestation_sha256"]==EXPECTED_ATTESTATION
    assert t["provider"]["state"]=="PASS"

    control_edges={e["id"]:e for e in c["federation_bridges"]}
    topo_edges={e["id"]:e for e in t["edges"]}
    assert set(control_edges)=={"GM-I-A-BRIDGE-DOW","GM-I-A-BRIDGE-KEB"}
    assert set(topo_edges)=={"DOW","KEB"}

    pairs=[
      ("GM-I-A-BRIDGE-DOW","DOW","GBOGEB/ABACUS"),
      ("GM-I-A-BRIDGE-KEB","KEB","GBOGEB/CODEX"),
    ]
    passed=waiting=red=0
    for cid,tid,repo in pairs:
        ce=control_edges[cid]
        te=topo_edges[tid]
        assert ce["consumer_repo"]==repo
        assert te["to"]==repo
        assert ce["compensates_other_bridge"] is False
        assert te["credit"]==ce["downstream_credit"]
        state=str(ce["runtime_state"])
        if state=="PASS":
            assert ce["downstream_credit"]>0
            passed+=1
        elif state in {"QUEUED","WAIT_RUNNER","BLOCKED"}:
            assert ce["downstream_credit"]==0
            waiting+=1
        else:
            assert ce["downstream_credit"]==0
            red+=1

    assert c["fanout"]["registered_consumers"]==2
    assert c["fanout"]["runtime_pass_consumers"]==passed
    assert c["fanout"]["runtime_wait_consumers"]==waiting
    assert "BRIDGE_RESULTS_ARE_NON_COMPENSATING" in c["authority_guards"]

    receipt={
      "schema":"missioncontrol.gm_i_a.federation_sentinel.v1",
      "status":"PASS",
      "provider_identity":"EXACT",
      "registered_edges":2,
      "runtime_pass_edges":passed,
      "runtime_wait_edges":waiting,
      "runtime_red_edges":red,
      "authority_transfer":False,
      "formal_credit_delta":0,
      "invariants":[
        "WAIT_OR_BLOCKED_EDGE_CREDIT_ZERO",
        "BRIDGES_NON_COMPENSATING",
        "EXACT_PROVIDER_ATTESTATION",
        "DOW_AND_KEB_DISTINCT"
      ]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")

if __name__=="__main__":
    main()
