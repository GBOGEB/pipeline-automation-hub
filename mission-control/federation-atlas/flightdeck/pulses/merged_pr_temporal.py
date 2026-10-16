"""Read-only merged PR history: identity-bound timeline, never admission."""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

SOURCE_SCHEMA = "code-purple.temporal.merged-pr.v1"
SHA = re.compile(r"^[a-f0-9]{40}$")


def validate(d):
    if d.get("schema") != SOURCE_SCHEMA: raise ValueError("schema")
    a = d.get("authority", {})
    if a.get("merge_admission") != "HOLD" or a.get("security_waiver") is not False or a.get("authority_transfer") is not False or a.get("accepted_root_closed") is not None or a.get("accepted_rex") is not None:
        raise ValueError("authority")
    ids = set()
    for e in d.get("merge_edges", []):
        key = (e.get("repo"), e.get("pr"))
        if key in ids: raise ValueError("duplicate PR")
        ids.add(key)
        if not all(isinstance(e.get(k), str) and SHA.fullmatch(e[k]) for k in ("head", "merge_sha")):
            raise ValueError("SHA")
        if e.get("destination_kind") not in ("MAIN", "FEATURE") or e.get("post_merge_run_qualification") is not None:
            raise ValueError("unqualified post merge")
        if not str(e.get("merged_at", "")).endswith("Z"): raise ValueError("timestamp")
        c = e.get("associated_runs", {})
        if set(c) != {"success","failure","cancelled","nonterminal"} or any(type(v) is not int or v < 0 for v in c.values()):
            raise ValueError("counts")
        if e.get("evidence_url") != "https://github.com/" + e["repo"] + "/pull/" + str(e["pr"]): raise ValueError("url")
    if not ids: raise ValueError("no observations")
    return d


def render(d, digest):
    validate(d)
    h = html.escape
    rows = []
    for e in sorted(d["merge_edges"], key=lambda r:(r["merged_at"],r["repo"],r["pr"])):
        counts=e["associated_runs"]
        rows.append("<tr><td>"+h(e["merged_at"])+"</td><td><a href='"+h(e["evidence_url"])+"'>"+h(e["repo"])+" #"+str(e["pr"])+"</a></td><td>"+h(e["destination_kind"])+" · "+h(e["base"])+"</td><td><code>"+h(e["head"][:12])+"</code> → <code>"+h(e["merge_sha"][:12])+"</code></td><td>"+str(counts["success"])+" PASS / "+str(counts["failure"])+" FAIL</td><td>UNKNOWN — push-run qualification absent</td></tr>")
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CODE PURPLE · merged PR temporal lineage</title><style>body{font:15px/1.5 system-ui;background:#0c1526;color:#e9f4ff;margin:0}main{max-width:1240px;margin:auto;padding:22px}a{color:#a4d5ff}section{background:#1a2840;padding:16px;border-radius:12px;margin:15px 0}table{border-collapse:collapse;width:100%;min-width:810px}th,td{text-align:left;padding:10px;border-bottom:1px solid #45566e}th{color:#d4e0f1}.scroll{overflow-x:auto}code{overflow-wrap:anywhere;color:#9ff3d9}.warning{color:#ffd29b}</style></head><body><main><p><a href="../index.html">← Mission Control</a></p><h1>Merged-PR temporal and recursive lineage</h1><p class="warning">Read-only projection; historical PR-head runs do not qualify post-merge main. UNKNOWN is not zero.</p><section><h2>Merge chronology</h2><div class="scroll"><table><thead><tr><th>Merge clock (UTC)</th><th>PR</th><th>Destination</th><th>Head → merge commit</th><th>PR-associated runs</th><th>Post-merge proof</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table></div></section><section><h2>Recursive evidence hooks</h2><p>PR_HEAD_CHANGED → RUN_TERMINAL → PR_MERGED → MAIN_ADVANCED → RECURSIVE_DOWNSTREAM_REPLAY → ROOT_RECURRED</p><p>Distinct clocks: source commit, run created, job started/completed, merge event, exact-main push run, recurrence. Missing clock fields remain null until obtained from native event/job/attempt APIs.</p><p>Same run identity = repository + run ID + attempt + job ID. Merges are graph edges, not automatically test successes. Re-run only the affected dependency descendants; preserve non-compensating A10, Safety, governance, security and review gates.</p></section><section><h2>Source lineage</h2><p>SHA-256: <code>""" + h(digest) + """</code></p><p><a href="snapshot.json">Frozen JSON</a> · <a href="https://github.com/GBOGEB/ABACUS/issues/1929">Canonical BD roots</a></p></section></main></body></html>"""


def build(source, out):
    source,out=Path(source),Path(out)
    raw=source.read_bytes()
    d=validate(json.loads(raw))
    out.mkdir(parents=True,exist_ok=True)
    (out/"snapshot.json").write_bytes(raw)
    (out/"index.html").write_text(render(d,hashlib.sha256(raw).hexdigest()),encoding="utf-8")
    receipt={"source_sha256":hashlib.sha256(raw).hexdigest(),"html_sha256":hashlib.sha256((out/"index.html").read_bytes()).hexdigest(),"merge_admission":"HOLD","post_merge_push_proof":None}
    (out/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    print(json.dumps(build(a.source,a.out),sort_keys=True))
