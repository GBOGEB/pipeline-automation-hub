#!/usr/bin/env python3
"""Fetch the public source refs actually named in the G3P manifest.

No mutable source truth is changed. Each ref, git SHA and copied JSON SHA is
recorded; this is a non-atomic cross-branch read, NOT native CI attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

REF = re.compile(r"(?!/)(?!.*\.\.)(?!.*//)[a-zA-Z0-9_./-]+\Z")
PATH = re.compile(r"mission-control/federation-atlas/[A-Za-z0-9_.-]+\.json\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")


def checked_run(args, cwd):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.PIPE).decode("utf-8").strip()


def validate(document: dict, wave: dict):
    if not (document.get("schema")=="missioncontrol.n3_continuation.v1"
            and document.get("mission",{}).get("repo")=="GBOGEB/pipeline-automation-hub"
            and document["mission"].get("id")=="CBD-GOLDEN-GRAPH-604"
            and document["mission"].get("wave")==wave["wave"]
            and document.get("authority_transfer") is False
            and document.get("policy",{}).get("security_waiver") is False
            and document.get("start_ordinal")==wave["start"]-1):
        raise ValueError("untrusted source identity or authority: "+wave["wave"])
    receipts=document.get("receipts",[])
    if len(receipts)!=3:
        raise ValueError("missing pulse receipts "+wave["wave"])
    for i,r in enumerate(receipts):
        if not (r.get("ordinal")==wave["start"]+i
                and r.get("merge_admission")=="HOLD"
                and r.get("authority_transfer") is False
                and SHA.fullmatch(r.get("output_source_sha",""))):
            raise ValueError("unsafe pulse "+wave["wave"])
        if i and r.get("input_source_sha")!=receipts[i-1]["output_source_sha"]:
            raise ValueError("intra-wave head drift "+wave["wave"])


def prepare(manifest_file: Path, repo_root: Path, output: Path, local_source: Path | None = None):
    manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
    if not (manifest.get("schema")=="missioncontrol.g3p.live_sources.v1"
            and manifest.get("repository")=="GBOGEB/pipeline-automation-hub"
            and manifest.get("mission_id")=="CBD-GOLDEN-GRAPH-604"
            and manifest.get("authority_transfer") is False
            and manifest.get("merge_admission")=="HOLD"):
        raise ValueError("unsafe Pages manifest")
    waves=manifest.get("waves",[])
    if not isinstance(waves,list) or not 1 <= len(waves) <=25:
        raise ValueError("bad wave count")
    output.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(manifest_file,output/manifest_file.name)
    evidence=[]
    for index,w in enumerate(waves):
        if not (w.get("start")==index*3+1 and w.get("end")==index*3+3
                and REF.fullmatch(w.get("ref",""))
                and PATH.fullmatch(w.get("path",""))):
            raise ValueError("unsafe manifest path/ref/ordinal")
        name=Path(w["path"]).name
        if local_source:
            raw=(local_source/name).read_bytes()
            ref_sha=None
            mode="LOCAL_SOURCE_COPY"
        else:
            checked_run(["git","fetch","--no-tags","--depth=1","origin","refs/heads/"+w["ref"]],repo_root)
            ref_sha=checked_run(["git","rev-parse","FETCH_HEAD"],repo_root)
            if not SHA.fullmatch(ref_sha):
                raise ValueError("invalid fetched source ref")
            raw=subprocess.check_output(["git","show",ref_sha+":"+w["path"]],cwd=repo_root)
            mode="GIT_REF_FETCH_SOURCE_READ"
        data=json.loads(raw)
        validate(data,w)
        dest=output/name
        dest.write_bytes(raw)
        evidence.append({"wave":w["wave"],"ref":w["ref"],"path":w["path"],"resolved_git_sha":ref_sha,
                         "sha256":hashlib.sha256(raw).hexdigest(),"pulse_count":len(data["receipts"]),
                         "source_class":mode,"native_attestation":False})
    result={"schema":"missioncontrol.g3p.qa_source_census.v1",
            "manifest_sha256":hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
            "sources":evidence,"all_ordinals_present":sum(x["pulse_count"] for x in evidence),
            "observation_class":"NONATOMIC_READ_ONLY_SOURCE_REPLAY",
            "merge_admission":"HOLD","authority_transfer":False}
    (output/"source-readback.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--local-source",type=Path)
    args=ap.parse_args()
    r=prepare(args.manifest,args.repo_root,args.out,args.local_source)
    print(json.dumps({"pulse_count":r["all_ordinals_present"],"source_count":len(r["sources"]),
                      "admission":"HOLD"},sort_keys=True))


if __name__=="__main__":
    main()
