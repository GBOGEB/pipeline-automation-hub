"""Static contract and source-custody checks for additive gg_MATH projection."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "mission-control/v2/handoff/G3P_GGMATH_OBSERVED_CROSSWALK_20261017.json"
PAGE = ROOT / "docs/mission-control/g3p-math/index.html"


class G3PMathProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_contract_source_pinned(self):
        r = self.ref
        self.assertEqual(r["schema"],
                         "missioncontrol.ggmath.observed_projection_crosswalk.v1")
        for field in ("consumer_base_sha", "provider_candidate_head_sha",
                      "provider_data_blob_sha"):
            self.assertRegex(r[field], r"^[0-9a-f]{40}$")
        self.assertEqual(r["provider_repo"], "GBOGEB/gg_MATH")
        self.assertEqual(r["source_repo"], "GBOGEB/ABACUS")

    def test_no_authority_or_current_head_promotion(self):
        self.assertEqual(self.ref["merge_admission"], "HOLD")
        self.assertIs(self.ref["authority_transfer"], False)
        self.assertIsNone(self.ref["accepted_n_advances"])
        self.assertEqual(self.ref["qps_engineering_acceptance"], "NOT_ATTESTED")
        self.assertIn("STATIC_READ_ONLY", self.ref["projection_kind"])

    def test_provider_source_handoff_is_additive(self):
        self.assertEqual(self.ref["provider_pr"], 64)
        self.assertEqual(self.ref["provider_data_path"],
                         "mission/federation/G3P_OBSERVED_20261017.json")
        self.assertEqual(len(self.ref["observed_cohorts"]), 3)
        self.assertIn("SOURCE_BOUND_UNVERIFIED_RECEIPTS",
                      self.page)

    def test_four_real_plotly_card_containers(self):
        for ident in ("black", "isort", "coverage", "sigma"):
            self.assertIn('id="plot-' + ident + '"', self.page)
        self.assertIn("Plotly.newPlot", self.page)
        self.assertIn("Plotly.purge", self.page)
        self.assertIn("showModal()", self.page)
        self.assertIn("cdn.plot.ly/plotly-2.35.2.min.js", self.page)

    def test_matched_source_numerators(self):
        for fragment in ("52/68 → 68/68 → 68/68",
                         "62/68 → 68/68", "170/172 → 170/172",
                         "Statements 129/130, branches 41/42"):
            self.assertIn(fragment, self.page)
        self.assertIn("y:[100*52/68,100,100]", self.page)
        self.assertIn("y:[100*170/172,100*170/172]", self.page)

    def test_github_job_receipts_not_fictitious(self):
        self.assertIn("39058917892/job/117472645051", self.page)
        self.assertIn("39060875900/job/117478395057", self.page)
        self.assertIn("39061028603/job/117478847332", self.page)
        self.assertIn("issuecomment-6239719163", self.page)

    def test_no_false_pca_bt_six_sigma(self):
        for phrase in ("PCA", "Bradley", "Six Sigma",
                       "NOT_QUALIFIED", "INSUFFICIENT_TEMPORAL_DEPTH",
                       "BLOCKED_UNTIL_OWNER_EVIDENCE",
                       "three successive within-tolerance"):
            self.assertIn(phrase, self.page)
        self.assertIn("independent Bernoulli opportunities", self.page)

    def test_source_scope_is_not_global(self):
        self.assertIn("historical ABACUS PR-head evidence", self.page)
        self.assertIn("not current-main accepted N advances", self.page)
        self.assertIn("no independent", self.page.lower())
        self.assertNotIn("engineering acceptance PASS", self.page)

    def test_durable_fallback_on_external_plotly_unavailable(self):
        self.assertGreaterEqual(self.page.count('class="fallback"'), 4)
        self.assertIn("if(!window.Plotly||plotted)return", self.page)
        self.assertIn('data-plotly="UNAVAILABLE"', self.page.replace(
            'document.body.dataset.plotly="UNAVAILABLE"', 'data-plotly="UNAVAILABLE"'
        ))
        self.assertIn("Math.exp(Math.log(.05)/n)", self.page)

    def test_csp_and_link_boundaries(self):
        self.assertIn('http-equiv="Content-Security-Policy"', self.page)
        self.assertIn("connect-src 'none'", self.page)
        self.assertEqual(len(re.findall(r'<script src=', self.page)), 1)
        self.assertNotIn("http://", self.page)

    def test_cards_have_working_data_keys(self):
        buttons = re.findall(r'data-expand="([a-z]+)"', self.page)
        self.assertEqual(buttons, ["black", "isort", "coverage"])
        for key in buttons:
            self.assertRegex(self.page, r"(?m)^" + key + r":\{x:")
        self.assertIn('id="close-detail"', self.page)

    def test_not_main_readiness_contract(self):
        self.assertNotEqual(self.ref["consumer_base_sha"],
                            self.ref["provider_candidate_head_sha"])
        self.assertIn("source mutations", self.page)


if __name__ == "__main__":
    unittest.main()
