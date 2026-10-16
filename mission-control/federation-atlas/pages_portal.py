#!/usr/bin/env python3
"""Build sanitized CODE PURPLE Pages portal from existing generated Atlas."""
import argparse, hashlib, html, json, re, shutil
from pathlib import Path

ALLOW={"index.html","code-purple.html","lane-process.html","lane-process.mmd","federation.svg","federation-latest.html","federation-wave-metrics.json","federation-latest.json","metrics.json","lane-process.json","code-health.html","code-health.json","code-health-dag.mmd","code-health-manifest.json","sideload-k8s.html","sideload-k8s.json","sideload-k8s.mmd","sideload-k8s.sha256.json","sideload-operator.html","sideload-operator-receipt.json","sideload-telemetry.json","sideload-telemetry.sha256.json"}
FLIGHT={"index.html","flightdeck.svg","census.json","bd_leaves.json","anchors.json","manifest.json"}
def build(atlas,out,sha):
    atlas,out=Path(atlas),Path(out)
    if not re.fullmatch("[a-f0-9]{40}",sha): raise ValueError("exact SHA required")
    if not (atlas/"index.html").is_file(): raise ValueError("Atlas output absent")
    out.mkdir(parents=True,exist_ok=True); hashes={}
    for src in atlas.iterdir():
        if src.is_file() and (src.name in ALLOW or src.suffix in {".svg",".mmd"}):
            dest=out/"atlas"/src.name; dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest); hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    for name in FLIGHT:
        src=atlas/"flightdeck"/name
        if src.is_file():
            dest=out/"atlas"/"flightdeck"/name;dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest);hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    for name in ["native_pulse_ledger.json","native_pulse_index.html"]:
        src=atlas/"native-pulse"/name
        if src.is_file():
            dest=out/"native-pulse"/("index.html" if name.endswith("index.html") else name)
            dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # Source-bounded BD / CHAR is a supporting view from this same Atlas build.
    for name in ("index.html", "snapshot.json", "manifest.json"):
        src=atlas/"bd-char"/name
        if src.is_file():
            dest=out/"bd-char"/name; dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # Preserve existing publication ownership; PR history is review-only.
    for name in ("index.html", "snapshot.json", "manifest.json", "native-refresh.json"):
        src=atlas/"pr-history"/name
        if src.is_file():
            dest=out/"pr-history"/name; dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    links=[("Method Atlas","atlas/index.html"),("Process and Mermaid","atlas/lane-process.html"),("CODE PURPLE controls","atlas/code-purple.html"),("Federation pulses","atlas/federation-latest.html"),("Flight Deck","atlas/flightdeck/index.html"),("Native pulse evidence","native-pulse/index.html"),("BD / CHAR temporal pulses","bd-char/index.html"),("Merged PR historical run chronology","pr-history/index.html"),("Kubernetes source inventory","atlas/sideload-k8s.html"),("Side-load proof and admission ladder","atlas/sideload-operator.html")]
    cards="".join('<a class="card" href="'+html.escape(u)+'">'+html.escape(t)+' ↗</a>' for t,u in links if (out/u).is_file())
    diagram=(atlas/"lane-process.mmd").read_text() if (atlas/"lane-process.mmd").is_file() else 'flowchart LR\n A["Source"] --> B["Native CI"] --> C["Read-only Atlas"] --> D["Owner gate"]'
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>CODE PURPLE | MissionControl</title><style>
body{background:#0d1728;color:#e9f2fc;font:16px/1.6 system-ui;margin:0}main{max-width:1120px;margin:auto;padding:28px}h1{font-size:clamp(2rem,5vw,3.5rem)}p{color:#b9cbe1}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}.card{display:block;padding:22px;background:#1b2b46;color:#c6eeff;border:1px solid #516988;border-radius:14px;text-decoration:none;font-weight:650}.card:hover,.card:focus-visible{outline:2px solid #7ecce5}.note{border-left:4px solid #7ecce5;background:#22354e;padding:14px;margin:25px 0}.mermaid{background:#f4f8ff;color:#13233b;border-radius:12px;overflow:auto;padding:12px}a{color:#9de5fa}code{overflow-wrap:anywhere}</style></head><body><main><p>MISSIONCONTROL / CODE PURPLE — GOVERNED REVIEW PROJECTION</p><h1>Engineering evidence flight deck</h1><p>Source-bound methods, Mermaid diagrams, QPS evidence, ABACUS/DOW and CODEX/KEB workflows, separated by scope and authority.</p><div class="note"><strong>Read-only:</strong> hosted HTML is not merge admission, a security waiver, native federation acceptance or QPS engineering approval. UNKNOWN remains UNKNOWN.</div><section><h2>Navigate evidence views</h2><div class="grid">'''+cards+'''</div></section><section><h2>Execution and control DAG</h2><pre class="mermaid">'''+html.escape(diagram)+'''</pre><p><a href="atlas/lane-process.mmd">Open Mermaid source</a> · <a href="atlas/federation.svg">Open native SVG</a></p></section><section><h2>Exact source</h2><code>'''+sha+'''</code><p><a href="site-manifest.json">Published file hash manifest</a> · <a href="https://github.com/GBOGEB/pipeline-automation-hub">Repository</a></p></section></main><script type="module">try{let m=await import("https://cdn.jsdelivr.net/npm/mermaid@11.11.0/dist/mermaid.esm.min.mjs");m.default.initialize({startOnLoad:true,securityLevel:"strict",theme:"neutral"})}catch(e){document.querySelectorAll(".mermaid").forEach(x=>x.setAttribute("aria-label","Mermaid source available in text form"))}</script></body></html>'''
    (out/"index.html").write_text(page,encoding="utf-8");hashes["index.html"]=hashlib.sha256((out/"index.html").read_bytes()).hexdigest()
    m={"schema":"codepurple.pages.readonly/v1","source_git_sha":sha,"public_files_sha256":hashes,"qps_owner_decision":"DEFER","merge_authorized":False,"security_waiver":False}
    (out/"site-manifest.json").write_text(json.dumps(m,indent=2,sort_keys=True)+"\n")
    return m
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--atlas",required=True);p.add_argument("--out",required=True);p.add_argument("--sha",required=True);a=p.parse_args()
    print(json.dumps({"public_files":len(build(a.atlas,a.out,a.sha)["public_files_sha256"])}))
