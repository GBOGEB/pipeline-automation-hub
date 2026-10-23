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


class ReviewFindings(unittest.TestCase):
    """Regression tests for the Codex / Copilot review of PR #780."""

    def tampered(self, mutate):
        data, _ = converge.load(EVIDENCE)
        data = copy.deepcopy(data)
        mutate(data)
        return build(data)

    def test_baseline_integrity_counts(self):
        _, receipt, _ = build()
        integ = receipt["artifact_integrity"]
        self.assertEqual((integ["verified_unique_archives"], integ["verified_unique_members"]), (22, 276))
        self.assertEqual((integ["digest_failures"], integ["crc_failures"], integ["failed_archives"]), (0, 0, []))
        self.assertEqual(integ["verified_in_chat_only"], [12429667081])
        self.assertIn(12423779766, integ["unknown"])
        self.assertTrue(any("#2047 run 39786774636" in str(u) for u in integ["unknown"]))
        self.assertFalse(any("#2048" in str(u) for u in integ["unknown"]))

    def test_member_crc_failure_detected_and_counted(self):
        def mutate(d):
            d["members"][0]["crc_all_members_pass"] = False
        _, receipt, checks = self.tampered(mutate)
        integ = receipt["artifact_integrity"]
        self.assertEqual(checks["C03_member_ledger_per_archive"], "FAIL")
        self.assertEqual(integ["crc_failures"], 1)
        self.assertEqual(integ["verified_unique_archives"], 21)
        self.assertEqual(integ["failed_archives"], [12428658601])

    def test_zip_checksum_failure_counted(self):
        def mutate(d):
            d["zip"]["archives"][0]["checksum_verified"] = False
        _, receipt, checks = self.tampered(mutate)
        self.assertEqual(checks["C02_zip_per_archive"], "FAIL")
        self.assertEqual(receipt["artifact_integrity"]["digest_failures"], 1)

    def test_cross_ledger_disagreement_is_digest_failure(self):
        def mutate(d):
            next(a for a in d["zip"]["archives"] if a["artifact_id"] == 11964700323)["archive_sha256"] = "0" * 64
        _, receipt, checks = self.tampered(mutate)
        self.assertEqual(checks["C06_cross_ledger_digest_agreement"], "FAIL")
        self.assertIn(11964700323, receipt["artifact_integrity"]["failed_archives"])
        self.assertEqual(receipt["artifact_integrity"]["digest_failures"], 1)

    def test_member_accounting_failure_excluded_from_totals(self):
        def mutate(d):
            d["members"][1]["members"][0]["bytes"] += 1
        _, receipt, _ = self.tampered(mutate)
        self.assertEqual(receipt["artifact_integrity"]["inconsistent_archives"], [12431130883])
        self.assertEqual(receipt["artifact_integrity"]["verified_unique_archives"], 21)

    def test_cross_ledger_metadata_disagreement_is_inconsistent(self):
        # PR #789 review: both records self-consistent, digests equal, but run/totals differ
        for field, delta in (("run", 1), ("zip_bytes", 1)):
            def mutate(d, field=field, delta=delta):
                a = next(x for x in d["members"] if x["artifact_id"] == 11964700323)
                a[field] += delta
            with self.subTest(field=field):
                _, receipt, _ = self.tampered(mutate)
                self.assertIn(11964700323, receipt["artifact_integrity"]["inconsistent_archives"])
                self.assertEqual(receipt["artifact_integrity"]["verified_unique_archives"], 21)

    def test_nonempty_evidence_rejects_empty_value(self):
        for value in (None, 0, [], ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                converge.evidence("OBSERVED_NONEMPTY", value)

    @needs_jsonschema
    def test_schema_rejects_empty_nonempty_evidence(self):
        _, receipt, _ = build()
        for value in (0, [], "", {}):
            bad = copy.deepcopy(receipt)
            bad["repos"]["HUB"]["observed_main"]["value"] = value
            with self.subTest(value=value), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(bad, SCHEMA)

    def test_c07_reports_chat_only_citations(self):
        _, _, checks = build()
        self.assertEqual(checks["C07_event_artifact_citations"], "WARN")

    def test_c07_fails_on_wrong_run_binding(self):
        def mutate(d):
            d["members"][0]["run"] = 1
        _, _, checks = self.tampered(mutate)
        self.assertEqual(checks["C07_event_artifact_citations"], "FAIL")

    def test_c07_fails_on_missing_ledger_artifact(self):
        def mutate(d):
            d["zip"]["archives"] = [a for a in d["zip"]["archives"] if a["artifact_id"] != 12435475709]
        _, _, checks = self.tampered(mutate)
        self.assertEqual(checks["C07_event_artifact_citations"], "FAIL")

    def test_main_invalidated_by_later_merge(self):
        _, receipt, _ = build()
        qps = receipt["repos"]["QPS"]
        self.assertEqual(qps["observed_main"]["state"], "NOT_OBSERVED")
        self.assertTrue(any("merge of #2047" in s for s in qps["observed_main"]["sources"]))
        self.assertFalse(any(p["eligible_for_comparison"] for p in qps["populations"]))
        self.assertEqual(receipt["repos"]["HUB"]["observed_main"]["state"], "OBSERVED_NONEMPTY")

    def test_counted_zero_is_observed_empty(self):
        def mutate(d):
            for p in d["chat"]["pulses"]:
                for e in p["events"]:
                    if e["fingerprint"] == "GOVERNANCE_MERGE_WITHOUT_APPROVAL":
                        e["occurrences"] = 0
        _, receipt, _ = self.tampered(mutate)
        f = next(x for x in receipt["fingerprints"] if x["fingerprint"] == "GOVERNANCE_MERGE_WITHOUT_APPROVAL")
        self.assertEqual((f["occurrences"]["state"], f["occurrences"]["value"]), ("OBSERVED_EMPTY", 0))

    @needs_jsonschema
    def test_schema_rejects_malformed_exact_head(self):
        _, receipt, _ = build()
        bad = copy.deepcopy(receipt)
        bad["repos"]["ABACUS"]["populations"][0].update(head_sha="301960e92b12", head_sha_exact=True,
                                                        eligible_for_comparison=True)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA)

    @needs_jsonschema
    def test_schema_rejects_invalid_occurrences(self):
        _, receipt, _ = build()
        for occ in ({"state": "OBSERVED_NONEMPTY", "value": -1, "sources": []},
                    {"state": "OBSERVED_NONEMPTY", "value": "many", "sources": []},
                    {"state": "OBSERVED_NONEMPTY", "value": None, "sources": []},
                    {"state": "OBSERVED_EMPTY", "value": 3, "sources": []},
                    7):
            bad = copy.deepcopy(receipt)
            bad["fingerprints"][0]["occurrences"] = occ
            with self.subTest(occ=occ), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(bad, SCHEMA)

    @needs_jsonschema
    def test_schema_rejects_closed_root_without_id(self):
        _, receipt, _ = build()
        bad = copy.deepcopy(receipt)
        bad["fingerprints"][0]["closed"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA)


if __name__ == "__main__":
    unittest.main(verbosity=1)
