"""Behavioural coverage for mission-control/federation-atlas/pages_portal.py.

The module is loaded with __file__ relocated to tmp_path/mc/fa/, so every
source-owned sibling it probes (launchpad, jade_temple, G3P, gg_MATH bridge,
coverage-integrity source) is absent unless a test creates a fake of it.
"""
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "federation-atlas" / "pages_portal.py"
SHA = "c" * 40


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    fa = tmp_path / "mc" / "fa"
    fa.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location("cw_pages_portal", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(fa / "cw_pages_portal_shadow.py")
    spec.loader.exec_module(mod)
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    (atlas / "index.html").write_text("<title>atlas</title>", encoding="utf-8")
    return types.SimpleNamespace(mod=mod, fa=fa, mc=fa.parent, atlas=atlas, out=tmp_path / "out")


def h(data):
    return hashlib.sha256(data).hexdigest()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        content = json.dumps(content)
    if isinstance(content, str):
        content = content.encode("utf-8")
    path.write_bytes(content)
    return content


def bundle(root, files, manifest_name, manifest, hash_key, hash_names=None, bytes_key=None):
    """Write member files then a manifest binding their sha256 (and sizes)."""
    blobs = {name: write(root / name, content) for name, content in files.items()}
    names = hash_names if hash_names is not None else list(files)
    if hash_key not in manifest:
        manifest[hash_key] = {n: h(blobs[n]) for n in names}
    if bytes_key and bytes_key not in manifest:
        manifest[bytes_key] = {n: len(blobs[n]) for n in names}
    write(root / manifest_name, manifest)
    return manifest


def published(env):
    return json.loads((env.out / "site-manifest.json").read_text())["public_files_sha256"]


def home(env):
    return (env.out / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- basics

def test_atlas_index_required(env):
    (env.atlas / "index.html").unlink()
    with pytest.raises(ValueError, match="^Atlas output absent$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_minimal_build_manifest_and_default_diagram(env):
    m = env.mod.build(env.atlas, env.out, SHA)
    assert m["source_git_sha"] == SHA
    assert m["merge_authorized"] is False and m["security_waiver"] is False
    assert set(m["public_files_sha256"]) == {"index.html", "atlas/index.html"}
    page = home(env)
    assert "flowchart LR\n A[&quot;Source&quot;]" in page
    assert "missioncontrol/index.html" not in page
    assert "gg_MATH" not in page
    assert published(env)["index.html"] == h((env.out / "index.html").read_bytes())


def test_supporting_children_are_copied_and_hashed(env):
    a = env.atlas
    write(a / "native-pulse" / "native_pulse_ledger.json", "{}")
    write(a / "native-pulse" / "native_pulse_index.html", "np")
    for n in ("index.html", "snapshot.json", "manifest.json"):
        write(a / "bd-char" / n, "bd" + n)
        write(a / "federation-home" / n, "fh" + n)
    for n in ("index.html", "snapshot.json", "manifest.json", "native-refresh.json"):
        write(a / "pr-history" / n, "pr" + n)
    for n in ("index.html", "observed.json", "worker-plan.json", "manifest.json"):
        write(a / "worker-devkit" / n, "wd" + n)
    write(a / "p-process" / "index.html", "p")
    write(a / "p-process" / "sub" / "x.json", "{}")
    write(a / "p-process" / "skip.txt", "nope")
    write(a / "p-process" / "deep" / "nested.yaml", "a: 1")
    files = env.mod.build(a, env.out, SHA)["public_files_sha256"]
    assert files["native-pulse/index.html"] == h(b"np")
    assert "native-pulse/native_pulse_ledger.json" in files
    assert files["bd-char/manifest.json"] == h(b"bdmanifest.json")
    assert files["pr-history/native-refresh.json"] == h(b"prnative-refresh.json")
    assert files["worker-devkit/worker-plan.json"] == h(b"wdworker-plan.json")
    assert files["federation-home/snapshot.json"] == h(b"fhsnapshot.json")
    assert "p-process/sub/x.json" in files and "p-process/deep/nested.yaml" in files
    assert "p-process/skip.txt" not in files
    page = home(env)
    for href in ("native-pulse/index.html", "bd-char/index.html", "pr-history/index.html",
                 "worker-devkit/index.html", "federation-home/index.html", "p-process/index.html"):
        assert 'href="' + href + '"' in page


def test_lane_process_diagram_is_escaped(env):
    write(env.atlas / "lane-process.mmd", 'flowchart LR\n X["<b>"]')
    env.mod.build(env.atlas, env.out, SHA)
    assert "X[&quot;&lt;b&gt;&quot;]" in home(env)


# ---------------------------------------------------------------- coverage-integrity

MEMBERS = {"index.html": "<html></html>", "snapshot.json": None, "dependency.mmd": "flowchart LR\n a",
           "sipoc.mmd": "flowchart TB\n b", "spline.mmd": "  flowchart LR\n c",
           "graph-light.svg": '<svg xmlns="http://www.w3.org/2000/svg"/>',
           "graph-dark.svg": '<svg xmlns="http://www.w3.org/2000/svg"></svg>'}


def coverage_child(env, source_path, overrides=None, drop=None):
    src = {"schema": "codepurple.coverage_integrity.observations.v1",
           "authority": {"merge_admission": "HOLD", "engineering_acceptance": "WITHHELD",
                         "security_waiver": "NONE", "formal_credit_delta": 0,
                         "is_six_repo_canonical_breadth": False}}
    digest = h(write(source_path, src))
    files = dict(MEMBERS)
    files.update(overrides or {})
    files["snapshot.json"] = {"schema": "codepurple.coverage_integrity.snapshot.v1",
                              "presentation_head_sha": SHA, "source_json_sha256": digest,
                              "portfolio_total_coverage": None,
                              "authority": {"merge_admission": "HOLD", "engineering_acceptance": "WITHHELD",
                                            "security_waiver": "NONE", "formal_credit_delta": 0,
                                            "is_native_current_attestation": False, "run_dispatch": False}}
    manifest = {"schema": "codepurple.coverage_integrity.manifest.v1", "presentation_head_sha": SHA,
                "source_json_sha256": digest, "merge_admission": "HOLD", "authority_transfer": False,
                "formal_credit_delta": 0, "current_main_coverage_attestation": None}
    m = bundle(env.atlas / "coverage-integrity", files, "manifest.json", manifest, "member_sha256",
               bytes_key="member_bytes")
    if drop:
        m["member_sha256"].pop(drop)
        write(env.atlas / "coverage-integrity" / "manifest.json", m)
    return m


def test_coverage_child_must_be_directory(env):
    write(env.atlas / "coverage-integrity", "not a dir")
    with pytest.raises(ValueError, match="^COVERAGE_CHILD_INVALID_DIRECTORY$"):
        env.mod.stage_coverage_integrity(env.atlas, env.out, SHA, {})


def test_coverage_manifest_member_key_drift(env, tmp_path):
    src = tmp_path / "obs.json"
    coverage_child(env, src, drop="spline.mmd")
    with pytest.raises(ValueError, match="^COVERAGE_MEMBER_MANIFEST_DRIFT$"):
        env.mod.stage_coverage_integrity(env.atlas, env.out, SHA, {}, source_path=src)


def test_coverage_resealed_non_mermaid_rejected(env, tmp_path):
    src = tmp_path / "obs.json"
    coverage_child(env, src, overrides={"sipoc.mmd": "graph TD\n x"})
    with pytest.raises(ValueError, match="^COVERAGE_MERMAID_INVALID:sipoc.mmd$"):
        env.mod.stage_coverage_integrity(env.atlas, env.out, SHA, {}, source_path=src)


def test_coverage_child_staged_via_default_source_and_linked_first(env):
    coverage_child(env, env.fa / "COVERAGE_INTEGRITY_OBSERVATIONS_v1.json")
    m = env.mod.build(env.atlas, env.out, SHA)
    for name in list(MEMBERS) + ["manifest.json"]:
        key = "coverage-integrity/" + name
        assert m["public_files_sha256"][key] == h((env.atlas / "coverage-integrity" / name).read_bytes())
    page = home(env)
    grid = page[page.index('<div class="grid">'):]
    assert grid.index("coverage-integrity/index.html") < grid.index("atlas/index.html")


# ---------------------------------------------------------------- G3P bridge

def g3p_source(**over):
    doc = {"schema": "missioncontrol.g3p.live_sources.v1", "repository": "GBOGEB/pipeline-automation-hub",
           "authority_transfer": False, "merge_admission": "HOLD"}
    doc.update(over)
    return doc


def test_g3p_incomplete_pair_fails(env):
    write(env.fa / "G3P_LIVE_LEDGER.html", "<html>")
    with pytest.raises(ValueError, match="^incomplete G3P Pages source pair$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_g3p_contract_violation_fails(env):
    write(env.fa / "G3P_LIVE_LEDGER.html", "<html>")
    write(env.fa / "G3P_LIVE_SOURCES_v1.json", g3p_source(merge_admission="GO"))
    with pytest.raises(ValueError, match="^G3P Pages source contract invalid$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_g3p_pair_packaged(env):
    write(env.fa / "G3P_LIVE_LEDGER.html", "<html>g3p</html>")
    raw = write(env.fa / "G3P_LIVE_SOURCES_v1.json", g3p_source())
    files = env.mod.build(env.atlas, env.out, SHA)["public_files_sha256"]
    assert files["g3p/index.html"] == h(b"<html>g3p</html>")
    assert files["g3p/G3P_LIVE_SOURCES_v1.json"] == h(raw)
    assert '<a class="card" href="g3p/index.html">G3P Live Evidence' in home(env)


# ---------------------------------------------------------------- Live Lossless

def live_lossless(env, manifest_over=None, state_over=None):
    state = {"schema": "missioncontrol.live_lossless.dashboard.v1", "authority_transfer": False,
             "merge_admission": "INDEPENDENT_HOLD"}
    state.update(state_over or {})
    manifest = {"schema": "missioncontrol.live_lossless.publication_manifest.v1",
                "publisher": "EXISTING_PAGES_ONLY", "authority_transfer": False, "security_waiver": False,
                "merge_admission": "HOLD"}
    manifest.update(manifest_over or {})
    files = {"index.html": "ll", "app.js": "js", "style.css": "css", "snapshot.json": state}
    return bundle(env.atlas / "live-lossless", files, "manifest.json", manifest, "files_sha256")


def test_live_lossless_partial_fails(env):
    write(env.atlas / "live-lossless" / "index.html", "x")
    with pytest.raises(ValueError, match="^incomplete Live Lossless Pages source$"):
        env.mod.build(env.atlas, env.out, SHA)


@pytest.mark.parametrize("m_over,s_over", [({"publisher": "OTHER"}, None),
                                           (None, {"merge_admission": "HOLD"})])
def test_live_lossless_unsafe_projection(env, m_over, s_over):
    live_lossless(env, m_over, s_over)
    with pytest.raises(ValueError, match="^unsafe Live Lossless Pages projection$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_live_lossless_hash_mismatch(env):
    live_lossless(env)
    write(env.atlas / "live-lossless" / "app.js", "tampered")
    with pytest.raises(ValueError, match="^Live Lossless source hash mismatch: app.js$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_live_lossless_packaged(env):
    live_lossless(env)
    files = env.mod.build(env.atlas, env.out, SHA)["public_files_sha256"]
    assert {k for k in files if k.startswith("live-lossless/")} == {
        "live-lossless/" + n for n in ("index.html", "app.js", "style.css", "snapshot.json", "manifest.json")}
    assert 'href="live-lossless/index.html"' in home(env)


# ---------------------------------------------------------------- Mission rebuild / W2 / N3

def rebuild(env, receipt_over=None, graph_over=None):
    graph = {"source_sha": SHA, "gate": {"merge_admission": "HOLD"}, "scheduler": {"dispatch_authorized": False}}
    graph.update(graph_over or {})
    receipt = {"schema": "missioncontrol.makeover.manifest.v1", "source_sha": SHA,
               "published_by": "EXISTING_METHOD_ATLAS_PAGES_ONLY", "merge_admission": "HOLD",
               "security_waiver": False, "authority_transfer": False}
    receipt.update(receipt_over or {})
    files = {"index.html": "mr", "graph.json": graph, "graph.mmd": "flowchart LR\n a"}
    return bundle(env.atlas / "mission-rebuild", files, "manifest.json", receipt, "files_sha256")


def w2(env, receipt_over=None, state_over=None, members=None):
    state = {"schema": "missioncontrol.makeover.w2_native_observation.v1", "source_head_sha": SHA,
             "governance": {"merge_admission": "HOLD"}, "gg_math": {"native_live_pulse_receipts_ingested": 0},
             "fleet": {"capacity_slots": None}, "unknown_burndown": {"coverage": {"covered_statements": None}}}
    state.update(state_over or {})
    receipt = {"schema": "missioncontrol.makeover.w2_plotly_manifest.v1", "source_sha": SHA,
               "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY", "merge_admission": "HOLD",
               "security_waiver": False, "authority_transfer": False, "gg_math_kernel_duplicated": False}
    receipt.update(receipt_over or {})
    if members is not None:
        receipt["member_sha256"] = members
    files = {"evidence.json": state, "evidence.html": "w2"}
    return bundle(env.atlas / "mission-rebuild", files, "evidence-manifest.json", receipt, "member_sha256")


def n3(env, receipt_over=None, state_over=None, members=None):
    state = {"schema": "missioncontrol.n3.scoped_native_kpi.v1", "presentation_sha": SHA, "producer_sha": "p1",
             "source_repo": "GBOGEB/pipeline-automation-hub",
             "authority": {"merge_admission": "HOLD", "remote_dispatch": False},
             "fleet_runner_capacity": None, "owner_required_status_gate": {"owner_installed": None}}
    state.update(state_over or {})
    receipt = {"schema": "missioncontrol.n3.readonly_publisher_manifest.v1", "presentation_sha": SHA,
               "producer_sha": "p1", "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY",
               "merge_admission": "HOLD", "authority_transfer": False}
    receipt.update(receipt_over or {})
    if members is not None:
        receipt["member_sha256"] = members
    files = {"n3-metrics.html": "n3", "n3-metrics.json": state}
    return bundle(env.atlas / "mission-rebuild", files, "n3-manifest.json", receipt, "member_sha256")


def test_rebuild_unsafe_source(env):
    rebuild(env, graph_over={"scheduler": {"dispatch_authorized": True}})
    with pytest.raises(ValueError, match="^unsafe Mission rebuild source$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_rebuild_hash_mismatch(env):
    rebuild(env)
    write(env.atlas / "mission-rebuild" / "graph.mmd", "flowchart TB")
    with pytest.raises(ValueError, match="^Mission rebuild hash mismatch: graph.mmd$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_w2_partial_fails(env):
    write(env.atlas / "mission-rebuild" / "evidence.html", "x")
    with pytest.raises(ValueError, match="^partial W2 MissionControl evidence output$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_w2_unsafe_admission(env):
    w2(env, state_over={"fleet": {"capacity_slots": 4}})
    with pytest.raises(ValueError, match="^unsafe W2 gg_MATH/Plotly bridge admission$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_w2_population_drift(env):
    w2(env, members={"evidence.json": "0" * 64})
    with pytest.raises(ValueError, match="^W2 manifest population drift$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_w2_hash_mismatch(env):
    w2(env)
    write(env.atlas / "mission-rebuild" / "evidence.html", "changed")
    with pytest.raises(ValueError, match="^W2 evidence source hash mismatch: evidence.html$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_n3_partial_fails(env):
    write(env.atlas / "mission-rebuild" / "n3-metrics.json", "{}")
    with pytest.raises(ValueError, match="^partial N3 source-bound KPI output$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_n3_producer_mismatch_is_promotion(env):
    n3(env, receipt_over={"producer_sha": "other"})
    with pytest.raises(ValueError, match="^unsafe N3 KPI/REX publication promotion$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_n3_population_drift(env):
    n3(env, members={"n3-metrics.html": "0" * 64, "n3-metrics.json": "0" * 64, "extra": "0" * 64})
    with pytest.raises(ValueError, match="^N3 manifest member population drift$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_n3_digest_mismatch(env):
    n3(env)
    write(env.atlas / "mission-rebuild" / "n3-metrics.html", "tampered")
    with pytest.raises(ValueError, match="^N3 source member digest mismatch: n3-metrics.html$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_rebuild_w2_n3_packaged_with_cards(env):
    rebuild(env)
    w2(env)
    n3(env)
    files = env.mod.build(env.atlas, env.out, SHA)["public_files_sha256"]
    for name in ("index.html", "graph.json", "graph.mmd", "manifest.json", "evidence.json", "evidence.html",
                 "evidence-manifest.json", "n3-metrics.html", "n3-metrics.json", "n3-manifest.json"):
        assert files["mission-rebuild/" + name] == h((env.atlas / "mission-rebuild" / name).read_bytes())
    page = home(env)
    tail = page[page.index('<div class="grid">'):page.index("</div></section>")]
    assert tail.index("mission-rebuild/index.html") < tail.index("mission-rebuild/evidence.html") \
        < tail.index("mission-rebuild/n3-metrics.html")


# ---------------------------------------------------------------- Convergence hub

def hub(env, manifest_over=None, members=None):
    ledger = {"presentation_head": SHA, "schema": "codepurple.convergence_hub.projection.v1",
              "browser_refresh_credit": False, "native_cross_repo_attestation": None,
              "kpis": {"coverage_rollup_global": None}}
    manifest = {"schema": "codepurple.convergence_hub.manifest.v1", "presentation_head": SHA,
                "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY", "merge_admission": "HOLD",
                "security_waiver": False, "authority_transfer": False, "qps_owner_acceptance": None}
    manifest.update(manifest_over or {})
    if members is not None:
        manifest["member_sha256"] = members
    files = {"index.html": "hub", "ledger.json": ledger, "lineage.mmd": "flowchart LR\n h"}
    return bundle(env.atlas / "convergence", files, "manifest.json", manifest, "member_sha256")


def test_hub_unsafe_contract(env):
    hub(env, {"qps_owner_acceptance": "ACCEPTED"})
    with pytest.raises(ValueError, match="^unsafe Convergence Hub publication contract$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_hub_member_drift(env):
    hub(env, members={"index.html": "0" * 64})
    with pytest.raises(ValueError, match="^Convergence Hub manifest member drift$"):
        env.mod.build(env.atlas, env.out, SHA)


# ---------------------------------------------------------------- Superstitch

SW_ALLOW = ("index.html", "app.js", "stitch_interaction.js", "style.css", "stitch_interaction.css", "graph.svg",
            "graph.json", "spline.svg", "taxonomy.json", "glossary.json", "groups.json", "sipoc-lanes.svg",
            "trigger-dag.svg", "superstitch.mmd", "sipoc-lanes.mmd", "trigger-dag.mmd")


def superstitch(env, manifest_over=None, members=None):
    files = {n: "content of " + n for n in SW_ALLOW}
    files["graph.json"] = {"publication": {"presentation_head": SHA, "native_current_attestation": None},
                           "authority": {"zip_verifier": "MC-530", "breadth_producer": "MC-531",
                                         "method_viewer": "MC-533", "merge_admission": "HOLD"}}
    manifest = {"schema": "missioncontrol.superstitch.manifest.v1", "presentation_head": SHA,
                "role": "READ_ONLY_EXISTING_PAGES_CONSUMER", "merger_admission": "HOLD", "run_dispatch": False,
                "qps_owner_acceptance": None, "native_test_attestation": None}
    manifest.update(manifest_over or {})
    if members is not None:
        manifest["member_sha256"] = members
    return bundle(env.atlas / "superstitch", files, "manifest.json", manifest, "member_sha256",
                  bytes_key="member_bytes")


def test_superstitch_partial_fails(env):
    write(env.atlas / "superstitch" / "app.js", "x")
    with pytest.raises(ValueError, match="^partial W34 Superstitch output$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_superstitch_contract_violation(env):
    superstitch(env, {"run_dispatch": True})
    with pytest.raises(ValueError, match="^Superstitch publication/authority contract$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_superstitch_population_drift(env):
    superstitch(env, members={"index.html": "0" * 64})
    with pytest.raises(ValueError, match="^Superstitch public-member population drift$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_superstitch_byte_size_mismatch(env):
    m = superstitch(env)
    m["member_bytes"]["style.css"] += 1
    write(env.atlas / "superstitch" / "manifest.json", m)
    with pytest.raises(ValueError, match="^Superstitch public-member byte mismatch: style.css$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_superstitch_and_hub_packaged(env):
    superstitch(env)
    hub(env)
    files = env.mod.build(env.atlas, env.out, SHA)["public_files_sha256"]
    assert {k for k in files if k.startswith("superstitch/")} == \
        {"superstitch/" + n for n in (*SW_ALLOW, "manifest.json")}
    assert files["convergence/ledger.json"] == h((env.atlas / "convergence" / "ledger.json").read_bytes())
    assert 'href="convergence/index.html"' in home(env)


# ---------------------------------------------------------------- JADE bridge

def test_jade_site_without_bridge_fails(env):
    write(env.mc / "jade_temple" / "site" / "green.html", "g")
    with pytest.raises(ValueError, match="^JADE_SOURCE_WITHOUT_VALIDATED_BRIDGE$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_jade_bridge_stages_and_links(env):
    write(env.mc / "jade_temple" / "portal_bridge.py",
          "import hashlib\n"
          "def stage_jade(root, out, hashes, sha):\n"
          "    d = out / 'jade'\n"
          "    d.mkdir(parents=True, exist_ok=True)\n"
          "    (d / 'green.html').write_text('green ' + sha, encoding='utf-8')\n"
          "    hashes['jade/green.html'] = hashlib.sha256((d / 'green.html').read_bytes()).hexdigest()\n")
    files = env.mod.build(env.atlas, env.out, SHA)["public_files_sha256"]
    assert files["jade/green.html"] == h(("green " + SHA).encode())
    page = home(env)
    assert 'href="jade/green.html"' in page
    assert 'href="jade/burndown.html"' not in page


# ---------------------------------------------------------------- gg_MATH bridge

def fake_math(monkeypatch, env, url):
    write(env.fa / "GG_MATH_CONVERGENCE_BRIDGE_v1.json", {"url": url})
    consumer = types.ModuleType("gg_math_convergence_consumer")
    consumer.validate_bridge = lambda doc: {"provider_source_url": doc["url"]}
    monkeypatch.setitem(sys.modules, "gg_math_convergence_consumer", consumer)


def test_math_bridge_rejects_foreign_link(env, monkeypatch):
    fake_math(monkeypatch, env, "https://evil.example/gg_MATH")
    with pytest.raises(ValueError, match="^unsafe math provider link$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_math_bridge_link_is_escaped(env, monkeypatch):
    fake_math(monkeypatch, env, 'https://github.com/GBOGEB/gg_MATH/blob/main/a.py?x="1"&y=2')
    env.mod.build(env.atlas, env.out, SHA)
    page = home(env)
    assert 'rel="noopener noreferrer" href="https://github.com/GBOGEB/gg_MATH/blob/main/a.py?x=&quot;1&quot;&amp;y=2"' \
        in page
    assert "native/Pages verification pending" in page


# ---------------------------------------------------------------- MissionControl launchpad

def fake_launchpad(monkeypatch, env, nav_over=None, digest_override=None, atom_over=None):
    launch = env.mc / "launchpad"
    graph_path = write(launch / "graph.json", {"nodes": [1, 2], "edges": [1]}) and launch / "graph.json"
    atoms = {"schema": "missioncontrol.launchpad.graph_atoms.v1",
             "source_git_blob_sha": "74a8e45d26d24f52aa751713df3706c492a9f94e",
             "authority_transfer": False, "merge_admission": "HOLD", "canonical_bd_unchanged": True,
             "metrics": {"all_atoms": 3}, "atoms": [1, 2, 3]}
    atoms.update(atom_over or {})
    write(launch / "GRAPH_ATOMS_W1_v1.json", atoms)

    def build_launchpad(dest, sha):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("nav", encoding="utf-8")
        (dest / "manifest.json").write_text("{}", encoding="utf-8")
        nav = {"schema": "missioncontrol.launchpad.publication_manifest.v1",
               "publisher": "EXISTING_ATLAS_PAGES_ONLY", "source_head_sha": sha, "native_qa": None,
               "hosted_http_verified": False, "authority_transfer": False, "merge_admission": "HOLD",
               "files_sha256": {"index.html": digest_override or h(b"nav")}}
        nav.update(nav_over or {})
        return nav

    render = types.ModuleType("render_launchpad")
    render.build = build_launchpad
    nav_model = types.ModuleType("nav_model")
    nav_model.CONFIG = graph_path
    monkeypatch.setitem(sys.modules, "render_launchpad", render)
    monkeypatch.setitem(sys.modules, "nav_model", nav_model)
    return launch


def test_launchpad_packaged_with_atoms_and_featured_note(env, monkeypatch):
    launch = fake_launchpad(monkeypatch, env)
    files = env.mod.build(env.atlas, env.out, SHA)["public_files_sha256"]
    assert str(launch) in sys.path
    assert files["missioncontrol/index.html"] == h(b"nav")
    assert files["missioncontrol/manifest.json"] == h(b"{}")
    assert files["missioncontrol/GRAPH_ATOMS_W1_v1.json"] == h((launch / "GRAPH_ATOMS_W1_v1.json").read_bytes())
    page = home(env)
    assert "<strong>Mission Control makeover:</strong>" in page
    assert '<a class="card" href="missioncontrol/index.html">' in page


def test_launchpad_policy_drift(env, monkeypatch):
    fake_launchpad(monkeypatch, env, nav_over={"hosted_http_verified": True})
    with pytest.raises(ValueError, match="^MC navigation publication policy drift$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_launchpad_digest_mismatch(env, monkeypatch):
    fake_launchpad(monkeypatch, env, digest_override="0" * 64)
    with pytest.raises(ValueError, match="^MC navigation file digest mismatch: index.html$"):
        env.mod.build(env.atlas, env.out, SHA)


def test_launchpad_atom_parity_failure(env, monkeypatch):
    fake_launchpad(monkeypatch, env, atom_over={"metrics": {"all_atoms": 4}})
    with pytest.raises(ValueError, match="^MC graph atom source parity/authority failure$"):
        env.mod.build(env.atlas, env.out, SHA)


# ---------------------------------------------------------------- __main__

def test_script_entrypoint_prints_public_file_count(env, monkeypatch, capsys):
    write(env.atlas / "federation.svg", "<svg/>")
    write(env.atlas / "notes.txt", "private")
    monkeypatch.setattr(sys, "argv", ["pages_portal", "--atlas", str(env.atlas), "--out", str(env.out),
                                      "--sha", SHA])
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(env.fa / "cw_pages_main.py")})
    assert json.loads(capsys.readouterr().out) == {"public_files": 3}
    assert not (env.out / "atlas" / "notes.txt").exists()


def test_script_entrypoint_requires_arguments(env, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pages_portal", "--atlas", str(env.atlas)])
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    with pytest.raises(SystemExit) as exc:
        exec(code, {"__name__": "__main__", "__file__": str(env.fa / "cw_pages_main.py")})
    assert exc.value.code == 2
    assert "the following arguments are required: --out, --sha" in capsys.readouterr().err
