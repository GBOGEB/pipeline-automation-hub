"""Source/guard adversarial tests for the federation exact-head rollup."""
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "exact_head_receipts", HERE / "exact_head_receipts.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
SHA = "a" * 40
DIGEST = "b" * 64


def fixture():
    return {
        "schema": mod.SCHEMA,
        "classification": "OBSERVED_GITHUB_READBACK_NOT_OWNER_ACCEPTANCE",
        "observed_at": "2026-10-26T16:00:00Z",
        "observations": [
            {
                "repository": repo, "head_sha": SHA, "source_sha": SHA,
                "run_id": 100 + i, "run_attempt": 1, "conclusion": "SUCCESS",
                "security": "SUCCESS", "independent_review": "VERIFIED",
                "red_canary_blocked": True, "artifact_sha256": DIGEST,
                "owner_accepted": False, "override": False,
            }
            for i, repo in enumerate(mod.REPOS)
        ],
    }


class ReceiptContract(unittest.TestCase):
    def reject(self, mutate):
        data = fixture()
        mutate(data)
        with self.assertRaises(ValueError):
            mod.validate(data)

    def test_complete_success_is_only_a_candidate_not_owner_acceptance(self):
        result = mod.validate(fixture())
        self.assertEqual(result["repos_count"], 5)
        self.assertEqual(result["merge_admission"], "CANDIDATE_FOR_INDEPENDENT_QUALIFICATION")
        self.assertFalse(result["automatic_merge_authorized"])
        self.assertEqual(result["qps_engineering_acceptance"], "UNKNOWN")

    def test_red_and_unknown_fail_closed(self):
        data = fixture()
        data["observations"][0]["conclusion"] = "FAILURE"
        data["observations"][1]["security"] = "UNKNOWN"
        result = mod.validate(data)
        self.assertEqual(result["merge_admission"], "HOLD")
        self.assertEqual(result["red"], 1)
        self.assertEqual(len(result["blocked_repositories"]), 2)

    def test_duplicate_repo(self):
        self.reject(lambda d: d["observations"][0].update(
            repository=d["observations"][1]["repository"]
        ))

    def test_unmatched_head(self):
        self.reject(lambda d: d["observations"][0].update(source_sha="f" * 40))

    def test_no_native_run_id(self):
        self.reject(lambda d: d["observations"][0].update(run_id=None))

    def test_digest_and_review_missing(self):
        data = fixture()
        data["observations"][0]["artifact_sha256"] = None
        data["observations"][0]["independent_review"] = "NOT_VERIFIED"
        self.assertEqual(mod.validate(data)["merge_admission"], "HOLD")

    def test_no_owner_promotion(self):
        self.reject(lambda d: d["observations"][0].update(owner_accepted=True))

    def test_no_override(self):
        self.reject(lambda d: d["observations"][0].update(override=True))

    def test_bool_is_not_a_native_run_identifier(self):
        self.reject(lambda d: d["observations"][0].update(run_id=True))

    def test_observation_must_be_utc(self):
        self.reject(lambda d: d.update(observed_at="2026-10-26 16:00"))


if __name__ == "__main__":
    unittest.main()
