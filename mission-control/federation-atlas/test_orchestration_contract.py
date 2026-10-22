"""Include execution-Atlas behavioral tests in the existing native Atlas gate."""
from pathlib import Path
import unittest


def load_tests(loader, tests, pattern):
    return unittest.TestLoader().discover(
        str(Path(__file__).resolve().parent / "orchestration"), pattern="test_*.py")
