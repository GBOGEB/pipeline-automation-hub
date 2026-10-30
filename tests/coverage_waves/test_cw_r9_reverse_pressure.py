"""Coverage wave r9: reverse_pressure.py branch and statement coverage."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import runpy
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "federation-atlas" / "flightdeck" / "pulses"
MOD_PATH = MOD_DIR / "reverse_pressure.py"
if str(MOD_DIR) not in sys.path:
    sys.path.insert(0, str(MOD_DIR))

_spec = importlib.util.spec_from_file_location("cw_r9_reverse_pressure_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

COUNT_KEYS = ("success", "failure", "cancelled", "pending", "queued", "in_progress", "other")


def build(state="open"):
    ids = [
        ("FORMAT", "DOW_BLACK_ISORT", "P1", 2),
        ("SECURITY", "DOW_BANDIT_SAFETY", "P0", 3),
        ("PY_COMPAT", "PY310_DEPENDENCY", "P1", 2),
        ("WORKFLOW_POLICY", "GOVERNANCE_CANONICAL", "P0", 2),
        ("COVERAGE_MODE", None, "P1", 1),
        ("REPLAY", "FOUR_HOP", "P2", 1),
    ]
    families = [{"id": alias, "priority": tier} for _, alias, tier, _ in ids if alias]
    owners, obs, serial = [], [], 0
    for rid, _alias, _tier, n in ids:
        links = []
        for _ in range(n):
            serial += 1
            links.append(f"GBOGEB/ABACUS#{serial}")
            obs.append({"repository": "GBOGEB/ABACUS", "pr": serial,
                        "head_sha": f"{serial:040x}", "state": state, "failed": 2})
        owners.append({"id": rid, "canonical": links[0], "related": links[1:],
                       "status": "MULTIPLE_OVERLAPPING_X" if rid == "SECURITY" else "REPAIR_OPEN"})
    return {"families": families}, {"all_observations": obs, "root_owners": owners}


def delta_for(rows, **counts):
    c = dict.fromkeys(COUNT_KEYS, 0)
    c.update(counts or {"success": 1, "pending": 1})
    return {"schema": m.DELTA_SCHEMA, "observation_grade": "METADATA_ONLY",
            "authority_transfer": False, "merge_authorized": False,
            "accepted_root_closures": 0,
            "rows": [{"repository": r["repository"], "pr": r["pr"], "head_sha": r["head_sha"],
                      "state": r["state"], "reused_artifact_bytes": False,
                      "observed_workflow_runs": sum(c.values()), "counts": dict(c)}
                     for r in rows]}


@pytest.fixture
def stubs(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "cbq_ch_bd_render",
                        types.SimpleNamespace(validate=lambda a: calls.append("pulse")))
    monkeypatch.setitem(sys.modules, "cbq_impact_census",
                        types.SimpleNamespace(validate=lambda a, b: calls.append("census")))
    return calls


# --- require / identity -------------------------------------------------------

def test_require_passes_and_raises():
    assert m.require(True, "X") is None
    with pytest.raises(ValueError, match="^BOOM$"):
        m.require(0, "BOOM")


def test_identity_ok():
    assert m.identity({"repository": "GBOGEB/x", "pr": 5, "head_sha": "a" * 40}) == "GBOGEB/x#5"


@pytest.mark.parametrize("row,msg", [
    ([], "INVALID_OBSERVATION_ROW"),
    ({"repository": 1, "pr": 1}, "INVALID_PR_IDENTITY"),
    ({"repository": "OTHER/x", "pr": 1}, "INVALID_PR_IDENTITY"),
    ({"repository": "GBOGEB/x", "pr": True}, "INVALID_PR_IDENTITY"),
    ({"repository": "GBOGEB/x", "pr": 0}, "INVALID_PR_IDENTITY"),
    ({"repository": "GBOGEB/x", "pr": 1, "head_sha": None}, "INVALID_HEAD_SHA"),
    ({"repository": "GBOGEB/x", "pr": 1, "head_sha": "A" * 40}, "INVALID_HEAD_SHA"),
    ({"repository": "GBOGEB/x", "pr": 1, "head_sha": "a" * 41}, "INVALID_HEAD_SHA"),
])
def test_identity_rejects(row, msg):
    with pytest.raises(ValueError, match=msg):
        m.identity(row)


# --- validate_delta -----------------------------------------------------------

def test_validate_delta_none_is_empty():
    assert m.validate_delta(None) == {}


def test_validate_delta_ok_keys():
    _, c = build()
    out = m.validate_delta(delta_for(c["all_observations"][:2]))
    assert list(out) == ["GBOGEB/ABACUS#1", "GBOGEB/ABACUS#2"]


@pytest.mark.parametrize("mutate", [
    lambda d: "not a dict",
    lambda d: {**d, "schema": "x"},
    lambda d: {**d, "observation_grade": "FULL"},
    lambda d: {**d, "authority_transfer": 0},
    lambda d: {**d, "accepted_root_closures": 1},
])
def test_validate_delta_authority(mutate):
    _, c = build()
    with pytest.raises(ValueError, match="DELTA_AUTHORITY_OR_SCHEMA"):
        m.validate_delta(mutate(delta_for(c["all_observations"][:1])))


@pytest.mark.parametrize("rows", [None, [], {}])
def test_validate_delta_missing_rows(rows):
    _, c = build()
    d = delta_for(c["all_observations"][:1])
    d["rows"] = rows
    with pytest.raises(ValueError, match="DELTA_MISSING_ROWS"):
        m.validate_delta(d)


def _one_row_delta():
    _, c = build()
    return delta_for(c["all_observations"][:1])


def test_validate_delta_invalid_state():
    d = _one_row_delta()
    d["rows"][0]["state"] = "draft"
    with pytest.raises(ValueError, match="DELTA_INVALID_STATE"):
        m.validate_delta(d)


@pytest.mark.parametrize("counts", [None, [1], {"success": 1}])
def test_validate_delta_counts_schema(counts):
    d = _one_row_delta()
    d["rows"][0]["counts"] = counts
    with pytest.raises(ValueError, match="DELTA_COUNTS_SCHEMA"):
        m.validate_delta(d)


def test_validate_delta_negative_count():
    d = _one_row_delta()
    d["rows"][0]["counts"]["success"] = -1
    with pytest.raises(ValueError, match="DELTA_COUNTS_INVALID"):
        m.validate_delta(d)


@pytest.mark.parametrize("value", ["2", True])
def test_validate_delta_runs_not_int(value):
    d = _one_row_delta()
    d["rows"][0]["observed_workflow_runs"] = value
    with pytest.raises(ValueError, match="DELTA_COUNTS_NOT_EXHAUSTIVE"):
        m.validate_delta(d)


def test_validate_delta_zero_runs_rejected():
    d = _one_row_delta()
    d["rows"][0]["counts"] = dict.fromkeys(COUNT_KEYS, 0)
    d["rows"][0]["observed_workflow_runs"] = 0
    with pytest.raises(ValueError, match="DELTA_COUNTS_NOT_EXHAUSTIVE"):
        m.validate_delta(d)


def test_validate_delta_missing_reuse_flag():
    d = _one_row_delta()
    del d["rows"][0]["reused_artifact_bytes"]
    with pytest.raises(ValueError, match="DELTA_FORGED_ARTIFACT_PROOF"):
        m.validate_delta(d)


def test_validate_delta_bad_identity():
    d = _one_row_delta()
    d["rows"][0]["head_sha"] = "nope"
    with pytest.raises(ValueError, match="INVALID_HEAD_SHA"):
        m.validate_delta(d)


# --- analyze ------------------------------------------------------------------

def test_analyze_calls_validators_and_ranks(stubs):
    p, c = build()
    r = m.analyze(p, c)
    assert stubs == ["pulse", "census"]
    rows = r["root_owners"]
    assert [x["root_id"] for x in rows] == [
        "SECURITY", "WORKFLOW_POLICY", "FORMAT", "PY_COMPAT", "COVERAGE_MODE", "REPLAY"]
    assert [x["pressure_score"] for x in rows] == [9, 6, 4, 4, 2, 1]
    assert [x["rank_within_policy_tiers"] for x in rows] == [1, 2, 3, 4, 5, 6]
    cov = next(x for x in rows if x["root_id"] == "COVERAGE_MODE")
    assert cov["priority_basis"] == "PROVISIONAL_COVERAGE_POLICY"
    assert rows[0]["priority_basis"] == "FROZEN_CBQ_POLICY"
    assert rows[0]["owner_reconciliation_required"] is True
    assert rows[1]["owner_reconciliation_required"] is False
    assert rows[0]["failed_workflow_manifestations"] == 6
    assert rows[0]["not_refreshed_refs"] == rows[0]["direct_references"]
    assert rows[0]["descriptive_pressure_share"] == round(9 / 26, 6)
    met = r["metrics"]
    assert met["canonical_owner_overlap_clusters"] == 1
    assert met["unique_open_referenced_prs"] == 11
    assert met["overlapping_pressure_total_not_unique_roots"] == 26
    assert met["delta_workflow_status_counts"] == dict.fromkeys(COUNT_KEYS, 0)
    assert r["worker_proposals"]["candidate_root_ids"] == ["SECURITY", "WORKFLOW_POLICY"]
    assert r["worker_proposals"]["proposed_readonly_waves"][1]["pr_ids"] == []
    assert r["schema"] == m.SCHEMA


def test_analyze_no_open_prs_zero_total(stubs):
    p, c = build(state="merged")
    r = m.analyze(p, c)
    assert all(x["pressure_score"] == 0 for x in r["root_owners"])
    assert all(x["descriptive_pressure_share"] is None for x in r["root_owners"])
    assert r["metrics"]["unique_open_referenced_prs"] == 0
    # tie on weight and score -> sorted by root_id within tier
    p0 = [x["root_id"] for x in r["root_owners"] if x["priority"] == "P0"]
    assert p0 == sorted(p0)


def test_analyze_full_delta_matched_and_closed_overrides(stubs):
    p, c = build()
    d = delta_for(c["all_observations"], success=1, failure=2, queued=1)
    for row in d["rows"]:
        row["state"] = "closed"
    r = m.analyze(p, c, d)
    for x in r["root_owners"]:
        assert x["source_matched_for_delta"] is True
        assert x["changed_head_refs"] == [] and x["not_refreshed_refs"] == []
        assert x["referenced_open_prs"] == [] and x["reverse_reach"] == 0
    met = r["metrics"]
    assert met["delta_observed_prs"] == 11
    assert met["delta_workflow_observations"] == 44
    assert met["delta_terminal_workflow_observations"] == 33
    assert met["delta_nonterminal_workflow_observations"] == 11
    assert met["delta_terminal_fraction_descriptive"] == 0.75
    assert met["delta_workflow_status_counts"]["failure"] == 22
    q = r["proof_drain"]
    assert [x["pr"] for x in q] == sorted(x["pr"] for x in q)
    assert q[0]["terminal_fraction_descriptive"] == 0.75
    assert r["worker_proposals"]["proposed_readonly_waves"][1]["pr_ids"] == [q[0]["pr"], q[1]["pr"]]


@pytest.mark.xfail(strict=True, reason="production_defect: failed_workflow_manifestations "
                   "ignores delta counts['failure'] (reads top-level 'failure'/'failed' only), "
                   "so refreshed PRs report 0 failures")
def test_delta_failures_counted_in_manifestations(stubs):
    p, c = build()
    d = delta_for(c["all_observations"], failure=3)
    r = m.analyze(p, c, d)
    fmt = next(x for x in r["root_owners"] if x["root_id"] == "FORMAT")
    assert fmt["failed_workflow_manifestations"] == 6


def test_analyze_top_level_failure_key_preferred(stubs):
    p, c = build()
    c["all_observations"][0]["failure"] = 10
    r = m.analyze(p, c)
    fmt = next(x for x in r["root_owners"] if x["root_id"] == "FORMAT")
    assert fmt["failed_workflow_manifestations"] == 12


def test_analyze_family_alias_missing(stubs):
    p, c = build()
    p["families"] = [f for f in p["families"] if f["id"] != "FOUR_HOP"]
    with pytest.raises(ValueError, match="FAMILY_ALIAS_MISSING"):
        m.analyze(p, c)


def test_analyze_invalid_priority(stubs):
    p, c = build()
    p["families"][0]["priority"] = "P9"
    with pytest.raises(ValueError, match="INVALID_PRIORITY"):
        m.analyze(p, c)


def test_analyze_bad_ident_reference(stubs):
    p, c = build()
    c["root_owners"][0]["related"] = ["not-an-ident"]
    with pytest.raises(ValueError, match="UNSUPPORTED_DEPENDENCY_EDGE"):
        m.analyze(p, c)


def test_analyze_validator_error_propagates(monkeypatch):
    def boom(a):
        raise ValueError("NATIVE_PULSE_BAD")
    monkeypatch.setitem(sys.modules, "cbq_ch_bd_render", types.SimpleNamespace(validate=boom))
    monkeypatch.setitem(sys.modules, "cbq_impact_census",
                        types.SimpleNamespace(validate=lambda a, b: None))
    p, c = build()
    with pytest.raises(ValueError, match="NATIVE_PULSE_BAD"):
        m.analyze(p, c)


# --- produce / main -----------------------------------------------------------

def _write_inputs(tmp_path, with_delta):
    p, c = build()
    pp, cp = tmp_path / "pulse.json", tmp_path / "census.json"
    pp.write_text(json.dumps(p), encoding="utf-8")
    cp.write_text(json.dumps(c), encoding="utf-8")
    dp = None
    if with_delta:
        dp = tmp_path / "delta.json"
        d = delta_for(c["all_observations"][:3], success=1, pending=3)
        d["rows"][1]["head_sha"] = "f" * 40
        dp.write_text(json.dumps(d), encoding="utf-8")
    return pp, cp, dp


def test_produce_with_delta(tmp_path, stubs):
    pp, cp, dp = _write_inputs(tmp_path, True)
    out = tmp_path / "out" / "nested"
    manifest = m.produce(pp, cp, dp, out)
    assert set(manifest["input_sha256"]) == {"pulse.json", "census.json", "delta.json"}
    assert manifest["input_sha256"]["delta.json"] == hashlib.sha256(dp.read_bytes()).hexdigest()
    for name, digest in manifest["output_sha256"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    on_disk = json.loads((out / "reverse_pressure_manifest.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    data = json.loads((out / "reverse_pressure.json").read_text(encoding="utf-8"))
    assert data["source_hashes"] == manifest["input_sha256"]
    with (out / "reverse_pressure.csv").open(encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))
    assert len(rows) == 6 and rows[0]["root_id"] == "SECURITY"
    assert "direct_references" not in rows[0]
    md = (out / "reverse_pressure.md").read_text(encoding="utf-8")
    assert "PARTIAL_OR_DRIFT" in md
    assert "| GBOGEB/ABACUS#1 | 3 | 1 | 25.00% |" in md
    assert md.count("| GBOGEB/ABACUS#") == 3


def test_produce_without_delta_all_matched_label(tmp_path, stubs):
    pp, cp, _ = _write_inputs(tmp_path, False)
    p, c = build()
    dp = tmp_path / "full.json"
    dp.write_text(json.dumps(delta_for(c["all_observations"])), encoding="utf-8")
    out = tmp_path / "o2"
    m.produce(str(pp), str(cp), str(dp), str(out))
    md = (out / "reverse_pressure.md").read_text(encoding="utf-8")
    assert "MATCHED" in md and "PARTIAL_OR_DRIFT" not in md

    out3 = tmp_path / "o3"
    man = m.produce(pp, cp, None, out3)
    assert set(man["input_sha256"]) == {"pulse.json", "census.json"}
    md3 = (out3 / "reverse_pressure.md").read_text(encoding="utf-8")
    assert "PARTIAL_OR_DRIFT" in md3
    assert md3.endswith("QPS=DEFER.\n")


def test_main_prints_manifest(tmp_path, stubs, monkeypatch, capsys):
    pp, cp, _ = _write_inputs(tmp_path, False)
    out = tmp_path / "cli"
    monkeypatch.setattr(sys, "argv", ["rp", "--pulse", str(pp), "--recensus", str(cp),
                                      "--out", str(out)])
    m.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == "code-purple.reverse-pressure.manifest.v1"
    assert (out / "reverse_pressure.json").is_file()


def test_main_requires_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["rp"])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 2


def test_dunder_main(tmp_path, stubs, monkeypatch, capsys):
    pp, cp, dp = _write_inputs(tmp_path, True)
    out = tmp_path / "rm"
    monkeypatch.setattr(sys, "argv", ["rp", "--pulse", str(pp), "--recensus", str(cp),
                                      "--delta", str(dp), "--out", str(out)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    printed = json.loads(capsys.readouterr().out)
    assert "delta.json" in printed["input_sha256"]


def test_module_constants_structural():
    assert set(m.ALIASES) == {"FORMAT", "SECURITY", "PY_COMPAT", "WORKFLOW_POLICY",
                              "COVERAGE_MODE", "REPLAY"}
    assert all(k in m.DEFAULT_PRIORITY for k, v in m.ALIASES.items() if v is None)
    assert copy.deepcopy(m.PRIORITY_WEIGHT)["P0"] > m.PRIORITY_WEIGHT["P1"]
