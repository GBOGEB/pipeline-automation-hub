#!/usr/bin/env python3
"""Independent same-origin Pages readback for the JADE child of the existing publisher.

This script is only called after deploy-pages on exact MAIN. It cannot deploy,
change branch rules, authorize merges, or assert engineering acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SHA40=re.compile(r"^[a-f0-9]{40}$")
REQUIRED_JADE={"jade/index.html","jade/green.html","jade/jade.css","jade/jade.js",
 "jade/jade_data.js","jade/site-manifest.json","jade/snapshot.json","jade/publisher-receipt.json",
 "jade/top21_bd_queue.csv",
 "jade/burndown.html","jade/burndown.css","jade/burndown.js","jade/burndown-data.js",
 "jade/burndown.json","jade/burndown.csv","jade/burndown-manifest.json",
 "jade/eightpoint.html","jade/eightpoint.css","jade/eightpoint.js",
 "jade/eightpoint-data.js","jade/eightpoint.json","jade/eightpoint.csv","jade/eightpoint-manifest.json",
 "jade/redtrace.html","jade/redtrace-slides.html","jade/redtrace-slides.pdf","jade/redtrace-manifest.json"}
MAX_BYTES=2_000_000


def digest(b: bytes) -> str: return hashlib.sha256(b).hexdigest()


def base_url(url: str) -> str:
    p=urllib.parse.urlsplit(url)
    if not (p.scheme == "https" and p.netloc == "gbogeb.github.io" and
            p.path.rstrip("/") == "/pipeline-automation-hub" and not p.username and not p.password
            and not p.query and not p.fragment):
        raise ValueError("JADE_HOSTED_REFUSE_NONCANONICAL_ORIGIN")
    return "https://gbogeb.github.io/pipeline-automation-hub/"


def trusted_files(root: Path, head: str) -> dict[str, str]:
    if not SHA40.fullmatch(head or ""):
        raise ValueError("JADE_BAD_SOURCE_SHA")
    root=Path(root)
    portal=json.loads((root/"site-manifest.json").read_text(encoding="utf-8"))
    if not (portal.get("schema")=="codepurple.pages.readonly/v1"
            and portal.get("source_git_sha")==head
            and portal.get("merge_authorized") is False
            and portal.get("security_waiver") is False):
        # Publisher's v1 manifest has no security_waiver key; absent means it
        # must not claim waiver. If absent, None is accepted below.
        if not (portal.get("schema")=="codepurple.pages.readonly/v1"
                and portal.get("source_git_sha")==head
                and portal.get("merge_authorized") is False
                and portal.get("security_waiver") is None):
            raise ValueError("JADE_PUBLISHER_HEAD_OR_AUTHORITY")
    entries=portal.get("public_files_sha256",{})
    jade={rel:sha for rel,sha in entries.items() if rel.startswith("jade/")}
    if set(jade) != REQUIRED_JADE:
        raise ValueError("JADE_PUBLISHER_POPULATION_DRIFT")
    for rel, expected in jade.items():
        path=root/rel
        if not re.fullmatch("[a-f0-9]{64}",expected) or not path.is_file() or path.is_symlink() or digest(path.read_bytes())!=expected:
            raise ValueError("JADE_PUBLISHER_LOCAL_DIGEST_DRIFT: "+rel)
    receipt=json.loads((root/"jade/publisher-receipt.json").read_text(encoding="utf-8"))
    if not (receipt.get("schema")=="jade.temple.pages_bridge.v1"
            and receipt.get("presentation_head")==head
            and receipt.get("publisher")=="EXISTING_METHOD_ATLAS_PAGES_ONLY"
            and receipt.get("merge_admission")=="HOLD"
            and receipt.get("authority_transfer") is False
            and receipt.get("security_waiver") is False
            and receipt.get("hosted_http_verified") is False):
        raise ValueError("JADE_BRIDGE_UNSAFE_CLAIM")
    future=json.loads((root/"jade/burndown-manifest.json").read_text(encoding="utf-8"))
    if not (future.get("schema")=="jade.temple.burndown_manifest.v2"
            and future.get("merge_admission")=="HOLD"
            and future.get("security_waiver") is False
            and future.get("authority_transfer") is False
            and future.get("hosted_sha") is None
            and future.get("publisher")=="EXISTING_METHOD_ATLAS_PAGES_ONLY"):
        raise ValueError("JADE_BURNDOWN_UNSAFE_CLAIM")
    for rel, want in future.get("public_files_sha256", {}).items():
        if "jade/"+rel not in jade or jade["jade/"+rel]!=want:
            raise ValueError("JADE_BURNDOWN_BRIDGE_MANIFEST_MISMATCH")
    eight=json.loads((root/'jade/eightpoint-manifest.json').read_text(encoding='utf-8'))
    if not (eight.get('schema')=='jade.temple.eightpoint_manifest.v3'
            and eight.get('merge_admission')=='HOLD'
            and eight.get('security_waiver') is False
            and eight.get('authority_transfer') is False
            and eight.get('hosted_eightpoint_sha') is None
            and eight.get('publisher')=='EXISTING_METHOD_ATLAS_PAGES_ONLY'
            and eight.get('controlled_ids')==['J%02d'%i for i in range(1,9)]
            and eight.get('repo_count')==21):
        raise ValueError('JADE_EIGHT_UNSAFE_HOSTED_CLAIM')
    for rel,want in eight.get('public_files_sha256',{}).items():
        if 'jade/'+rel not in jade or jade['jade/'+rel]!=want:
            raise ValueError('JADE_EIGHT_HOSTED_MANIFEST_MISMATCH')
    red=json.loads((root/'jade/redtrace-manifest.json').read_text(encoding='utf-8'))
    if not (red.get('schema')=='jade.temple.redtrace_manifest.v1'
            and red.get('merge_authorized') is False
            and red.get('pdf',{}).get('file')=='redtrace-slides.pdf'
            and red.get('pdf',{}).get('deterministic') is False):
        raise ValueError('JADE_N8_UNSAFE_HOSTED_CLAIM')
    for rel,want in red.get('public_files_sha256',{}).items():
        if 'jade/'+rel not in jade or jade['jade/'+rel]!=want:
            raise ValueError('JADE_N8_HOSTED_MANIFEST_MISMATCH')
    return jade


def fetch_hosted(url: str, rel: str) -> bytes:
    if rel not in REQUIRED_JADE:
        raise ValueError("JADE_INVALID_RELATIVE_ASSET")
    endpoint=base_url(url)+urllib.parse.quote(rel, safe="/")
    req=urllib.request.Request(endpoint,headers={"Cache-Control":"no-cache","User-Agent":"JADE-CASTE-READONLY-PROOF/2"})
    with urllib.request.urlopen(req, timeout=14) as response:
        served=urllib.parse.urlsplit(response.geturl())
        if (served.scheme!="https" or served.netloc!="gbogeb.github.io" or response.status!=200
                or served.path!=urllib.parse.urlsplit(endpoint).path or served.query or served.fragment
                or served.username or served.password):
            raise ValueError("JADE_BAD_HOSTED_STATUS_OR_REDIRECT")
        b=response.read(MAX_BYTES+1)
        if len(b)>MAX_BYTES:
            raise ValueError("JADE_HOSTED_TOO_LARGE")
        return b


def verify(root: Path, url: str, head: str, *, repeat: int = 2, attempts: int = 8,
           wait: float = 5.0, fetcher=None):
    base_url(url)
    if not (2<=repeat<=3 and 1<=attempts<=12 and 0<=wait<=30):
        raise ValueError("JADE_BOUNDED_RETRY_CONTRACT")
    expected=trusted_files(root,head)
    fetcher=fetcher or fetch_hosted
    matched=[]
    for round_number in range(repeat):
        for attempt in range(1,attempts+1):
            mismatch=[];observations={}
            for rel in sorted(expected):
                try:
                    body=fetcher(url,rel)
                    value=digest(body)
                    observations[rel]=value
                    if value!=expected[rel]:mismatch.append(rel)
                except (OSError,urllib.error.URLError,ValueError) as exc:
                    mismatch.append(rel)
                    observations[rel]=f"ERROR:{type(exc).__name__}"
            if not mismatch:
                matched.append({"round":round_number+1,"attempt":attempt,"files":len(observations),"digest_checks":observations})
                break
            if attempt==attempts:
                raise ValueError("JADE_HOSTED_SHA_MISMATCH: "+", ".join(sorted(set(mismatch))))
            if wait:time.sleep(wait)
    return {"schema":"jade.temple.hosted_parity.v2","status":"PASS","head":head,
      "publisher":"EXISTING_METHOD_ATLAS_PAGES_ONLY", "source":"EXACT_MAIN_PUBLISHER_ARTIFACT",
      "evidence_level":"NATIVE_HOSTED_READBACK", "url":base_url(url)+"jade/burndown.html",
      "members_verified":len(expected),"repeat":repeat,"observations":matched,
      "checked_at_utc":datetime.now(timezone.utc).isoformat(),
      "engineering_acceptance":None,"authority_transfer":False,"merge_admission":"HOLD"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--expected-dir",required=True)
    p.add_argument("--base-url",required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--receipt",required=True)
    p.add_argument("--repeat",type=int,default=2)
    p.add_argument("--attempts",type=int,default=8)
    p.add_argument("--wait",type=float,default=5)
    a=p.parse_args()
    data=verify(Path(a.expected_dir),a.base_url,a.head,repeat=a.repeat,attempts=a.attempts,wait=a.wait)
    Path(a.receipt).write_text(json.dumps(data,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"status":"PASS","head":data["head"],"members":data["members_verified"],"rounds":len(data["observations"])}))
if __name__=="__main__":main()
