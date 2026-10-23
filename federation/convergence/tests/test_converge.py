"""Negative / fail-closed tests for the convergence reducer.

Run from the repository root: python -m pytest federation/convergence/tests
"""
import copy
import json
import unittest

from federation.convergence import converge

try:
    import jsonschema
except ImportError:  # schema tests report as skipped, never as passed
    jsonschema = None

EVIDENCE = converge.EVIDENCE_DIR
SCHEMA = json.loads((converge.REPO_ROOT / "contracts" / "convergence-receipt.schema.json").read_text(encoding="utf-8"))
needs_jsonschema = unittest.skipUnless(jsonschema, "jsonschema not installed")


def build(data=None):
    base, manifest = converge.load(EVIDENCE)
    data = data or base
    events = converge.normalise_events(data)
    checks = converge.crosschecks(data, events)
    return data, converge.reduce(data, manifest, checks, events), {c["id"]: c["result"] for c in checks}


class EvidenceModel(unittest.TestCase):
    def test_not_observed_cannot_carry_value(self):
        with self.assertRaises(ValueError):
            converge.evidence("NOT_OBSERVED", 0)

    def test_numerator_requires_denominator_and_scope(self):
        with self.assertRaises(ValueError):
            converge.evidence("VERIFIED", 0.9, numerator=763)

    def test_missing_count_is_not_zero(self):
        self.assertEqual(converge.count_evidence(None, [])["state"], "NOT_OBSERVED")
        self.assertEqual(converge.count_evidence(0, [])["state"], "OBSERVED_EMPTY")
        self.assertEqual(converge.count_evidence(6, [])["state"], "OBSERVED_NONEMPTY")


class Plateau(unittest.TestCase):
    def series(self, n, fresh=True, vals=None):
        vals = vals or [(6, 42)] * n
        return [{"cohort": "c", "num": a, "den": b, "fresh": fresh} for a, b in vals]

    def test_replayed_snapshots_starve(self):
        self.assertEqual(converge.plateau(self.series(5, fresh=False), "STABLE_HOLD")["state"], "STARVED")

    def test_three_equal_fresh_transitions_hold(self):
        self.assertEqual(converge.plateau(self.series(4), "NONE")["state"], "STABLE_HOLD")

    def test_two_equal_fresh_transitions_active(self):
        self.assertEqual(converge.plateau(self.series(3), "NONE")["state"], "ACTIVE")

    def test_change_resets_run(self):
        s = self.series(5, vals=[(6, 42), (6, 42), (6, 42), (7, 42), (7, 42)])
        self.assertEqual(converge.plateau(s, "NONE")["comparable_equal_transitions"], 1)

    def test_denominator_change_breaks_equality(self):
        s = self.series(4, vals=[(6, 42), (6, 42), (6, 43), (6, 43)])
        self.assertEqual(converge.plateau(s, "NONE")["state"], "ACTIVE")


class Receipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.receipt, cls.checks = build()

    @needs_jsonschema
    def test_schema_valid(self):
        jsonschema.validate(self.receipt, SCHEMA)

    def test_no_root_closures_or_credit(self):
        fed = self.receipt["federation"]
        self.assertEqual((fed["admission"], fed["formal_credit_delta"], fed["qualified_root_closures"]), ("HOLD", 0, 0))
        self.assertTrue(all(f["accepted_root_id"] is None for f in self.receipt["fingerprints"]))

    def test_occurrences_not_roots(self):
        f = next(x for x in self.receipt["fingerprints"] if x["fingerprint"] == "GITHUB_WORKFLOW_ACTION_REQUIRED")
        self.assertEqual(f["occurrences"]["value"], 106)
        self.assertEqual(len(f["populations"]), 4)

    def test_unknown_occurrence_count_stays_unknown(self):
        f = next(x for x in self.receipt["fingerprints"] if x["fingerprint"] == "BANDIT_NEW_DEBT_TEST_FIXTURES")
        self.assertEqual(f["occurrences"]["state"], "NOT_OBSERVED")

    def test_truncated_or_unknown_pr_heads_ineligible(self):
        for repo in self.receipt["repos"].values():
            for p in repo["populations"]:
                if p["eligible_for_comparison"]:
                    self.assertTrue(p["head_sha_exact"])
                    self.assertEqual(p["head_sha"], repo["observed_main"]["value"])

    @needs_jsonschema
    def test_schema_rejects_truncated_head_marked_eligible(self):
        bad = copy.deepcopy(self.receipt)
        bad["repos"]["ABACUS"]["populations"][0].update(head_sha_exact=False, eligible_for_comparison=True)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA)

    @needs_jsonschema
    def test_schema_rejects_value_on_not_observed(self):
        bad = copy.deepcopy(self.receipt)
        bad["repos"]["HUB"]["progress"]["worker_hours"] = {"state": "NOT_OBSERVED", "value": 0, "sources": []}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA)

    def test_hub_asserted_hold_not_derived(self):
        p = self.receipt["repos"]["HUB"]["plateau"]
        self.assertEqual((p["asserted_state"], p["state"]), ("STABLE_HOLD", "STARVED"))


class Tamper(unittest.TestCase):
    def test_summary_tamper_detected(self):
        data, _ = converge.load(EVIDENCE)
        data = copy.deepcopy(data)
        data["zip"]["summary"]["validated_members"] += 1
        _, _, checks = build(data)
        self.assertEqual(checks["C01_zip_summary_totals"], "FAIL")
        self.assertEqual(checks["C05_new_terminals_summary_vs_zip_ledger"], "FAIL")

    def test_member_byte_tamper_detected(self):
        data, _ = converge.load(EVIDENCE)
        data = copy.deepcopy(data)
        data["members"][1]["members"][0]["bytes"] += 1
        _, _, checks = build(data)
        self.assertEqual(checks["C03_member_ledger_per_archive"], "FAIL")
        self.assertEqual(checks["C04_terminal_summary_vs_member_ledger"], "PASS")

    def test_digest_disagreement_detected(self):
        data, _ = converge.load(EVIDENCE)
        data = copy.deepcopy(data)
        a = next(x for x in data["zip"]["archives"] if x["artifact_id"] == 11964700323)
        a["archive_sha256"] = "0" * 64
        _, _, checks = build(data)
        self.assertEqual(checks["C06_cross_ledger_digest_agreement"], "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=1)
