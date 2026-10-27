"""Behavioural tests for mission-control/qps-triage-ultra/crew/validate_skill_receipt_set.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "validate_skill_receipt_set.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_skill_receipt_set_mod", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vsr = _load()
REPO = "GBOGEB/pipeline-automation-hub"
SRC = "a" * 40
SKR = "b" * 40


def _receipt(skill, /, **over):
    r = {
        "schema": vsr.SCHEMA,
        "skill": skill,
        "source_repo": REPO,
        "source_ref": SRC,
        "skills_repo": "GBOGEB/skills",
        "skills_ref": SKR,
        "resolution_mode": "pinned",
        "resolved_skill_path": "skills/" + skill + "/SKILL.md",
        "entrypoint_sha256": "c" * 64,
        "authority_transfer": False,
        "status": "PASS_SKILL_BUNDLE_RESOLUTION",
        "extra_noise": "ignored",
    }
    r.update(over)
    return r


def _validate(r, ref=SRC, skills_ref=SKR):
    vsr.validate_receipt(r, expected_repo=REPO, expected_ref=ref, skills_ref=skills_ref)


def test_canonical_semantic_receipt_projects_fixed_keys():
    sem = vsr.canonical_semantic_receipt({"skill": "math", "extra": 1})
    assert "extra" not in sem
    assert sem["skill"] == "math"
    assert sem["schema"] is None
    assert len(sem) == 11


def test_fail_raises_systemexit_with_message():
    with pytest.raises(SystemExit, match="^boom$"):
        vsr.fail("boom")


def test_valid_receipt_passes():
    for skill in ("math", "plots", "math-plots"):
        _validate(_receipt(skill))


@pytest.mark.parametrize(
    "over, kwargs, message",
    [
        ({"schema": "other"}, {}, "receipt schema mismatch"),
        ({"skill": "rogue"}, {}, "unexpected skill: rogue"),
        ({"status": "FAIL"}, {}, "non-pass skill receipt: math"),
        ({"source_repo": "x/y"}, {}, "source repo mismatch: math"),
        ({"source_ref": "d" * 40}, {}, "source ref mismatch or non-SHA: math"),
        ({"source_ref": "main"}, {"ref": "main"}, "source ref mismatch or non-SHA: math"),
        ({"skills_repo": "x/skills"}, {}, "skills repo mismatch: math"),
        ({"skills_ref": "e" * 40}, {}, "skills ref mismatch or non-SHA: math"),
        ({"skills_ref": "HEAD"}, {"skills_ref": "HEAD"}, "skills ref mismatch or non-SHA: math"),
        ({"entrypoint_sha256": None}, {}, "missing or invalid entrypoint digest: math"),
        ({"entrypoint_sha256": "C" * 64}, {}, "missing or invalid entrypoint digest: math"),
        ({"authority_transfer": None}, {}, "authority inversion detected: math"),
        ({"resolved_skill_path": "skills/plots/SKILL.md"}, {}, "resolved path mismatch: math"),
    ],
)
def test_invalid_receipt_rejected(over, kwargs, message):
    with pytest.raises(SystemExit) as exc:
        _validate(_receipt("math", **over), **kwargs)
    assert str(exc.value.code) == message


def _write_receipts(d: Path, receipts):
    d.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(receipts):
        (d / ("r" + str(i) + ".json")).write_text(json.dumps(r), encoding="utf-8")


def _argv(monkeypatch, rdir, *extra):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_skill_receipt_set.py",
            "--receipts-dir", str(rdir),
            "--expected-source-repo", REPO,
            "--expected-source-ref", SRC,
            "--skills-ref", SKR,
            *extra,
        ],
    )


def _expected_set_digest(skills):
    sem = sorted((vsr.canonical_semantic_receipt(_receipt(s)) for s in skills), key=lambda x: x["skill"])
    canonical = json.dumps(sem, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_main_pass_writes_out_and_prints(tmp_path, monkeypatch, capsys):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt("plots"), _receipt("math-plots"), _receipt("math")])
    out = tmp_path / "nested" / "dir" / "set.json"
    _argv(monkeypatch, rdir, "--out", str(out))
    vsr.main()
    printed = capsys.readouterr().out
    result = json.loads(printed)
    assert out.read_text(encoding="utf-8") == printed
    assert result["status"] == "PASS_MIP_HARDENED_SKILL_RECEIPT_SET"
    assert result["skills"] == ["math", "math-plots", "plots"]
    assert result["receipt_count"] == 3
    assert result["authority_transfer"] is False
    assert result["source_ref"] == SRC and result["skills_ref"] == SKR
    assert result["receipt_set_sha256"] == _expected_set_digest(["math", "plots", "math-plots"])


def test_main_digest_ignores_non_semantic_fields_and_no_out(tmp_path, monkeypatch, capsys):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt(s, extra_noise=s * 3) for s in ("math", "plots", "math-plots")])
    _argv(monkeypatch, rdir)
    vsr.main()
    result = json.loads(capsys.readouterr().out)
    assert result["receipt_set_sha256"] == _expected_set_digest(["math", "plots", "math-plots"])
    assert list(tmp_path.iterdir()) == [rdir]


def test_main_wrong_count(tmp_path, monkeypatch):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt("math")])
    _argv(monkeypatch, rdir)
    with pytest.raises(SystemExit) as exc:
        vsr.main()
    assert exc.value.code == "expected 3 receipt files, found 1"


def test_main_invalid_json(tmp_path, monkeypatch):
    rdir = tmp_path / "receipts"
    rdir.mkdir()
    (rdir / "bad.json").write_text("{not json", encoding="utf-8")
    _argv(monkeypatch, rdir, "--expected-count", "1")
    with pytest.raises(SystemExit) as exc:
        vsr.main()
    assert str(exc.value.code).startswith("invalid JSON in ")


def test_main_invalid_receipt_propagates(tmp_path, monkeypatch):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt("math", status="FAIL")])
    _argv(monkeypatch, rdir, "--expected-count", "1")
    with pytest.raises(SystemExit) as exc:
        vsr.main()
    assert exc.value.code == "non-pass skill receipt: math"


def test_main_duplicate_skill(tmp_path, monkeypatch):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt("math"), _receipt("math"), _receipt("plots")])
    _argv(monkeypatch, rdir)
    with pytest.raises(SystemExit) as exc:
        vsr.main()
    assert exc.value.code == "duplicate skill receipt: math"


def test_main_skill_set_mismatch(tmp_path, monkeypatch):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt("math"), _receipt("plots")])
    _argv(monkeypatch, rdir, "--expected-count", "2")
    with pytest.raises(SystemExit) as exc:
        vsr.main()
    assert exc.value.code == "skill set mismatch: ['math', 'plots']"


def test_main_ignores_non_json_files(tmp_path, monkeypatch, capsys):
    rdir = tmp_path / "receipts"
    _write_receipts(rdir, [_receipt(s) for s in ("math", "plots", "math-plots")])
    (rdir / "notes.txt").write_text("not a receipt", encoding="utf-8")
    _argv(monkeypatch, rdir)
    vsr.main()
    assert json.loads(capsys.readouterr().out)["receipt_count"] == 3
