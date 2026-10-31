"""Runs the offline self-check of tools/workstation/Invoke-DraftPrPass.ps1 (security thread rule)."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "workstation" / "Invoke-DraftPrPass.ps1"


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh not installed")
def test_security_rule_selftest():
    out = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(SCRIPT), "-SelfTest"],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "SELFTEST 13/13 passed" in out.stdout


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
