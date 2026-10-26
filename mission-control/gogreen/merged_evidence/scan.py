#!/usr/bin/env python3
"""Read-only GoGREEN merged-head check census. A merged PR is not a green PR."""
import argparse, csv, hashlib, json, os, pathlib, urllib.request
from collections import Counter

BAD = {"failure","timed_out","action_required","startup_failure"}
OTHER = {"cancelled","skipped","neutral","stale"}

def classify(pr, runs, total):
    assert pr.get("merged_at") and len(pr["head"]["sha"]) == 40
    head=pr["head"]["sha"]
    seen=set(); counts=Counter(); debt=[]
    for r in runs:
        if r.get("head_sha") != head:
            raise ValueError("run source SHA differs from merged PR head")
        key=(r["id"],r.get("run_attempt",1))
        if key in seen:
            raise ValueError("duplicate native run/attempt")
        seen.add(key)
        if r.get("status") != "completed":
            state="pending"
        else:
            c=r.get("conclusion")
            state="failure" if c in BAD else c if c in OTHER else "success" if c=="success" else "unknown"
        counts[state]+=1
        if state in ("failure","cancelled","unknown"):
            debt.append({"run_id":r["id"],"attempt":r.get("run_attempt",1),
               "workflow":r.get("name"),"classification":state,
               "first_red":"NOT_FETCHED","source_head_sha":head,
               "url":r.get("html_url"),"root_closure_credit":0})
    complete=(total==len(runs))
    status=("INCOMPLETE_PAGE" if not complete else
            "NO_RUN_EVIDENCE" if not runs else
            "MIXED_OR_RED" if any(counts[z] for z in ("failure","cancelled","unknown")) else
            "PENDING" if counts["pending"] else
            "PARTIAL_TERMINAL" if any(counts[z] for z in ("skipped","neutral","stale")) else
            "ALL_OBSERVED_SUCCESS")
    return {"number":pr["number"],"title":pr.get("title"),"head_sha":head,
      "merge_commit_sha":pr.get("merge_commit_sha"),"merged_at":pr["merged_at"],
      "run_count":len(runs),"api_total":total,"complete":complete,
      "states":dict(counts),"verdict":status,"everred_candidates":debt,
      "required_checks_verified":False,"security_verified":False,
      "formal_root_closure_credit":0,"merge_authorized":False}

def request(root, token, path):
    req=urllib.request.Request(root+path,headers={
      "Accept":"application/vnd.github+json","Authorization":"Bearer "+token,
      "User-Agent":"GoGREEN-TOP21-Merged-Census","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.load(response)

def execute(roster,token,limit):
    if len(roster)!=21 or len(set(roster))!=21:
        raise ValueError("TOP21 requires 21 unique owner/repo entries")
    result=[]
    for repo in roster:
        if not repo.startswith("GBOGEB/"):
            raise ValueError("unexpected federation repository")
        root="https://api.github.com/repos/"+repo
        page=request(root,token,"/pulls?state=closed&sort=updated&direction=desc&per_page=100")
        if not isinstance(page,list):
            raise ValueError("invalid PR API response")
        merged=[x for x in page if x.get("merged_at")][:limit]
        records=[]
        for pr in merged:
            sha=pr["head"]["sha"]
            evidence=request(root,token,"/actions/runs?head_sha="+sha+"&per_page=100")
            if evidence.get("total_count") is None:
                raise ValueError("missing run count")
            entry=classify(pr,evidence.get("workflow_runs",[]),evidence["total_count"])
            entry["closed_pr_page_may_be_truncated"]=len(page)==100
            records.append(entry)
        result.append({"repo":repo,"sampled":len(records),"merged_prs":records,
                       "closed_pr_page_may_be_truncated":len(page)==100})
    return result

def output(repos,directory):
    target=pathlib.Path(directory);target.mkdir(parents=True,exist_ok=True)
    rows=[dict(repo=p["repo"],**x) for p in repos for x in p["merged_prs"]]
    debt=[dict(repo=r["repo"],pr=r["number"],**d) for r in rows for d in r["everred_candidates"]]
    stats={"schema":"gogreen.merged-top21.evidence.v1","observed_prs":len(rows),
       "observed_repositories":len(repos),
       "run_associations":sum(r["run_count"] for r in rows),
       "negative_run_associations":len(debt),
       "verdicts":dict(Counter(r["verdict"] for r in rows)),
       "global_success_rate":None,"formal_root_closures":0,
       "historical_complete":False,"admission_authorized":False}
    (target/"snapshot.json").write_text(json.dumps({"stats":stats,"repositories":repos},indent=2)+"\n",encoding="utf-8",newline="\n")
    with (target/"everred_candidates.csv").open("w",newline="",encoding="utf-8") as fh:
        cols=["repo","pr","run_id","attempt","workflow","classification","first_red",
              "source_head_sha","url","root_closure_credit"]
        writer=csv.DictWriter(fh,fieldnames=cols);writer.writeheader();writer.writerows(debt)
    with (target/"merged_pr_rollup.csv").open("w",newline="",encoding="utf-8") as fh:
        writer=csv.writer(fh)
        writer.writerow(["repository","merged_pr","source_head","observed_runs","status","page_complete"])
        for r in rows:writer.writerow([r["repo"],r["number"],r["head_sha"],r["run_count"],
                                       r["verdict"],r["complete"]])
    names=["snapshot.json","everred_candidates.csv","merged_pr_rollup.csv"]
    manifest={"schema":"gogreen.merged-top21.manifest.v1",
       "file_sha256":{n:hashlib.sha256((target/n).read_bytes()).hexdigest() for n in names},
       "merge_authorized":False}
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8",newline="\n")
    return stats

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--roster",required=True);p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=1)
    a=p.parse_args()
    if not 1<=a.limit<=10: raise SystemExit("bounded limit 1..10")
    token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:raise SystemExit("authenticated read-only token required")
    roster=json.loads(pathlib.Path(a.roster).read_text(encoding="utf-8"))
    print(json.dumps(output(execute(roster,token,a.limit),a.out),sort_keys=True))
if __name__=="__main__":main()
