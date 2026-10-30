"""Behavioural tests for mission-control/jade_temple/tools/regen.py.

The existing test_regen.py covers CHAIN ordering, CI sync and report(). These cover run(), dirty(),
check_all(), write_all() and main() dispatch. subprocess is replaced on the loaded module, so no
generator, git or Python child process ever runs and no committed JADE output is touched.
"""
import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = ROOT / "mission-control" / "jade_temple" / "tools" / "regen.py"
MOD_NAME = "cw_jade_regen_mod"

_spec = importlib.util.spec_from_file_location(MOD_NAME, MOD_PATH)
regen = importlib.util.module_from_spec(_spec)
sys.modules[MOD_NAME] = regen  # dataclasses resolve string annotations through sys.modules
_spec.loader.exec_module(regen)

Step = regen.Step


def cp(rc=0, out="", err=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=out, stderr=err)


class FakeSubprocess:
    """Stands in for the subprocess module on the loaded regen module."""

    CompletedProcess = subprocess.CompletedProcess

    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return self.result


class Script:
    """Programmable replacement for regen.run / regen.dirty keyed by (step id, args)."""

    def __init__(self, results=None, dirty=()):
        self.results = results or {}
        self.dirty_paths = list(dirty)
        self.runs = []
        self.dirty_calls = []

    def run(self, step, args):
        self.runs.append((step.id, tuple(args)))
        return self.results.get((step.id, tuple(args)), cp(0))

    def dirty(self, paths):
        self.dirty_calls.append(tuple(paths))
        return list(self.dirty_paths)


@pytest.fixture
def script(monkeypatch):
    def install(chain, **kw):
        s = Script(**kw)
        monkeypatch.setattr(regen, "CHAIN", tuple(chain))
        monkeypatch.setattr(regen, "run", s.run)
        monkeypatch.setattr(regen, "dirty", s.dirty)
        return s
    return install


# --- run / dirty -----------------------------------------------------------------------------

def test_run_invokes_current_interpreter_on_step_script_from_root(monkeypatch):
    fake = FakeSubprocess(cp(0, "ok"))
    monkeypatch.setattr(regen, "subprocess", fake)
    step = Step("x", "mission-control/jade_temple/tools/x.py", ("--write",), ("--check",))
    result = regen.run(step, ("--check", "--v"))
    assert result.stdout == "ok"
    (cmd, kw), = fake.calls
    assert cmd == [sys.executable, "mission-control/jade_temple/tools/x.py", "--check", "--v"]
    assert kw == {"cwd": regen.ROOT, "capture_output": True, "text": True, "encoding": "utf-8",
                  "errors": "replace"}


def test_dirty_parses_porcelain_paths(monkeypatch):
    fake = FakeSubprocess(cp(0, " M mission-control/a.json\n?? mission-control/b.csv\nA  c.html\n"))
    monkeypatch.setattr(regen, "subprocess", fake)
    assert regen.dirty(("mission-control/a.json", "x/**")) == [
        "mission-control/a.json", "mission-control/b.csv", "c.html"]
    (cmd, kw), = fake.calls
    assert cmd == ["git", "status", "--porcelain", "--", "mission-control/a.json", "x/**"]
    assert kw["cwd"] == regen.ROOT and kw["capture_output"] is True


def test_dirty_clean_tree_is_empty(monkeypatch):
    monkeypatch.setattr(regen, "subprocess", FakeSubprocess(cp(0, "")))
    assert regen.dirty(("a",)) == []


def test_root_is_repository_root():
    assert regen.ROOT == MOD_PATH.resolve().parents[3]
    assert (regen.ROOT / regen.JT / "tools" / "regen.py").is_file()


# --- check_all -------------------------------------------------------------------------------

def test_check_all_skips_unchecked_and_reports_last_output_line(script):
    chain = [
        Step("ext", "e.py", None, None),
        Step("ok", "o.py", (), ("--check",)),
        Step("noisy", "n.py", (), ("--check",)),
        Step("silent", "s.py", (), ()),
        Step("stderr", "t.py", (), ("--check",)),
    ]
    s = script(chain, results={
        ("noisy", ("--check",)): cp(1, "line one\nDRIFT: site/x.html\n\n"),
        ("silent", ()): cp(3, "  \n", ""),
        ("stderr", ("--check",)): cp(2, "out\n", "err last\n"),
    })
    stale = regen.check_all()
    assert [(st.id, why) for st, why in stale] == [
        ("noisy", "DRIFT: site/x.html"), ("silent", "exit 3"), ("stderr", "err last")]
    assert s.runs == [("ok", ("--check",)), ("noisy", ("--check",)), ("silent", ()), ("stderr", ("--check",))]


def test_check_all_all_fresh_is_empty(script):
    script([Step("a", "a.py", (), ("--check",))])
    assert regen.check_all() == []


# --- write_all -------------------------------------------------------------------------------

def test_write_all_walks_chain_in_order(script, capsys):
    chain = [
        Step("ext", "e.py", None, None, outputs=("site/ext/**",), note="external: harvest"),
        Step("fresh", "f.py", ("--write",), ("--check",), outputs=("site/f.json",)),
        Step("stale", "g.py", ("--write",), ("--check",), outputs=("site/g.json",)),
        Step("nocheck", "h.py", (), None, outputs=("site/h.json",)),
        Step("launch", "l.py", (), ("--check",), outputs=("site/l.html",), note="commit first", needs_commit=True),
    ]
    s = script(chain, results={("stale", ("--check",)): cp(1, "stale\n")}, dirty=[])
    rc = regen.write_all()
    out = capsys.readouterr().out.splitlines()
    assert out[:5] == [
        "REGEN_SKIP ext: external: harvest",
        "REGEN_FRESH fresh",
        "REGEN_WROTE stale",
        "REGEN_WROTE nocheck",
        "REGEN_FRESH launch",
    ]
    # the trailing full check reruns every check; the scripted "stale" check still fails
    assert rc == 1
    assert out[5:] == ["REGEN_STALE stale: stale",
                       "first stale step: stale; fix: python mission-control/jade_temple/tools/regen.py --write"]
    # pending excludes outputs of needs_commit steps
    assert s.dirty_calls == [("site/ext/**", "site/f.json", "site/g.json", "site/h.json")]
    assert ("stale", ("--write",)) in s.runs and ("nocheck", ()) in s.runs
    assert ("fresh", ("--write",)) not in s.runs


def test_write_all_success_ends_with_ok(script, monkeypatch, capsys):
    calls = {"n": 0}
    chain = [Step("a", "a.py", ("--write",), ("--check",), outputs=("a.json",))]
    s = script(chain)

    def run(step, args):
        s.runs.append((step.id, tuple(args)))
        if args == ("--check",):
            calls["n"] += 1
            return cp(1 if calls["n"] == 1 else 0, "drift\n")
        return cp(0)

    monkeypatch.setattr(regen, "run", run)
    assert regen.write_all() == 0
    assert capsys.readouterr().out.splitlines() == [
        "REGEN_WROTE a", "REGEN_OK: every committed JADE output matches its sources"]
    assert s.runs == [("a", ("--check",)), ("a", ("--write",)), ("a", ("--check",))]


def test_write_all_defers_needs_commit_step_when_outputs_dirty(script, capsys):
    chain = [
        Step("a", "a.py", ("--write",), ("--check",), outputs=("o1", "o2")),
        Step("launch", "l.py", (), ("--check",), note="reads owner outputs at HEAD", needs_commit=True),
    ]
    s = script(chain, dirty=["o1", "o2", "o3", "o4"])
    assert regen.write_all() == 0
    out = capsys.readouterr().out.splitlines()
    assert out[1] == "REGEN_DEFER launch: reads owner outputs at HEAD; uncommitted: o1, o2, o3"
    assert ("launch", ()) not in s.runs
    assert len(s.dirty_calls) == 2  # once for the test, once for the message


def test_write_all_stops_at_first_failed_write_and_dumps_tail(script, capsys):
    chain = [
        Step("bad", "b.py", ("--write",), ("--check",)),
        Step("later", "l.py", ("--write",), ("--check",)),
    ]
    long_out = "x" * 2500 + "OUT_END"
    s = script(chain, results={
        ("bad", ("--check",)): cp(1),
        ("bad", ("--write",)): cp(4, long_out, "boom"),
    })
    assert regen.write_all() == 1
    out = capsys.readouterr().out
    assert out.startswith("REGEN_FAIL bad: exit 4\n")
    tail = out.split("\n", 1)[1]
    assert tail == long_out[-2000:] + "boom"
    assert all(step_id != "later" for step_id, _ in s.runs)


# --- report ----------------------------------------------------------------------------------

def test_report_lists_every_stale_step_in_order(capsys):
    a = Step("a", "a.py", ("--write",), ("--check",))
    b = Step("b", "b.py", None, ("--check",), note="external b")
    assert regen.report([(a, "why a"), (b, "why b")]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "REGEN_STALE a: why a", "REGEN_STALE b: why b",
        "first stale step: a; fix: python mission-control/jade_temple/tools/regen.py --write"]


# --- main ------------------------------------------------------------------------------------

def test_main_default_is_check(monkeypatch, capsys):
    stale = [(Step("s", "s.py", None, ("--check",), note="external s"), "drift")]
    monkeypatch.setattr(regen, "check_all", lambda: stale)
    monkeypatch.setattr(regen, "write_all", lambda: pytest.fail("write_all must not run"))
    assert regen.main([]) == 1
    assert regen.main(["--check"]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "first stale step: s; fix: external s"


def test_main_write_dispatches_to_write_all(monkeypatch):
    monkeypatch.setattr(regen, "write_all", lambda: 7)
    monkeypatch.setattr(regen, "check_all", lambda: pytest.fail("check_all must not run directly"))
    assert regen.main(["--write"]) == 7


def test_main_modes_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as exc:
        regen.main(["--write", "--list"])
    assert exc.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_main_list_formats_flags_and_dependencies(monkeypatch, capsys):
    monkeypatch.setattr(regen, "CHAIN", (
        Step("ext", "e.py", None, None),
        Step("mid", "m.py", (), ("--check",), after=("ext",)),
        Step("last", "l.py", (), (), after=("ext", "mid"), needs_commit=True),
    ))
    monkeypatch.setattr(regen, "run", lambda *a: pytest.fail("--list must not run steps"))
    assert regen.main(["--list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        " 1. " + "ext".ljust(22) + " e.py  external ",
        " 2. " + "mid".ljust(22) + " m.py  after ext",
        " 3. " + "last".ljust(22) + " l.py  needs-commit after ext,mid",
    ]


def test_script_entrypoint_list_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["regen.py", "--list"])
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    fake_file = tmp_path / "a" / "b" / "c" / "cw_regen_main.py"
    with pytest.raises(SystemExit) as exc:
        exec(code, {"__name__": "__main__", "__file__": str(fake_file)})
    assert exc.value.code == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(regen.CHAIN)
    assert lines[0].split()[1] == regen.CHAIN[0].id


def test_by_id_indexes_current_chain(monkeypatch):
    a = Step("a", "a.py", (), ())
    b = Step("b", "b.py", None, None, after=("a",))
    monkeypatch.setattr(regen, "CHAIN", (a, b))
    assert regen.by_id() == {"a": a, "b": b}
