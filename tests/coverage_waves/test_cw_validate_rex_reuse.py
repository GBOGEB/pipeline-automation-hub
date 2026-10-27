"""Behavioural tests for mission-control/qps-triage-ultra/crew/measured/validate_rex_reuse.py.

The module validates at import time from paths derived from __file__, so synthetic cases
execute it with __file__ pointing into a tmp_path tree (crew/measured layout).
"""
import importlib.util
import itertools
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CREW_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew"
MOD_PATH = CREW_DIR / "measured" / "validate_rex_reuse.py"
LEVELS = ["NEW", "RECURRING", "PERSISTENT", "REGRESSION"]
_counter = itertools.count()


def _exec(fake_file):
    spec = importlib.util.spec_from_file_location("cw_validate_rex_reuse_%d" % next(_counter), MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    if fake_file is not None:
        mod.__file__ = str(fake_file)
    spec.loader.exec_module(mod)
    return mod


def _ledger(n=6, fixes=None):
    entries = []
    for i in range(1, n + 1):
        e = {"rex_id": "REX-%03d" % i}
        if fixes and i in fixes:
            e["known_fix"] = fixes[i]
        entries.append(e)
    return {"entries": entries}


def _check(n=6, **over):
    c = {
        "preflight_required": True,
        "postflight_required": True,
        "authority_transfer": False,
        "recurrence_levels": list(LEVELS),
        "checklist": [{"rex_id": "REX-%03d" % i, "before_task": "b", "if_triggered": "t",
                       "proof_of_prevention": "p"} for i in range(1, n + 1)],
    }
    c.update(over)
    return c


def _run(tmp_path, ledger=None, check=None):
    crew = tmp_path / "crew"
    measured = crew / "measured"
    measured.mkdir(parents=True)
    (crew / "REX_LEARNING_LEDGER_v1.json").write_text(json.dumps(ledger or _ledger()), encoding="utf-8")
    (measured / "REX_REUSE_CHECKLIST_v1.json").write_text(json.dumps(check or _check()), encoding="utf-8")
    return _exec(measured / "rex_entry.py")


def test_minimal_valid_set_passes(tmp_path, capsys):
    mod = _run(tmp_path, ledger=_ledger(fixes={2: "pin the action"}))
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "status": "PASS_REX_REUSE_CHECKLIST",
        "rex_count": 6,
        "preflight_required": True,
        "postflight_required": True,
        "recurrence_levels": LEVELS,
        "authority_transfer": False,
    }
    assert mod.expected == {"REX-%03d" % i for i in range(1, 7)}


def test_larger_contiguous_set(tmp_path, capsys):
    _run(tmp_path, ledger=_ledger(9), check=_check(9))
    assert json.loads(capsys.readouterr().out)["rex_count"] == 9


def test_too_few_entries(tmp_path):
    with pytest.raises(AssertionError) as exc:
        _run(tmp_path, ledger=_ledger(5), check=_check(5))
    assert exc.value.args[0] == ("rex_count", 5)


def test_non_contiguous_ledger_ids(tmp_path):
    ledger = _ledger(6)
    ledger["entries"][5]["rex_id"] = "REX-007"
    with pytest.raises(AssertionError) as exc:
        _run(tmp_path, ledger=ledger)
    assert exc.value.args[0] == ("ledger_ids", ["REX-001", "REX-002", "REX-003", "REX-004", "REX-005", "REX-007"])


def test_checklist_missing_id(tmp_path):
    with pytest.raises(AssertionError) as exc:
        _run(tmp_path, ledger=_ledger(7), check=_check(6))
    assert exc.value.args[0] == ("check_ids", ["REX-%03d" % i for i in range(1, 7)])


@pytest.mark.parametrize("over", [
    {"preflight_required": False},
    {"postflight_required": False},
    {"authority_transfer": True},
    {"recurrence_levels": ["NEW", "RECURRING"]},
])
def test_checklist_flags(tmp_path, over):
    with pytest.raises(AssertionError):
        _run(tmp_path, check=_check(**over))


@pytest.mark.parametrize("fix", ["", "   ", 42])
def test_blank_known_fix_rejected(tmp_path, fix):
    with pytest.raises(AssertionError) as exc:
        _run(tmp_path, ledger=_ledger(fixes={3: fix}))
    assert exc.value.args[0] == "REX-003"


@pytest.mark.parametrize("field", ["before_task", "if_triggered", "proof_of_prevention"])
def test_empty_checklist_field_rejected(tmp_path, field):
    check = _check()
    check["checklist"][4][field] = ""
    with pytest.raises(AssertionError) as exc:
        _run(tmp_path, check=check)
    assert exc.value.args[0] == "REX-005"


def test_real_committed_ledger_and_checklist(capsys):
    """Offline run against the current committed ledger (REX-007/008+ added on master)."""
    ledger = json.loads((CREW_DIR / "REX_LEARNING_LEDGER_v1.json").read_text(encoding="utf-8"))
    _exec(None)
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS_REX_REUSE_CHECKLIST"
    assert out["rex_count"] == len(ledger["entries"])
    assert out["rex_count"] >= 8
