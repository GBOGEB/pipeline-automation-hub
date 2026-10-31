"""Behavioural tests for mission-control/federation-atlas/orchestration/main.py.

The existing suite (orchestration/test_main.py) covers the artifact, contract,
bundle and receipt gates in isolation.  These tests drive the end-to-end
source_model -> build -> verify_bundle path, the local run handlers and the CLI
against a synthetic checkout in tmp_path.  git, subprocess and the sibling
broker/coverage/render modules are replaced on the loaded module, so no external
program runs and nothing is written into the repository.
"""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_DIR = REPO / "mission-control" / "federation-atlas" / "orchestration"
MOD_PATH = MOD_DIR / "main.py"


def _load():
    if str(MOD_DIR) not in sys.path:
        sys.path.insert(0, str(MOD_DIR))
    spec = importlib.util.spec_from_file_location("cw_orchestration_main_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


atlas = _load()
HEAD = "a" * 40
OTHER = "b" * 40
POLICY = "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json"
TASK_IDS = ["validate", "method", "control", "superstitch", "convergence", "orchestration", "assemble", "portal"]


# ---------------------------------------------------------------- synthetic checkout
def _out_port(identity="result", path="result.json"):
    return {"id": identity, "path": path, "kind": "json", "schema": "example.result.v1",
            "required": True, "source_scope": "GENERATED"}


def _block(identity, role, needs=(), extra_inputs=(), outputs=None):
    return {"id": identity, "label": identity.replace("-", " ").title(), "role": role, "needs": list(needs),
            "source_path": "src/worker.py", "entrypoint": "emit",
            "inputs": [{"id": "input", "path": "mission-control/input.json", "kind": "json",
                        "schema": "example.input.v1", "required": True, "source_scope": "REPOSITORY"},
                       *extra_inputs],
            "outputs": outputs or [_out_port()]}


def profile_doc():
    gen_in = {**_out_port(), "source_scope": "GENERATED"}
    blocks = [
        _block("source-contracts", "producer"),
        _block("method-atlas", "producer"),
        _block("burndown", "control", needs=["method-atlas"], extra_inputs=[gen_in]),
        _block("superstitch", "semantic"),
        _block("convergence", "actor"),
        _block("orchestration-view", "viewer"),
        _block("pages-portal", "packager",
               outputs=[{"id": "page", "path": "index.html", "kind": "html", "required": True,
                         "source_scope": "GENERATED"}]),
    ]
    mc = "mission-control/"
    return {"schema": "missioncontrol.orchestration.profile.v1", "repository": "example/project",
            "title": "Synthetic atlas", "authority_transfer": False, "remote_dispatch": False,
            "publisher": ".github/workflows/publisher.yml",
            "inherits": {"glossary": mc + "glossary.json", "programmes": mc + "programmes.json",
                         "views": mc + "views.json"},
            "sources": {"federation": mc + "federation.yaml", "beams": mc + "beams.json", "lanes": mc + "lanes.json",
                        "superstitch": mc + "stitch.json", "groups": mc + "groups.json", "queue": mc + "queue.json",
                        "series": mc + "series.json", "jade": mc + "jade.json"},
            "hierarchy": {"levels": ["programme", "block"]}, "io_rules": ["typed joins only"],
            "blocks": blocks,
            "joins": [{"from": "method-atlas:result", "to": "burndown:result", "join": "ALL"}]}


PUBLISHER = """name: Publisher
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - run: python src/worker.py --out site
  publish:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - id: deploy
        run: echo done
"""

OWN_MAIN = "def helper():\n    return 1\n\ndef main():\n    return helper()\n\nif __name__ == '__main__':\n    main()\n"


def write(root: Path, name: str, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_bytes(atlas.canonical(value))
    return path


def populate(root: Path):
    write(root, atlas.PROFILE, profile_doc())
    write(root, POLICY, {"default_max_pending": 4})
    write(root, "src/worker.py", "def emit():\n    return {}\n")
    write(root, "mission-control/input.json", {"schema": "example.input.v1"})
    write(root, "mission-control/glossary.json", {})
    write(root, "mission-control/programmes.json", {"PROGRAMMES": {"records": [{"id": "CODE_PURPLE"}]}})
    write(root, "mission-control/views.json", {"terms": ["atlas"]})
    write(root, "mission-control/federation.yaml",
          "nodes:\n  - {id: owner, label: Owner, role: actor}\n  - {id: repo, label: Repo, status: HOLD}\n"
          "edges:\n  - {from: owner, to: repo, type: owns}\n")
    write(root, "mission-control/beams.json", {
        "beams": [{"id": "A", "title": "Input"}, {"id": "B", "title": "Output"}, {"id": "C", "title": "Audit"}],
        "edges": [{"from": "A", "to": "B", "type": "DEPENDENCY"}, {"from": "B", "to": "A", "type": "FEEDBACK"},
                  {"from": "C", "to": "A", "type": "FEEDBACK"}]})
    write(root, "mission-control/lanes.json", {"lanes": [{"id": "L1", "label": "Lane one", "stages": [
        ["s1", "Define", ["need"], ["charter"]], ["s2", "Measure", ["charter"], ["baseline"]]]}]})
    write(root, "mission-control/stitch.json", {
        "nodes": [{"id": "n1", "label": "One"}, {"id": "n2", "label": "Two", "state": "WAITING"},
                  {"id": "n3", "label": "Three", "native_qualified": True}],
        "edges": [{"from": "n1", "to": "n2", "binding": "RECEIPT"}, {"from": "n2", "to": "n3"}],
        "observations": {
            "historical_six_repo_breadth": {"eligible": 42, "observed": 6, "evidence_class": "HISTORICAL"},
            "authenticated_codex_qps_pairs": {"eligible": 1, "observed": None, "evidence_class": "UNKNOWN"}}})
    write(root, "mission-control/groups.json", {"groups": [{"id": "g1", "label": "Group one", "nodes": ["n1", "n2"]}]})
    write(root, "mission-control/queue.json", {"schema": "example.queue.v1", "open_states": ["TODO"], "items": [
        {"id": "CPQ-001", "title": "First", "depends_on": [], "history": [{"state": "DONE", "flow": "NONE"}]},
        {"id": "CPQ-002", "title": "Second", "depends_on": ["CPQ-001"],
         "history": [{"state": "TODO", "flow": "BLOCKED"}]}]})
    write(root, "mission-control/series.json", {"entries": [
        {"key": "W1.C1.I0.S0", "tree": HEAD, "metrics": {"bd_total": 2, "bd_complete": 1}}]})
    write(root, "mission-control/jade.json", {
        "metrics": {"owner_actions_open": 1, "owner_actions_closed": 1}, "evidence_level": "FROZEN",
        "pulses": [{"id": "P1", "metrics": {"accepted_owner_actions": 1}, "eligible_denominator": 2,
                    "scope": "JADE", "cohort_sha": HEAD, "qualification": "FROZEN"}]})
    write(root, "mission-control/coverage.json", {"events": [{"id": 1}, {"id": 2}]})
    write(root, ".github/workflows/publisher.yml", PUBLISHER)
    write(root, ".github/workflows/broken.yml", "name: Broken\njobs: [1, 2]\n")
    write(root, "mission-control/federation-atlas/orchestration/main.py", OWN_MAIN)
    write(root, "tools/broken.py", "def broken(:\n")
    write(root, "docs/flow.mmd", "flowchart TD\n  A --> B\n")


class World(SimpleNamespace):
    pass


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    populate(root)
    w = World(root=root, tmp=tmp_path, head=HEAD, dirty="", calls=[], append_checks=[],
              run_hook=None, after_hook=None, generator_rc={}, verify_rc={}, portal=None)

    def fake_git(where, *args):
        w.calls.append(("git", args))
        if args[0] == "ls-files":
            return None  # use the filesystem walk
        if args == ("rev-parse", "HEAD"):
            return w.head
        if args[:2] == ("show", "-s"):
            return "2026-10-01T00:00:00+00:00"
        if args == ("status", "--porcelain"):
            return w.dirty
        if args == ("show", "HEAD:mission-control/coverage.json"):
            return json.dumps({"events": [{"id": 1}]})
        return None

    def plan(tasks, snapshot, policy):
        return {"tasks": [dict(t) for t in tasks], "generated_at": "2026-10-30T00:00:00Z",
                "dispatch_authorized": False, "snapshot": snapshot, "cohort": policy["cohort"]}

    def broker_run_local(tasks, handlers, workers=2, max_pending=8, root=None, policy=None):
        w.calls.append(("run_local", workers, max_pending, root, policy))
        if w.run_hook:
            w.run_hook()
        results = {t["id"]: handlers[t["id"]]() for t in tasks}
        if w.after_hook:
            w.after_hook()
        return {"schema": "atlas.local-broker.receipt.v1", "success": True, "outcome": "LOCAL_GENERATORS_PASS",
                "results": results}

    def build_model(where, profile):
        return {"source_path": "mission-control/coverage.json",
                "hierarchy": {"id": "portfolio", "label": "Portfolio", "kind": "PORTFOLIO", "children": [
                    {"id": "repo", "label": "Repo", "kind": "REPOSITORY",
                     "children": [{"id": "cohort", "label": "Cohort", "kind": "COHORT"}]}]},
                "ledger_records": [{"event": 1}, {"event": 2}]}

    def validate_append_only(previous, current):
        w.append_checks.append((previous, current))
        if current[:len(previous)] != previous:
            raise ValueError("coverage history rewritten")

    def write_outputs(coverage, out):
        (Path(out) / "metric_observations.json").write_bytes(atlas.canonical(coverage))
        (Path(out) / "coverage_burndown.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in coverage["ledger_records"]), encoding="utf-8")

    def render(model, out):
        (Path(out) / "index.html").write_text("<html><body>" + model["title"] + "</body></html>", encoding="utf-8")
        (Path(out) / "style.css").write_text("body{}", encoding="utf-8")
        (Path(out) / "app.js").write_text("'use strict';", encoding="utf-8")

    modules = {"atlas_local_broker": SimpleNamespace(plan=plan, run_local=broker_run_local),
               "atlas_coverage_contract": SimpleNamespace(build_model=build_model, write_outputs=write_outputs,
                                                          validate_append_only=validate_append_only),
               "atlas_execution_renderer": SimpleNamespace(render=render)}

    def fake_module(name, path):
        w.calls.append(("module", name, Path(path).name))
        return modules[name]

    def fake_run(command, cwd=None, env=None, capture_output=False, text=False, timeout=None, check=False):
        w.calls.append(("run", list(command)))
        assert Path(cwd) == root
        if "--atlas" in command:
            portal = Path(command[command.index("--out") + 1])
            portal.mkdir(parents=True)
            raw = b"<html>portal</html>"
            (portal / "index.html").write_bytes(raw)
            manifest = {"source_git_sha": command[command.index("--sha") + 1],
                        "public_files_sha256": {"index.html": atlas.digest(raw)}}
            if w.portal:
                w.portal(portal, manifest)
            (portal / "site-manifest.json").write_bytes(atlas.canonical(manifest))
            return SimpleNamespace(returncode=0, stdout="portal ok\n", stderr="")
        assert env["GITHUB_SHA"] == HEAD
        identity = Path(command[command.index("--out") + 1]).name
        if "--verify-only" in command:
            return SimpleNamespace(returncode=w.verify_rc.get(identity, 0), stdout="", stderr="")
        rc = w.generator_rc.get(identity, 0)
        if rc == 0:
            write(Path(command[command.index("--out") + 1]), "result.json", {"schema": "example.result.v1"})
        return SimpleNamespace(returncode=rc, stdout=identity + " out\n", stderr="boom\n" if rc else "")

    monkeypatch.setattr(atlas, "ROOT", root)
    monkeypatch.setattr(atlas, "git", fake_git)
    monkeypatch.setattr(atlas, "module", fake_module)
    monkeypatch.setattr(atlas, "subprocess", SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired))
    return w


def receipt_for(model, waits=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7), state="succeeded"):
    tasks = {}
    for t, wait in zip(model["broker"]["tasks"], waits):
        tasks[t["id"]] = {"state": state, "repo": t["repo"], "needs": t["needs"], "ready_wait_seconds": wait,
                          "execution_seconds": 1.0, "verification_seconds": None}
    count = len(tasks)
    ordered = sorted(waits)
    return {"schema": "atlas.local-broker.receipt.v1", "source_sha": model["source"]["head_sha"],
            "source_digest": model["source"]["source_digest"], "local_process_only": True,
            "dispatch_authorized": False, "merge_authorized": False, "authority_transfer": False,
            "source_changed_during_run": False, "success": state == "succeeded",
            "outcome": "LOCAL_GENERATORS_PASS" if state == "succeeded" else "LOCAL_GENERATORS_FAIL",
            "bounds": {"task_count": count, "workers": 2, "max_pending": 4},
            "metrics": {"elapsed_seconds": 5.0, "max_running": 2, "peak_ready": 3, "ready_wait_sample_count": count,
                        "deferred_ready_count": 0, "peak_deferred_ready": 0, "succeeded": count, "failed": 0,
                        "blocked": 0, "ready_wait_p50_seconds": ordered[math.ceil(count * .5) - 1],
                        "ready_wait_p95_seconds": ordered[math.ceil(count * .95) - 1]},
            "tasks": tasks}


# ---------------------------------------------------------------- source model
def test_source_model_binds_head_inventory_and_graphs(world):
    model = atlas.source_model(world.root, HEAD)
    src = model["source"]
    assert src["head_sha"] == HEAD and src["checkout_sha"] == HEAD and src["dirty"] is False
    assert src["commit_at"] == "2026-10-01T00:00:00+00:00"
    assert src["inventory_policy"] == atlas.SNAPSHOT_POLICY
    assert src["source_digest"] == atlas.digest(atlas.canonical(src["source_files_sha256"]))
    assert {"docs/flow.mmd", "tools/broken.py", ".github/workflows/broken.yml",
            atlas.PROFILE} <= set(src["source_files_sha256"])
    inv = model["inventory"]
    assert (inv["python_module_count"], inv["python_parse_errors"], inv["python_with_main"]) == (3, 1, 1)
    assert (inv["workflow_count"], inv["workflow_parse_errors"], inv["workflow_jobs"], inv["workflow_steps"]) == (2, 1, 2, 3)
    assert inv["diagram_count"] == 1
    assert model["blocks"][0]["source_url"] == "https://github.com/example/project/blob/" + HEAD + "/src/worker.py"
    assert model["blocks"][0]["attributes"]["name"] == "emit"
    assert model["taxonomy"]["programmes"] == [{"id": "CODE_PURPLE"}]
    assert model["taxonomy"]["glossary"] == {"terms": ["atlas"]}
    assert model["merge_admission"] == "HOLD" and model["remote_dispatch"] is False
    # Deterministic plan when no snapshot is supplied.
    assert model["broker"]["generated_at"] is None
    assert model["broker"]["time_basis"] == "DETERMINISTIC_SOURCE_PLAN_NO_RUNTIME_OBSERVATION"
    assert model["broker"]["cohort"] == {"repo": "example/project", "source_sha": HEAD}
    assert [t["id"] for t in model["broker"]["tasks"]] == TASK_IDS
    # Coverage history validated against the one available prior revision.
    assert world.append_checks == [([{"id": 1}], [{"id": 1}, {"id": 2}])]
    assert model["coverage"]["history_validation"]["status"] == "ORDERED_PREFIX_VERIFIED"
    assert model["coverage"]["history_validation"]["checked_available_git_revisions"] == ["HEAD"]


def test_source_model_graph_inventory(world):
    graphs = {g["id"]: g for g in atlas.source_model(world.root, HEAD)["graphs"]}
    expected = {"functional-spine", "local-rebuild", "typed-artifact-handoffs", "broker-control", "federation",
                "canonical-beams", "lane-l1", "superstitch", "group-g1", "cpq-dependencies", "python-main",
                "coverage-hierarchy"} | {"sipoc-" + b["id"] for b in profile_doc()["blocks"]}
    assert expected <= set(graphs)
    workflow = [g for g in graphs.values() if g["kind"] == "WORKFLOW_JOBS"]
    assert len(workflow) == 1 and workflow[0]["label"] == "Publisher"  # broken workflow skipped
    steps = sorted(g["id"] for g in graphs.values() if g["kind"] == "WORKFLOW_STEPS")
    assert steps == [workflow[0]["id"] + "-build", workflow[0]["id"] + "-publish"]
    build_steps = graphs[workflow[0]["id"] + "-build"]
    assert [n["id"] for n in build_steps["nodes"]] == ["build:1", "build:2"]
    assert build_steps["nodes"][1]["python_targets"] == ["src/worker.py"]
    assert graphs["typed-artifact-handoffs"]["nodes"] == [
        {"id": "method-atlas:result", "label": "method-atlas · result", "visual_role": "source"},
        {"id": "burndown:result", "label": "burndown · result", "visual_role": "source"}]
    beams = graphs["canonical-beams"]
    assert [n["id"] for n in beams["nodes"]] == ["A", "B", "C", "A@NEXT_PULSE"]
    assert [e["to"] for e in beams["edges"]] == ["B", "A@NEXT_PULSE", "A@NEXT_PULSE"]
    assert [n["id"] for n in graphs["lane-l1"]["nodes"]] == ["L1:s1", "L1:s2"]
    assert graphs["lane-l1"]["parent_id"] == "functional-spine"
    group = graphs["group-g1"]
    assert [n["id"] for n in group["nodes"]] == ["n1", "n2"]
    assert group["boundary_edges"] == [{"from": "n2", "to": "n3"}]
    assert graphs["python-main"]["edges"] == [{"from": "main", "to": "helper", "kind": "STATIC_CALL",
                                               "binding": "STATIC_SOURCE"}]
    sipoc = graphs["sipoc-method-atlas"]
    assert sipoc["nodes"][-1]["label"] == "Consumers: burndown"
    assert graphs["sipoc-pages-portal"]["nodes"][-1]["label"] == "Consumers: Owner / analyst"
    cov = graphs["coverage-hierarchy"]
    assert [n["role"] for n in cov["nodes"]] == ["viewer", "source", "source"]
    assert [(e["from"], e["to"]) for e in cov["edges"]] == [("portfolio", "repo"), ("repo", "cohort")]
    # Visual roles are attached to every node.
    roles = {n["id"]: n["visual_role"] for n in graphs["superstitch"]["nodes"]}
    assert roles == {"n1": "source", "n2": "waiting", "n3": "qualified"}
    fed = {n["id"]: n["visual_role"] for n in graphs["federation"]["nodes"]}
    assert fed == {"owner": "neutral", "repo": "blocked"}
    assert graphs["cpq-dependencies"]["nodes"][1]["status"] == "TODO"


def test_source_model_keeps_snapshot_time_and_reports_new_coverage_source(world, monkeypatch):
    original = world.root / "mission-control" / "coverage.json"
    assert original.exists()

    def no_history(where, *args):
        return {("rev-parse", "HEAD"): HEAD, ("status", "--porcelain"): ""}.get(args)
    monkeypatch.setattr(atlas, "git", no_history)
    model = atlas.source_model(world.root, HEAD, snapshot={"observed": "remote"})
    assert model["broker"]["generated_at"] == "2026-10-30T00:00:00Z"
    assert "time_basis" not in model["broker"]
    assert model["broker"]["snapshot"] == {"observed": "remote"}
    assert model["coverage"]["history_validation"]["status"] == "NEW_SOURCE_NO_PRIOR_REGISTRY_AVAILABLE"
    assert model["coverage"]["history_validation"]["checked_available_git_revisions"] == []


def test_source_model_rejects_inexact_or_mismatched_head(world):
    with pytest.raises(ValueError, match="^exact head required$"):
        atlas.source_model(world.root, "abc")
    with pytest.raises(ValueError, match="^checkout/head mismatch$"):
        atlas.source_model(world.root, OTHER)
    world.head = None  # not a git checkout: the declared head is accepted
    assert atlas.source_model(world.root, OTHER)["source"]["checkout_sha"] is None


def test_source_model_dirty_checkout_is_recorded(world):
    world.dirty = " M src/worker.py"
    assert atlas.source_model(world.root, HEAD)["source"]["dirty"] is True


def test_source_model_rejects_rewritten_coverage_history(world):
    write(world.root, "mission-control/coverage.json", {"events": [{"id": 9}]})
    with pytest.raises(ValueError, match="coverage history rewritten"):
        atlas.source_model(world.root, HEAD)


# ---------------------------------------------------------------- build
def test_build_writes_verified_bundle_and_replaces_it(world):
    out = world.tmp / "site" / "orchestration"
    result = atlas.build(world.root, out, HEAD)
    assert result["status"] == "LOCAL_SOURCE_BUILD_PASS" and result["out"] == str(out.resolve())
    manifest = atlas.verify_bundle(out, HEAD, require_clean=True, source_root=world.root)
    assert manifest["source_digest"] == result["source_digest"]
    assert result["members"] == len(manifest["files_sha256"])
    model = json.loads((out / "atlas.json").read_text(encoding="utf-8"))
    assert result["graphs"] == len(model["graphs"])
    for g in model["graphs"]:
        stem = atlas.artifact_stem(g["id"])
        assert g["paths"] == {"mermaid": "graphs/" + stem + ".mmd", "svg_light": "graphs/" + stem + ".light.svg",
                              "svg_dark": "graphs/" + stem + ".dark.svg"}
        assert (out / g["mermaid_path"]).read_text(encoding="utf-8") == g["mermaid"]
        assert g["canonical_mermaid_sha256"] == atlas.digest(g["mermaid"].encode())
    diagram = model["inventory"]["diagrams"][0]
    assert (out / diagram["artifact_path"]).read_bytes() == (world.root / "docs/flow.mmd").read_bytes()
    assert not any(p.name.startswith(".atlas-build-") for p in out.parent.iterdir())
    # A second build replaces the verified, manifest-owned directory.
    (world.root / "mission-control" / "views.json").write_bytes(atlas.canonical({"terms": ["changed"]}))
    again = atlas.build(world.root, out, HEAD)
    assert again["source_digest"] != result["source_digest"]
    assert atlas.verify_bundle(out, HEAD, source_root=world.root)["source_digest"] == again["source_digest"]


def test_build_refuses_to_replace_unverified_directory(world):
    out = world.tmp / "foreign"
    out.mkdir()
    (out / "keep.txt").write_text("not ours", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        atlas.build(world.root, out, HEAD)
    assert (out / "keep.txt").read_text(encoding="utf-8") == "not ours"


def test_build_rejects_output_overlapping_source(world):
    with pytest.raises(ValueError, match="^output overlaps source root$"):
        atlas.build(world.root, world.root / "build", HEAD)
    with pytest.raises(ValueError, match="^output overlaps source root$"):
        atlas.build(world.root, world.tmp, HEAD)


def test_build_attaches_validated_local_receipt(world):
    model = atlas.source_model(world.root, HEAD)
    receipt = receipt_for(model)
    out = world.tmp / "with-receipt"
    atlas.build(world.root, out, HEAD, local_receipt=receipt)
    assert json.loads((out / "local-run.json").read_text(encoding="utf-8")) == receipt
    assert json.loads((out / "atlas.json").read_text(encoding="utf-8"))["broker"]["local_receipt"] == receipt
    atlas.verify_bundle(out, HEAD)
    # Tampering with the receipt member breaks the bundle even after resealing it.
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    raw = atlas.canonical({**receipt, "outcome": "LOCAL_GENERATORS_FAIL"})
    (out / "local-run.json").write_bytes(raw)
    manifest["files_sha256"]["local-run.json"] = atlas.digest(raw)
    manifest["files_bytes"]["local-run.json"] = len(raw)
    (out / "manifest.json").write_bytes(atlas.canonical(manifest))
    with pytest.raises(ValueError, match="^local receipt member mismatch$"):
        atlas.verify_bundle(out, HEAD)


def test_build_rejects_receipt_from_other_snapshot(world):
    model = atlas.source_model(world.root, HEAD)
    receipt = receipt_for(model)
    receipt["source_digest"] = "0" * 64
    out = world.tmp / "rejected"
    with pytest.raises(ValueError, match="^local receipt source mismatch$"):
        atlas.build(world.root, out, HEAD, local_receipt=receipt)
    assert not out.exists()


def test_verify_bundle_detects_coverage_drift(world):
    out = world.tmp / "cov"
    atlas.build(world.root, out, HEAD)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    def reseal(name, raw):
        (out / name).write_bytes(raw)
        manifest["files_sha256"][name] = atlas.digest(raw)
        manifest["files_bytes"][name] = len(raw)
        (out / "manifest.json").write_bytes(atlas.canonical(manifest))

    original = (out / "coverage_burndown.jsonl").read_bytes()
    reseal("coverage_burndown.jsonl", b'{"event": 1}\n')
    with pytest.raises(ValueError, match="^coverage ledger mismatch$"):
        atlas.verify_bundle(out, HEAD)
    reseal("coverage_burndown.jsonl", original)
    reseal("metric_observations.json", atlas.canonical({"changed": True}))
    with pytest.raises(ValueError, match="^coverage model mismatch$"):
        atlas.verify_bundle(out, HEAD)
    (out / "metric_observations.json").unlink()
    del manifest["files_sha256"]["metric_observations.json"]
    del manifest["files_bytes"]["metric_observations.json"]
    (out / "manifest.json").write_bytes(atlas.canonical(manifest))
    with pytest.raises(ValueError, match="^coverage outputs missing$"):
        atlas.verify_bundle(out, HEAD)


# ---------------------------------------------------------------- local receipt edge
def test_receipt_percentile_without_samples_is_rejected():
    tasks = [{"id": "only", "repo": "r", "needs": []}]
    model = {"source": {"head_sha": HEAD, "source_digest": "d" * 64}, "broker": {"tasks": tasks}}
    receipt = {"schema": "atlas.local-broker.receipt.v1", "source_sha": HEAD, "source_digest": "d" * 64,
               "local_process_only": True, "dispatch_authorized": False, "merge_authorized": False,
               "authority_transfer": False, "source_changed_during_run": False, "success": False,
               "outcome": "LOCAL_GENERATORS_FAIL", "bounds": {"task_count": 1, "workers": 1, "max_pending": 1},
               "metrics": {"elapsed_seconds": 0, "max_running": 0, "peak_ready": 0, "ready_wait_sample_count": 0,
                           "deferred_ready_count": 0, "peak_deferred_ready": 0, "succeeded": 0, "failed": 0,
                           "blocked": 1, "ready_wait_p50_seconds": None, "ready_wait_p95_seconds": None},
               "tasks": {"only": {"state": "blocked", "repo": "r", "needs": [], "ready_wait_seconds": None,
                                  "execution_seconds": None}}}
    assert atlas.validate_local_receipt(receipt, model) is receipt
    receipt["metrics"]["ready_wait_p95_seconds"] = 0.0
    with pytest.raises(ValueError, match="^percentile without local samples$"):
        atlas.validate_local_receipt(receipt, model)


# ---------------------------------------------------------------- run_local
def test_run_local_executes_every_registered_handler(world):
    out = world.tmp / "run"
    receipt = atlas.run_local(world.root, out, HEAD, workers=3)
    run_call = next(c for c in world.calls if c[0] == "run_local")
    assert run_call[1:4] == (3, 4, world.root) and run_call[4] == {"default_max_pending": 4}
    results = receipt["results"]
    assert results["validate"]["status"] == "PASS"
    for identity in ("method", "control", "superstitch", "convergence"):
        assert results[identity]["status"] == "OUTPUT_CONTRACT_PASS"
        assert results[identity]["artifacts"][0]["path"] == "result.json"
        assert (out / (identity + ".log")).read_text(encoding="utf-8") == identity + " out\n"
    assert results["orchestration"]["status"] == "LOCAL_SOURCE_BUILD_PASS"
    assert results["assemble"] == {"status": "VERIFIED_MEMBERS_JOINED"}
    assert results["portal"] == {"status": "LOCAL_PACKAGE_PASS_NOT_PUBLISHED"}
    assert (out / "assemble" / "orchestration" / "manifest.json").is_file()
    assert (out / "assemble" / "superstitch" / "result.json").is_file()
    assert (out / "portal.log").read_text(encoding="utf-8") == "portal ok\n"
    verify_runs = [c[1] for c in world.calls if c[0] == "run" and "--verify-only" in c[1]]
    assert sorted(Path(c[c.index("--out") + 1]).name for c in verify_runs) == ["convergence", "superstitch"]
    head_args = [c[1] for c in world.calls if c[0] == "run" and "--head" in c[1]]
    assert all(c[c.index("--head") + 1] == HEAD for c in head_args) and len(head_args) == 4
    assert receipt["source_changed_during_run"] is False and receipt["success"] is True
    assert receipt["evidence_class"] == "LOCAL_EXECUTION_NOT_NATIVE_CI"
    assert receipt["output_directory"] == str(out.resolve())
    assert json.loads((out / "local-run.json").read_text(encoding="utf-8")) == receipt


def test_run_local_marks_source_change_during_run(world):
    world.run_hook = lambda: write(world.root, "mission-control/late.json", {"late": True})
    out = world.tmp / "run"
    receipt = atlas.run_local(world.root, out, HEAD)
    assert receipt["source_changed_during_run"] is True
    assert receipt["success"] is False and receipt["outcome"] == "SOURCE_CHANGED_DURING_LOCAL_RUN"
    assert receipt["error"] == "Source snapshot changed during execution; rebuild from a stable checkout."


def move_head(world):
    def hook():
        world.head = OTHER
    return hook


def test_run_local_head_moved_before_handlers_blocks_nested_build(world):
    world.run_hook = move_head(world)
    # The checkout no longer matches, so the nested orchestration build refuses.
    with pytest.raises(ValueError, match="^checkout/head mismatch$"):
        atlas.run_local(world.root, world.tmp / "run", HEAD)
    assert not (world.tmp / "run" / "orchestration").exists()


def test_run_local_head_moved_after_handlers_is_source_change(world):
    world.after_hook = move_head(world)
    receipt = atlas.run_local(world.root, world.tmp / "run", HEAD)
    assert receipt["source_changed_during_run"] is True
    assert receipt["outcome"] == "SOURCE_CHANGED_DURING_LOCAL_RUN"


def test_run_local_generator_failure_names_log(world):
    world.generator_rc["method"] = 3
    out = world.tmp / "run"
    with pytest.raises(ValueError, match="^method generator failed; see method.log$"):
        atlas.run_local(world.root, out, HEAD)
    assert (out / "method.log").read_text(encoding="utf-8") == "method out\nboom\n"


def test_run_local_verify_only_failure(world):
    world.verify_rc["superstitch"] = 1
    with pytest.raises(ValueError, match="^superstitch output verification failed$"):
        atlas.run_local(world.root, world.tmp / "run", HEAD)


def test_run_local_portal_source_mismatch(world):
    world.portal = lambda portal, manifest: manifest.update(source_git_sha=OTHER)
    with pytest.raises(ValueError, match="^Pages package source mismatch$"):
        atlas.run_local(world.root, world.tmp / "run", HEAD)


def test_run_local_preconditions(world):
    with pytest.raises(ValueError, match="^local run output must be outside the source checkout$"):
        atlas.run_local(world.root, world.root / "out", HEAD)
    busy = world.tmp / "busy"
    busy.mkdir()
    (busy / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="^local run requires a new or empty output directory$"):
        atlas.run_local(world.root, busy, HEAD)
    with pytest.raises(ValueError, match="^checkout/head mismatch$"):
        atlas.run_local(world.root, world.tmp / "fresh", OTHER)
    assert not (world.tmp / "fresh").exists()


# ---------------------------------------------------------------- CLI
def _run_main(argv, capsys):
    code = atlas.main(argv)
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_main_build_then_check_bundle(world, capsys):
    out = world.tmp / "cli"
    code, stdout, _ = _run_main(["build", "--root", str(world.root), "--out", str(out)], capsys)
    assert code == 0 and json.loads(stdout)["status"] == "LOCAL_SOURCE_BUILD_PASS"
    code, stdout, _ = _run_main(["check", "--root", str(world.root), "--out", str(out)], capsys)
    result = json.loads(stdout)
    assert code == 0 and result["bundle"] == "VERIFIED" and result["status"] == "PASS"
    code, _, err = _run_main(["check", "--root", str(world.root), "--out", str(out), "--head", OTHER], capsys)
    assert code == 1 and json.loads(err) == {"status": "FAIL", "error": "bundle head mismatch", "remote_dispatch": False}


def test_main_build_with_snapshot_and_local_receipt(world, capsys):
    model = atlas.source_model(world.root, HEAD, snapshot={"pulse": 1})
    receipt_path = write(world.tmp, "receipt.json", receipt_for(model))
    snap_path = write(world.tmp, "snapshot.json", {"pulse": 1})
    out = world.tmp / "cli"
    code, stdout, _ = _run_main(["build", "--root", str(world.root), "--out", str(out), "--head", HEAD,
                                 "--snapshot", str(snap_path), "--local-receipt", str(receipt_path)], capsys)
    assert code == 0, stdout
    bundled = json.loads((out / "atlas.json").read_text(encoding="utf-8"))
    assert bundled["broker"]["snapshot"] == {"pulse": 1}
    assert bundled["broker"]["generated_at"] == "2026-10-30T00:00:00Z"
    assert (out / "local-run.json").is_file()


def test_main_plan_with_snapshot_keeps_observation_time(world, capsys):
    snap = write(world.tmp, "snapshot.json", {"pulse": 2})
    out = world.tmp / "plan"
    code, stdout, _ = _run_main(["plan", "--root", str(world.root), "--out", str(out), "--head", HEAD,
                                 "--snapshot", str(snap)], capsys)
    plan = json.loads((out / "broker-plan.json").read_text(encoding="utf-8"))
    assert code == 0 and json.loads(stdout) == plan
    assert plan["generated_at"] == "2026-10-30T00:00:00Z" and "time_basis" not in plan
    assert plan["cohort"] == {"repo": "example/project", "source_sha": HEAD}


def test_main_run_local_success_and_source_change_exit_codes(world, capsys):
    code, stdout, _ = _run_main(["run-local", "--root", str(world.root), "--out", str(world.tmp / "r1"),
                                 "--workers", "1"], capsys)
    assert code == 0 and json.loads(stdout)["success"] is True
    world.run_hook = lambda: write(world.root, "mission-control/late.json", {"late": True})
    code, stdout, _ = _run_main(["run-local", "--root", str(world.root), "--out", str(world.tmp / "r2")], capsys)
    assert code == 1 and json.loads(stdout)["outcome"] == "SOURCE_CHANGED_DURING_LOCAL_RUN"


def test_main_requires_out_for_non_check_commands(world, capsys):
    for command in ("build", "plan", "run-local"):
        code, stdout, err = _run_main([command, "--root", str(world.root), "--head", HEAD], capsys)
        assert code == 1 and stdout == ""
        assert json.loads(err)["error"] == "--out required"


def test_main_reports_malformed_snapshot(world, capsys):
    bad = world.tmp / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    code, _, err = _run_main(["build", "--root", str(world.root), "--out", str(world.tmp / "o"),
                              "--snapshot", str(bad)], capsys)
    assert code == 1 and json.loads(err)["status"] == "FAIL"
    assert not (world.tmp / "o").exists()


# ---------------------------------------------------------------- small helpers
def test_graph_role_precedence():
    assert atlas.graph_role({"status": "failed", "native_qualified": True}) == "blocked"
    assert atlas.graph_role({"role": "hold"}) == "blocked"
    assert atlas.graph_role({"native_qualified": True, "state": "PENDING"}) == "qualified"
    assert atlas.graph_role({"state": "DEFERRED", "role": "viewer"}) == "waiting"
    assert atlas.graph_role({"class": "Control"}) == "viewer"
    assert atlas.graph_role({"role": "actor"}) == "neutral"
    assert atlas.graph_role({"role": "anything"}) == "source"


def test_graph_svg_cycle_falls_back_to_grid_rows():
    nodes = [{"id": "n" + str(i), "label": "Node " + str(i)} for i in range(6)]
    edges = [{"from": "n0", "to": "n1", "kind": "DEPENDENCY", "binding": "DECLARED"},
             {"from": "n1", "to": "n0", "kind": "UNKNOWN_KIND", "binding": "LOCAL_CONTRACT"}]
    graph = atlas.graph_record("cyclic", "Cyclic graph", "TEST", nodes, edges, "x.json")
    svg = atlas.graph_svg(graph, "dark")
    assert 'viewBox="0 0 1080 420"' in svg  # two grid rows of at most four
    assert '<rect x="30" y="230"' in svg  # n4 starts the second row
    assert 'stroke="#8568bf"' in svg and 'stroke-dasharray="6 4"' in svg
    with pytest.raises(ValueError, match="^unknown graph theme$"):
        atlas.graph_svg(graph, "sepia")


def test_validate_artifact_text_and_unschematised_json(tmp_path):
    (tmp_path / "notes.txt").write_text("plain text", encoding="utf-8")
    row = atlas.validate_artifact(tmp_path, {"path": "notes.txt", "kind": "text"})
    assert row == {"path": "notes.txt", "bytes": 10, "sha256": atlas.digest(b"plain text")}
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    with pytest.raises(UnicodeDecodeError):
        atlas.validate_artifact(tmp_path, {"path": "bad.txt", "kind": "text"})
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert atlas.validate_artifact(tmp_path, {"path": "list.json", "kind": "json"})["bytes"] == 6
    with pytest.raises(ValueError, match="^missing artifact field: k$"):
        atlas.validate_artifact(tmp_path, {"path": "list.json", "kind": "json", "required_fields": ["k"]})
    assert atlas.validate_artifact(tmp_path, {"path": "absent.json", "required": False}) is None
