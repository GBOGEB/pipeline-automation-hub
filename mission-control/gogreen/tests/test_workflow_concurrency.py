"""Negative contract: GoGREEN Wave and fleet must not cancel each other."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / ".github/workflows/gogreen-pulses.yml"
FLEET = REPO / ".github/workflows/gogreen-g4-fleet.yml"


def group(path):
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^  group:\s*(\S.*)$", text)
    if len(matches) != 1:
        raise ValueError("exactly one concurrency group required")
    return matches[0].strip(), text


class WorkflowConcurrency(unittest.TestCase):
    def test_wave_and_fleet_have_disjoint_concurrency_lanes(self):
        wave, wsrc = group(WAVE)
        fleet, fsrc = group(FLEET)
        self.assertNotEqual(wave.casefold(), fleet.casefold())
        self.assertIn("${{ github.ref }}", wave)
        self.assertIn("${{ github.ref }}", fleet)
        self.assertIn("  pull_request:", wsrc)
        self.assertIn("  pull_request:", fsrc)
        self.assertIn("  cancel-in-progress: false", wsrc)
        self.assertIn("  cancel-in-progress: false", fsrc)

    def test_regression_detects_original_collision(self):
        # The historical two-workflow collision shared the same g4 ref lane.
        observed_old = "gogreen-g4-${{ github.ref }}"
        new_wave, _ = group(WAVE)
        self.assertNotEqual(new_wave, observed_old)


if __name__ == "__main__":
    unittest.main()
