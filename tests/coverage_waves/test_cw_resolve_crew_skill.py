"""Behavioural tests for mission-control/qps-triage-ultra/crew/resolve_crew_skill.py."""
import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "resolve_crew_skill.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_resolve_crew_skill", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


resolver = _load()


def _skills(root, skill="math", body=None, agents=True):
    d = root / "skills" / skill
    d.mkdir(parents=True)
    raw = (body if body is not None else "---\nname: " + skill + "\n---\n# Skill\n").encode("utf-8")
    (d / "SKILL.md").write_bytes(raw)
    if agents:
        (d / "agents").mkdir()
        (d / "agents" / "openai.yaml").write_text("x: 1\n", encoding="utf-8")
    return raw


def _argv(root, skill="math", extra=()):
    return ["resolve_crew_skill.py", "--skills-root", str(root), "--skill", skill, "--task-id", "T-1",
            "--source-repo", "o/r", "--source-ref", "main", *extra]


@pytest.mark.parametrize("skill", ["math", "plots", "math-plots"])
def test_resolves_and_prints_receipt(tmp_path, monkeypatch, capsys, skill):
    raw = _skills(tmp_path, skill)
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, skill))
    resolver.main()
    receipt = json.loads(capsys.readouterr().out)
    assert receipt == {
        "schema": "missioncontrol.crew.skill_resolution_receipt.v1",
        "skill": skill,
        "task_id": "T-1",
        "source_repo": "o/r",
        "source_ref": "main",
        "skills_repo": "GBOGEB/skills",
        "skills_ref": "UNSPECIFIED",
        "resolution_mode": "missioncontrol_resolver",
        "resolved_skill_path": "skills/" + skill + "/SKILL.md",
        "entrypoint_sha256": hashlib.sha256(raw).hexdigest(),
        "authority_transfer": False,
        "status": "PASS_SKILL_BUNDLE_RESOLUTION",
    }


def test_out_file_written_with_custom_refs(tmp_path, monkeypatch, capsys):
    _skills(tmp_path)
    out = tmp_path / "deep" / "dir" / "receipt.json"
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, extra=(
        "--skills-ref", "abc", "--resolution-mode", "manual", "--out", str(out))))
    resolver.main()
    printed = capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == printed
    data = json.loads(printed)
    assert (data["skills_ref"], data["resolution_mode"]) == ("abc", "manual")
    assert printed.endswith("}\n")


def test_missing_entrypoint(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", _argv(tmp_path))
    with pytest.raises(SystemExit) as exc:
        resolver.main()
    expected = tmp_path / "skills" / "math" / "SKILL.md"
    assert exc.value.code == "missing skill entrypoint: " + str(expected)


def test_frontmatter_name_mismatch(tmp_path, monkeypatch):
    _skills(tmp_path, "math", body="---\nname: plots\n---\n")
    monkeypatch.setattr(sys, "argv", _argv(tmp_path))
    with pytest.raises(SystemExit) as exc:
        resolver.main()
    assert exc.value.code == "skill frontmatter name mismatch"


def test_missing_agents_yaml(tmp_path, monkeypatch):
    _skills(tmp_path, agents=False)
    monkeypatch.setattr(sys, "argv", _argv(tmp_path))
    with pytest.raises(SystemExit) as exc:
        resolver.main()
    assert exc.value.code == "missing agents/openai.yaml"


def test_disallowed_skill_rejected_by_argparse(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, skill="shell"))
    with pytest.raises(SystemExit) as exc:
        resolver.main()
    assert exc.value.code == 2
    assert "invalid choice: 'shell'" in capsys.readouterr().err


def test_main_guard(tmp_path, monkeypatch, capsys):
    _skills(tmp_path, "plots")
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, "plots"))
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["skill"] == "plots"
