"""N3 testflight bridge for CP.CLOSEOUT; no second schema authority."""
from pathlib import Path
import sys

HANDOFF_DIR = Path(__file__).resolve().parent / "handoff"
if str(HANDOFF_DIR) not in sys.path:
    sys.path.insert(0, str(HANDOFF_DIR))

from test_chat_closeout import ChatCloseoutContractTests  # noqa: E402,F401
