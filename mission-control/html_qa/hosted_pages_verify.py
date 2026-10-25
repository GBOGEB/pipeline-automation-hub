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


MAX_PROBE_BYTES = 8_000_000
QUALIFY_SCHEMA = "missioncontrol.pages.hosted_qualification.v1"


def fetch_status(url: str):
    """Read-only GET that reports non-200 instead of raising.

    Returns (status, body, final_url); status/body are None when no HTTP answer
    was received (UNKNOWN, never zero)."""
    from urllib.error import HTTPError
    req = Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache",
                                "User-Agent": "G3P-Pages-Parity/1.0"})
    try:
        with urlopen(req, timeout=15) as response:
            body = response.read(MAX_PROBE_BYTES + 1)
            if len(body) > MAX_PROBE_BYTES:
                return response.status, None, response.url
            return response.status, body, response.url
    except HTTPError as exc:
        return exc.code, None, url
    except OSError:
        return None, None, url


def _page_parser():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "html_contract", Path(__file__).resolve().parent / "html_contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PageParser


def local_links(html: bytes, page_url: str, base: str) -> list[str]:
    """Same-site href/src targets of a served page, as absolute URLs (no fragment/query).

    Reuses html_contract.PageParser; external origins, mailto and pure in-page anchors
    are not host assets and are skipped."""
    parser = _page_parser()()
    parser.feed(html.decode("utf-8", errors="replace"))
    values = [a.get("href") for a in parser.anchors] + [a["value"] for a in parser.assets]
    out = set()
    for value in values:
        if not value or value.startswith("#"):
            continue
        target = urlparse(urljoin(page_url, value.strip()))
        if target.scheme != "https" or target.hostname != "gbogeb.github.io":
            continue
        if not target.path.startswith(EXPECTED_ROUTE):
            continue
        out.add(target._replace(query="", fragment="").geturl())
    return sorted(out)


def _relative(base: str, url: str) -> str:
    return urlparse(url).path[len(urlparse(base).path):]


def qualify(base: str, paths, *, expected=None, repeat: int = 2,
            follow_links: bool = True, fetch=fetch_status) -> dict:
    """Per-path hosted qualification: HTTP status, sha256, repeated convergence,
    optional parity against expected sha256 bytes and local link resolution.

    ``paths`` are base-relative ("" is the root). ``expected`` maps a path to the
    sha256 of the bytes that should be served (publisher manifest or git blob); a
    path without one keeps parity None (UNKNOWN). Read-only; no credit, no merge."""
    check_base(base)
    if not 2 <= repeat <= 4:
        raise ValueError("invalid bounded repeat policy")
    expected = expected or {}
    link_cache = {}

    def off_origin(final):
        parsed = urlparse(final or "")
        return bool(final) and (parsed.hostname != "gbogeb.github.io" or parsed.scheme != "https")

    def link_status(url):
        if url not in link_cache:
            status, _, final = fetch(url)
            link_cache[url] = None if off_origin(final) else status
        return link_cache[url]

    results = []
    for rel in paths:
        url = urljoin(base, rel)
        fetches = []
        bodies = []
        for _ in range(repeat):
            status, body, final = fetch(url)
            if off_origin(final):
                status, body = None, None
            ok = status == 200 and body is not None
            bodies.append(body if ok else None)
            fetches.append({"status": status,
                            "sha256": sha256(body) if ok else None,
                            "bytes": len(body) if ok else None})
        digests = {f["sha256"] for f in fetches}
        converged = (all(f["status"] == 200 for f in fetches) and len(digests) == 1
                     and None not in digests)
        served = fetches[0]["sha256"] if converged else None
        want = expected.get(rel)
        if want is None or not converged:
            parity = None
        else:
            parity = "MATCH" if served == want else "MISMATCH"
        record = {"path": rel, "url": url, "fetches": fetches, "converged": converged,
                  "served_sha256": served, "expected_sha256": want, "parity": parity,
                  "links": None}
        is_html = rel == "" or rel.endswith("/") or rel.endswith((".html", ".htm"))
        if follow_links and converged and is_html:
            record["links"] = [{"path": _relative(base, target), "status": link_status(target)}
                               for target in local_links(bodies[0], url, base)]
        results.append(record)

    def count(pred):
        return sum(1 for r in results if pred(r))

    link_rows = [link for r in results for link in (r["links"] or [])]
    summary = {
        "paths": len(results),
        "http_200_converged": count(lambda r: r["converged"]),
        "non_200_or_unstable": count(lambda r: not r["converged"]),
        "parity_match": count(lambda r: r["parity"] == "MATCH"),
        "parity_mismatch": count(lambda r: r["parity"] == "MISMATCH"),
        "parity_unknown": count(lambda r: r["parity"] is None),
        "links_checked": len({link["path"] for link in link_rows}),
        "links_200": len({link["path"] for link in link_rows if link["status"] == 200}),
        "links_broken": sorted({link["path"] for link in link_rows if link["status"] != 200}),
    }
    return {"schema": QUALIFY_SCHEMA, "base_url": base, "repeat": repeat,
            "results": results, "summary": summary,
            "merge_admission": "HOLD", "authority_transfer": False}


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
