"""Behavioural tests for mission-control/grand-missions/run_gm_iv_pilot2_recensus.py."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

nbformat = pytest.importorskip("nbformat")

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "run_gm_iv_pilot2_recensus.py"
SOURCE = "5" * 40


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_run_gm_iv_pilot2_recensus", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry():
    return {
        "authority_transfer": False,
        "grand_missions": [
            {
                "id": "GM-IV",
                "state": "STAGED_ACTIVE_PILOT_2_OF_8",
                "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
                "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
                "unfilled_frontier_slots": ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
                "children": [],
            },
            {"id": "GM-V", "state": "HELD", "children": []},
        ],
    }


ASSESSOR_PAYLOADS = {
    "assess_gm_iv_f01_pilot.py": {
        "frontier_disposition": "PILOT_CONTROL_READY",
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "mission_state": "STAGED_ACTIVE_PILOT_2_OF_8",
        "mission_promotion": "WITHHELD_FROM_F01_RECURRENCE_ONLY",
    },
    "assess_gm_iv_ring1.py": {
        "result": "PASS",
        "historical_evidence_stage": "RECON_2_OF_8",
        "current_mission_state": "STAGED_ACTIVE_PILOT_2_OF_8",
        "dispositions": {"GM-IV-F01": {"disposition": "PILOT"}, "GM-IV-F02": {"disposition": "REFERENCE"}},
    },
    "assess_gm_iv_f03_pilot.py": {
        "frontier_disposition": "PILOT_CONTROL_READY",
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "mission_state": "STAGED_ACTIVE_PILOT_2_OF_8",
        "mission_promotion": "WITHHELD_FROM_F03_RECURRENCE_ONLY",
    },
    "assess_gm_iv_ring2.py": {
        "result": "PASS",
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "mission_state": "STAGED_ACTIVE_PILOT_2_OF_8",
        "dispositions": {"GM-IV-F03": {"disposition": "PILOT_READY"}, "GM-IV-F04": {"disposition": "REFERENCE"}},
        "mission_promotion": "WITHHELD_FROM_RING2_RECURRENCE_ONLY",
    },
    "assess_gm_iv_pilot2_governor.py": {
        "result": "PASS",
        "promotion_decision": "PROMOTE_PILOT_2_OF_8",
        "mission_state": "STAGED_ACTIVE_PILOT_2_OF_8",
        "next_stage": "WITHHELD_PENDING_SEPARATE_RECON_4_OF_8_GOVERNOR_GATE",
    },
    "validate_gm_fleet.py": {"source_sha": SOURCE},
    "assess_gm_fleet_03.py": {"structural_gate": "PASS"},
}

BOUNDARY_MARKERS = (
    "validated F03 Level-1 SSOT identity",
    "validated F03 runtime producer role",
    "validated F03 authority_transfer=false",
    "validated F03 must_not authority boundary",
    "F03 authority validation passed",
)
BRIDGE_POSITIVE = (
    "validated glossary: g\nvalidated bridge manifest: m\nvalidated taxonomy: t\n"
    "validated QPS triage applicability: q\nADR_OCD bridge validation passed\n"
)


def _populate(dest: Path, name: str, f04_files):
    if name == "f01":
        p = dest / "federation" / "ADR_OCD" / "bridge_manifest.yaml"
        p.parent.mkdir(parents=True)
        p.write_text(yaml.safe_dump({"qps_authority_source": {"repo": "GBOGEB/cryoplant-project"}}), encoding="utf-8")
    elif name == "f02":
        (dest / "action.yml").write_text('runs:\n  using: "composite"\n  steps:\n    - uses: actions/attest@v1\n', encoding="utf-8")
        (dest / "README.md").write_text("A Wrapper action; new implementations should use `actions/attest`.\n", encoding="utf-8")
    elif name == "f03":
        (dest / "level1").mkdir()
        (dest / "level1" / "ssot.json").write_text(json.dumps({"authority_transfer": False}), encoding="utf-8")
    elif name == "f04":
        (dest / "ReadMe.md").write_text("YAML 1.2 Reference Parsers\nRun make test\n", encoding="utf-8")
        for rel, data in f04_files.items():
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)


class FakeWorld:
    """Simulates git, python validators/assessors and make for the recensus runner."""

    def __init__(self, mod):
        self.mod = mod
        self.calls = []
        self.dirty = set()
        self.payloads = json.loads(json.dumps(ASSESSOR_PAYLOADS))
        self.rev_override = {}
        self.f04_files = {}
        self.econ = {"status": "PASS", "passed": 3, "denominator": 3}
        self.crew = {"status": "PASS", "time_resolution": "MICROSECOND_INTEGER"}
        self.repo_head = SOURCE
        self.shas = {"f01": mod.F01_SHA, "f02": mod.F02_SHA, "f03": mod.F03_SHA, "f04": mod.F04_SHA}

    def _result(self, cmd, rc, stdout="", check=True):
        if check and rc != 0:
            raise subprocess.CalledProcessError(rc, cmd, stdout)
        return subprocess.CompletedProcess(cmd, rc, stdout, None)

    def __call__(self, cmd, *, cwd=None, check=True, capture=False, timeout=None, env=None):
        self.calls.append({"cmd": list(cmd), "cwd": cwd, "check": check, "capture": capture, "timeout": timeout, "env": env})
        if cmd[0] == "git" and cmd[1] == "-C":
            dest = Path(cmd[2])
            sub = cmd[3]
            if sub == "checkout":
                _populate(dest, dest.name, self.f04_files)
            if sub == "rev-parse":
                return self._result(cmd, 0, self.rev_override.get(dest.name, self.shas[dest.name]) + "\n", check)
            if sub == "status":
                return self._result(cmd, 0, " M x\n" if dest.name in self.dirty else "", check)
            return self._result(cmd, 0, "", check)
        if cmd[0] == "git":
            return self._result(cmd, 0, self.repo_head + "\n", check)
        if cmd[0] == "make":
            return self._result(cmd, 2, "make: no rule\n", check)
        script = Path(cmd[1]).name
        if script == "mip_repo_self_index.py":
            Path(cmd[cmd.index("--output") + 1]).write_text("{}", encoding="utf-8")
            return self._result(cmd, 0, "", check)
        if script == "validate_adr_ocd_bridge.py":
            if "--manifest" in cmd:
                data = yaml.safe_load(Path(cmd[cmd.index("--manifest") + 1]).read_text(encoding="utf-8"))
                if data["qps_authority_source"]["repo"] != "GBOGEB/cryoplant-project":
                    return self._result(cmd, 1, "qps_authority_source.repo must be GBOGEB/cryoplant-project\n", check)
            return self._result(cmd, 0, BRIDGE_POSITIVE, check)
        if script == "validate_gm_iv_f03_boundary.py":
            data = json.loads(Path(cmd[2]).read_text(encoding="utf-8"))
            if data["authority_transfer"]:
                return self._result(cmd, 1, "authority_transfer must be false\n", check)
            return self._result(cmd, 0, "\n".join(BOUNDARY_MARKERS), check)
        if script == "validate_gm_iv_evidence_economics.py":
            return self._result(cmd, 0, json.dumps(self.econ), check)
        if script == "validate_crew_exposure.py":
            receipt = json.loads(Path(cmd[2]).read_text(encoding="utf-8"))
            assert receipt["exposure_seconds"] == 4.0
            return self._result(cmd, 0, json.dumps(self.crew), check)
        if script in self.payloads:
            out = Path(cmd[cmd.index("--out") + 1])
            out.write_text(json.dumps(self.payloads[script], sort_keys=True), encoding="utf-8")
            return self._result(cmd, 0, "", check)
        raise AssertionError(f"unexpected command {cmd}")


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    mod = _load_module()
    here = tmp_path / "here"
    here.mkdir()
    (here / "GRAND_MISSION_REGISTRY.json").write_text(json.dumps(_registry()), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(mod, "HERE", here)
    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "PY", "py")
    work = tmp_path / "work"

    def fake_mkdtemp(prefix=""):
        assert prefix == "gmiv-pilot2-recensus-"
        work.mkdir()
        return str(work)

    monkeypatch.setattr(mod.tempfile, "mkdtemp", fake_mkdtemp)
    world = FakeWorld(mod)
    monkeypatch.setattr(mod, "run", world)
    digest = mod.NOTEBOOK_DIGEST
    monkeypatch.setattr(mod, "execute_notebook_twice", lambda f03: ((3, 0, digest), (3, 0, digest)))
    monkeypatch.setenv("SOURCE_SHA", SOURCE)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["recensus", "--out-dir", str(out)])
    return {"mod": mod, "world": world, "out": out, "work": work, "here": here, "repo": repo}


def _final(ctx):
    return json.loads((ctx["out"] / "GM_IV_PILOT2_FINAL_RECENSUS.json").read_text(encoding="utf-8"))


def test_main_full_pass(ctx, capsys):
    assert ctx["mod"].main() == 0
    final = _final(ctx)
    assert final["result"] == "PASS"
    assert len(final["checks"]) == 14
    assert all(final["checks"].values())
    assert final["run_id"] == "LOCAL"
    assert final["source_sha"] == SOURCE
    assert not ctx["work"].exists()
    f01 = json.loads((ctx["out"] / "f01-pilot-runtime.json").read_text(encoding="utf-8"))
    assert f01["positive_validated_surface_count"] == 4
    assert f01["negative_rejection_marker"] is True
    bad = yaml.safe_load((ctx["out"] / "f01-bad-manifest.yaml").read_text(encoding="utf-8"))
    assert bad["qps_authority_source"]["repo"] == "GBOGEB/NOT_THE_QPS_AUTHORITY"
    boundary = json.loads((ctx["out"] / "f03-boundary.json").read_text(encoding="utf-8"))
    assert boundary["positive_marker_count"] == 5 and boundary["negative_rejection_observed"]
    f04 = json.loads((ctx["out"] / "f04-reference.json").read_text(encoding="utf-8"))
    assert f04["test_exit_code"] == 2 and f04["reference_parser_identity"] is True
    canary = json.loads((ctx["out"] / "crew-exposure-canary.json").read_text(encoding="utf-8"))
    assert canary["assignment_opened_at"].split("+")[0].endswith(".123456")
    assessor_calls = [c for c in ctx["world"].calls if c["env"] is not None]
    assert assessor_calls and all(c["env"] == {"SOURCE_SHA": SOURCE} and c["cwd"] == ctx["repo"] for c in assessor_calls)
    make = [c for c in ctx["world"].calls if c["cmd"][0] == "make"][0]
    assert make["timeout"] == 180 and make["check"] is False
    assert json.loads(capsys.readouterr().out)["result"] == "PASS"


def test_source_sha_from_git_and_run_id(ctx, monkeypatch):
    monkeypatch.delenv("SOURCE_SHA")
    monkeypatch.setenv("GITHUB_RUN_ID", "99")
    assert ctx["mod"].main() == 0
    final = _final(ctx)
    assert final["source_sha"] == SOURCE
    assert final["run_id"] == "99"
    first = ctx["world"].calls[0]
    assert first["cmd"] == ["git", "rev-parse", "HEAD"] and first["cwd"] == ctx["repo"]


def test_inexact_source_sha(ctx, monkeypatch):
    monkeypatch.setenv("SOURCE_SHA", "abc")
    with pytest.raises(RuntimeError, match="SOURCE_SHA is not exact"):
        ctx["mod"].main()
    assert not ctx["work"].exists()


def test_exact_fetch_mismatch_cleans_work(ctx):
    ctx["world"].rev_override["f02"] = "0" * 40
    with pytest.raises(RuntimeError, match="exact fetch mismatch"):
        ctx["mod"].main()
    assert not ctx["work"].exists()


def test_dirty_targets_fail_checks(ctx):
    ctx["world"].dirty = {"f01", "f02", "f03", "f04"}
    assert ctx["mod"].main() == 1
    checks = _final(ctx)["checks"]
    assert checks["02_f01_positive_negative_clean"] is False
    assert checks["04_f02_reference_contract"] is False
    assert checks["06_f03_positive_negative_runtime_clean"] is False
    assert checks["08_f04_reference_real_attempt"] is False
    assert checks["10_governor_transition"] is True
    ctrl = json.loads((ctx["out"] / "f03-runtime-control.json").read_text(encoding="utf-8"))
    assert ctrl["target_dirty_count"] == 1


def test_f04_authority_claim_and_file_skips(ctx):
    ctx["world"].f04_files = {
        "big.txt": b"qps authority " + b"x" * 1_000_001,
        "bin.dat": b"\xff\xfe\x00bad",
        ".git/config": b"gbogeb/cryoplant-project",
        "src/claim.txt": b"see GBOGEB/cryoplant-project here",
    }
    assert ctx["mod"].main() == 1
    f04 = json.loads((ctx["out"] / "f04-reference.json").read_text(encoding="utf-8"))
    assert f04["qps_authority_claim_detected"] is True
    assert _final(ctx)["checks"]["08_f04_reference_real_attempt"] is False


def test_f04_skips_do_not_trigger_claim(ctx):
    ctx["world"].f04_files = {
        "big.txt": b"qps authority " + b"x" * 1_000_001,
        "bin.dat": b"\xff\xfe\x00bad",
        ".git/config": b"gbogeb/cryoplant-project",
    }
    assert ctx["mod"].main() == 0
    f04 = json.loads((ctx["out"] / "f04-reference.json").read_text(encoding="utf-8"))
    assert f04["qps_authority_claim_detected"] is False


def test_notebook_digest_mismatch(ctx, monkeypatch):
    monkeypatch.setattr(ctx["mod"], "execute_notebook_twice", lambda f03: ((3, 0, "d1"), (3, 1, "d2")))
    assert ctx["mod"].main() == 1
    final = _final(ctx)
    assert final["checks"]["06_f03_positive_negative_runtime_clean"] is False
    ring = json.loads((ctx["out"] / "f03-ring2-runtime.json").read_text(encoding="utf-8"))
    assert ring["repeat_equal"] is False and ring["error_count"] == 1


@pytest.mark.parametrize(
    "script,field,value,check",
    [
        ("assess_gm_iv_f01_pilot.py", "mission_promotion", "PROMOTED", "03_f01_assessor_repeat_history"),
        ("assess_gm_iv_ring1.py", "result", "FAIL", "05_ring1_repeat_history"),
        ("assess_gm_iv_f03_pilot.py", "frontier_disposition", "X", "07_f03_assessor_repeat_history"),
        ("assess_gm_iv_ring2.py", "mission_promotion", "PROMOTED", "09_ring2_repeat_history"),
        ("assess_gm_iv_pilot2_governor.py", "promotion_decision", "HOLD", "10_governor_transition"),
        ("validate_gm_fleet.py", "source_sha", "0" * 40, "11_fleet_capacity_regressions"),
        ("assess_gm_fleet_03.py", "structural_gate", "FAIL", "11_fleet_capacity_regressions"),
    ],
)
def test_assessor_disagreement_fails_check(ctx, script, field, value, check):
    ctx["world"].payloads[script][field] = value
    assert ctx["mod"].main() == 1
    final = _final(ctx)
    assert final["result"] == "FAIL"
    assert final["checks"][check] is False


def test_evidence_economics_fail(ctx):
    ctx["world"].econ = {"status": "PASS", "passed": 2, "denominator": 3}
    assert ctx["mod"].main() == 1
    assert _final(ctx)["checks"]["12_evidence_economics"] is False


def test_crew_exposure_resolution(ctx):
    ctx["world"].crew = {"status": "PASS"}
    assert ctx["mod"].main() == 1
    assert _final(ctx)["checks"]["13_crew_exposure_microsecond_control"] is False


def test_terminal_shape(ctx):
    reg = _registry()
    reg["grand_missions"][1]["state"] = "LIVE"
    (ctx["here"] / "GRAND_MISSION_REGISTRY.json").write_text(json.dumps(reg), encoding="utf-8")
    assert ctx["mod"].main() == 1
    assert _final(ctx)["checks"]["14_terminal_shape"] is False


def test_f02_contract_missing_wrapper(ctx, monkeypatch):
    world = ctx["world"]
    orig = world.__call__

    def wrapped(cmd, **kw):
        res = orig(cmd, **kw)
        if cmd[0] == "git" and cmd[1] == "-C" and cmd[3] == "checkout" and Path(cmd[2]).name == "f02":
            (Path(cmd[2]) / "README.md").write_text("plain\n", encoding="utf-8")
        return res

    monkeypatch.setattr(ctx["mod"], "run", wrapped)
    assert ctx["mod"].main() == 1
    assert _final(ctx)["checks"]["04_f02_reference_contract"] is False


def test_run_builds_subprocess_kwargs(monkeypatch):
    mod = _load_module()
    seen = []

    def fake_run(cmd, **kw):
        seen.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, "o", None)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setenv("CW_BASE_VAR", "base")
    mod.run(["x"], cwd="d", check=False, capture=True, timeout=5, env={"EXTRA": "1"})
    cmd, kw = seen[0]
    assert kw["stdout"] is subprocess.PIPE and kw["stderr"] is subprocess.STDOUT
    assert kw["env"]["EXTRA"] == "1" and kw["env"]["CW_BASE_VAR"] == "base"
    assert kw["cwd"] == "d" and kw["check"] is False and kw["timeout"] == 5 and kw["text"] is True
    mod.run(["y"])
    _, kw2 = seen[1]
    assert "stdout" not in kw2 and kw2["check"] is True
    assert "EXTRA" not in kw2["env"]


def test_json_and_hash_helpers(tmp_path):
    mod = _load_module()
    p = tmp_path / "a.json"
    mod.write_json(p, {"b": 1, "a": [1]})
    assert p.read_text(encoding="utf-8").endswith("\n")
    assert mod.read_json(p) == {"a": [1], "b": 1}
    assert mod.sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_git_clean_and_call_assessor(monkeypatch, tmp_path):
    mod = _load_module()
    calls = []

    def fake(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, "?? f\n" if "status" in cmd else "", None)

    monkeypatch.setattr(mod, "run", fake)
    monkeypatch.setattr(mod, "PY", "py")
    monkeypatch.setattr(mod, "HERE", tmp_path)
    monkeypatch.setattr(mod, "REPO", tmp_path / "r")
    assert mod.git_clean(tmp_path) is False
    mod.call_assessor("s.py", ["--a", "1"], tmp_path / "o.json", SOURCE)
    cmd, kw = calls[-1]
    assert cmd == ["py", str(tmp_path / "s.py"), "--a", "1", "--out", str(tmp_path / "o.json")]
    assert kw == {"cwd": tmp_path / "r", "env": {"SOURCE_SHA": SOURCE}}


def test_exact_fetch_success_and_existing_dest(monkeypatch, tmp_path):
    mod = _load_module()
    calls = []

    def fake(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, mod.F01_SHA + "\n", None)

    monkeypatch.setattr(mod, "run", fake)
    dest = tmp_path / "d"
    mod.exact_fetch("https://example.invalid/r.git", mod.F01_SHA, dest)
    assert [c[3] for c in calls] == ["init", "remote", "fetch", "checkout", "rev-parse"]
    assert calls[2][-2:] == ["origin", mod.F01_SHA]
    with pytest.raises(FileExistsError):
        mod.exact_fetch("u", mod.F01_SHA, dest)


def _notebook(path: Path):
    nb = nbformat.v4.new_notebook()
    code = nbformat.v4.new_code_cell("print(1)")
    code.outputs = [
        nbformat.v4.new_output("stream", name="stdout", text="1\n"),
        nbformat.v4.new_output("execute_result", data={"text/plain": "2", "image/png": "AAAA", "text/html": "<b>2</b>"}, execution_count=1),
        nbformat.v4.new_output("display_data", data={"text/plain": "d"}),
        nbformat.v4.new_output("error", ename="ValueError", evalue="bad", traceback=[]),
    ]
    other = nbformat.v4.new_code_cell("x = 1")
    md = nbformat.v4.new_markdown_cell("# title")
    nb.cells = [md, code, other]
    path.parent.mkdir(parents=True)
    nbformat.write(nb, str(path))


def test_execute_notebook_twice(monkeypatch, tmp_path):
    mod = _load_module()
    f03 = tmp_path / "f03"
    _notebook(f03 / "notebooks" / "population.ipynb")
    seen = []

    class FakeEP:
        def __init__(self, timeout, kernel_name):
            seen.append((timeout, kernel_name))

        def preprocess(self, nb, resources):
            seen.append(resources["metadata"]["path"])
            return nb, resources

    monkeypatch.setattr(mod, "ExecutePreprocessor", FakeEP)
    first, second = mod.execute_notebook_twice(f03)
    assert first == second
    cells, errors, digest = first
    assert cells == 2 and errors == 1
    assert len(digest) == 64
    assert seen[0] == (120, "python3")
    assert seen[1] == str(f03 / "notebooks")
    governed = [
        {
            "source": "print(1)",
            "outputs": [
                {"output_type": "stream", "name": "stdout", "text": "1\n"},
                {"output_type": "execute_result", "data": {"text/html": "<b>2</b>", "text/plain": "2"}},
                {"output_type": "display_data", "data": {"text/plain": "d"}},
                {"output_type": "error", "ename": "ValueError", "evalue": "bad"},
            ],
        },
        {"source": "x = 1", "outputs": []},
    ]
    raw = json.dumps(governed, sort_keys=True, separators=(",", ":")).encode()
    assert digest == mod.sha256_bytes(raw)
