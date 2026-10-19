#!/usr/bin/env python3
"""Build sanitized CODE PURPLE Pages portal from existing generated Atlas."""
import argparse, hashlib, html, json, re, shutil
from pathlib import Path

ALLOW={"index.html","code-purple.html","code-purple.json","lane-process.html","lane-process.mmd","federation.svg","federation-latest.html","federation-wave-metrics.json","federation-latest.json","metrics.json","lane-process.json","code-health.html","code-health.json","code-health-dag.mmd","code-health-manifest.json","sideload-k8s.html","sideload-k8s.json","sideload-k8s.mmd","sideload-k8s.sha256.json","sideload-operator.html","sideload-operator-receipt.json","sideload-telemetry.json","sideload-telemetry.sha256.json"}
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
    # The P3 worker view is a supporting projection within the same Pages build.
    for name in ("index.html", "observed.json", "worker-plan.json", "manifest.json"):
        src=atlas/"worker-devkit"/name
        if src.is_file():
            dest=out/"worker-devkit"/name;dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # Canonical input-bound recursive SIPOC review; no new Pages publisher.
    for name in ("index.html", "snapshot.json", "manifest.json"):
        src=atlas/"federation-home"/name
        if src.is_file():
            dest=out/"federation-home"/name; dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # Execution Atlas is a derived child of this existing publisher. The shared
    # verifier checks every member and current source byte before packaging.
    execution_source = atlas / "orchestration"
    if execution_source.exists():
        import importlib.util
        checker_path = Path(__file__).resolve().parent / "orchestration" / "main.py"
        spec = importlib.util.spec_from_file_location("execution_atlas_packaging", checker_path)
        if spec is None or spec.loader is None:
            raise ValueError("execution Atlas verifier unavailable")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        receipt = checker.verify_bundle(execution_source, sha,
                                        source_root=Path(__file__).resolve().parents[2])
        for name in [*receipt["files_sha256"], "manifest.json"]:
            source = checker.safe_path(execution_source, name)
            dest = out / "orchestration" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            hashes[str(dest.relative_to(out))] = hashlib.sha256(dest.read_bytes()).hexdigest()
        # Recheck the copied child as well: source verification alone cannot
        # detect a copy-time mutation before the parent seals its public hashes.
        checker.verify_bundle(out / "orchestration", sha,
                              source_root=Path(__file__).resolve().parents[2])
    # Single-owner Pages bridge: consume the approved G3P view in this existing
    # portal build. This is file packaging only; no new deployer or release gate.
    g3p_source=Path(__file__).resolve().parent
    g3p_html=g3p_source/"G3P_LIVE_LEDGER.html"
    g3p_manifest=g3p_source/"G3P_LIVE_SOURCES_v1.json"
    if g3p_html.exists() != g3p_manifest.exists():
        raise ValueError("incomplete G3P Pages source pair")
    if g3p_html.is_file() and g3p_manifest.is_file():
        source=json.loads(g3p_manifest.read_text(encoding="utf-8"))
        if not (source.get("schema")=="missioncontrol.g3p.live_sources.v1"
                and source.get("repository")=="GBOGEB/pipeline-automation-hub"
                and source.get("authority_transfer") is False
                and source.get("merge_admission")=="HOLD"):
            raise ValueError("G3P Pages source contract invalid")
        for src,name in ((g3p_html,"index.html"),(g3p_manifest,"G3P_LIVE_SOURCES_v1.json")):
            dest=out/"g3p"/name
            dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # Live Lossless is a generated sanitized consumer of the existing
    # closeout/GitHub provenance. It has no separate Pages publisher.
    live_allow = ("index.html", "app.js", "style.css", "snapshot.json", "manifest.json")
    live_source = atlas / "live-lossless"
    live_present = [name for name in live_allow if (live_source / name).is_file()]
    if live_present and len(live_present) != len(live_allow):
        raise ValueError("incomplete Live Lossless Pages source")
    if len(live_present) == len(live_allow):
        ll = json.loads((live_source / "manifest.json").read_text(encoding="utf-8"))
        state = json.loads((live_source / "snapshot.json").read_text(encoding="utf-8"))
        if not (ll.get("schema") == "missioncontrol.live_lossless.publication_manifest.v1"
                and ll.get("publisher") == "EXISTING_PAGES_ONLY"
                and ll.get("authority_transfer") is False
                and ll.get("security_waiver") is False
                and ll.get("merge_admission") == "HOLD"
                and state.get("schema") == "missioncontrol.live_lossless.dashboard.v1"
                and state.get("authority_transfer") is False
                and state.get("merge_admission") == "INDEPENDENT_HOLD"):
            raise ValueError("unsafe Live Lossless Pages projection")
        for name in live_allow:
            src = live_source / name
            if name != "manifest.json" and hashlib.sha256(src.read_bytes()).hexdigest() != ll.get("files_sha256", {}).get(name):
                raise ValueError("Live Lossless source hash mismatch: " + name)
            dest = out / "live-lossless" / name
            dest.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(src, dest)
            hashes[str(dest.relative_to(out))] = hashlib.sha256(dest.read_bytes()).hexdigest()
    # Mission rebuild: one owner portal; never an alternate Pages publisher.
    rebuild_allow = ("index.html", "graph.json", "graph.mmd", "manifest.json")
    rebuild_src = atlas / "mission-rebuild"
    rebuild_present = [n for n in rebuild_allow if (rebuild_src / n).is_file()]
    if rebuild_present and len(rebuild_present) != len(rebuild_allow):
        raise ValueError("partial Mission rebuild output")
    if len(rebuild_present) == len(rebuild_allow):
        receipt = json.loads((rebuild_src / "manifest.json").read_text(encoding="utf-8"))
        graph = json.loads((rebuild_src / "graph.json").read_text(encoding="utf-8"))
        if not (receipt.get("schema") == "missioncontrol.makeover.manifest.v1"
                and receipt.get("source_sha") == sha
                and receipt.get("published_by") == "EXISTING_METHOD_ATLAS_PAGES_ONLY"
                and receipt.get("merge_admission") == "HOLD"
                and receipt.get("security_waiver") is False
                and receipt.get("authority_transfer") is False
                and graph.get("source_sha") == sha
                and graph.get("gate", {}).get("merge_admission") == "HOLD"
                and graph.get("scheduler", {}).get("dispatch_authorized") is False):
            raise ValueError("unsafe Mission rebuild source")
        for name in rebuild_allow:
            src = rebuild_src / name
            if name != "manifest.json" and hashlib.sha256(src.read_bytes()).hexdigest() != receipt.get("files_sha256", {}).get(name):
                raise ValueError("Mission rebuild hash mismatch: " + name)
            dst = out / "mission-rebuild" / name
            dst.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(src, dst)
            hashes[str(dst.relative_to(out))] = hashlib.sha256(dst.read_bytes()).hexdigest()
    # Additive W2 read-only gg_MATH evidence inlay; no second publisher.
    w2_names = ("evidence.json", "evidence.html", "evidence-manifest.json")
    w2_root = atlas / "mission-rebuild"
    w2_present = [name for name in w2_names if (w2_root / name).is_file()]
    if w2_present and len(w2_present) != len(w2_names):
        raise ValueError("partial W2 MissionControl evidence output")
    if len(w2_present) == len(w2_names):
        w2_receipt = json.loads((w2_root / "evidence-manifest.json").read_text(encoding="utf-8"))
        w2_state = json.loads((w2_root / "evidence.json").read_text(encoding="utf-8"))
        if not (w2_receipt.get("schema") == "missioncontrol.makeover.w2_plotly_manifest.v1"
                and w2_receipt.get("source_sha") == sha
                and w2_receipt.get("publisher") == "EXISTING_METHOD_ATLAS_PAGES_ONLY"
                and w2_receipt.get("merge_admission") == "HOLD"
                and w2_receipt.get("security_waiver") is False
                and w2_receipt.get("authority_transfer") is False
                and w2_receipt.get("gg_math_kernel_duplicated") is False
                and w2_state.get("schema") == "missioncontrol.makeover.w2_native_observation.v1"
                and w2_state.get("source_head_sha") == sha
                and w2_state.get("governance", {}).get("merge_admission") == "HOLD"
                and w2_state.get("gg_math", {}).get("native_live_pulse_receipts_ingested") == 0
                and w2_state.get("fleet", {}).get("capacity_slots") is None
                and w2_state.get("unknown_burndown", {}).get("coverage", {}).get("covered_statements") is None):
            raise ValueError("unsafe W2 gg_MATH/Plotly bridge admission")
        if set(w2_receipt.get("member_sha256", {})) != {"evidence.json", "evidence.html"}:
            raise ValueError("W2 manifest population drift")
        for name in w2_names:
            src = w2_root / name
            if name != "evidence-manifest.json" and hashlib.sha256(src.read_bytes()).hexdigest() != w2_receipt["member_sha256"].get(name):
                raise ValueError("W2 evidence source hash mismatch: " + name)
            dst = out / "mission-rebuild" / name
            dst.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(src, dst)
            hashes[str(dst.relative_to(out))] = hashlib.sha256(dst.read_bytes()).hexdigest()
    # N3 consumes a scoped historical native run; Pages only mirrors verified bytes.
    n3_root = atlas / "mission-rebuild"
    n3_names = ("n3-metrics.html", "n3-metrics.json", "n3-manifest.json")
    n3_present = [name for name in n3_names if (n3_root / name).is_file()]
    if n3_present and len(n3_present) != len(n3_names):
        raise ValueError("partial N3 source-bound KPI output")
    if len(n3_present) == len(n3_names):
        n3_receipt = json.loads((n3_root / "n3-manifest.json").read_text(encoding="utf-8"))
        n3_state = json.loads((n3_root / "n3-metrics.json").read_text(encoding="utf-8"))
        if not (n3_receipt.get("schema") == "missioncontrol.n3.readonly_publisher_manifest.v1"
                and n3_receipt.get("presentation_sha") == sha
                and n3_receipt.get("producer_sha") == n3_state.get("producer_sha")
                and n3_receipt.get("publisher") == "EXISTING_METHOD_ATLAS_PAGES_ONLY"
                and n3_receipt.get("merge_admission") == "HOLD"
                and n3_receipt.get("authority_transfer") is False
                and n3_state.get("schema") == "missioncontrol.n3.scoped_native_kpi.v1"
                and n3_state.get("presentation_sha") == sha
                and n3_state.get("source_repo") == "GBOGEB/pipeline-automation-hub"
                and n3_state.get("authority", {}).get("merge_admission") == "HOLD"
                and n3_state.get("authority", {}).get("remote_dispatch") is False
                and n3_state.get("fleet_runner_capacity") is None
                and n3_state.get("owner_required_status_gate", {}).get("owner_installed") is None):
            raise ValueError("unsafe N3 KPI/REX publication promotion")
        if set(n3_receipt.get("member_sha256", {})) != {
                "n3-metrics.html", "n3-metrics.json"}:
            raise ValueError("N3 manifest member population drift")
        for name in n3_names:
            src = n3_root / name
            if name != "n3-manifest.json":
                if hashlib.sha256(src.read_bytes()).hexdigest() != n3_receipt["member_sha256"].get(name):
                    raise ValueError("N3 source member digest mismatch: " + name)
            dst = out / "mission-rebuild" / name
            dst.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(src, dst)
            hashes[str(dst.relative_to(out))] = hashlib.sha256(dst.read_bytes()).hexdigest()
    # W32 Global DoV: pack an existing-publisher-only, exact-head projection.
    # No second authority, no second Pages workflow, no GitHub status as proof.
    hub_allow = ("index.html", "ledger.json", "lineage.mmd", "manifest.json")
    hub_src = atlas / "convergence"
    hub_present = [n for n in hub_allow if (hub_src / n).is_file()]
    if hub_present and len(hub_present) != len(hub_allow):
        raise ValueError("partial Convergence Hub output")
    if len(hub_present) == len(hub_allow):
        hub_manifest = json.loads((hub_src / "manifest.json").read_text(encoding="utf-8"))
        hub_ledger = json.loads((hub_src / "ledger.json").read_text(encoding="utf-8"))
        if not (hub_manifest.get("schema") == "codepurple.convergence_hub.manifest.v1"
                and hub_manifest.get("presentation_head") == sha
                and hub_manifest.get("publisher") == "EXISTING_METHOD_ATLAS_PAGES_ONLY"
                and hub_manifest.get("merge_admission") == "HOLD"
                and hub_manifest.get("security_waiver") is False
                and hub_manifest.get("authority_transfer") is False
                and hub_manifest.get("qps_owner_acceptance") is None
                and hub_ledger.get("presentation_head") == sha
                and hub_ledger.get("schema") == "codepurple.convergence_hub.projection.v1"
                and hub_ledger.get("browser_refresh_credit") is False
                and hub_ledger.get("native_cross_repo_attestation") is None
                and hub_ledger.get("kpis", {}).get("coverage_rollup_global") is None):
            raise ValueError("unsafe Convergence Hub publication contract")
        if set(hub_manifest.get("member_sha256", {})) != {
                "index.html", "ledger.json", "lineage.mmd"}:
            raise ValueError("Convergence Hub manifest member drift")
        for name in hub_allow:
            src = hub_src / name
            if name != "manifest.json" and hashlib.sha256(src.read_bytes()).hexdigest() != hub_manifest["member_sha256"][name]:
                raise ValueError("Convergence Hub source member hash mismatch: " + name)
            dst = out / "convergence" / name
            dst.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(src, dst)
            hashes[str(dst.relative_to(out))] = hashlib.sha256(dst.read_bytes()).hexdigest()
    # W34 Superstitch: existing Method Atlas is the ONLY public publisher.
    sw_allow=("index.html","app.js","stitch_interaction.js","style.css",
              "stitch_interaction.css","graph.svg","graph.json","spline.svg",
              "taxonomy.json","glossary.json","groups.json","sipoc-lanes.svg",
              "trigger-dag.svg","superstitch.mmd","sipoc-lanes.mmd",
              "trigger-dag.mmd","manifest.json")
    sw_src=atlas/"superstitch"
    sw_present=[n for n in sw_allow if (sw_src/n).is_file()]
    if sw_present and len(sw_present)!=len(sw_allow):
        raise ValueError("partial W34 Superstitch output")
    sw_ready=len(sw_present)==len(sw_allow)
    if sw_ready:
        sw_m=json.loads((sw_src/"manifest.json").read_text(encoding="utf-8"))
        sw_g=json.loads((sw_src/"graph.json").read_text(encoding="utf-8"))
        if not (sw_m.get("schema")=="missioncontrol.superstitch.manifest.v1"
                and sw_m.get("presentation_head")==sha
                and sw_m.get("role")=="READ_ONLY_EXISTING_PAGES_CONSUMER"
                and sw_m.get("merger_admission")=="HOLD"
                and sw_m.get("run_dispatch") is False
                and sw_m.get("qps_owner_acceptance") is None
                and sw_m.get("native_test_attestation") is None
                and sw_g.get("publication",{}).get("presentation_head")==sha
                and sw_g.get("publication",{}).get("native_current_attestation") is None
                and sw_g.get("authority",{}).get("zip_verifier")=="MC-530"
                and sw_g.get("authority",{}).get("breadth_producer")=="MC-531"
                and sw_g.get("authority",{}).get("method_viewer")=="MC-533"
                and sw_g.get("authority",{}).get("merge_admission")=="HOLD"):
            raise ValueError("Superstitch publication/authority contract")
        if set(sw_m.get("member_sha256",{})) != set(sw_allow)-{"manifest.json"}:
            raise ValueError("Superstitch public-member population drift")
        for filename in sw_allow:
            src=sw_src/filename
            if filename!="manifest.json":
                if hashlib.sha256(src.read_bytes()).hexdigest()!=sw_m["member_sha256"][filename] or src.stat().st_size!=sw_m["member_bytes"][filename]:
                    raise ValueError("Superstitch public-member byte mismatch: "+filename)
            dest=out/"superstitch"/filename
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,dest)
            hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # P process (Code Purple x EVERRED): prebuilt static site committed under qps-triage-ultra/p-process/site.
    psite=atlas/"p-process"
    if psite.is_dir():
        for src in sorted(psite.rglob("*")):
            if src.is_file() and src.suffix in {".html",".js",".json",".pdf",".md",".yaml",".py"}:
                dest=out/"p-process"/src.relative_to(psite); dest.parent.mkdir(exist_ok=True,parents=True)
                shutil.copyfile(src,dest); hashes[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    # JADE_CASTE is a fail-closed, hash-bound child of this existing Pages publisher.
    # This is file staging, not independent deployment or release authority.
    jade_root = Path(__file__).resolve().parents[1] / "jade_temple"
    jade_bridge = jade_root / "portal_bridge.py"
    if jade_bridge.is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location("jade_temple_pages_bridge", jade_bridge)
        if spec is None or spec.loader is None:
            raise ValueError("JADE_BRIDGE_IMPORT_FAILED")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.stage_jade(jade_root, out, hashes, sha)
    elif (jade_root / "site" / "green.html").exists():
        raise ValueError("JADE_SOURCE_WITHOUT_VALIDATED_BRIDGE")
    links=[("JADE_CASTE · N+3 eight-point MIP","jade/eightpoint.html"),("JADE_CASTE · N+2 measured burn-down and stop rules","jade/burndown.html"),("JADE_CASTE · GoGREEN Top21 readiness","jade/green.html"),("GLOBAL DoV · Consolidated Convergence Hub","convergence/index.html"),("Live Lossless · Session Status","live-lossless/index.html"),("G3P Live Evidence","g3p/index.html"),("Method Atlas","atlas/index.html"),("Process and Mermaid","atlas/lane-process.html"),("CODE PURPLE controls","atlas/code-purple.html"),("Federation pulses","atlas/federation-latest.html"),("Flight Deck","atlas/flightdeck/index.html"),("Native pulse evidence","native-pulse/index.html"),("BD / CHAR temporal pulses","bd-char/index.html"),("Federation neighbors & recursive SIPOC","federation-home/index.html"),("Merged PR historical run chronology","pr-history/index.html"),("Disjoint worker and IDE P3","worker-devkit/index.html"),("P process: Code Purple × EVERRED","p-process/index.html"),("Kubernetes source inventory","atlas/sideload-k8s.html"),("Side-load proof and admission ladder","atlas/sideload-operator.html")]
    cards="".join('<a class="card" href="'+html.escape(u)+'">'+html.escape(t)+' ↗</a>' for t,u in links if (out/u).is_file())
    if (out / "orchestration" / "index.html").is_file():
        cards = '<a class="card" href="orchestration/index.html">Method Atlas · functional I/O, all workflow DAGs, broker and burndown ↗</a>' + cards
    if (out / "mission-rebuild" / "index.html").is_file():
        cards += '<a class="card" href="mission-rebuild/index.html">MISSION CONTROL · Repository and DAG explorer ↗</a>'
    if (out / "mission-rebuild" / "evidence.html").is_file():
        cards += '<a class="card" href="mission-rebuild/evidence.html">MissionControl W2 · live queue / gg_MATH Plotly evidence ↗</a>'
    if (out / "mission-rebuild" / "n3-metrics.html").is_file():
        cards += '<a class="card" href="mission-rebuild/n3-metrics.html">N3 · Native job queue / KPI / LDAB proof boundary ↗</a>'
    # Source-owned gg_MATH Plotly proof is a navigational link, not a deployed
    # Pages asset or a second KPI producer. Fail closed on unsafe bridge claims.
    math_bridge=Path(__file__).resolve().parent/"GG_MATH_CONVERGENCE_BRIDGE_v1.json"
    if math_bridge.is_file():
        from gg_math_convergence_consumer import validate_bridge
        math_view=validate_bridge(json.loads(math_bridge.read_text(encoding="utf-8")))
        math_url=math_view["provider_source_url"]
        if not math_url.startswith("https://github.com/GBOGEB/gg_MATH/blob/"):
            raise ValueError("unsafe math provider link")
        cards+='<a class="card" rel="noopener noreferrer" href="'+html.escape(math_url,quote=True)+'">gg_MATH · Convergence Plotly source (native/Pages verification pending) ↗</a>'

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
