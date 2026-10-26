"""N+4 first-red regressions: review denial, privacy and repeated taxonomy pulses."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import issue_rank as ir
import taxonomy_pulse as tp
from test_issue_rank import QPS, fixture


class ReviewAdmission(unittest.TestCase):
    def test_explicit_changes_requested_overrides_stale_approval(self):
        for key in ("review_decision", "review"):
            self.assertFalse(ir._approved({key: "CHANGES_REQUESTED", "approvals": 5}))
            self.assertFalse(ir._approved({key: "REVIEW_REQUIRED", "approvals": 5}))
        self.assertTrue(ir._approved({"review_decision": "APPROVED", "approvals": 0}))
        self.assertTrue(ir._approved({"approvals": 1}))
        self.assertFalse(ir._approved({"review_decision": "", "approvals": 1}))


class RedactedPulse(unittest.TestCase):
    def test_public_taxonomy_from_redacted_private_snapshot(self):
        raw = ir.rank(fixture(), draws=0)
        private_sha = raw["heads"][QPS]["head_sha"]
        red = ir.redact(raw)
        self.assertIsNone(red["heads"][QPS]["head_sha"])
        self.assertIn(QPS, red["privacy_projection"]["validated_then_redacted_heads"])
        r = tp.build(red, public=True, parser_sha="a" * 40)
        self.assertEqual(r["visibility"], "PUBLIC_PROJECTION")
        self.assertEqual(r["parser_pin_state"], "PINNED")
        self.assertNotIn(private_sha, json.dumps(r))
        self.assertNotIn(QPS, json.dumps(r["source_heads"]))

    def test_raw_private_invalid_head_is_not_a_redacted_exception(self):
        raw = ir.rank(fixture(), draws=0)
        raw["heads"][QPS]["head_sha"] = None
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_HEAD"):
            tp.build(raw, public=True)
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_HEAD_BEFORE_REDACTION"):
            ir.redact(raw)

    def test_previous_redacted_pulse_produces_two_real_model_points(self):
        base = ir.rank(fixture(), draws=0)
        older = ir.redact(copy.deepcopy(base))
        newer = ir.redact(copy.deepcopy(base))
        older["fetched_at"] = "2026-10-25T10:00:00Z"
        newer["fetched_at"] = "2026-10-26T10:00:00Z"
        r = tp.build(newer, older, public=True, parser_sha="a" * 40,
                     previous_parser_sha="a" * 40)
        self.assertEqual(len(r["history_points"]), 2)
        self.assertTrue(r["delta"]["parser_identity_comparable"])
        self.assertEqual(r["formal_credit_delta"], 0)

    def test_parser_flags_and_previous_model_reach_taxonomy_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = fixture()
            first["fetched_at"] = "2026-10-25T10:00:00Z"
            second = copy.deepcopy(first)
            second["fetched_at"] = "2026-10-26T10:00:00Z"
            one = root / "one.json"
            two = root / "two.json"
            one.write_text(json.dumps(first), encoding="utf-8")
            two.write_text(json.dumps(second), encoding="utf-8")
            out1, out2 = root / "one", root / "two"
            def rank_once(*args):
                with redirect_stdout(io.StringIO()):
                    return ir.main(["rank", *args, "--redact-private",
                                    "--draws", "0", "--parser-sha", "a" * 40,
                                    "--previous-parser-sha", "a" * 40])
            self.assertEqual(rank_once("--snapshot", str(one), "--out", str(out1)), 0)
            self.assertEqual(rank_once("--snapshot", str(two),
                                       "--prev", str(out1 / "issue_rank.json"),
                                       "--out", str(out2)), 0)
            pulse = json.loads((out2 / "taxonomy_pulse.json").read_text(encoding="utf-8"))
            self.assertEqual(len(pulse["history_points"]), 2)
            self.assertTrue(pulse["delta"]["parser_identity_comparable"])
            self.assertEqual(pulse["formal_credit_delta"], 0)


if __name__ == "__main__":
    unittest.main()
