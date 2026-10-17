"""MissionControl gg_MATH exact-source bridge: negative and provenance cases."""
import copy
import json
import unittest
from pathlib import Path

from gg_math_convergence_consumer import render, validate_bridge

ROOT=Path(__file__).resolve().parent
SOURCE=json.loads((ROOT/"GG_MATH_CONVERGENCE_BRIDGE_v1.json").read_text(encoding="utf-8"))


class MathConvergenceConsumerTests(unittest.TestCase):
    def test_valid_opaque_bridge_and_source_link(self):
        r=render(SOURCE)
        c=r["consumer"]
        self.assertEqual(c["provider_repo"],"GBOGEB/gg_MATH")
        self.assertIn(SOURCE["provider"]["merge_commit_sha"],c["provider_source_url"])
        self.assertEqual(c["live_pulse_receipts_ingested"],0)
        self.assertEqual(c["merge_admission"],"HOLD")

    def reject(self,change):
        bad=copy.deepcopy(SOURCE)
        change(bad)
        with self.assertRaises(ValueError):validate_bridge(bad)

    def test_source_sha_malformed(self):
        self.reject(lambda d:d["provider"].update(merge_commit_sha="SHORT"))

    def test_source_repo_mismatch(self):
        self.reject(lambda d:d["provider"].update(repo="GBOGEB/ABACUS"))

    def test_claimed_native_pass_without_receipt(self):
        self.reject(lambda d:d["provider"].update(native_terminal_verified=True))

    def test_claimed_pages_url_forbidden(self):
        self.reject(lambda d:d["consumer"].update(published_pages_url="https://example.com/fake"))

    def test_claimed_hosted_http_forbidden(self):
        self.reject(lambda d:d["consumer"].update(hosted_http_verified=True))

    def test_synthetic_promoted_as_live_forbidden(self):
        self.reject(lambda d:d["method"].update(evidence_class="LIVE_PRODUCTION"))

    def test_false_six_sigma_forbidden(self):
        self.reject(lambda d:d["method"].update(six_sigma_attested=True))

    def test_false_bt_stability_forbidden(self):
        self.reject(lambda d:d["method"].update(bt_stable_certified=True))

    def test_false_pca_stability_forbidden(self):
        self.reject(lambda d:d["method"].update(pca_temporal_certified=True))

    def test_false_qps_acceptance_forbidden(self):
        self.reject(lambda d:d["controls"].update(qps_acceptance=True))

    def test_false_merge_go_forbidden(self):
        self.reject(lambda d:d["controls"].update(merge_admission="GO"))

    def test_new_kpi_registry_forbidden(self):
        self.reject(lambda d:d["controls"].update(new_global_kpi_registry=True))

    def test_source_provenance_nonatomic(self):
        self.reject(lambda d:d.update(snapshot_atomic=True))

    def test_live_receipt_cannot_be_inferred_from_fixture(self):
        self.reject(lambda d:d["method"].update(live_pulse_receipts_ingested=1))

    def test_forged_native_consumer_qa_forbidden(self):
        self.reject(lambda d:d["consumer"].update(native_consumer_qa="PASS"))

    def test_bridge_digest_repeatable(self):
        self.assertEqual(render(SOURCE),render(SOURCE))

    def test_provider_does_not_grant_security_waiver(self):
        self.reject(lambda d:d["controls"].update(security_waiver=True))


if __name__=="__main__":
    unittest.main()
