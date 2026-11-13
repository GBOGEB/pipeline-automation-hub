"""Contract and negative tests for the JADE weekly portfolio census bridge."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "portfolio_readiness" / "census_bridge.py"
SPEC = importlib.util.spec_from_file_location("jade_portfolio_census_bridge", SOURCE)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def fixture():
    obj = {
        "schema": "jade.devops.census.v1",
        "observed_at_utc": "2026-11-09T09:30:00Z",
        "repos": [
            {"repo": "GBOGEB/pipeline-automation-hub", "reachable": True,
             "branch": "master", "head_sha": "a" * 40},
            {"repo": "GBOGEB/cryoplant-project", "reachable": True,
             "branch": "main", "head_sha": "PRIVATE_AGGREGATE_ONLY"},
            {"repo": "GBOGEB/GEMINI", "reachable": False,
             "branch": "main", "head_sha": None},
        ],
    }
    sign(obj)
    return obj, {"private_repos": ["GBOGEB/cryoplant-project"]}


def sign(census):
    body = {k: v for k, v in census.items() if k != "digest_sha256"}
    census["digest_sha256"] = hashlib.sha256(bridge.canonical(body)).hexdigest()


class PortfolioCensusBridgeTest(unittest.TestCase):
    def test_structural_projection_holds_release_and_closure(self):
        census, reg = fixture()
        model, rec = bridge.convert(census, reg, 3)
        self.assertEqual(model["schema"], "jade.portfolio-observation.v1")
        self.assertEqual(len(model["repos"]), 3)
        self.assertEqual(rec["source_repos"], 3)
        self.assertIsNone(rec["native_check_population"])
        self.assertIsNone(rec["qualified_current_point_release"])
        self.assertIsNone(rec["weighted_root_closure"])
        self.assertEqual(rec["merge_admission"], "HOLD")

    def test_private_identifiers_not_serialized(self):
        census, reg = fixture()
        model, _ = bridge.convert(census, reg)
        raw = json.dumps(model)
        self.assertNotIn("PRIVATE_AGGREGATE_ONLY", raw)
        self.assertEqual(model["repos"][1], {
            "repo": "GBOGEB/cryoplant-project", "private": True,
            "head_sha": None,
        })
        self.assertNotIn("cryoplant-project/commit/", raw)

    def test_no_fabricated_check_success(self):
        census, reg = fixture()
        model, _ = bridge.convert(census, reg)
        self.assertIsNone(model["repos"][0]["check_counts"])
        self.assertIs(model["repos"][0]["check_collection_complete"], False)
        self.assertEqual(model["frontier"][0]["status"], "NOT_REQUALIFIED")

    def test_digest_mismatch_rejected(self):
        census, reg = fixture()
        census["repos"][0]["head_sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "SOURCE_CENSUS_DIGEST_DRIFT"):
            bridge.convert(census, reg)

    def test_duplicate_repo_rejected(self):
        census, reg = fixture()
        census["repos"].append(dict(census["repos"][0]))
        sign(census)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REPO"):
            bridge.convert(census, reg)

    def test_bad_public_head_rejected(self):
        census, reg = fixture()
        census["repos"][0]["head_sha"] = "PRIVATE_AGGREGATE_ONLY"
        sign(census)
        with self.assertRaisesRegex(ValueError, "INVALID_PUBLIC_HEAD"):
            bridge.convert(census, reg)

    def test_population_floor_rejected(self):
        census, reg = fixture()
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_DECLARED_POPULATION"):
            bridge.convert(census, reg, 21)

    def test_unreachable_head_unknown(self):
        census, reg = fixture()
        model, _ = bridge.convert(census, reg)
        self.assertIsNone(model["repos"][2]["head_sha"])
        self.assertEqual(model["frontier"][-1]["state"], "UNREACHABLE")

    def test_naive_timestamp_rejected(self):
        census, reg = fixture()
        census["observed_at_utc"] = "2026-11-09T09:30:00"
        sign(census)
        with self.assertRaisesRegex(ValueError, "NAIVE_TIMESTAMP"):
            bridge.convert(census, reg)

    def test_private_registry_required(self):
        census, _ = fixture()
        with self.assertRaisesRegex(ValueError, "NO_CANONICAL_PRIVATE_REGISTRY"):
            bridge.convert(census, {})

    def test_branch_unsafe_rejected(self):
        census, reg = fixture()
        census["repos"][0]["branch"] = "../../master"
        sign(census)
        with self.assertRaisesRegex(ValueError, "INVALID_BRANCH"):
            bridge.convert(census, reg)


    def test_public_artifact_records_actual_bridge_source_hash(self):
        spec = importlib.util.spec_from_file_location(
            "jade_portfolio_readiness_lineage", SOURCE.parent / "portfolio_readiness.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source_hashes = module.source_hashes(module.JADE)
        key = "mission-control/jade_temple/portfolio_readiness/census_bridge.py"
        self.assertIn(key, source_hashes)
        self.assertEqual(source_hashes[key]["sha256"],
                         hashlib.sha256(SOURCE.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
