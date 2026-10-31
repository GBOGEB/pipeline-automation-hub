"""Coverage wave r9: branch coverage for mission-control/gogreen/spine.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "gogreen" / "spine.py"
_spec = importlib.util.spec_from_file_location("cw_r9_spine_mod", MOD_PATH)
spine = importlib.util.module_from_spec(_spec)
sys.modules["cw_r9_spine_mod"] = spine
_spec.loader.exec_module(spine)

HEAD = "a" * 40
BASE = "b" * 40
REPO = "Org/repo"


def _catalog_entry(repo=REPO, families=("ci_contract", "security")):
    return {"repository": repo, "head_sha": HEAD, "ref_kind": "MAIN",
            "target_families": list(families), "authority_transfer": False}


def _obs(run_id=11, **over):
    row = {
        "repository": REPO, "family": "ci_contract", "source_sha": HEAD,
        "suite_id": "pytest", "run_id": run_id, "run_number": 3, "run_attempt": 1,
        "job_id": 77, "workflow_status": "completed", "workflow_conclusion": "success",
        "job_status": "completed", "job_conclusion": "success",
        "config_identity": "cfg-1",
        "run_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
        "evidence_class": "GITHUB_NATIVE_METADATA",
    }
    row.update(over)
    return row


def _intake(observations=None, catalog=None):
    return {"schema": spine.INPUT_SCHEMA,
            "repositories": catalog if catalog is not None else [_catalog_entry()],
            "observations": observations if observations is not None else [_obs()]}


def _cat():
    return spine._check_catalog([_catalog_entry()])


# ---------------------------------------------------------------- helpers

def test_canonical_is_sorted_compact_ascii():
    assert spine.canonical({"b": 1, "a": "é"}) == '{"a":"\\u00e9","b":1}'


@pytest.mark.parametrize("value,positive", [(-1, False), (0, True), (True, False), (1.0, False), ("1", True)])
def test_strict_count_rejects(value, positive):
    with pytest.raises(ValueError, match="positive" if positive else "nonnegative"):
        spine._strict_count(value, "x", positive=positive)


def test_strict_count_accepts():
    assert spine._strict_count(0, "x") == 0
    assert spine._strict_count(5, "x", positive=True) == 5


@pytest.mark.parametrize("value", [None, "A" * 40, "a" * 39, 123])
def test_sha_rejects(value):
    with pytest.raises(ValueError, match="40-byte"):
        spine._sha(value, "lbl")


# ---------------------------------------------------------------- catalog

@pytest.mark.parametrize("catalog,msg", [
    (None, "nonempty"), ([], "nonempty"), (["x"], "invalid catalog entry"),
    ([{"repository": "bad name"}], "repository identity"),
    ([{"repository": 5}], "repository identity"),
    ([_catalog_entry(), _catalog_entry()], "repository identity"),
    ([{**_catalog_entry(), "head_sha": "zz"}], "40-byte"),
    ([{**_catalog_entry(), "ref_kind": "BRANCH"}], "distinguish"),
    ([{**_catalog_entry(), "target_families": []}], "families"),
    ([{**_catalog_entry(), "target_families": "ci_contract"}], "families"),
    ([{**_catalog_entry(), "target_families": ["security", "security"]}], "families"),
    ([{**_catalog_entry(), "target_families": ["nope"]}], "families"),
    ([{**_catalog_entry(), "authority_transfer": None}], "authority transfer"),
])
def test_check_catalog_rejects(catalog, msg):
    with pytest.raises(ValueError, match=msg):
        spine._check_catalog(catalog)


def test_check_catalog_accepts_pr_head():
    found = spine._check_catalog([{**_catalog_entry(), "ref_kind": "PR_HEAD"}, _catalog_entry("Org/two")])
    assert set(found) == {REPO, "Org/two"}


# ---------------------------------------------------------------- observations

ART = {"id": 4, "archive_sha256": "c" * 64, "bytes_verified": False}
BD = {"before": 5, "after": 4, "resolved": 2, "introduced": 1, "scope_id": "s", "tool_version": "v"}


@pytest.mark.parametrize("row,msg", [
    ("notadict", "invalid observation"),
    (_obs(repository="Other/x"), "outside declared"),
    (_obs(family="coverage"), "outside declared"),
    (_obs(source_sha="nope"), "observation source"),
    (_obs(base_sha="nope"), "observation baseline"),
    (_obs(source_sha="d" * 40), "exact head"),
    (_obs(suite_id=""), "suite identity"),
    (_obs(suite_id=3), "suite identity"),
    (_obs(run_number=0), "run_number"),
    (_obs(job_id=None), "job_id"),
    (_obs(job_status="weird"), "invalid workflow/job state"),
    (_obs(workflow_status="queued"), "nonterminal workflow"),
    (_obs(job_status="in_progress"), "nonterminal job"),
    (_obs(config_identity=""), "config identity"),
    (_obs(run_url="https://example.invalid/x"), "native run URL"),
    (_obs(evidence_class="SCRAPED"), "evidence class"),
    (_obs(artifact="x"), "artifact identity"),
    (_obs(artifact={"id": "4"}), "artifact identity"),
    (_obs(artifact={"id": 0}), "artifact identity"),
    (_obs(artifact={"id": 1, "archive_sha256": 5}), "SHA-256"),
    (_obs(artifact={"id": 1, "archive_sha256": "z" * 64}), "SHA-256"),
    (_obs(artifact={"id": 1, "archive_sha256": "c" * 64, "bytes_verified": 1}), "verification status"),
    (_obs(artifact={"id": 1, "archive_sha256": "c" * 64, "bytes_verified": True}), "independent receipt"),
    (_obs(test_counts=[1]), "invalid test counts"),
    (_obs(test_counts={"executed": 1, "passed": -1, "failed": 0, "skipped": 0}), "passed"),
    (_obs(test_counts={"executed": 3, "passed": 1, "failed": 0, "skipped": 0}), "denominator"),
    (_obs(scoped_burndown=BD), "observed exact baseline"),
    (_obs(base_sha=BASE, scoped_burndown="x"), "invalid burndown"),
    (_obs(base_sha=BASE, scoped_burndown={**BD, "resolved": None}), "resolved"),
    (_obs(base_sha=BASE, scoped_burndown={**BD, "after": 9}), "nonreconciling"),
    (_obs(base_sha=BASE, scoped_burndown={**BD, "scope_id": ""}), "measurement scope"),
    (_obs(base_sha=BASE, scoped_burndown={**BD, "tool_version": None}), "tool version"),
])
def test_check_observation_rejects(row, msg):
    with pytest.raises(ValueError, match=msg):
        spine._check_observation(row, _cat())


def test_observation_bytes_verified_with_counts_and_burndown():
    row = _obs(base_sha=BASE, scoped_burndown=dict(BD),
               test_counts={"executed": 3, "passed": 2, "failed": 0, "skipped": 1},
               artifact={"id": 9, "archive_sha256": "c" * 64, "bytes_verified": True,
                         "verifier_receipt": "r"})
    v = spine._check_observation(row, _cat())
    assert v["status"] == "NATIVE_PASS_BYTES_VERIFIED"
    assert v["artifact_id"] == 9 and v["artifact_bytes_verified"] is True
    assert v["scoped_burndown"]["after"] == 4
    assert v["merge_admitted"] is False and v["root_closed"] is False


def test_observation_status_only_and_metadata_and_artifact_unverified():
    assert spine._check_observation(_obs(config_identity="UNKNOWN"), _cat())["status"] == "NATIVE_PASS_STATUS_ONLY"
    v = spine._check_observation(_obs(artifact=dict(ART)), _cat())
    assert v["status"] == "NATIVE_PASS_METADATA" and v["artifact_id"] == 4
    assert v["artifact_bytes_verified"] is False


@pytest.mark.parametrize("over", [
    {"test_counts": {"executed": 2, "passed": 1, "failed": 1, "skipped": 0}},
    {"test_counts": {"executed": 1, "passed": 0, "failed": 0, "skipped": 1}},
    {"workflow_conclusion": "failure"},
    {"workflow_status": "queued", "workflow_conclusion": None},
])
def test_observation_non_green(over):
    assert spine._check_observation(_obs(**over), _cat())["status"] == "NON_GREEN_OR_NONTERMINAL"


def test_observation_zero_executed_counts_still_pass():
    v = spine._check_observation(_obs(test_counts={"executed": 0, "passed": 0, "failed": 0, "skipped": 0}), _cat())
    assert v["status"] == "NATIVE_PASS_METADATA"


# ---------------------------------------------------------------- build

@pytest.mark.parametrize("intake,msg", [
    ("x", "input schema"), ({"schema": "other"}, "input schema"),
    ({"schema": spine.INPUT_SCHEMA, "repositories": [_catalog_entry()], "observations": None}, "observations array"),
    (_intake([_obs(), _obs()]), "duplicated"),
])
def test_build_rejects(intake, msg):
    with pytest.raises(ValueError, match=msg):
        spine.build(intake)


def test_build_breadth_packets_and_repeatability():
    obs = [_obs(run_id=20), _obs(run_id=10, config_identity="UNKNOWN"),
           _obs(run_id=30, job_conclusion="failure"),
           _obs(run_id=40, artifact={"id": 2, "archive_sha256": "e" * 64,
                                     "bytes_verified": True, "verifier_receipt": "rcpt"})]
    catalog = [_catalog_entry(), _catalog_entry("Org/two", ("coverage",))]
    evidence, plan, hooks = spine.build(_intake(obs, catalog))
    assert [o["run_id"] for o in evidence["observations"]] == [10, 20, 30, 40]
    b = evidence["breadth"]
    assert b["catalog_repositories"] == 2 and b["catalog_repo_family_cells"] == 3
    assert b["observed_cells"] == 1 and b["not_observed_cells"] == 2
    assert b["native_green_status_only_observations"] == 1
    assert b["native_green_status_only_cells"] == 1
    assert b["native_green_metadata_observations"] == 1
    assert b["native_green_bytes_verified_observations"] == 1
    assert b["native_green_cells"] == 1 and b["fleet_release_admission"] == "HOLD"
    assert evidence["repeatability"] == [{"repo": REPO, "suite_id": "pytest", "sha": HEAD,
                                          "distinct_pass_run_ids": 3, "statistically_independent": None,
                                          "repeatability_qualified": None}]
    ids = [p["packet_id"] for p in plan["packets"]]
    assert ids == ["GG-G0-001", "GG-G0-002", "GG-G1-003"]
    assert [(p["repository"], p["family"]) for p in plan["packets"][:2]] == [
        ("Org/repo", "security"), ("Org/two", "coverage")]
    assert plan["target_repositories"] == ["Org/repo", "Org/two"]
    assert not any(p["dispatch_authorized"] for p in plan["packets"])
    assert [c["repository"] for c in hooks["catalog"]] == ["Org/repo", "Org/two"]
    assert hooks["qps_triage"]["suggested_disposition"] == "DEFER"


def test_build_empty_observations():
    evidence, plan, _ = spine.build(_intake([]))
    assert evidence["observations"] == [] and evidence["repeatability"] == []
    assert len(plan["packets"]) == 2


# ---------------------------------------------------------------- emit / verify

def test_emit_then_verify_roundtrip(tmp_path):
    out = tmp_path / "o"
    ev = spine.emit(_intake(), out)
    assert ev["breadth"]["native_green_metadata_observations"] == 1
    manifest = spine.verify_output(out)
    assert set(manifest["sha256"]) == set(spine.OUTPUTS)
    assert b"\r\n" not in (out / "summary.md").read_bytes()
    assert "Target repositories: **1**" in (out / "summary.md").read_text(encoding="utf-8")


def _rewrite(out, name, mutate):
    data = json.loads((out / name).read_text(encoding="utf-8"))
    mutate(data)
    blob = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (out / name).write_bytes(blob)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    m["sha256"][name] = hashlib.sha256(blob).hexdigest()
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")


@pytest.mark.parametrize("name,mutate,msg", [
    ("manifest.json", lambda m: m.update(schema="x"), "invalid output manifest"),
    ("manifest.json", lambda m: m.update(authority_transfer=True), "invalid output manifest"),
    ("manifest.json", lambda m: m["sha256"].pop("summary.md"), "invalid output manifest"),
    ("manifest.json", lambda m: m["sha256"].update({"summary.md": "XYZ"}), "bytes mismatch"),
    ("manifest.json", lambda m: m["sha256"].update({"summary.md": "0" * 64}), "bytes mismatch"),
    ("evidence.json", lambda e: e.update(merge_authorized=True), "unauthorized promotion"),
    ("evidence.json", lambda e: e.update(authority_transfer=None), "unauthorized promotion"),
    ("federation_hooks.json", lambda h: h.update(authority_transfer=True), "federation"),
    ("federation_hooks.json", lambda h: h.update(child_acceptance="ACCEPT"), "federation"),
    ("federation_hooks.json", lambda h: h["qps_triage"].update(suggested_disposition="GO"), "federation"),
    ("federation_hooks.json", lambda h: h["qps_triage"].update(admission_evidence=True), "federation"),
    ("federation_hooks.json", lambda h: h.pop("qps_triage"), "federation"),
    ("scout_packets.json", lambda p: p.update(execution_authorized=True), "unauthorized dispatch"),
    ("scout_packets.json", lambda p: p["packets"][0].update(dispatch_authorized=True), "unauthorized dispatch"),
])
def test_verify_output_rejects_tampering(tmp_path, name, mutate, msg):
    out = tmp_path / "o"
    spine.emit(_intake(), out)
    if name == "manifest.json":
        m = json.loads((out / name).read_text(encoding="utf-8"))
        mutate(m)
        (out / name).write_text(json.dumps(m), encoding="utf-8")
    else:
        _rewrite(out, name, mutate)
    with pytest.raises(ValueError, match=msg):
        spine.verify_output(out)


# ---------------------------------------------------------------- main

def test_main_generate_and_verify(tmp_path, capsys):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(_intake()), encoding="utf-8")
    out = tmp_path / "out"
    spine.main(["--input", str(inp), "--out", str(out)])
    breadth = json.loads(capsys.readouterr().out)
    assert breadth["catalog_repositories"] == 1 and breadth["observed_cells"] == 1
    spine.main(["--out", str(out), "--verify"])
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["schema"] == "gogreen.manifest.v1"


def test_main_requires_input(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        spine.main(["--out", str(tmp_path / "o")])
    assert exc.value.code == 2
    assert "--input required" in capsys.readouterr().err


def test_dunder_main_runs(tmp_path, monkeypatch, capsys):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(_intake()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["spine.py", "--input", str(inp), "--out", str(tmp_path / "o")])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["catalog_repositories"] == 1


def test_real_sample_structural():
    sample = REPO_ROOT / "mission-control" / "gogreen" / "samples" / "fleet_g0.json"
    if not sample.exists():
        pytest.skip("sample absent")
    evidence, plan, hooks = spine.build(json.loads(sample.read_text(encoding="utf-8")))
    assert isinstance(evidence["breadth"], dict) and "packets" in plan and "catalog" in hooks
