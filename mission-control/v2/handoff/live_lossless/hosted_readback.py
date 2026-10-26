#!/usr/bin/env python3
"""Independent postmerge public Pages SHA256 parity for Live Lossless.

This tests publication bytes, not ChatGPT session completeness, protected
branch policy, human reviewer approval or engineering admission.
"""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

FILES=("site-manifest.json","live-lossless/index.html","live-lossless/app.js",
       "live-lossless/style.css","live-lossless/snapshot.json",
       "live-lossless/manifest.json")
ORIGIN="gbogeb.github.io"
ROOT_PATH="/pipeline-automation-hub/"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def check_host(base):
    u=urlparse(base)
    if u.scheme!="https" or u.hostname!=ORIGIN or u.port is not None or u.path!=ROOT_PATH or u.query or u.fragment or u.username:
        raise ValueError("LIVE_LOSSLESS_HOST_GUARD: unapproved GitHub Pages root")

def read(url):
    with urlopen(Request(url,headers={"Cache-Control":"no-cache","Pragma":"no-cache",
            "User-Agent":"MissionControl-LiveLossless-Parity/1.0"}),timeout=15) as res:
        if res.status!=200:
            raise ValueError("HTTP "+str(res.status))
        return res.read(),res.url

def verify(root,base,repeat=2,attempts=8,wait=5,fetch=read):
    check_host(base)
    if not (1<=repeat<=attempts<=24) or wait<0:
        raise ValueError("invalid bounded readback policy")
    root=Path(root).resolve()
    site=json.loads((root/"site-manifest.json").read_text(encoding="utf-8"))
    live=json.loads((root/"live-lossless/manifest.json").read_text(encoding="utf-8"))
    if (site.get("schema")!="codepurple.pages.readonly/v1"
            or not re.fullmatch(r"[0-9a-f]{40}",site.get("source_git_sha",""))
            or site.get("merge_authorized") is not False
            or site.get("security_waiver") is not False
            or live.get("schema")!="missioncontrol.live_lossless.publication_manifest.v1"
            or live.get("authority_transfer") is not False
            or live.get("merge_admission")!="HOLD"):
        raise ValueError("unsafe source candidate")
    expected={}
    for rel in FILES:
        f=(root/rel).resolve()
        if not f.is_file() or root not in f.parents:
            raise ValueError("missing candidate "+rel)
        raw=f.read_bytes();expected[rel]=sha(raw)
        if rel!="site-manifest.json":
            if expected[rel]!=site.get("public_files_sha256",{}).get(rel):
                raise ValueError("site-manifest hash mismatch "+rel)
            inner=rel.replace("live-lossless/","")
            if expected[rel]!=live.get("files_sha256",{}).get(inner) and rel!="live-lossless/manifest.json":
                raise ValueError("live-lossless manifest hash mismatch "+rel)
    runs=[]
    for n in range(attempts):
        matched=[];failed=[]
        for relative in FILES:
            try:
                body,after=fetch(urljoin(base,relative))
                dst=urlparse(after)
                if dst.scheme!="https" or dst.hostname!=ORIGIN or dst.path!=ROOT_PATH+relative:
                    raise ValueError("redirect moved outside exact GitHub Pages route")
                if sha(body)!=expected[relative]:
                    failed.append(relative+":SHA256_MISMATCH")
                else:
                    matched.append(relative)
            except Exception as exc:
                failed.append(relative+":"+type(exc).__name__)
        runs.append({"attempt":n+1,"verified_files":matched,"errors":failed})
        consecutive=0
        for item in reversed(runs):
            if not item["errors"] and len(item["verified_files"])==len(FILES):
                consecutive+=1
            else:
                break
        if consecutive>=repeat:
            return {"schema":"missioncontrol.live_lossless.hosted_receipt.v1",
                    "state":"PASS","source_git_sha":site["source_git_sha"],
                    "url":urljoin(base,"live-lossless/index.html"),
                    "consecutive_full_matches":consecutive,
                    "source_level":"ACTUAL_PUBLIC_HTTP_SHA256_PARITY_ONLY",
                    "attempts":runs,"hosted_verified":True,
                    "merge_admission":"HOLD","authority_transfer":False}
        if n+1<attempts and wait:
            time.sleep(wait)
    return {"schema":"missioncontrol.live_lossless.hosted_receipt.v1",
            "state":"FAIL","source_git_sha":site["source_git_sha"],
            "url":None,"consecutive_full_matches":0,
            "source_level":"HOSTED_HTTP_NOT_ESTABLISHED",
            "attempts":runs,"hosted_verified":False,
            "merge_admission":"HOLD","authority_transfer":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--expected-dir",type=Path,required=True)
    p.add_argument("--base-url",required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--repeat",type=int,default=2)
    p.add_argument("--attempts",type=int,default=8)
    p.add_argument("--wait",type=float,default=5)
    a=p.parse_args()
    outcome=verify(a.expected_dir,a.base_url,a.repeat,a.attempts,a.wait)
    a.receipt.write_text(json.dumps(outcome,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"status":outcome["state"],"hosted_verified":outcome["hosted_verified"],
                      "matched":outcome["consecutive_full_matches"],
                      "url":outcome["url"]},sort_keys=True))
    return 0 if outcome["state"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
