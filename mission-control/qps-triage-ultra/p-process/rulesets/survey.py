import json,subprocess,collections,sys
def gh(p):
    r=subprocess.run(["gh","api",p],capture_output=True,text=True)
    if r.returncode: return {"_error":r.stderr.strip()[:160]}
    return json.loads(r.stdout) if r.stdout.strip() else None
out={}
for repo in ["GBOGEB/ABACUS","GBOGEB/CODEX","GBOGEB/cryoplant-project","GBOGEB/gg_MATH","GBOGEB/pipeline-automation-hub","GBOGEB/Q_engineering_tools"]:
    R=gh(f"repos/{repo}"); db=R.get("default_branch")
    br=gh(f"repos/{repo}/branches/{db}")
    rs=gh(f"repos/{repo}/rulesets") or []
    rsd=[gh(f"repos/{repo}/rulesets/{x['id']}") for x in rs] if isinstance(rs,list) else rs
    eff=gh(f"repos/{repo}/rules/branches/{db}")
    prs=gh(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=30")
    merged=[p for p in prs if isinstance(p,dict) and p.get("merged_at")][:12] if isinstance(prs,list) else []
    stat=collections.defaultdict(collections.Counter); apps={}
    for p in merged:
        cr=gh(f"repos/{p['base']['repo']['full_name']}/commits/{p['head']['sha']}/check-runs?per_page=100")
        for c in (cr or {}).get("check_runs",[]):
            stat[c["name"]][c["conclusion"] or c["status"]]+=1; apps[c["name"]]=c["app"]["slug"]
    wfs=gh(f"repos/{repo}/actions/workflows?per_page=100")
    out[repo]={"visibility":R.get("visibility"),"private":R.get("private"),"default_branch":db,"protected":(br or {}).get("protected"),
      "allow_auto_merge":R.get("allow_auto_merge"),"merge_methods":{k:R.get(k) for k in ["allow_squash_merge","allow_merge_commit","allow_rebase_merge"]},
      "delete_branch_on_merge":R.get("delete_branch_on_merge"),
      "rulesets":[{"id":x.get("id"),"name":x.get("name"),"enforcement":x.get("enforcement"),"target":x.get("target"),"rules":[r["type"] for r in x.get("rules",[])],"bypass":len(x.get("bypass_actors",[]))} for x in rsd if isinstance(x,dict) and "id" in x],
      "effective_rules":[r.get("type") for r in eff] if isinstance(eff,list) else eff,
      "workflows":(wfs or {}).get("total_count"),
      "merged_sampled":len(merged),
      "checks":{n:{"seen":sum(v.values()),**dict(v),"app":apps[n]} for n,v in sorted(stat.items(),key=lambda x:-sum(x[1].values()))}}
json.dump(out,open("survey.json","w"),indent=1)
for repo,v in out.items():
    print("==",repo,v["visibility"],"default",v["default_branch"],"protected",v["protected"],"rulesets",v["rulesets"],"workflows",v["workflows"],"merged sampled",v["merged_sampled"])
    good=[(n,c) for n,c in v["checks"].items() if c["seen"]>=max(3,v["merged_sampled"]*0.6)]
    for n,c in good[:14]: print("   ",n,{k:x for k,x in c.items() if k not in("app",)},c["app"])
