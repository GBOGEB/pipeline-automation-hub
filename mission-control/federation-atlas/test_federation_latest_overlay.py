"""Latest N+2 overlay regression controls; no code-promotion from stale snapshots."""
import copy
import json
import unittest
from pathlib import Path

import federation_latest_overlay as overlay

HERE = Path(__file__).resolve().parent


def fixtures():
    return (json.loads((HERE / "FEDERATION_STATUS_N2_v1.json").read_text()),
            json.loads((HERE / "FEDERATION_OBSERVED_PULSES_v1.json").read_text()))


class LatestPulseTests(unittest.TestCase):
    def test_verified_terminal_overlay(self):
        o, h = fixtures()
        r = overlay.validate(o, h)
        self.assertEqual("N+2", r["pulse"])
        self.assertEqual("P2", r["qps_source_pulse"])
        self.assertEqual("TERMINAL_FAIL", r["w70"]["state"])
        self.assertIsNone(r["w70"]["line"])
        self.assertEqual({"verified": 1, "eligible": 5}, r["measured_breadth"])

    def test_histories_are_not_overwritten(self):
        o, h = fixtures()
        r = overlay.validate(o, h)
        self.assertEqual(["N", "N+1", "N+2"],
                         [x["program_pulse"] for x in r["stages"]])
        self.assertEqual(["QUEUED", "FAILED", "FAILED"],
                         [x["w70"] for x in r["stages"]])
        self.assertEqual([0, 1, 2], [x["pulse"] for x in r["qps_pulses"]])

    def test_w70_queued_revert_rejected(self):
        o, h = fixtures()
        o["w70"]["state"] = "QUEUED"
        with self.assertRaisesRegex(ValueError, "W70 terminal"):
            overlay.validate(o, h)

    def test_w70_synthetic_coverage_rejected(self):
        o, h = fixtures()
        o["w70"]["line"] = {"covered": 88, "eligible": 100}
        with self.assertRaisesRegex(ValueError, "W70 terminal"):
            overlay.validate(o, h)

    def test_w70_foreign_source_sha_rejected(self):
        o, h = fixtures()
        o["w70"]["head_sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "W70 observed"):
            overlay.validate(o, h)

    def test_qps_artifact_denominator_drift_fails(self):
        o, h = fixtures()
        h["observations"][0]["line"]["eligible"] = 134
        with self.assertRaisesRegex(ValueError, "source identity"):
            overlay.validate(o, h)

    def test_qps_python_parity_is_required(self):
        o, h = fixtures()
        h["observations"][1]["line"]["covered"] -= 1
        with self.assertRaisesRegex(ValueError, "Python population"):
            overlay.validate(o, h)

    def test_wrong_fleet_baseline_fails(self):
        o, h = fixtures()
        o["census"]["open_prs"] = 39
        with self.assertRaisesRegex(ValueError, "N\+2 fleet"):
            overlay.validate(o, h)

    def test_qps_engineering_accept_never_auto_promotes(self):
        o, h = fixtures()
        o["qps_accepted"] = True
        with self.assertRaisesRegex(ValueError, "authority"):
            overlay.validate(o, h)

    def test_generated_html_distinguishes_pulse_identifiers(self):
        o, h = fixtures()
        page = overlay.render(overlay.validate(o, h))
        self.assertIn("P2", page)
        self.assertIn("N+2", page)
        self.assertIn("TERMINAL RED", page)
        # Assert the semantic rendered pulse row, not explanatory prose
        # stating that an artificial QPS P3 must never be invented.
        self.assertNotIn('<b>P3</b>', page)
        self.assertEqual(page.count('class="pulse"'), 3)
        self.assertEqual([p["pulse"] for p in overlay.validate(o, h)["qps_pulses"]], [0, 1, 2])
        self.assertIn("not an artificial QPS P3", page)
        self.assertIn("38 / 613", page)

    def test_later_sample_cannot_be_silent_n2(self):
        o, h = fixtures()
        o["program_pulse"] = "N+3"
        with self.assertRaisesRegex(ValueError, "N\+2 requires"):
            overlay.validate(o, h)
