"""Consumer source roles must fail before loading or running the renderer."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "mission-control/grand-missions/verify_p0005_mermaid_browser.py"


def invoke(source_sha, out):
    return subprocess.run([sys.executable, str(SCRIPT), "--method-root", str(ROOT),
                           "--source-sha", source_sha, "--out", str(out)], capture_output=True, text=True)


def test_mismatched_diagram_source_fails_closed(tmp_path):
    result = invoke("0" * 40, tmp_path)
    receipt = json.loads((tmp_path / "receipt.json").read_text())
    assert result.returncode == 1 and receipt["ok"] is False
    assert "diagram checkout SHA mismatch" in receipt["error"]
    assert receipt["merge_admission"] == "HOLD"


def test_consumer_head_cannot_masquerade_as_method_head(tmp_path):
    source_sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    result = invoke(source_sha, tmp_path)
    receipt = json.loads((tmp_path / "receipt.json").read_text())
    assert result.returncode == 1 and receipt["ok"] is False
    assert "method checkout SHA mismatch" in receipt["error"]
    assert receipt["closure_credit"] == 0
