"""G0 tests: negative controls must refuse forged evidence and admission."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gogreen_spine", ROOT / "spine.py")
spine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spine)


def fixture():
    return json.loads((ROOT / "samples" / "fleet_g0.json").read_text(encoding="utf-8"))


class GreenSpineTests(unittest.TestCase):
    def test_wide_first_counts_and_unknown(self):
        proof, plan, hooks = spine.build(fixture())
        b = proof["breadth"]
        self.assertEqual((6, 42, 1, 1, 41),
                         (b["catalog_repositories"], b["catalog_repo_family_cells"],
                          b["observed_cells"], b["native_green_metadata_observations"],
                          b["not_observed_cells"]))
        self.assertIsNone(b["coverage_gain_percentage_points"])
        self.assertIsNone(b["independent_green_trials"])
        self.assertIsNone(b["stress_capacity"])
        self.assertFalse(proof["merge_authorized"])
        self.assertFalse(plan["execution_authorized"])
        self.assertFalse(hooks["authority_transfer"])
        self.assertTrue(all(not p["dispatch_authorized"] for p in plan["packets"]))

    def test_run_number_eight_not_eight_trials(self):
        p, _, _ = spine.build(fixture())
        self.assertEqual(p["observations"][0]["run_number"], 8)
        self.assertEqual(p["observations"][0]["run_attempt"], 1)
        self.assertIsNone(p["repeatability"][0]["statistically_independent"])
        self.assertEqual(p["repeatability"][0]["distinct_pass_run_ids"], 1)

    def test_provenance_mismatch(self):
        f = fixture(); f["observations"][0]["source_sha"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "exact head"):
            spine.build(f)

    def test_wrong_repo_run_url(self):
        f = fixture(); f["observations"][0]["run_url"] = "https://github.com/GBOGEB/CODEX/actions/runs/38601239666"
        with self.assertRaisesRegex(ValueError, "run URL"):
            spine.build(f)

    def test_nonterminal_success_claim(self):
        f = fixture(); f["observations"][0]["workflow_status"] = "in_progress"
        with self.assertRaisesRegex(ValueError, "nonterminal"):
            spine.build(f)

    def test_test_count_boolean_rejected(self):
        f = fixture(); f["observations"][0]["test_counts"] = {"executed": True, "passed": 1, "failed": 0, "skipped": 0}
        with self.assertRaises(ValueError):
            spine.build(f)

    def test_test_counts_nonreconciling_rejected(self):
        f = fixture(); f["observations"][0]["test_counts"] = {"executed": 9, "passed": 6, "failed": 0, "skipped": 1}
        with self.assertRaisesRegex(ValueError, "denominator"):
            spine.build(f)

    def test_not_verified_archive_not_counted(self):
        f = fixture(); p, _, _ = spine.build(f)
        self.assertEqual(p["breadth"]["native_green_bytes_verified_observations"], 0)
        self.assertFalse(p["observations"][0]["artifact_bytes_verified"])

    def test_unsubstantiated_bytes_claim_rejected(self):
        f = fixture(); f["observations"][0]["artifact"]["bytes_verified"] = True
        with self.assertRaisesRegex(ValueError, "receipt"):
            spine.build(f)

    def test_invalid_artifact_digest_rejected(self):
        f = fixture(); f["observations"][0]["artifact"]["archive_sha256"] = "1234"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            spine.build(f)

    def test_nonreconciling_debt_rejected(self):
        f = fixture(); f["observations"][0]["scoped_burndown"]["after"] = 3
        with self.assertRaisesRegex(ValueError, "nonreconciling"):
            spine.build(f)

    def test_duplicate_attempt_rejected(self):
        f = fixture(); f["observations"].append(copy.deepcopy(f["observations"][0]))
        with self.assertRaisesRegex(ValueError, "duplicated"):
            spine.build(f)

    def test_duplicated_repository_rejected(self):
        f = fixture(); f["repositories"].append(copy.deepcopy(f["repositories"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            spine.build(f)

    def test_empty_observations_unknown_not_zero_green(self):
        f = fixture(); f["observations"] = []
        p, plan, _ = spine.build(f)
        self.assertEqual(p["breadth"]["observed_cells"], 0)
        self.assertEqual(p["breadth"]["not_observed_cells"], 42)
        self.assertIsNone(p["breadth"]["fleet_release_admission"] if False else p["breadth"]["coverage_gain_percentage_points"])
        self.assertEqual(len(plan["packets"]), 42)

    def test_deterministic_output_and_tamper_rejection(self):
        f = fixture()
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a", Path(d) / "b"
            spine.emit(f, a); spine.emit(f, b)
            self.assertEqual(sorted(p.name for p in a.iterdir()), sorted(p.name for p in b.iterdir()))
            for name in list(spine.OUTPUTS) + ["manifest.json"]:
                self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())
            spine.verify_output(a)
            with (a / "evidence.json").open("ab") as h:
                h.write(b"\nFORGED")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                spine.verify_output(a)

    def test_rehashed_forged_child_acceptance_still_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            spine.emit(fixture(), path)
            hook_path = path / "federation_hooks.json"
            hooks = json.loads(hook_path.read_text(encoding="utf-8"))
            hooks["child_acceptance"] = "ACCEPT"
            hook_path.write_text(json.dumps(hooks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest_path = path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["sha256"]["federation_hooks.json"] = hashlib.sha256(hook_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "admission boundary"):
                spine.verify_output(path)

    def test_untrusted_remote_authority_rejected(self):
        f = fixture(); f["repositories"][0]["authority_transfer"] = True
        with self.assertRaisesRegex(ValueError, "authority"):
            spine.build(f)


if __name__ == "__main__":
    unittest.main()
