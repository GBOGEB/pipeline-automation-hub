"""Include the GitHub-first handover guards in the canonical N3 testflight.

Original contract and tests remain in the existing handoff folder;
this small consumer wrapper does not create a second SSOT.
"""
import sys
from pathlib import Path

HANDOFF_DIR = Path(__file__).resolve().parent / "handoff"
if str(HANDOFF_DIR) not in sys.path:
    sys.path.insert(0, str(HANDOFF_DIR))

from test_github_first_handoff import HandoffContractTests  # noqa: E402,F401
