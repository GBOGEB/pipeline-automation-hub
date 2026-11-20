"""Collect the BIOS suite through the existing offline JADE workflow; no new publisher."""
from pathlib import Path
import unittest


def load_tests(loader, tests, pattern):
    root = Path(__file__).resolve().parents[4]
    target = str(root / "tools/repo-bios")
    return unittest.TestLoader().discover(target, pattern="test_*.py", top_level_dir=target)
