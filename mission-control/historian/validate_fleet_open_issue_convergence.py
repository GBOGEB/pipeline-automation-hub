#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"mission-control/historian/FLEET_OPEN_ISSUE_CONVERGENCE_CURRENT_v1.json"

def main():
    d=json.loads(P.read_text())
    assert d["schema"]=="missioncontrol.fleet_open_issue_convergence.v1"
    assert d["authority_transfer"] is False
    assert d["formal_credit_delta"]==0
    repos=d["repositories"]
    assert len(repos)==7
    total=control=active=blocked=0
    seen_global=set()
    for repo,row in repos.items():
        c=set(row["control"]); a=set(row["active"]); b=set(row["blocked"])
        assert not (c&a or c&b or a&b), (repo,"overlap")
        assert len(c)+len(a)+len(b)==row["open_issues"], (repo,len(c),len(a),len(b),row["open_issues"])
        total+=row["open_issues"]; control+=len(c); active+=len(a); blocked+=len(b)
        for n in c|a|b:
            key=(repo,n)
            assert key not in seen_global
            seen_global.add(key)
        assert len(a)<=1, (repo,"active WIP cap")
    f=d["fleet"]
    assert (total,control,active,blocked)==(95,31,2,62)
    assert (f["open_issues"],f["control"],f["active"],f["blocked"])==(95,31,2,62)
    assert f["executable_frontier_width"]==2
    assert abs(f["control_share"]-31/95)<1e-10
    assert abs(f["active_share"]-2/95)<1e-10
    assert abs(f["blocked_share"]-62/95)<1e-10
    assert sum(len(row["active"]) for row in repos.values())==2
    assert repos["GBOGEB/cryoplant-project"]["open_issues"]==55
    assert len(repos["GBOGEB/cryoplant-project"]["blocked_breakdown"]["external_source_decision_return"])==32
    assert repos["GBOGEB/GEMINI"]["open_issues"]==2
    assert len(repos["GBOGEB/GEMINI"]["control"])==0
    assert repos["GBOGEB/gg_MATH"]["nested_queue"]["bd_total"]==6
    print("PASS_FLEET_OPEN_ISSUE_CONVERGENCE_95_31_2_62")

if __name__=="__main__":
    main()
