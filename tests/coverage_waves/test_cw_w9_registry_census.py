"""Coverage wave w9: mission-control/registry/census.py (offline; git faked via subprocess.run)."""
import importlib.util
import json
import runpy
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "registry" / "census.py"
_spec = importlib.util.spec_from_file_location("cw_w9_registry_census_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def _iso(days_ago):
    return datetime.fromtimestamp(NOW.timestamp() - days_ago * 86400, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_hub(root: Path, *, red_trace=True, top7=("core-a", "sat-b", "ghost", "ghost2"), top21=None, live=("core-a",)):
    fa = root / "mission-control" / "federation-atlas"
    (fa / "central" / "top21").mkdir(parents=True)
    top21 = list(top21 if top21 is not None else ["GBOGEB/core-a", "GBOGEB/sat-b", "GBOGEB/old-c",
                                                   "GBOGEB/fork-d", "GBOGEB/legacy-x"])
    (fa / "central" / "top21" / "TOP21_COHORT_ROSTER.json").write_text(json.dumps(top21), encoding="utf-8")
    (fa / "TOP7_CENSUS_PULSES_v1.json").write_text(json.dumps(
        {"pulses": [{"rows": []}, {"rows": [{"repo": "GBOGEB/" + n} for n in top7]}]}), encoding="utf-8")
    (fa / "live-census" / "source").mkdir(parents=True)
    (fa / "live-census" / "source" / "live_census.py").write_text(
        "X = 1\nREPOS = {" + ", ".join(repr(n) + ": 1" for n in live) + "}\n", encoding="utf-8")
    data = root / "mission-control" / "jade_temple" / "data"
    data.mkdir(parents=True)
    (data / "REPO_READINESS_NPLUS1.json").write_text(json.dumps({"rows": [
        {"repo": "GBOGEB/core-a", "priority": "P0", "lane": "L1", "owner_role": "owner", "extra": 1},
        {"repo": "GBOGEB/sat-b", "priority": "P1"},
        {"repo": "GBOGEB/old-c", "priority": "P2"},
        {"repo": "GBOGEB/fork-d", "priority": None},
    ]}), encoding="utf-8")
    if red_trace:
        (data / "RED_TRACE_FEDERATION_N8.json").write_text(
            json.dumps({"repositories": [{"short": "core-a"}, {"short": "rt-only"}]}), encoding="utf-8")
    return root


def write_seed(hub: Path, rows):
    seed = hub / "seed.tsv"
    lines = ["# comment line", ""]
    lines += ["\t".join(r) for r in rows]
    seed.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return seed


SEED_ROWS = [
    ("core-a", _iso(1), "public", "false"),
    ("sat-b", _iso(5), "public", "false"),
    ("old-c", _iso(20), "private", "false"),
    ("fork-d", _iso(60), "public", "true"),
    ("e-quarter", _iso(200), "public", "false"),
    ("f-ancient", _iso(800), "public", "false"),
    ("g-tie", _iso(800), "public", "false"),
]


# ------------------------------------------------------------------ small helpers
def test_read_seed_skips_comments_and_parses_fork(tmp_path):
    seed = write_seed(tmp_path, [("a", "2026-01-01T00:00:00Z", "public", "true"),
                                 ("b", "2026-01-01T00:00:00Z", "private", "false")])
    rows = mod.read_seed(seed)
    assert [r["name"] for r in rows] == ["a", "b"]
    assert rows[0]["fork"] is True and rows[1]["fork"] is False


@pytest.mark.parametrize("days,pts", [(1, 25), (2, 25), (6, 20), (29, 12), (89, 6), (364, 2), (366, 0)])
def test_recency_points_bands(days, pts):
    assert mod.recency_points(days) == pts


def test_score_repo_parts_archived_and_unknown_priority():
    lists = {"LIVE_CENSUS_REPOS": ["x"], "TOP7_CENSUS": ["x"], "TOP21_COHORT_ROSTER": ["x"]}
    jade = {"x": {"priority": "P0"}}
    s, parts, days = mod.score_repo({"name": "x", "pushed_at": _iso(1), "fork": True, "archived": True},
                                    lists, jade, NOW)
    assert parts == {"core_federation": 30, "top7": 12, "top21": 8, "jade_priority": 5,
                     "recency": 25, "fork": -20, "archived": -30}
    assert s == sum(parts.values()) and days == 1.0
    s2, parts2, _ = mod.score_repo({"name": "y", "pushed_at": _iso(400), "fork": False}, {}, {}, NOW)
    assert s2 == 0 and parts2["jade_priority"] == 0


def test_mission_lists_with_and_without_red_trace(tmp_path):
    with_rt = mod.mission_lists(make_hub(tmp_path / "a"))
    assert with_rt["RED_TRACE_CORE"] == ["core-a", "rt-only"]
    assert with_rt["TOP7_CENSUS"] == ["core-a", "sat-b", "ghost", "ghost2"]
    assert with_rt["LIVE_CENSUS_REPOS"] == ["core-a"]
    without = mod.mission_lists(make_hub(tmp_path / "b", red_trace=False))
    assert "RED_TRACE_CORE" not in without


def test_jade_rows_keyed_by_short_name(tmp_path):
    rows = mod.jade_rows(make_hub(tmp_path))
    assert set(rows) == {"core-a", "sat-b", "old-c", "fork-d"}


# ------------------------------------------------------------------ repo census
def test_repo_census_end_to_end(tmp_path):
    hub = make_hub(tmp_path / "hub")
    seed = write_seed(hub, SEED_ROWS)
    out = tmp_path / "out"
    reg, tier = mod.repo_census(seed, hub, out, NOW)
    assert reg["population"] == 7 and reg["seed"] == "seed.tsv" and reg["merge_authorized"] is False
    names = [r["name"] for r in reg["repositories"]]
    assert names[0] == "core-a"
    assert [r["rank"] for r in reg["repositories"]] == list(range(1, 8))
    assert list(reg["repositories"][0])[0] == "rank"
    by = {r["name"]: r for r in reg["repositories"]}
    assert by["core-a"]["class"] == "CORE"
    assert by["sat-b"]["class"] == "SATELLITE"
    assert by["fork-d"]["class"] == "UPSTREAM_FORK"
    assert by["old-c"]["class"] == "OWNED"
    assert by["core-a"]["jade"] == {"priority": "P0", "lane": "L1", "owner_role": "owner"}
    assert "jade" not in by["e-quarter"]
    # ties on score and push time are broken by name
    assert names.index("f-ancient") < names.index("g-tie")
    a = tier["all"]
    assert a["population"] == 7 and a["top_3"] == names[:3] and a["top_100"] == names
    assert a["bottom_3"] == names[-3:][::-1] and "bottom_7" not in a
    assert tier["owned"]["population"] == 6 and "fork-d" not in tier["owned"]["top_100"]
    drift = tier["legacy_list_drift"]
    assert drift["TOP7_CENSUS"]["compared_with"] == "first 4"
    assert drift["TOP7_CENSUS"]["only_in_legacy"] == ["ghost", "ghost2"]
    assert drift["TOP21_COHORT_ROSTER"]["compared_with"] == "first 5"
    assert "legacy-x" in drift["TOP21_COHORT_ROSTER"]["only_in_legacy"]
    loaded = yaml.safe_load((out / "REPO_REGISTRY.yaml").read_text(encoding="utf-8"))
    assert loaded["population"] == 7
    assert (out / "REPO_REGISTRY.yaml").read_text(encoding="utf-8").startswith("# CANONICAL")
    assert (out / "REPO_TIERS.yaml").exists()


def test_repo_census_drift_uses_tier_when_size_matches(tmp_path):
    hub = make_hub(tmp_path / "hub", top7=("core-a", "sat-b", "old-c"))
    seed = write_seed(hub, SEED_ROWS)
    _, tier = mod.repo_census(seed, hub, tmp_path / "out", NOW)
    assert tier["legacy_list_drift"]["TOP7_CENSUS"]["compared_with"] == "top_3"


def test_repo_census_default_now(tmp_path):
    hub = make_hub(tmp_path / "hub")
    seed = write_seed(hub, SEED_ROWS[:2])
    reg, _ = mod.repo_census(seed, hub, tmp_path / "out")
    assert reg["observed_at_utc"].endswith("Z") and reg["population"] == 2


def test_dump_uses_block_style_for_multiline(tmp_path):
    p = tmp_path / "x.yaml"
    mod.dump({"k": "a\nb", "j": "plain"}, p, "line one\nline two")
    text = p.read_text(encoding="utf-8")
    assert text.startswith("# line one\n# line two\n") and "k: |" in text
    assert yaml.safe_load(text) == {"k": "a\nb", "j": "plain"}


# ------------------------------------------------------------------ binaries (git faked)
def _rec(mode, oid, path):
    return mode.encode() + b" " + oid.encode() + b" 0\t" + path.encode()


class FakeGit:
    def __init__(self, records, head="f" * 40):
        self.records, self.head, self.calls = records, head, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=self.head + "\n", stderr="")
        assert cmd[3:] == ["ls-files", "-s", "-z"] and kw.get("check") is True
        return subprocess.CompletedProcess(cmd, 0, stdout=b"\0".join(self.records) + b"\0", stderr=b"")


def build_repo(root: Path):
    (root / "docs").mkdir(parents=True)
    (root / "img").mkdir()
    files = {
        "docs/a.pdf": b"%PDF-1" + b"x" * 50,
        "img/copy.pdf": b"%PDF-1" + b"x" * 50,
        "logo.png": b"\x89PNG" + b"y" * 10,
        "img/deep/b.png": b"\x89PNG" + b"z" * 200,
        "noext": b"abc\0def",
        "data.zip": b"PK" + b"q" * 30,
        "README.md": b"see docs/a.pdf and a.pdf and logo.png\n",
        "plain.txt": b"no references here\n",
        "notes.txt": b"mentions data.zip once\n",
    }
    for rel, raw in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    big = root / "big.txt"
    big.write_bytes(b"a" * 2_000_001)
    return [
        _rec("100644", "1" * 40, "docs/a.pdf"),
        _rec("100644", "1" * 40, "img/copy.pdf"),
        _rec("100644", "2" * 40, "logo.png"),
        _rec("100644", "3" * 40, "img/deep/b.png"),
        _rec("100755", "4" * 40, "noext"),
        _rec("100644", "5" * 40, "data.zip"),
        _rec("100644", "6" * 40, "README.md"),
        _rec("100644", "7" * 40, "plain.txt"),
        _rec("100644", "8" * 40, "notes.txt"),
        _rec("100644", "9" * 40, "big.txt"),
        _rec("120000", "a" * 40, "link.pdf"),
        _rec("160000", "b" * 40, "submodule"),
        _rec("100644", "c" * 40, "deleted.pdf"),
    ]


def test_git_files_parses_and_skips_empty(tmp_path, monkeypatch):
    fake = FakeGit([_rec("100644", "1" * 40, "a b.txt"), b"", _rec("120000", "2" * 40, "l")])
    monkeypatch.setattr(mod.subprocess, "run", fake)
    assert list(mod.git_files(tmp_path)) == [("100644", "1" * 40, "a b.txt"), ("120000", "2" * 40, "l")]


def test_is_binary_ext_nul_text_and_oserror(tmp_path):
    t = tmp_path / "t.txt"
    t.write_bytes(b"hello")
    n = tmp_path / "n"
    n.write_bytes(b"he\0llo")
    assert mod.is_binary(tmp_path / "missing.pdf", "pdf") is True
    assert mod.is_binary(n, "") is True
    assert mod.is_binary(t, "txt") is False
    assert mod.is_binary(tmp_path / "missing", "") is False


def test_binary_census_end_to_end(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    records = build_repo(root)
    fake = FakeGit(records)
    monkeypatch.setattr(mod.subprocess, "run", fake)
    real_read_text = Path.read_text

    def flaky_read_text(self, *a, **kw):
        if self.name == "notes.txt":
            raise OSError("locked")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)
    out = tmp_path / "out"
    reg, tiers = mod.binary_census({"R": str(root)}, out, NOW)
    monkeypatch.setattr(Path, "read_text", real_read_text)
    per = reg["repositories"]["R"]
    assert per["head_sha"] == "f" * 40
    assert per["binaries"] == 6 and per["unique_contents"] == 5 and per["duplicate_groups"] == 1
    assert per["duplicate_bytes"] == 56
    assert reg["totals"]["binaries"] == 6 and reg["totals"]["duplicate_copies"] == 1
    assert reg["totals"]["duplicate_bytes"] == 56
    assert per["depth_spread"] == {0: 3, 1: 2, 2: 1}
    assert "(none)" in per["by_type"] and "." in per["hierarchy_top_dirs"]
    index = json.loads((out / "BINARY_INDEX.json").read_text(encoding="utf-8"))
    by_path = {b["path"]: b for b in index}
    assert by_path["docs/a.pdf"]["refs"] == 2 and by_path["docs/a.pdf"]["canonical"] is True
    assert by_path["img/copy.pdf"]["canonical"] is False
    assert by_path["img/copy.pdf"]["canonical_path"] == "docs/a.pdf" and by_path["img/copy.pdf"]["copies"] == 2
    assert by_path["logo.png"]["refs"] == 1
    # notes.txt was unreadable, so data.zip has no references
    assert by_path["data.zip"]["refs"] == 0
    assert per["referenced"] == 2 and per["unreferenced"] == 4
    assert "link.pdf" not in by_path and "submodule" not in by_path and "deleted.pdf" not in by_path
    assert len(tiers["priority.top_3"]) == 3 and tiers["priority.top_3"][0]["path"] == "docs/a.pdf"
    assert tiers["size.top_3"][0]["path"] == "img/deep/b.png"
    assert "priority.bottom_3" in tiers and "priority.bottom_7" not in tiers
    assert tiers["population_unique_contents"] == 5
    assert (out / "BINARY_REGISTRY.yaml").exists() and (out / "BINARY_TIERS.yaml").exists()


def test_binary_census_default_now_and_empty_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit([]))
    reg, tiers = mod.binary_census({"E": tmp_path}, tmp_path / "out")
    assert reg["totals"]["binaries"] == 0 and tiers["population_unique_contents"] == 0
    assert "priority.bottom_3" not in tiers


# ------------------------------------------------------------------ reader + CLI
@pytest.fixture
def tiers_file(tmp_path):
    p = tmp_path / "T.yaml"
    p.write_text(yaml.safe_dump({"schema": "s", "flat.key": [1], "all": {"top_3": ["a", "b"], "empty": [],
                                                                        "rows": [{"x": 1}], "leaf": "v"}}),
                 encoding="utf-8")
    return p


def test_get_direct_nested_and_missing(tiers_file):
    assert mod.get(tiers_file, "flat.key") == [1]
    assert mod.get(tiers_file, "all.top_3") == ["a", "b"]
    with pytest.raises(KeyError, match="available: all, flat.key"):
        mod.get(tiers_file, "all.nope")
    with pytest.raises(KeyError):
        mod.get(tiers_file, "all.leaf.deeper")


@pytest.mark.parametrize("tier,expected", [
    ("all.top_3", "a\nb"),
    ("all.empty", ""),
    ("all.rows", "- x: 1"),
    ("all.leaf", "v\n..."),
])
def test_main_get_formats(tiers_file, capsys, tier, expected):
    assert mod.main(["get", str(tiers_file), tier]) == 0
    assert capsys.readouterr().out.rstrip("\n") == expected


def test_main_repos_with_and_without_now(tmp_path, monkeypatch, capsys):
    hub = make_hub(tmp_path / "hub")
    seed = write_seed(hub, SEED_ROWS)
    monkeypatch.setattr(mod, "HUB", hub)
    assert mod.main(["repos", "--seed", str(seed), "--out", str(tmp_path / "o1"),
                     "--now", "2026-10-20T12:00:00Z"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["population"] == 7 and first["top_7"][0] == "core-a"
    assert mod.main(["repos", "--seed", str(seed), "--out", str(tmp_path / "o2")]) == 0
    assert json.loads(capsys.readouterr().out)["population"] == 7


def test_main_binaries(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    fake = FakeGit(build_repo(root))
    monkeypatch.setattr(mod.subprocess, "run", fake)
    assert mod.main(["binaries", "--repo", "R=" + str(root), "--out", str(tmp_path / "o")]) == 0
    assert json.loads(capsys.readouterr().out)["binaries"] == 6


def test_dunder_main_get(tiers_file, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "get", str(tiers_file), "all.top_3"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert capsys.readouterr().out.split() == ["a", "b"]
