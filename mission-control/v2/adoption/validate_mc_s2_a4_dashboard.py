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
    req(surface.get("schema")=="missioncontrol.v2.adoption.dashboard_todo_surface.v1","A4 schema drift")
    req(surface.get("state")=="ACTIVE_INITIAL_READ_ONLY_PROJECTION","A4 state drift")
    req(surface.get("mode")=="READ_ONLY_DERIVED_SURFACE","A4 mode drift")
    req(surface.get("authority_transfer") is False,"A4 authority transfer")
    req(surface.get("formal_credit_delta")==0,"A4 formal credit")
    req(surface.get("engineering_credit_delta")==0,"A4 engineering credit")
    adoption=current.get("adoption",{})
    req(adoption.get("active_wave")=="MC-A4_DASHBOARD_AND_TODO_SURFACES","A4 not active")
    req(adoption.get("a3_state")=="CONTROLLED_COMPLETE_TRUSTED_CONTROL_REPAIRED","A3 trusted disposition missing")
    req(adoption.get("a4_execution_allowed") is True,"A4 execution not governed-admitted")
    src_blob=subprocess.check_output(["git","hash-object",str(STATUS.relative_to(ROOT))],cwd=ROOT,text=True).strip()
    source=surface.get("source",{})
    req(source.get("path")=="mission-control/v2/MC_MISSION_STATUS_CURRENT_v1.json","A4 source path drift")
    req(source.get("blob")==src_blob,"A4 source blob drift")
    req(source.get("mission_rows")==len(status.get("missions",[])),"A4 source mission_rows drift")
    rows={m["mission_id"]:m for m in status.get("missions",[])}
    proj={m["mission_id"]:m for m in surface.get("missions",[])}
    req(set(rows)==set(proj),"A4 mission-set drift")
    by_execution={}; by_health={}; by_mcov={}; todo_by_state={}; todos=[]
    for mid,m in rows.items():
        p=proj.get(mid,{})
        ex=m.get("status",{}).get("execution","UNKNOWN")
        health=m.get("health",{}).get("signal","UNKNOWN")
        mcov=m.get("coverage",{}).get("maturity","UNKNOWN")
        by_execution[ex]=by_execution.get(ex,0)+1
        by_health[health]=by_health.get(health,0)+1
        by_mcov[mcov]=by_mcov.get(mcov,0)+1
        req(p.get("mission_class")==m.get("mission_class"),f"{mid} mission_class drift")
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
            state=t.get("state","UNKNOWN")
            todo_by_state[state]=todo_by_state.get(state,0)+1
    summary=surface.get("summary",{})
    req(summary.get("missions")==len(rows),"A4 mission summary drift")
    req(summary.get("by_execution")==by_execution,"A4 execution summary drift")
    req(summary.get("by_health")==by_health,"A4 health summary drift")
    req(summary.get("by_mcov")==by_mcov,"A4 MCOV summary drift")
    req(summary.get("todo_total")==len(todos),"A4 TODO total drift")
    req(summary.get("todo_by_state")==todo_by_state,"A4 TODO state summary drift")
    expected_todos={(mid,t.get("todo_id")):t for mid,t in todos}
    projected_todos={(t.get("mission_id"),t.get("todo_id")):t for t in surface.get("todos",[])}
    req(set(expected_todos)==set(projected_todos),"A4 TODO identity-set drift")
    for key,t in expected_todos.items():
        p=projected_todos.get(key,{})
        for fld in ("predicate","state","priority","crew_owner","runner_requirement","next_legal_transition","evidence_ref"):
            req(p.get(fld)==t.get(fld),f"A4 TODO field drift {key} {fld}")
    presentation=surface.get("presentation_contract",{})
    for key in (
        "separate_status_progress_health_coverage",
        "mcov_not_code_coverage",
        "unknown_never_coerced_to_zero",
        "todo_predicates_preserved_verbatim",
        "dashboard_is_not_authority",
    ):
        req(presentation.get(key) is True,f"A4 presentation contract weakened: {key}")
    return errors

def self_test(surface,status,current):
    bad=copy.deepcopy(surface); bad["missions"][0]["health"]="GREEN" if bad["missions"][0]["health"]!="GREEN" else "RED"
    assert validate(bad,status,current)
    bad=copy.deepcopy(surface); bad["todos"]=bad["todos"][:-1]
    assert validate(bad,status,current)
    bad=copy.deepcopy(surface); bad["missions"][0]["mission_class"]="WRONG"
    assert validate(bad,status,current)
    bad=copy.deepcopy(surface); bad["summary"]["todo_by_state"]={}
    assert validate(bad,status,current)
    bad=copy.deepcopy(surface); bad["source"]["mission_rows"]=0
    assert validate(bad,status,current)
    bad=copy.deepcopy(surface); bad["presentation_contract"]["dashboard_is_not_authority"]=False
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
