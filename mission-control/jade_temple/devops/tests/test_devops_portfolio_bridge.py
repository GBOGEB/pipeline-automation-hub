"""Contract and negative tests for the JADE weekly portfolio census bridge."""
from __future__ import annotations

import hashlib
import fnmatch
import importlib.util
import json
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "portfolio_readiness" / "census_bridge.py"
SPEC = importlib.util.spec_from_file_location("jade_portfolio_census_bridge", SOURCE)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
PRODUCER_SOURCE = SOURCE.parents[1] / "devops" / "census.py"
PRODUCER_SPEC = importlib.util.spec_from_file_location("bridge_producer_oracle", PRODUCER_SOURCE)
producer = importlib.util.module_from_spec(PRODUCER_SPEC)
PRODUCER_SPEC.loader.exec_module(producer)


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
    census["digest_sha256"] = hashlib.sha256(producer.canonical(body)).hexdigest()


class PortfolioCensusBridgeTest(unittest.TestCase):
    def test_finite_unicode_bytes_match_the_actual_producer(self):
        value = {"unicode": ["é", "λ"], "nested": {"float": -0.0, "null": None}}
        self.assertEqual(bridge.canonical(value), producer.canonical(value))
        census, reg = fixture()
        census["producer_metadata"] = value
        sign(census)
        model, _ = bridge.convert(census, reg)
        self.assertEqual(len(model["repos"]), 3)

    def test_nonfinite_source_values_are_rejected_even_with_a_producer_digest(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                census, reg = fixture()
                census["producer_metadata"] = value
                sign(census)
                with self.assertRaisesRegex(ValueError, "^PORTFOLIO_INPUT: NONFINITE_OR_INVALID_JSON"):
                    bridge.convert(census, reg)

    def test_bridge_uses_the_owner_error_prefix(self):
        census, reg = fixture()
        census["repos"][0]["head_sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "^PORTFOLIO_INPUT: SOURCE_CENSUS_DIGEST_DRIFT"):
            bridge.convert(census, reg)

    def test_invalid_timestamp_keeps_the_owner_error_prefix(self):
        with self.assertRaisesRegex(ValueError, "^PORTFOLIO_INPUT: BAD_TIMESTAMP"):
            bridge.utc_stamp("not-a-time")

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
        for source in (PRODUCER_SOURCE, PRODUCER_SOURCE.with_name("workflows.py")):
            key = "mission-control/jade_temple/devops/" + source.name
            self.assertEqual(source_hashes[key]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())


class BridgeWorkflowContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = SOURCE.parents[3] / ".github/workflows/jade-devops-census.yml"
        cls.doc = producer.W.yaml.safe_load(workflow.read_text(encoding="utf-8"))

    def test_bridge_only_changes_trigger_the_real_offline_suite(self):
        events = self.doc.get("on", self.doc.get(True))
        bridge_path = "mission-control/jade_temple/portfolio_readiness/census_bridge.py"
        for event in ("pull_request", "push"):
            self.assertTrue(any(fnmatch.fnmatchcase(bridge_path, p) for p in events[event]["paths"]))
        commands = "\n".join(s.get("run", "") for s in self.doc["jobs"]["offline"]["steps"])
        self.assertIn("test_devops_*.py", commands)
        self.assertTrue(fnmatch.fnmatchcase(Path(__file__).name, "test_devops_*.py"))
        self.assertIn("CANONICAL_21_REPO_BRIDGE=PASS", commands)

    def test_failed_projection_cannot_hide_required_census_artifacts(self):
        steps = self.doc["jobs"]["refresh"]["steps"]
        uploads = [s for s in steps if "actions/upload-artifact@" in s.get("uses", "")]
        required = next(s for s in uploads if s["with"]["name"].startswith("jade-devops-census-fresh-"))
        optional = next(s for s in uploads if s["with"]["name"].startswith("jade-portfolio-projection-"))
        self.assertEqual(required["if"], "always()")
        self.assertEqual(required["with"]["if-no-files-found"], "error")
        self.assertEqual(optional["if"], "always()")
        self.assertEqual(optional["with"]["if-no-files-found"], "warn")
        guard = next(s for s in steps if s.get("name") == "Verify required census outputs if collection succeeded")
        self.assertIn("always()", guard["if"])
        self.assertIn("steps.fetch_census.outcome == 'success'", guard["if"])
        for filename in ("DEVOPS_CENSUS_FRESH.json", "DEVOPS_OBJECTS_FRESH.json", "fetch.jsonl"):
            self.assertIn('test -s "$RUNNER_TEMP/' + filename + '"', guard["run"])


if __name__ == "__main__":
    unittest.main()
