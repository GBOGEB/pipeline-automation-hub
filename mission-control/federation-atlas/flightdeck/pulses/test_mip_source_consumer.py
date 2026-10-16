"""Adversarial contract tests for the read-only MIP consumer."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mip_source_consumer import consume, main


SHA = "a" * 40
DIGEST = "b" * 64
OUTCOMES = ("success", "failure", "neutral", "cancelled", "skipped",
            "timed_out", "action_required", "stale", "startup_failure")


def inputs():
    outcome = {x: 0 for x in OUTCOMES}
    outcome["success"] = 17
    outcome["failure"] = 3
    return ({
        "schema": "code-purple.mip-input-binding.v1",
        "repository": "GBOGEB/ABACUS",
        "head_sha": SHA,
        "producer_path": "tools/mip_ci_wave_telemetry.py",
        "producer_sha256": DIGEST,
        "artifact_bytes_authenticated": False,
        "authority_transfer": False,
    }, {
        "schema": "abacus.mip.ci-wave-telemetry.v2",
        "repository": "GBOGEB/ABACUS",
        "source_sha": SHA,
        "workflow_terminal_by_outcome": outcome,
        "workflow_records_observed": 20,
        "workflow_nonterminal": 0,
        "workflow_unclassified": 0,
        "queue_source_counts": {
            "job_created_at": 19,
            "workflow_run_created_at_fallback": 1,
        },
        "queue_samples": 20,
        "queue_seconds_p95": 95,
        "first_red_unique_signatures": 1,
        "first_red_repeated_signatures": 0,
        "first_red_manifestations": [{
            "fingerprint": "c" * 64, "job_id": 7,
        }],
        "first_red_signatures": [{
            "fingerprint": "c" * 64, "manifestations": 1,
            "workflow_path": "ci.yml", "job_name": "suite",
            "step_name": "pytest", "step_number": 3,
        }],
        "red_jobs_without_attributed_first_step": 2,
        "first_red_causal_roots_verified": None,
        "independent_process_observations": None,
        "merge_authorized": False,
        "authority_transfer": False,
        "security_waiver": False,
    })


class ConsumerTests(unittest.TestCase):
    def test_descriptive_rates_and_statistical_hold(self):
        binding, producer = inputs()
        result = consume(binding, producer)
        self.assertEqual(result["observed"]["workflow_success_n"], 17)
        self.assertEqual(result["observed"]["workflow_total_n"], 20)
        self.assertEqual(result["observed"]["workflow_success_fraction_descriptive"], .85)
        self.assertEqual(result["observed"]["queue_fallback_n"], 1)
        self.assertIsNone(result["observed"]["queue_cross_wave_comparable"])
        self.assertEqual(set(result["confidence_intervals"]), {"90", "95", "99"})
        self.assertTrue(all(x["estimate"] is None for x in
                            result["confidence_intervals"].values()))
        self.assertEqual(result["methods"]["pca"],
                         "HOLD_N_INDEPENDENT_AND_STABLE_COVARIANCE")
        self.assertFalse(result["root_register_created"])
        self.assertEqual(result["admission"], "HOLD")

    def test_pending_never_divided_into_final_success(self):
        b, p = inputs()
        p["workflow_records_observed"] = 21
        p["workflow_nonterminal"] = 1
        self.assertIsNone(consume(b, p)["observed"][
            "workflow_success_fraction_descriptive"])

    def test_reject_cross_sha_and_fake_governance(self):
        for mutate in (
            lambda b, p: p.update(source_sha="d" * 40),
            lambda b, p: p.update(merge_authorized=True),
            lambda b, p: b.update(authority_transfer=True),
            lambda b, p: p.update(first_red_causal_roots_verified=1),
            lambda b, p: p.update(independent_process_observations=20),
        ):
            b, p = inputs()
            mutate(b, p)
            with self.assertRaises(ValueError):
                consume(b, p)

    def test_reject_false_denominators(self):
        for mutate in (
            lambda p: p.update(workflow_records_observed=19),
            lambda p: p["queue_source_counts"].update(job_created_at=20),
            lambda p: p.update(first_red_repeated_signatures=1),
            lambda p: p.update(first_red_unique_signatures=2),
            lambda p: p["first_red_signatures"].append(
                copy.deepcopy(p["first_red_signatures"][0])),
            lambda p: p["workflow_terminal_by_outcome"].update(success=True),
        ):
            b, p = inputs()
            mutate(p)
            with self.assertRaises(ValueError):
                consume(b, p)

    def test_cli_matches_exact_source_bytes_and_refuses_alias(self):
        b, p = inputs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source.json"
            binding = root / "binding.json"
            target = root / "projection.json"
            raw = json.dumps(p, sort_keys=True).encode()
            src.write_bytes(raw)
            b["producer_sha256"] = hashlib.sha256(raw).hexdigest()
            binding.write_text(json.dumps(b))
            self.assertEqual(main(["--binding", str(binding), "--producer",
                                   str(src), "--out", str(target)]), 0)
            self.assertEqual(json.loads(target.read_text())["admission"], "HOLD")
            with self.assertRaises(ValueError):
                main(["--binding", str(binding), "--producer",
                      str(src), "--out", str(src)])
            src.write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "digest"):
                main(["--binding", str(binding), "--producer",
                      str(src), "--out", str(target)])


if __name__ == "__main__":
    unittest.main()
