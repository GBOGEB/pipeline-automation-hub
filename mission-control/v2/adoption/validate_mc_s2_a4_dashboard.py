#!/usr/bin/env python3
from __future__ import annotations
import copy, json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
V2=ROOT/"mission-control"/"v2"
SURFACE=V2/"adoption"/"MC_S2_A4_DASHBOARD_TODO_SURFACE_20260927_v1.json"
STATUS=V2/"MC_MISSION_STATUS_CURRENT_v1.json"
CURRENT=V2/"MISSION_CONTROL_CURRENT_v2.json"

def load(p): return json.loads(p.read_text(encoding="utf-8"))

def validate(surface,status,current):
    errors=[]
    def req(v,m):
        if not v: errors.append(m)
    req(surface.get("mode")=="READ_ONLY_DERIVED_SURFACE","A4 mode drift")
    req(surface.get("authority_transfer") is False,"A4 authority transfer")
    req(surface.get("formal_credit_delta")==0,"A4 formal credit")
    req(surface.get("engineering_credit_delta")==0,"A4 engineering credit")
    adoption=current.get("adoption",{})
    req(adoption.get("active_wave")=="MC-A4_DASHBOARD_AND_TODO_SURFACES","A4 not active")
    req(adoption.get("a3_state")=="CONTROLLED_COMPLETE_TRUSTED_CONTROL_REPAIRED","A3 trusted disposition missing")
    req(adoption.get("a4_execution_allowed") is True,"A4 execution not governed-admitted")
    src_blob=subprocess.check_output(["git","hash-object",str(STATUS.relative_to(ROOT))],cwd=ROOT,text=True).strip()
    req(surface.get("source",{}).get("blob")==src_blob,"A4 source blob drift")
    rows={m["mission_id"]:m for m in status.get("missions",[])}
    proj={m["mission_id"]:m for m in surface.get("missions",[])}
    req(set(rows)==set(proj),"A4 mission-set drift")
    by_execution={}; by_health={}; by_mcov={}; todos=[]
    for mid,m in rows.items():
        p=proj.get(mid,{})
        ex=m.get("status",{}).get("execution","UNKNOWN")
        health=m.get("health",{}).get("signal","UNKNOWN")
        mcov=m.get("coverage",{}).get("maturity","UNKNOWN")
        by_execution[ex]=by_execution.get(ex,0)+1
        by_health[health]=by_health.get(health,0)+1
        by_mcov[mcov]=by_mcov.get(mcov,0)+1
        req(p.get("execution")==ex,f"{mid} execution drift")
        req(p.get("health")==health,f"{mid} health drift")
        req(p.get("progress")==m.get("progress"),f"{mid} progress drift")
        req(p.get("mcov")==mcov,f"{mid} MCOV drift")
        req(p.get("lifecycle")==m.get("lifecycle",{}).get("state","UNKNOWN"),f"{mid} lifecycle drift")
        req(p.get("todo_state")==m.get("todo",{}).get("state","UNKNOWN"),f"{mid} TODO state drift")
        req(p.get("todo_count")==len(m.get("todo",{}).get("items",[])),f"{mid} TODO count drift")
        req(p.get("authority_transfer") is False,f"{mid} authority transfer")
        for t in m.get("todo",{}).get("items",[]):
            todos.append((mid,t))
    summary=surface.get("summary",{})
    req(summary.get("missions")==len(rows),"A4 mission summary drift")
    req(summary.get("by_execution")==by_execution,"A4 execution summary drift")
    req(summary.get("by_health")==by_health,"A4 health summary drift")
    req(summary.get("by_mcov")==by_mcov,"A4 MCOV summary drift")
    req(summary.get("todo_total")==len(todos),"A4 TODO total drift")
    expected_todos={(mid,t.get("todo_id")):t for mid,t in todos}
    projected_todos={(t.get("mission_id"),t.get("todo_id")):t for t in surface.get("todos",[])}
    req(set(expected_todos)==set(projected_todos),"A4 TODO identity-set drift")
    for key,t in expected_todos.items():
        p=projected_todos.get(key,{})
        for fld in ("predicate","state","priority","crew_owner","runner_requirement","next_legal_transition","evidence_ref"):
            req(p.get(fld)==t.get(fld),f"A4 TODO field drift {key} {fld}")
    return errors

def self_test(surface,status,current):
    bad=copy.deepcopy(surface); bad["missions"][0]["health"]="GREEN" if bad["missions"][0]["health"]!="GREEN" else "RED"
    assert validate(bad,status,current)
    bad=copy.deepcopy(surface); bad["todos"]=bad["todos"][:-1]
    assert validate(bad,status,current)
    bad=copy.deepcopy(current); bad["adoption"]["a4_execution_allowed"]=False
    assert validate(surface,status,bad)
    bad=copy.deepcopy(surface); bad["authority_transfer"]=True
    assert validate(bad,status,current)

def main():
    surface,status,current=load(SURFACE),load(STATUS),load(CURRENT)
    errors=validate(surface,status,current)
    self_test(surface,status,current)
    print(json.dumps({"schema":"missioncontrol.v2.adoption.a4_dashboard_validation_receipt.v1","result":"PASS" if not errors else "FAIL","mission_rows":len(surface.get("missions",[])),"todo_rows":len(surface.get("todos",[])),"errors":errors,"authority_transfer":False,"formal_credit_delta":0,"engineering_credit_delta":0},indent=2))
    raise SystemExit(0 if not errors else 1)
if __name__=="__main__": main()
