"""MIP read-only side-load / Kubernetes source GUI, part of existing Atlas artifact."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "SIDELOAD_K8S_SOURCE_v1.json"
ROLES = {"DOW": "ABACUS", "KEB": "CODEX", "QPS": "cryoplant-project"}
SHA40 = re.compile(r"^[a-f0-9]{40}$")
KINDS = {"K8S_STATIC", "K8S_API", "K8S_WORKLOAD", "DOCKER_COMPOSE", "LOCAL_EVIDENCE"}


def encode(data: object) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def validate(data: dict) -> None:
    if data.get("schema") != "missioncontrol.sideload_k8s.source.v1":
        raise ValueError("wrong side-load schema")
    if data.get("snapshot_class") != "HISTORICAL_SOURCE_ONLY_NOT_LIVE":
        raise ValueError("false live proof")
    a = data.get("adapters", [])
    if len(a) != 3 or {x.get("role") for x in a} != set(ROLES):
        raise ValueError("must have three repository adapters")
    for adapter in a:
        if adapter["state"] != "DRAFT" or not SHA40.fullmatch(adapter["head_sha"]):
            raise ValueError("candidate adapter promoted/invalid")
    transport = data.get("transport", {})
    if transport.get("state") != "DRAFT_NOT_ADMITTED":
        raise ValueError("transport claim promoted")
    if not SHA40.fullmatch(transport.get("contract_blob", "")):
        raise ValueError("invalid transport blob identity")
    rows = data.get("rows", [])
    if len(rows) != 8 or len({x.get("id") for x in rows}) != 8:
        raise ValueError("surface population drift")
    if {x.get("role") for x in rows} != set(ROLES):
        raise ValueError("a source owner missing")
    for x in rows:
        if x["source_repo"] != "GBOGEB/" + ROLES.get(x["role"], ""):
            raise ValueError("wrong source owner")
        if x["kind"] not in KINDS or not SHA40.fullmatch(x["source_sha"]):
            raise ValueError("kind/SHA mismatch")
        if not x["source_url"].startswith("https://github.com/" + x["source_repo"] + "/blob/"):
            raise ValueError("untrusted source locator")
        if x["state"] in ("PASS", "ACCEPT", "MERGED", "RUNTIME_VERIFIED"):
            raise ValueError("false admission state")
        if any(x[field] is not None for field in
               ("native_authenticated", "cluster_api_verified", "workload_verified")):
            raise ValueError("unsupported native/cluster proof")
    metrics = data["measurements"]
    if any(metrics[x] is not None for x in (
        "authenticated_four_hop_receipts", "real_k8s_runtime_sessions",
        "matched_coverage_delta")):
        raise ValueError("UNKNOWN imputed into runtime/coverage")
    if metrics["root_closures_credited"] != 0:
        raise ValueError("source GUI closed a root")
    gates = data["gates"]
    if gates != {"child": "DEFER", "release": "HOLD", "admission": "HOLD",
                 "edge_parent": "UNBOUND", "authority_transfer": False,
                 "engineering_credit_delta": 0, "formal_credit_delta": 0}:
        raise ValueError("gate or child authority promoted")


CSS = """html{background:#10121d;color:#edf0f8;font:15px system-ui,Arial,sans-serif}
body{max-width:1280px;margin:auto;padding:24px}a{color:#a7d3ff}h1{font-size:1.9rem}
p,small{color:#b8c5dd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
article,.panel{background:#1b2031;border:1px solid #45536c;padding:15px;border-radius:12px}
section{margin:28px 0}.bar{display:flex;gap:10px;flex-wrap:wrap}label{display:block}
input,select{padding:10px;background:#242b3f;border:1px solid #71839d;color:#fff;border-radius:7px}
code{overflow-wrap:anywhere}article h3{margin:5px 0}.pill{font-size:12px;color:#cae6ff}
[hidden]{display:none!important}@media(max-width:650px){body{padding:12px}.bar>label{width:100%}}
"""
HTML = Template("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CODE PURPLE · Side-load / Kubernetes</title><style>$css</style></head><body>
<header><p><a href="index.html">Mission Control Atlas</a> / DOW · KEB · QPS</p>
<h1>Side-loading, Kubernetes and execution evidence</h1>
<p>Historical source observation: $date. Read-only MIP control surface, never live cluster or acceptance proof.</p>
<div class="grid"><div class="panel"><strong>3</strong><p>Owning repositories</p></div>
<div class="panel"><strong>8</strong><p>Source-linked surfaces</p></div>
<div class="panel"><strong>UNKNOWN</strong><p>Runtime/cluster verified population</p></div>
<div class="panel"><strong>HOLD</strong><p>Engineering and merge admission</p></div></div></header>
<section><h2>Orchestration flow</h2><div class="grid">
<div class="panel">1. CENSUS<br><small>Exact repo SHA / available evidence</small></div>
<div class="panel">2. SIDE-LOAD<br><small>Sanitized metadata + optional original-byte hash</small></div>
<div class="panel">3. KEB<br><small>Source and semantic challenge; no self-approval</small></div>
<div class="panel">4. DOW / QPS<br><small>Runtime evidence → QPS child disposition</small></div></div></section>
<section><h2>Current pipeline assets and evidence</h2>
<div class="bar"><label>Repository <select id="repo"><option value="ALL">All</option>
<option value="DOW">DOW</option><option value="KEB">KEB</option><option value="QPS">QPS</option></select></label>
<label>Evidence type <select id="kind"><option value="ALL">All</option>$kinds</select></label>
<label>Search <input id="query" type="search" placeholder="W169, K8S, source path"></label></div>
<p id="count" aria-live="polite"></p><div class="grid">$cards</div></section>
<section><h2>Source-owned candidate PRs</h2><div class="grid">$prs</div></section>
<section><h2>Receipts and exact identity</h2><p>
<a href="sideload-k8s.json">Machine projection</a> ·
<a href="sideload-k8s.mmd">Declared dependency flow</a> ·
<a href="sideload-k8s.sha256.json">SHA256 manifest</a></p>
<p>Do not copy kubeconfig, Secrets, raw logs or bidder evidence into Git. Frontend never executes kubectl, merges PRs or updates engineering SSOT.</p></section>
<footer><small>Captured $date · input SHA256 $sha · source class historical · QPS DEFER · Kubernetes/runtime unknown · no formal credit.</small></footer>
<script>const cards=[...document.querySelectorAll('[data-row]')];
function show(){const r=document.getElementById('repo').value,k=document.getElementById('kind').value;
const q=document.getElementById('query').value.toLowerCase();let n=0;
cards.forEach(c=>{const ok=(r==='ALL'||c.dataset.repo===r)&&(k==='ALL'||c.dataset.kind===k)
&&c.textContent.toLowerCase().includes(q);c.hidden=!ok;if(ok)n++;});
document.getElementById('count').textContent=n+' / '+cards.length+' source-linked surfaces';}
['repo','kind','query'].forEach(id=>document.getElementById(id).addEventListener('input',show));show();</script>
</body></html>""")


def build(out: str | Path) -> dict:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    validate(data)
    source_sha = digest(encode(data))
    cards = []
    for x in data["rows"]:
        cards.append('<article data-row="1" data-repo="' + h(x["role"])
                     + '" data-kind="' + h(x["kind"]) + '"><small class="pill">'
                     + h(x["role"]) + " | " + h(x["kind"]) + "</small><h3>"
                     + h(x["title"]) + "</h3><p>" + h(x["state"])
                     + "</p><p>" + h(x["next"]) + "</p><p><code>"
                     + h(x["source_path"]) + "</code></p><small>Exact SHA: "
                     + h(x["source_sha"]) + '</small><p><a href="'
                     + h(x["source_url"]) + '" target="_blank" rel="noopener noreferrer">'
                     "Open canonical source</a></p></article>")
    prs = []
    for a in data["adapters"]:
        repo = ROLES[a["role"]]
        prs.append('<article><h3>' + h(a["role"]) + "</h3><p>"
                   + h(a["state"]) + '</p><a href="https://github.com/GBOGEB/'
                   + h(repo) + "/pull/" + str(a["pr"]) + '" target="_blank" '
                   'rel="noopener noreferrer">Open PR #' + str(a["pr"]) + "</a></article>")
    page = HTML.substitute(
        css=CSS, date=h(data["snapshot_date"]), sha=source_sha,
        kinds="".join('<option value="' + h(k) + '">' + h(k) + "</option>"
                      for k in sorted({a["kind"] for a in data["rows"]})),
        cards="".join(cards), prs="".join(prs),
    )
    metrics = {
        "schema": "missioncontrol.sideload_k8s.view.v1",
        "source_sha256": source_sha,
        "snapshot_class": data["snapshot_class"],
        "repo_owners": len(data["adapters"]),
        "source_surfaces": len(data["rows"]),
        "authenticated_runtime": None,
        "matched_coverage_gain": None, "root_closures": 0,
        "merge_admission": "HOLD", "authority_transfer": False,
        "rows": data["rows"], "gates": data["gates"],
    }
    mermaid = (
        "flowchart LR\n"
        '  D["DOW W74/W169 source"] -.-> K["KEB source challenge"]\n'
        '  K -.-> Q["QPS W165 child gate"]\n'
        '  Q -.-> M["MissionControl read-only Atlas"]\n'
        '  M -.->|"next pulse only"| D\n'
    )
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    derived = {
        "sideload-k8s.html": page.encode("utf-8"),
        "sideload-k8s.json": encode(metrics),
        "sideload-k8s.mmd": mermaid.encode("utf-8"),
    }
    for name, content in derived.items():
        (folder / name).write_bytes(content)
    manifest = {
        "schema": "missioncontrol.sideload_k8s.sha256.v1",
        "source_sha256": source_sha,
        "files": {name: digest(content) for name, content in sorted(derived.items())},
        "admission": "HOLD", "authority_transfer": False,
    }
    (folder / "sideload-k8s.sha256.json").write_bytes(encode(manifest))
    return metrics


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    x = p.parse_args()
    print(json.dumps(build(x.out), sort_keys=True))
