"""Coverage wave 10: mission-control/v2/handoff/live_lossless/build_live_lossless.py (tmp_path writes only)."""
import copy
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "v2" / "handoff" / "live_lossless" / "build_live_lossless.py"
_spec = importlib.util.spec_from_file_location("cw_w10_build_live_lossless_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_REAL_READ = mod.read


@pytest.fixture(scope="module")
def src():
    _state, _stats, ledger, _bd, _prov = mod.validate_frozen()
    delta, _ = mod.read(mod.HERE / "FOLLOWUP_DELTA_20261017.json")
    obs, _ = mod.read(mod.HERE / "GITHUB_OBSERVED_20261017.json")
    return delta, obs, ledger


def patch_read(monkeypatch, filename, mutate):
    """Wrap mod.read so one named source is mutated in memory; repo files stay untouched."""
    def fake(path):
        value, digest = _REAL_READ(path)
        if Path(path).name == filename:
            value = copy.deepcopy(value)
            mutate(value)
        return value, digest
    monkeypatch.setattr(mod, "read", fake)


# --------------------------------------------------------------------------- public_link
def test_public_link_rejects_unparseable_and_foreign():
    assert mod.public_link("https://github.com/GBOGEB/x") is True
    assert mod.public_link("http://[::1") is False  # urlparse raises ValueError
    assert mod.public_link("https://user@github.com/GBOGEB/x") is False
    assert mod.public_link("https://example.com/GBOGEB/x") is False


# --------------------------------------------------------------------------- validate_frozen
@pytest.mark.parametrize("filename,mutate,pattern", [
    ("MANIFEST.json", lambda m: m.update(authority_transfer=True), "frozen manifest authority"),
    ("MANIFEST.json", lambda m: m.update(verbatim_transcript_claim=True), "full ChatGPT transcript"),
    ("MANIFEST.json", lambda m: m["member_sha256"].update({"EXTRA.json": "0" * 64}), "unexpected frozen file"),
    ("STATE.json", lambda s: s.update(authority_transfer=True), "cardinality / privacy / BD drift"),
])
def test_validate_frozen_guards(monkeypatch, filename, mutate, pattern):
    patch_read(monkeypatch, filename, mutate)
    with pytest.raises(ValueError, match=pattern):
        mod.validate_frozen()


# --------------------------------------------------------------------------- validate_delta
def _delta_case(src, mutate, ledger_mutate=None):
    delta, obs, ledger = (copy.deepcopy(x) for x in src)
    mutate(delta, obs)
    if ledger_mutate:
        ledger_mutate(ledger)
    return delta, obs, ledger


def _set_run(key, value):
    def m(d, o):
        o["native_run"][key] = value
    return m


@pytest.mark.parametrize("mutate,pattern", [
    (lambda d, o: d.update(schema="x"), "delta schema"),
    (lambda d, o: d["intent"].update(id="SC-I999"), "append-only"),
    (lambda d, o: d.update(subrequests=d["subrequests"][:3]), "missing distinct subrequests"),
    (lambda d, o: d["subrequests"][0].update(title=""), "unowned subrequest"),
    (lambda d, o: o.update(schema="x"), "observed GitHub schema"),
    (lambda d, o: o.update(prs=[p for p in o["prs"] if p["number"] != 620]), "required PR source observations"),
    (_set_run("conclusion", "failure"), "native matched SHA"),
    (_set_run("tests_total", 0), "native QA denominator"),
    (_set_run("url", "https://example.com/run"), "native run source URL"),
])
def test_validate_delta_guards(src, mutate, pattern):
    delta, obs, ledger = _delta_case(src, mutate)
    with pytest.raises(ValueError, match=pattern):
        mod.validate_delta(delta, obs, ledger)


def test_validate_delta_dangling_dag_edge(src):
    def ledger_mutate(ledger):
        ledger["actions"][0]["depends_on"] = ["NOT-AN-ACTION"]
    delta, obs, ledger = _delta_case(src, lambda d, o: None, ledger_mutate)
    with pytest.raises(ValueError, match="dangling DAG edge"):
        mod.validate_delta(delta, obs, ledger)


# --------------------------------------------------------------------------- build_data guards
def test_build_data_rejects_live_profile_prompt_count(monkeypatch):
    patch_read(monkeypatch, "LIVE_LOSSLESS_PROFILE_v1.json",
               lambda p: p.setdefault("data_population_policy", {}).update(original_user_prompt_count=5))
    with pytest.raises(ValueError, match="CP.LIVE cannot replace canonical source"):
        mod.build_data()


def test_build_data_rejects_unresolved_intent_link(monkeypatch):
    patch_read(monkeypatch, "INTENT_ACTION_LEDGER.json",
               lambda led: led["intents"][0].setdefault("actions", []).append("GHOST-ACTION"))
    with pytest.raises(ValueError, match="unresolved intent link"):
        mod.build_data()


# --------------------------------------------------------------------------- build / CLI
def test_build_check_on_absent_dir(tmp_path):
    with pytest.raises(ValueError, match="published source directory absent"):
        mod.build(tmp_path / "missing", check=True)


def test_build_then_check_roundtrip_and_extra_file(tmp_path):
    out = tmp_path / "pub"
    res = mod.build(out)
    assert res["artifacts"] == len(mod.FILES) and res["prompts"] is None
    assert mod.build(out, check=True)["manifest_sha256"] == res["manifest_sha256"]
    (out / "stray.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognized/extra public files"):
        mod.build(out, check=True)


def test_main_writes_to_out(tmp_path, monkeypatch, capsys):
    out = tmp_path / "site"
    monkeypatch.setattr(sys, "argv", ["build_live_lossless.py", "--out", str(out)])
    mod.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == mod.SCHEMA
    assert sorted(p.name for p in out.iterdir()) == sorted(mod.FILES)


def test_dunder_main_success(tmp_path, monkeypatch, capsys):
    out = tmp_path / "site"
    monkeypatch.setattr(sys, "argv", ["build_live_lossless.py", "--out", str(out)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["merge_admission"] == "HOLD"


def test_dunder_main_fail_closed_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["build_live_lossless.py", "--out", str(tmp_path / "absent"), "--check"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 2
    assert "published source directory absent" in capsys.readouterr().err
