#!/usr/bin/env python3
"""Adversarial contract tests for Section 10 native BIOS/Top21 consumer."""
import copy
import hashlib
import json
import unittest
from section10_consumer import consume, canonical

S = "a" * 40
R = "GBOGEB/pipeline-automation-hub"
BIOS = {
    "schema": "jade.repo-bios.source-report.v1",
    "authority": "SOURCE_INVENTORY_ONLY",
    "merge_authorized": False,
    "release_authorized": False,
    "repositories": [{
        "repository": R, "source_sha": S, "tree_oid": "b" * 40,
        "runtime_kpis": {"state": "UNKNOWN"}
    }]
}
O = {
    "schema": "jade.portfolio-observation.v1",
    "repos": [{"repo": R, "private": False, "head_sha": "c" * 40}] +
             [{"repo": f"GBOGEB/test{i:02d}", "private": False,
               "head_sha": "d" * 40} for i in range(19)] +
             [{"repo": "GBOGEB/private-example", "private": True, "head_sha": None}]
}

def make_receipt(observation):
    return {
        "schema": "jade.portfolio-census-bridge.v1",
        "source_schema": "jade.devops.census.v1",
        "merge_admission": "HOLD",
        "authority_transfer": False,
        "dispatch_performed": False,
        "observation_sha256": hashlib.sha256(canonical(observation)).hexdigest(),
        "source_digest_sha256": "f" * 64,
        "source_repos": 21,
        "private_rows_masked": 1,
        "native_check_population": None,
        "qualified_current_point_release": None,
        "observed_at_utc": "2026-10-25T00:00:00Z",
    }

class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.b = copy.deepcopy(BIOS)
        self.o = copy.deepcopy(O)
        self.r = make_receipt(self.o)

    def run_consumer(self):
        return consume(self.b, self.o, self.r, S)

    def reject(self, reason):
        with self.assertRaisesRegex(ValueError, reason):
            self.run_consumer()

    def test_success_is_source_only(self):
        x = self.run_consumer()
        self.assertEqual(x["qualification"], "NATIVE_INPUT_VALIDATED_SOURCE_ONLY")
        self.assertEqual(x["top21_count"], 21)
        self.assertEqual(x["private_rows_masked"], 1)
        self.assertEqual(x["merge_admission"], "HOLD")
        self.assertIsNone(x["current_native_check_population"])

    def test_expected_sha_mismatch(self):
        with self.assertRaisesRegex(ValueError, "BIOS_NOT_EXACT_HEAD"):
            consume(self.b, self.o, self.r, "e" * 40)

    def test_bios_schema(self):
        self.b["schema"] = "wrong"; self.reject("BIOS_SCHEMA")

    def test_bios_unauthorized_release(self):
        self.b["release_authorized"] = True; self.reject("BIOS_AUTHORITY")

    def test_duplicate_bios(self):
        self.b["repositories"].append(copy.deepcopy(self.b["repositories"][0]))
        self.reject("BIOS_REPO_ID")

    def test_bios_invalid_tree(self):
        self.b["repositories"][0]["tree_oid"] = "x"; self.reject("BIOS_TREE")

    def test_bios_runtime_false_green(self):
        self.b["repositories"][0]["runtime_kpis"]["state"] = "PASS"
        self.reject("BIOS_RUNTIME")

    def test_top21_tamper(self):
        self.o["repos"][0]["head_sha"] = "e" * 40; self.reject("TOP21_DIGEST")

    def test_top21_unauthorized_admission(self):
        self.r["merge_admission"] = "ADMITTED"; self.reject("TOP21_AUTHORITY")

    def test_top21_duplicate(self):
        self.o["repos"][1]["repo"] = R
        self.r = make_receipt(self.o)
        self.reject("TOP21_REPO_ID")

    def test_top21_private_leak(self):
        self.o["repos"][-1]["head_sha"] = "a" * 40
        self.r = make_receipt(self.o)
        self.reject("TOP21_PRIVATE_LEAK")

    def test_top21_partial_population(self):
        self.o["repos"].pop()
        self.r = make_receipt(self.o)
        self.reject("TOP21_POPULATION")

    def test_top21_misreported_private_count(self):
        self.r["private_rows_masked"] = 0
        self.reject("TOP21_PRIVATE_COUNT")

    def test_top21_native_false_green(self):
        self.r["native_check_population"] = 100
        self.reject("TOP21_FALSE_NATIVE")

    def test_top21_bad_source_digest(self):
        self.r["source_digest_sha256"] = "wrong"
        self.reject("TOP21_SOURCE_DIGEST")

    def test_no_release_authority_in_result(self):
        self.assertIs(self.run_consumer()["release_authorized"], False)

if __name__ == "__main__":
    unittest.main()
