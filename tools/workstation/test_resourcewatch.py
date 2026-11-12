"""Dry-run tests for ResourceWatch.ps1: band selection and the junction skip (#1166)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent / "ResourceWatch"
PS = shutil.which("powershell.exe") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PS is None, reason="needs Windows PowerShell")


def run(body: str) -> str:
    script = f". '{HERE / 'ResourceWatch.ps1'}' -LoadOnly\n{body}"
    out = subprocess.run(
        [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pytest.mark.parametrize(
    "free, band",
    [(50, "ok"), (30, "30 GB"), (25, "30 GB"), (12, "15 GB"), (4, "5 GB"), (0.5, "1 GB")],
)
def test_band_selection(free, band):
    got = run(f"$b = Get-DiskBand {free}; if ($b) {{ $b.name }} else {{ 'ok' }}")
    assert got == band


def test_deeper_cleanup_replaces_milder():
    got = run("(Get-CleanupsFor (Get-DiskBand 4)) -join ','").split(",")
    assert "temp1" in got and "temp7" not in got and "temp2" not in got
    assert "oneDriveUnpin30" in got and "oneDriveUnpin90" not in got


def test_junction_skipped(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    work = tmp_path / "work"
    (work / "old").mkdir(parents=True)
    (work / "old" / "a.txt").write_text("x")
    link = work / "link"
    made = subprocess.run(
        [PS, "-NoProfile", "-Command",
         f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null"],
        capture_output=True,
    )
    if made.returncode != 0 or not link.exists():
        pytest.skip("cannot create a junction here")
    run(f"[void](Remove-OlderThan '{work}' -1)")
    assert (target / "keep.txt").exists(), "deleted through a junction"
    assert link.exists(), "junction itself must be left alone"
    assert not (work / "old").exists()
