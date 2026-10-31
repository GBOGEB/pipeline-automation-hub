#!/usr/bin/env python3
"""Self-contained governed MissionControl launcher: consumes nav_model only."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import nav_model

HERE=Path(__file__).resolve().parent
TEMPLATE=HERE/"launchpad_template.html"
SHA=re.compile(r"[a-f0-9]{40}\Z")
SOURCE_HOLE="/*MC_NAV_SOURCE*/null"
DATA_HOLE="/*MC_NAV_DATA*/null"
FILES=("index.html","snapshot.json","federation.mmd","SIPOC.md")

def render(source,sha):
    if SHA.fullmatch(sha) is None:raise ValueError("MC_NAV_HOLD:exact publisher SHA")
    if source.get("schema")!="missioncontrol.launchpad.public_projection.v1" or source.get("admission")!="HOLD":raise ValueError("MC_NAV_HOLD:untrusted public payload")
    if source["policy"].get("authority_transfer") is not False or source["policy"].get("remote_dispatch_enabled") is not False:raise ValueError("MC_NAV_HOLD:false dispatch")
    html=TEMPLATE.read_text(encoding="utf-8")
    if html.count(DATA_HOLE)!=1 or html.count(SOURCE_HOLE)!=1:raise ValueError("MC_NAV_HOLD:template anchors")
    data=(json.dumps(source,ensure_ascii=True,separators=(",",":"),sort_keys=True,allow_nan=False)
          .replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026"))
    pub=json.dumps({"sha":sha,"authority_transfer":False,"hosted_http_verified":False})
    return html.replace(DATA_HOLE,data).replace(SOURCE_HOLE,pub)

def build(out,sha):
    out=Path(out)
    source=json.loads(nav_model.CONFIG.read_text(encoding="utf-8"))
    projection=nav_model.project(source)
    out.mkdir(parents=True,exist_ok=True)
    files={
      "index.html":render(projection,sha),
      "snapshot.json":json.dumps(projection,indent=2,sort_keys=True)+"\n",
      "federation.mmd":nav_model.mermaid(source),
      "SIPOC.md":nav_model.sipoc_md(source)
    }
    hashes={}
    for name in FILES:
        b=files[name].encode("utf-8")
        (out/name).write_bytes(b)
        hashes[name]=hashlib.sha256(b).hexdigest()
    manifest={"schema":"missioncontrol.launchpad.publication_manifest.v1",
              "source_head_sha":sha,"model_sha256":projection["input_sha256"],
              "files_sha256":hashes,"publisher":"EXISTING_ATLAS_PAGES_ONLY",
              "native_qa":None,"browser_qa":None,"hosted_http_verified":False,
              "authority_transfer":False,"security_waiver":False,
              "qps_engineering_acceptance":False,"merge_admission":"HOLD"}
    (out/"manifest.json").write_bytes((json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode("utf-8"))
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--sha",required=True)
    args=p.parse_args();m=build(args.out,args.sha)
    print("MISSIONCONTROL_LAUNCHPAD_BUILD=PASS",len(m["files_sha256"]),"admission=HOLD")
