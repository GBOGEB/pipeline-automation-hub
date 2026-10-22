#!/usr/bin/env python3
"""Independent hosted Pages readback: HTTP status, file hashes, repeated convergence.

Invoke only after the existing Mission Control Pages publisher finishes. HTTP 200
alone cannot prove integrity. This does not promote governance/engineering credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

EXPECTED_ROUTE = "/pipeline-automation-hub/"
REQUIRED = ("index.html", "site-manifest.json", "g3p/index.html",
            "g3p/G3P_LIVE_SOURCES_v1.json")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_base(base: str):
    parsed = urlparse(base)
    if parsed.scheme != "https" or parsed.hostname != "gbogeb.github.io" or parsed.port is not None:
        raise ValueError("hosted endpoint outside approved GitHub Pages origin")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credential-bearing URLs forbidden")
    if parsed.path != EXPECTED_ROUTE or parsed.query or parsed.fragment:
        raise ValueError("unexpected Pages repository root path")
    return base


def get(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"Cache-Control":"no-cache","Pragma":"no-cache",
                                "User-Agent":"G3P-Pages-Parity/1.0"})
    with urlopen(req, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError("hosted response not HTTP 200")
        return response.read(), response.url


def verify(expected_dir: Path, base: str, *, repeat: int = 2,
           max_attempts: int = 8, wait_seconds: float = 5, fetch=get) -> dict:
    check_base(base)
    if not (1 <= repeat <= max_attempts <= 24):
        raise ValueError("invalid bounded repeat policy")
    root=expected_dir.resolve()
    manifest=json.loads((root/"site-manifest.json").read_text(encoding="utf-8"))
    if not (manifest.get("schema")=="codepurple.pages.readonly/v1"
            and manifest.get("merge_authorized") is False
            and manifest.get("security_waiver") is False):
        raise ValueError("unsafe expected Pages authority")
    records=[]
    for attempt in range(1,max_attempts+1):
        problems=[]
        matched=[]
        for relative in REQUIRED:
            path=(root/relative).resolve()
            if root not in path.parents or not path.is_file():
                raise ValueError("required candidate file absent or escapes public build: "+relative)
            expected=path.read_bytes()
            if relative!="site-manifest.json":
                declared=manifest.get("public_files_sha256",{}).get(relative)
                if declared != sha256(expected):
                    raise ValueError("candidate Pages file hash does not match portal manifest")
            url=urljoin(base,relative)
            try:
                content, final_url=fetch(url)
                parsed=urlparse(final_url)
                if parsed.hostname != "gbogeb.github.io" or parsed.scheme != "https":
                    raise ValueError("unexpected hosted redirect origin")
                if sha256(content)!=sha256(expected):
                    problems.append(relative+":SHA256_MISMATCH")
                else:
                    matched.append(relative)
            except Exception as exc:
                problems.append(relative+":"+type(exc).__name__)
        records.append({"attempt":attempt,"matched":matched,"errors":problems})
        consecutive=0
        for entry in reversed(records):
            if not entry["errors"] and len(entry["matched"])==len(REQUIRED):
                consecutive+=1
            else:
                break
        if consecutive>=repeat:
            return {"schema":"missioncontrol.pages.hosted_parity.v1",
                    "status":"PASS","source_git_sha":manifest["source_git_sha"],
                    "base_url":base,"proofs":records,"consecutive_matched":consecutive,
                    "published_route":urljoin(base,"g3p/index.html"),
                    "hosted_http_verified":True,"evidence_level":"HOSTED_HTTP_CONTENT_PARITY",
                    "merge_admission":"HOLD","authority_transfer":False}
        if attempt<max_attempts and wait_seconds:
            time.sleep(wait_seconds)
    return {"schema":"missioncontrol.pages.hosted_parity.v1",
            "status":"FAIL","source_git_sha":manifest["source_git_sha"],
            "base_url":base,"proofs":records,"consecutive_matched":0,
            "published_route":None,
            "hosted_http_verified":False,"evidence_level":"HOSTED_NOT_PROVEN",
            "merge_admission":"HOLD","authority_transfer":False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--expected-dir",type=Path,required=True)
    ap.add_argument("--base-url",required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    ap.add_argument("--repeat",type=int,default=2)
    ap.add_argument("--attempts",type=int,default=8)
    ap.add_argument("--wait",type=float,default=5)
    args=ap.parse_args()
    receipt=verify(args.expected_dir,args.base_url,
                   repeat=args.repeat,max_attempts=args.attempts,wait_seconds=args.wait)
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt["status"],
                      "consecutive_matched":receipt["consecutive_matched"],
                      "hosted_http_verified":receipt["hosted_http_verified"],
                      "published_route":receipt["published_route"]},sort_keys=True))
    return 0 if receipt["status"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
