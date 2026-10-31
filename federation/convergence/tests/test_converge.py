"""Negative / fail-closed tests for the convergence reducer.

Run from the repository root: python -m pytest federation/convergence/tests
"""
import copy
import hashlib
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


ADDENDUM = converge.REPO_ROOT / "federation" / "convergence" / "evidence" / "20261025" / \
    "C18_ABACUS_2367_SUPERSESSION_20261025.json"
OLD_RECEIPT = EVIDENCE / "CODE_PURPLE_SCALED_CONVERGENCE_20261022.json"
OLD_RECEIPT_SHA256 = "4d6eda634a13852f8c6517e96fe0714540dd52f1cb83ba3b97dea8cf3433a79b"
NEW_RECEIPT = ADDENDUM.with_name("CODE_PURPLE_SCALED_CONVERGENCE_20261025.json")


class C18Supersession(unittest.TestCase):
    """W2 / C18: a supersession record keyed by item id resolves C18 only with exact-SHA evidence."""

    def run_c18(self, resolutions):
        data, _ = converge.load(EVIDENCE)
        events = converge.normalise_events(data)
        return next(c for c in converge.crosschecks(data, events, resolutions) if c["id"] == converge.C18_ID)

    def record(self):
        resolutions, _ = converge.load_resolutions(ADDENDUM)
        return copy.deepcopy(resolutions)

    def test_with_addendum_c18_superseded(self):
        c = self.run_c18(self.record())
        self.assertEqual(c["resolution"], "SUPERSEDED")
        self.assertIn(c["result"], ("PASS", "WARN"))
        self.assertNotIn("resolution_rejected", c)
        ev = c["resolution_evidence"]
        self.assertEqual((ev["old_head_sha"], ev["new_head_sha"], ev["merge_commit_sha"]),
                         ("301960e92b12e687d6fe0245bf550d6b8ebb7cae", "15dd7b73553e431e9e84c857eb19d3a4070b80b3",
                          "94a3c281e947dba8aed85a831a67ffc55309080a"))
        self.assertEqual(ev["run_head_sha"], ev["old_head_sha"])

    def test_failed_checks_keep_warn_not_pass(self):
        c = self.run_c18(self.record())
        self.assertGreater(c["resolution_evidence"]["checks_failed"], 0)
        self.assertEqual(c["result"], "WARN")

    def test_without_addendum_c18_fails(self):
        for resolutions in (None, {}):
            c = self.run_c18(resolutions)
            self.assertEqual(c["result"], "FAIL")
            self.assertNotIn("resolution", c)

    def assert_rejected(self, mutate):
        rec = self.record()
        mutate(rec[converge.C18_ID])
        c = self.run_c18(rec)
        self.assertEqual(c["result"], "FAIL")
        self.assertNotIn("resolution", c)
        self.assertTrue(c["resolution_rejected"])
        return c["resolution_rejected"]

    def test_prefix_only_sha_rejected(self):
        def mutate(r):
            r["old_head"]["sha"] = "301960e92b12"
        self.assertTrue(any("40-hex" in e for e in self.assert_rejected(mutate)))

    def test_prefix_only_new_head_rejected(self):
        def mutate(r):
            r["new_head"]["sha"] = r["new_head"]["sha"][:12]
        self.assert_rejected(mutate)

    def test_mismatched_old_head_rejected(self):
        def mutate(r):
            r["old_head"]["sha"] = "0" * 40
        self.assertTrue(any("reported prefix" in e for e in self.assert_rejected(mutate)))

    def test_run_on_other_head_rejected(self):
        def mutate(r):
            r["run"]["head_sha"] = "f" * 40
        self.assert_rejected(mutate)

    def test_merge_without_new_head_parent_rejected(self):
        def mutate(r):
            r["merge_commit"]["parents"] = ["a" * 40]
        self.assert_rejected(mutate)

    def test_not_ancestor_rejected(self):
        def mutate(r):
            r["ancestry"]["behind_by"] = 3
        self.assert_rejected(mutate)

    def test_inconsistent_check_counts_rejected(self):
        def mutate(r):
            r["checks_at_new_head"]["failed"] = 9
        self.assert_rejected(mutate)

    def test_pass_only_when_failures_shown_non_required_and_unrelated(self):
        rec = self.record()
        chk = rec[converge.C18_ID]["checks_at_new_head"]
        chk["failed_preexisting_on_base_parent"] += chk["failed_not_shown_unrelated"]
        chk["failed_not_shown_unrelated"] = []
        self.assertEqual(self.run_c18(rec)["result"], "PASS")
        # unknown required set is NOT_OBSERVED, never "none required"
        chk.pop("required_checks")
        self.assertEqual(self.run_c18(rec)["result"], "WARN")
        # missing unrelated list is UNKNOWN, not an empty list
        rec2 = self.record()
        rec2[converge.C18_ID]["checks_at_new_head"].pop("failed_not_shown_unrelated")
        self.assertEqual(self.run_c18(rec2)["result"], "WARN")

    def test_wrong_authority_addendum_refused(self):
        import tempfile
        from pathlib import Path
        doc = json.loads(ADDENDUM.read_text(encoding="utf-8"))
        doc["authority"] = "CHAT_TRANSCRIPT_UNVERIFIED"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                converge.load_resolutions(p)

    @needs_jsonschema
    def test_schema_valid_with_and_without_resolution(self):
        for resolutions in (None, self.record()):
            data, manifest = converge.load(EVIDENCE)
            events = converge.normalise_events(data)
            checks = converge.crosschecks(data, events, resolutions)
            jsonschema.validate(converge.reduce(data, manifest, checks, events), SCHEMA)

    @needs_jsonschema
    def test_schema_rejects_superseded_fail(self):
        receipt = json.loads(NEW_RECEIPT.read_text(encoding="utf-8"))
        jsonschema.validate(receipt, SCHEMA)
        c18 = next(c for c in receipt["crosschecks"] if c["id"] == converge.C18_ID)
        c18["result"] = "FAIL"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(receipt, SCHEMA)


class Receipts(unittest.TestCase):
    def test_old_receipt_byte_identical(self):
        raw = OLD_RECEIPT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), OLD_RECEIPT_SHA256)
        sidecar = OLD_RECEIPT.with_name(OLD_RECEIPT.name + ".sha256").read_text(encoding="utf-8")
        self.assertEqual(sidecar, f"{OLD_RECEIPT_SHA256}  {OLD_RECEIPT.name}\n")

    def test_no_addendum_reproduces_old_receipt_bytes(self):
        old = json.loads(OLD_RECEIPT.read_text(encoding="utf-8"))
        _, receipt, _ = build()
        receipt["generated_utc"] = old["generated_utc"]
        body = json.dumps(receipt, indent=2, sort_keys=False) + "\n"
        self.assertEqual(body.encode("utf-8"), OLD_RECEIPT.read_bytes())

    def test_new_receipt_sidecar_and_input_digest(self):
        raw = NEW_RECEIPT.read_bytes()
        self.assertNotIn(b"\r\n", raw)
        sidecar = NEW_RECEIPT.with_name(NEW_RECEIPT.name + ".sha256").read_text(encoding="utf-8")
        self.assertEqual(sidecar, f"{hashlib.sha256(raw).hexdigest()}  {NEW_RECEIPT.name}\n")
        entry = json.loads(raw)["inputs"][-1]
        self.assertEqual(entry["sha256"], hashlib.sha256(ADDENDUM.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=1)


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
