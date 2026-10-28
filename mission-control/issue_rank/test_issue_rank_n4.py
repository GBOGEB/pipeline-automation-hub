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

    def test_same_source_time_is_not_fabricated_as_n_plus_one(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = fixture()
            first["fetched_at"] = "2026-10-26T10:00:00Z"
            src = root / "same.json"
            src.write_text(json.dumps(first), encoding="utf-8")
            out = root / "out"
            args = ["rank", "--snapshot", str(src), "--out", str(out),
                    "--draws", "0", "--redact-private"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ir.main(args), 0)
                first_pulse = json.loads((out / "taxonomy_pulse.json").read_text())
                args.extend(["--prev", str(out / "issue_rank.json")])
                self.assertEqual(ir.main(args), 0)
            repeated = json.loads((out / "taxonomy_pulse.json").read_text())
            self.assertEqual(len(first_pulse["history_points"]), 1)
            self.assertEqual(len(repeated["history_points"]), 1)
            self.assertEqual(repeated["delta"]["formal_credit_delta"], 0)

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


class MathCoverageFrontier(unittest.TestCase):
    """Disjoint graph/statistics negatives; no live source or private records."""

    def test_empty_structure_has_no_fabricated_critical_chain(self):
        self.assertEqual(ir.IM.strongly_connected([], {}), [])
        result = ir.IM.blocker_chains([], {})
        self.assertEqual(result, {"below": {}, "above": {}, "critical": [], "cycles": []})

    def test_singleton_and_unknown_scc_neighbors(self):
        self.assertEqual(ir.IM.strongly_connected(["a"], {"a": ["missing"]}), [["a"]])
        out = ir.IM.blocker_chains(["a"], {"a": ["absent"]})
        self.assertEqual(out["critical"], ["a"])
        self.assertEqual(out["below"]["a"], 0)

    def test_empty_and_singleton_quantile(self):
        self.assertIsNone(ir.IM.quantile([], .5))
        self.assertEqual(ir.IM.quantile([7], .5), 7)
        self.assertEqual(ir.IM.quantile([1, 2, 3, 4], 0), 1)
        self.assertEqual(ir.IM.quantile([1, 2, 3, 4], 1), 4)

    def test_rank_mismatch_constant_or_singleton_is_withheld(self):
        self.assertIsNone(ir.IM.spearman([1], [1]))
        self.assertIsNone(ir.IM.spearman([1, 2], [1]))
        self.assertIsNone(ir.IM.spearman([3, 3, 3], [1, 2, 3]))
        self.assertIsNone(ir.IM.kendall_tau_b([1], [1]))
        self.assertIsNone(ir.IM.kendall_tau_b([1, 2], [1]))

    def test_kendall_ties_and_no_pairs_are_handled_without_fake_signal(self):
        self.assertIsNone(ir.IM.kendall_tau_b([2, 2, 2], [3, 3, 3]))
        value = ir.IM.kendall_tau_b([1, 1, 2, 3], [1, 2, 2, 3])
        self.assertIsNotNone(value)
        self.assertTrue(-1 <= value <= 1)

    def test_poisson_boundary_and_invalid_level(self):
        self.assertEqual(ir.IM._poisson_cdf(-1, 2.0), 0)
        self.assertEqual(ir.IM._poisson_cdf(0, 0), 1)
        for k, level in ((-1, .90), (1.0, .90), (1, 0), (1, 1)):
            with self.assertRaises(ValueError):
                ir.IM.poisson_interval(k, level)

    def test_dirichlet_zero_gamma_draws_fallback(self):
        class ZeroRandom:
            def gammavariate(self, alpha, beta):
                return 0.0
        self.assertEqual(ir.IM.dirichlet(ZeroRandom(), [1.0, 2.0, 4.0]),
                         [1 / 3, 1 / 3, 1 / 3])

    def test_tie_ranks_stable_under_permutation(self):
        self.assertEqual(ir.IM.average_ranks([7, 2, 7, 9]), [2.5, 1.0, 2.5, 4.0])
        self.assertEqual(ir.IM.average_ranks([]), [])



if __name__ == "__main__":
    unittest.main()
