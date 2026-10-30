"""Behavioural coverage for scripts/run_processing.py.

subprocess.run is faked on the loaded module; every input/output dir lives
under tmp_path. module.__file__ points at tmp_path/repo/scripts so REPO_ROOT
and default dirs never resolve into the real checkout.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "scripts" / "run_processing.py"


@pytest.fixture
def rp(tmp_path):
    fake_file = tmp_path / "repo" / "scripts" / "cw_run_processing_shadow.py"
    fake_file.parent.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location("cw_run_processing", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(fake_file)
    spec.loader.exec_module(mod)
    return mod


def wjson(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


GOOD_TABLE = {"summary": {"errors": 0, "tables_exported": 3, "schedule_candidates": 1},
              "authority": {"authority_transfer": False}}
GOOD_SCHED = {"summary": {"process_status": "PASS", "activities": 4, "red": 1, "yellow": 2, "green": 1,
                          "validation_pass_rate_pct": 97.5},
              "authority": {"authority_transfer": False}}


class FakeRun:
    """Records commands; per-script behaviour returns CompletedProcess-like objects."""

    def __init__(self, behaviours):
        self.behaviours = behaviours
        self.calls = []

    def __call__(self, cmd, capture_output, text, cwd):
        assert capture_output is True and text is True
        self.calls.append((list(cmd), cwd))
        name = Path(cmd[1]).name
        action = self.behaviours[name]
        return action(cmd) if callable(action) else action


def proc(rc=0, out="", err=""):
    return SimpleNamespace(returncode=rc, stdout=out, stderr=err)


# ---------------------------------------------------------------- _env_bool / parse_args

@pytest.mark.parametrize("raw,expected", [(" TRUE ", True), ("yes", True), ("On", True), ("1", True),
                                          ("0", False), ("no", False), ("", False)])
def test_env_bool_values(rp, monkeypatch, raw, expected):
    monkeypatch.setenv("CW_FLAG", raw)
    assert rp._env_bool("CW_FLAG") is expected


def test_env_bool_default_when_unset(rp, monkeypatch):
    monkeypatch.delenv("CW_FLAG", raising=False)
    assert rp._env_bool("CW_FLAG") is False
    assert rp._env_bool("CW_FLAG", True) is True


ENV_KEYS = ("PIPELINE_INPUT_DIR", "PIPELINE_OUTPUT_DIR", "PIPELINE_EXCEL_INPUT", "PIPELINE_EXCEL_OUTPUT_ROOT",
            "PIPELINE_EXCEL_CELL_MODE", "PIPELINE_EXCEL_TABLES_ONLY", "PIPELINE_EXCEL_SCHEDULE_AS_OF",
            "PIPELINE_EXCEL_DUE_SOON_DAYS")


def test_parse_args_defaults_come_from_module_root(rp, monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(sys, "argv", ["run_processing"])
    a = rp.parse_args()
    assert Path(a.input_dir) == rp.REPO_ROOT / "app" / "public" / "master_input"
    assert Path(a.output_dir) == rp.REPO_ROOT / "app" / "public" / "outputs"
    assert a.excel_input is None
    assert Path(a.excel_output_root) == rp.REPO_ROOT
    assert (a.excel_cell_mode, a.excel_tables_only, a.excel_schedule_as_of, a.excel_due_soon_days) == \
        ("formula", False, None, 14)


def test_parse_args_environment_overrides(rp, monkeypatch, tmp_path):
    monkeypatch.setenv("PIPELINE_INPUT_DIR", str(tmp_path / "i"))
    monkeypatch.setenv("PIPELINE_OUTPUT_DIR", str(tmp_path / "o"))
    monkeypatch.setenv("PIPELINE_EXCEL_INPUT", str(tmp_path / "w.xlsx"))
    monkeypatch.setenv("PIPELINE_EXCEL_OUTPUT_ROOT", str(tmp_path / "x"))
    monkeypatch.setenv("PIPELINE_EXCEL_CELL_MODE", "cached")
    monkeypatch.setenv("PIPELINE_EXCEL_TABLES_ONLY", "yes")
    monkeypatch.setenv("PIPELINE_EXCEL_SCHEDULE_AS_OF", "2026-01-02")
    monkeypatch.setenv("PIPELINE_EXCEL_DUE_SOON_DAYS", "7")
    monkeypatch.setattr(sys, "argv", ["run_processing"])
    a = rp.parse_args()
    assert a.input_dir == str(tmp_path / "i")
    assert a.output_dir == str(tmp_path / "o")
    assert a.excel_input == str(tmp_path / "w.xlsx")
    assert a.excel_output_root == str(tmp_path / "x")
    assert (a.excel_cell_mode, a.excel_tables_only, a.excel_schedule_as_of, a.excel_due_soon_days) == \
        ("cached", True, "2026-01-02", 7)


def test_parse_args_rejects_unknown_cell_mode(rp, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_processing", "--excel-cell-mode", "values"])
    with pytest.raises(SystemExit) as exc:
        rp.parse_args()
    assert exc.value.code == 2
    assert "invalid choice: 'values'" in capsys.readouterr().err


# ---------------------------------------------------------------- phase runners

def test_run_ppt_processing_success_command(rp, monkeypatch, tmp_path, capsys):
    fake = FakeRun({"ppt_processor.py": proc(0, "done\n")})
    monkeypatch.setattr(rp.subprocess, "run", fake)
    assert rp.run_ppt_processing(tmp_path / "in", tmp_path / "out") is True
    cmd, cwd = fake.calls[0]
    assert cmd == [sys.executable, str(rp.CURRENT_DIR / "ppt_processor.py"),
                   "--input-dir", str(tmp_path / "in"), "--output-dir", str(tmp_path / "out")]
    assert cwd == rp.REPO_ROOT
    assert capsys.readouterr().out.splitlines()[-1] == "done"


def test_run_ppt_processing_failure_reports_stderr(rp, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"ppt_processor.py": proc(1, "", "boom\n")}))
    assert rp.run_ppt_processing(tmp_path, tmp_path) is False
    assert capsys.readouterr().err == "boom\n"


def test_run_ppt_processing_failure_without_stderr(rp, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"ppt_processor.py": proc(3)}))
    assert rp.run_ppt_processing(tmp_path, tmp_path) is False
    assert capsys.readouterr().err == ""


def test_summarize_missing_and_failures(rp, tmp_path, capsys):
    assert rp.summarize(tmp_path) is False
    assert "Summary missing:" in capsys.readouterr().err
    wjson(tmp_path / "processing_summary.json", {"processing_scope": "S", "total_files": 3, "successful": 2,
                                                 "failed": 1, "cross_references_global": [1, 2]})
    assert rp.summarize(tmp_path) is False
    shown = json.loads(capsys.readouterr().out)
    assert shown["candidate_cross_references"] == 2
    assert shown["authority"] == rp.AUTHORITY
    assert shown["failed"] == 1


def test_run_recursive_build_failure_paths(rp, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"Recursive_Build_Master.py": proc(1, "", "bad\n")}))
    assert rp.run_recursive_build(tmp_path) is None
    assert capsys.readouterr().err == "bad\n"
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"Recursive_Build_Master.py": proc(2)}))
    assert rp.run_recursive_build(tmp_path) is None
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"Recursive_Build_Master.py": proc(0)}))
    assert rp.run_recursive_build(tmp_path) is None
    assert "Recursive-build receipt missing:" in capsys.readouterr().err


def test_load_json_rejects_non_object(rp, tmp_path):
    p = wjson(tmp_path / "a.json", [1])
    with pytest.raises(ValueError, match="^Expected JSON object: "):
        rp._load_json(p)


def excel_engine(root, table=GOOD_TABLE, sched=GOOD_SCHED, rc=0, raw_table=None, raw_sched=None):
    def action(cmd):
        if raw_table is not None:
            p = root / "Outputs" / "excel" / "table_manifest.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(raw_table, encoding="utf-8")
        elif table is not None:
            wjson(root / "Outputs" / "excel" / "table_manifest.json", table)
        if raw_sched is not None:
            p = root / "Outputs" / "excel" / "schedule" / "schedule_manifest.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(raw_sched, encoding="utf-8")
        elif sched is not None:
            wjson(root / "Outputs" / "excel" / "schedule" / "schedule_manifest.json", sched)
        return proc(rc, "engine ok\n")
    return action


def test_excel_engine_command_flags_and_pass(rp, monkeypatch, tmp_path):
    fake = FakeRun({"excel_schedule_engine.py": excel_engine(tmp_path)})
    monkeypatch.setattr(rp.subprocess, "run", fake)
    got = rp.run_excel_schedule_engine(tmp_path / "w.xlsx", tmp_path, cell_mode="cached",
                                       tables_only=True, schedule_as_of="2026-02-03", due_soon_days=5)
    assert got == tmp_path / "Outputs" / "excel" / "table_manifest.json"
    cmd = fake.calls[0][0]
    assert cmd[1:] == [str(rp.EXCEL_ENGINE), str(tmp_path / "w.xlsx"), "--output-root", str(tmp_path),
                       "--cell-mode", "cached", "--tables-only", "--schedule-as-of", "2026-02-03",
                       "--schedule-due-soon-days", "5"]


def test_excel_engine_default_flags(rp, monkeypatch, tmp_path):
    fake = FakeRun({"excel_schedule_engine.py": excel_engine(tmp_path)})
    monkeypatch.setattr(rp.subprocess, "run", fake)
    assert rp.run_excel_schedule_engine(tmp_path / "w.xlsx", tmp_path) is not None
    cmd = fake.calls[0][0]
    assert "--tables-only" not in cmd and "--schedule-as-of" not in cmd
    assert cmd[-2:] == ["--schedule-due-soon-days", "14"]


@pytest.mark.parametrize("kwargs,message", [
    (dict(rc=1), None),
    (dict(table=None, sched=None), "Excel table manifest missing:"),
    (dict(raw_table="{not json"), "Cannot read Excel table manifest:"),
    (dict(raw_table="[]"), "Cannot read Excel table manifest: Expected JSON object"),
    (dict(table={"summary": {"errors": 2}, "authority": {"authority_transfer": False}}),
     "Excel table manifest reports export errors"),
    (dict(table={"summary": {}, "authority": {"authority_transfer": True}}),
     "Excel table manifest authority guardrail failed"),
    (dict(table={}), "Excel table manifest authority guardrail failed"),
    (dict(sched=None), "Schedule projection manifest missing:"),
    (dict(raw_sched="nope"), "Cannot read schedule projection manifest:"),
    (dict(sched={"summary": {"process_status": "PASS"}, "authority": {}}),
     "Schedule projection authority guardrail failed"),
    (dict(sched={"summary": {"process_status": "FAIL"}, "authority": {"authority_transfer": False}}),
     "Schedule projection process status is not PASS"),
])
def test_excel_engine_fail_closed(rp, monkeypatch, tmp_path, capsys, kwargs, message):
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"excel_schedule_engine.py": excel_engine(tmp_path, **kwargs)}))
    assert rp.run_excel_schedule_engine(tmp_path / "w.xlsx", tmp_path) is None
    err = capsys.readouterr().err
    if message is not None:
        assert message in err


def test_excel_engine_failure_prints_stderr(rp, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rp.subprocess, "run", FakeRun({"excel_schedule_engine.py": proc(1, "", "xl broke\n")}))
    assert rp.run_excel_schedule_engine(tmp_path / "w.xlsx", tmp_path) is None
    assert capsys.readouterr().err == "xl broke\n"


# ---------------------------------------------------------------- receipts

def test_receipt_path_bases(rp, tmp_path):
    out = tmp_path / "out"
    assert rp._receipt_path(out / "a" / "b.json", out) == {"path": str(Path("a") / "b.json"),
                                                           "path_base": "output_dir"}
    assert rp._receipt_path(rp.REPO_ROOT / "x.json", out) == {"path": "x.json", "path_base": "repo_root"}
    outside = tmp_path / "elsewhere" / "y.json"
    assert rp._receipt_path(outside, out) == {"path": str(outside.resolve()), "path_base": "absolute"}


def phases(out, summary=None, recursive=None):
    wjson(out / "processing_summary.json", summary or {"total_files": 1, "successful": 1, "failed": 0})
    return wjson(out / "recursive_build" / "build_receipt.json",
                 recursive or {"status": "PASS", "generated_at": "T0", "record_count": 9})


def test_write_receipt_missing_inputs(rp, tmp_path, capsys):
    assert rp.write_pipeline_receipt(tmp_path, tmp_path / "nope.json") is None
    assert capsys.readouterr().err.strip() == "Cannot write pipeline receipt: required phase receipt missing"
    wjson(tmp_path / "processing_summary.json", {})
    assert rp.write_pipeline_receipt(tmp_path, tmp_path / "nope.json") is None


def test_write_receipt_unreadable_phase(rp, tmp_path, capsys):
    rec = phases(tmp_path)
    rec.write_text("[1]", encoding="utf-8")
    assert rp.write_pipeline_receipt(tmp_path, rec) is None
    assert "Cannot read phase receipt: Expected JSON object" in capsys.readouterr().err


def test_write_receipt_not_requested_and_failures(rp, tmp_path):
    rec = phases(tmp_path, summary={"failed": 2}, recursive={"status": "FAIL_X"})
    target = rp.write_pipeline_receipt(tmp_path, rec)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["status"] == "FAIL"
    assert data["generated_at"] is None
    assert data["phases"]["metadata"]["status"] == "FAIL"
    assert data["phases"]["metadata"]["sha256"] == sha(tmp_path / "processing_summary.json")
    assert data["phases"]["recursive_build"] == {"status": "FAIL_X",
                                                 "path": str(Path("recursive_build") / "build_receipt.json"),
                                                 "sha256": sha(rec), "record_count": 0}
    assert data["phases"]["excel_schedule"] == {"status": "NOT_REQUESTED", "requested": False}


def test_write_receipt_excel_requested_without_manifest_fails(rp, tmp_path):
    rec = phases(tmp_path)
    data = json.loads(rp.write_pipeline_receipt(tmp_path, rec, None, excel_requested=True).read_text())
    assert data["phases"]["excel_schedule"] == {"status": "FAIL", "requested": True}
    assert data["status"] == "FAIL"


def test_write_receipt_excel_without_schedule_fails(rp, tmp_path):
    rec = phases(tmp_path)
    xl = wjson(tmp_path / "xl" / "Outputs" / "excel" / "table_manifest.json", GOOD_TABLE)
    data = json.loads(rp.write_pipeline_receipt(tmp_path, rec, xl, excel_requested=True).read_text())
    ex = data["phases"]["excel_schedule"]
    assert ex["status"] == "FAIL"
    assert ex["schedule_projection"] is None
    assert ex["path_base"] == "output_dir"
    assert ex["path"] == str(Path("xl") / "Outputs" / "excel" / "table_manifest.json")
    assert ex["sha256"] == sha(xl)
    assert ex["tables_exported"] == 3
    assert data["status"] == "FAIL"


def test_write_receipt_excel_full_pass(rp, tmp_path):
    out = tmp_path / "out"
    rec = phases(out)
    xl = wjson(out / "excel" / "table_manifest.json", GOOD_TABLE)
    sched = wjson(out / "excel" / "schedule" / "schedule_manifest.json", GOOD_SCHED)
    data = json.loads(rp.write_pipeline_receipt(out, rec, xl, excel_requested=True).read_text())
    assert data["status"] == "PASS"
    assert data["generated_at"] == "T0"
    assert data["schema"] == "pipeline_automation_hub.pipeline_run_receipt.v3"
    ex = data["phases"]["excel_schedule"]
    assert ex["status"] == "PASS"
    assert ex["path_base"] == "output_dir"
    assert ex["schedule_projection"] == {
        "status": "PASS", "path": str(Path("excel") / "schedule" / "schedule_manifest.json"),
        "path_base": "output_dir", "sha256": sha(sched), "activities": 4, "red": 1, "yellow": 2,
        "green": 1, "validation_pass_rate_pct": 97.5, "authority_transfer": False}


def test_write_receipt_schedule_not_pass_fails(rp, tmp_path):
    out = tmp_path / "out"
    rec = phases(out)
    xl = wjson(out / "excel" / "table_manifest.json", GOOD_TABLE)
    wjson(out / "excel" / "schedule" / "schedule_manifest.json", {"summary": {}, "authority": {}})
    data = json.loads(rp.write_pipeline_receipt(out, rec, xl, excel_requested=True).read_text())
    proj = data["phases"]["excel_schedule"]["schedule_projection"]
    assert proj["status"] is None and proj["validation_pass_rate_pct"] == 100.0
    assert data["phases"]["excel_schedule"]["status"] == "FAIL"


# ---------------------------------------------------------------- main via sys.argv

def full_pipeline(out, summary=None, write_receipt=True):
    def ppt(cmd):
        wjson(out / "processing_summary.json", summary or {"total_files": 2, "successful": 2, "failed": 0})
        return proc(0, "ppt\n")

    def rec(cmd):
        if write_receipt:
            wjson(out / "recursive_build" / "build_receipt.json", {"status": "PASS_ALL", "record_count": 1})
        return proc(0, "")
    return {"ppt_processor.py": ppt, "Recursive_Build_Master.py": rec}


def run_main(rp, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["run_processing", *argv])
    return rp.main()


def base_argv(tmp_path):
    return ["--input-dir", str(tmp_path / "in"), "--output-dir", str(tmp_path / "out")]


def test_main_metadata_phase_failure_returns_2(rp, monkeypatch, tmp_path):
    fake = FakeRun({"ppt_processor.py": proc(1)})
    monkeypatch.setattr(rp.subprocess, "run", fake)
    assert run_main(rp, monkeypatch, base_argv(tmp_path)) == 2
    assert len(fake.calls) == 1


def test_main_summary_failure_returns_3(rp, monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setattr(rp.subprocess, "run", FakeRun(full_pipeline(out, summary={"failed": 1})))
    assert run_main(rp, monkeypatch, base_argv(tmp_path)) == 3


def test_main_recursive_failure_returns_4(rp, monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setattr(rp.subprocess, "run", FakeRun(full_pipeline(out, write_receipt=False)))
    assert run_main(rp, monkeypatch, base_argv(tmp_path)) == 4


def test_main_excel_failure_returns_5(rp, monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    beh = full_pipeline(out)
    beh["excel_schedule_engine.py"] = proc(1)
    fake = FakeRun(beh)
    monkeypatch.setattr(rp.subprocess, "run", fake)
    argv = base_argv(tmp_path) + ["--excel-input", str(tmp_path / "w.xlsx"),
                                  "--excel-output-root", str(tmp_path / "xl")]
    assert run_main(rp, monkeypatch, argv) == 5
    printed = capsys.readouterr().out
    assert "excel_input=" + str((tmp_path / "w.xlsx").resolve()) in printed
    assert "excel_output_root=" + str((tmp_path / "xl").resolve()) in printed
    assert len(fake.calls) == 3


def test_main_receipt_failure_returns_6(rp, monkeypatch, tmp_path):
    out = tmp_path / "out"
    beh = full_pipeline(out)
    monkeypatch.setattr(rp.subprocess, "run", FakeRun(beh))
    monkeypatch.setattr(rp, "write_pipeline_receipt", lambda *a, **k: None)
    assert run_main(rp, monkeypatch, base_argv(tmp_path)) == 6


def test_main_full_excel_pass(rp, monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    xl = tmp_path / "xl"
    beh = full_pipeline(out)
    beh["excel_schedule_engine.py"] = excel_engine(xl)
    fake = FakeRun(beh)
    monkeypatch.setattr(rp.subprocess, "run", fake)
    argv = base_argv(tmp_path) + ["--excel-input", str(tmp_path / "w.xlsx"), "--excel-output-root", str(xl),
                                  "--excel-tables-only", "--excel-schedule-as-of", "2026-05-05",
                                  "--excel-due-soon-days", "3", "--excel-cell-mode", "cached"]
    assert run_main(rp, monkeypatch, argv) == 0
    xl_cmd = fake.calls[2][0]
    assert ["--cell-mode", "cached"] == xl_cmd[5:7]
    assert "--tables-only" in xl_cmd and xl_cmd[-1] == "3"
    out_text = capsys.readouterr().out
    final = json.loads(out_text[out_text.rindex("{\n  \"authority\""):])
    assert final["status"] == "PASS" and final["excel_requested"] is True
    receipt = json.loads((out / "pipeline_run_receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert receipt["phases"]["excel_schedule"]["status"] == "PASS"
    assert final["pipeline_receipt"] == str((out / "pipeline_run_receipt.json").resolve())


def test_script_entrypoint_exit_code(tmp_path, monkeypatch, capsys):
    """__main__ guard raises SystemExit(main()); subprocess faked so phase 1 fails."""
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return proc(1, "", "fail\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_processing", *base_argv(tmp_path)])
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    fake_file = tmp_path / "repo" / "scripts" / "cw_rp_main.py"
    with pytest.raises(SystemExit) as exc:
        exec(code, {"__name__": "__main__", "__file__": str(fake_file)})
    assert exc.value.code == 2
    assert len(calls) == 1 and Path(calls[0][1]).name == "ppt_processor.py"
    assert capsys.readouterr().err == "fail\n"
