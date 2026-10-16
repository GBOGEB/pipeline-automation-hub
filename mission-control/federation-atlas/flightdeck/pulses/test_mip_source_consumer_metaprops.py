"""Metamorphic, stress, identity-join, and evidence-file immutability tests.

Fixtures are synthetic and intentionally carry no CI, QPS or security authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from mip_source_consumer import consume, first_red_digest, main
from test_mip_source_consumer import inputs


class MetamorphicConsumerTests(unittest.TestCase):
    def test_repeated_step_is_a_compressed_signature_not_two_roots(self):
        binding, producer = inputs()
        repeated = copy.deepcopy(producer["first_red_manifestations"][0])
        repeated["run_id"], repeated["job_id"] = 22, 8
        producer["first_red_manifestations"].append(repeated)
        producer["first_red_signatures"][0]["manifestations"] = 2
        producer["first_red_repeated_signatures"] = 1
        producer["red_jobs_without_attributed_first_step"] = 1
        result = consume(binding, producer)
        observed = result["observed"]
        self.assertEqual(observed["first_red_unique_signatures"], 1)
        self.assertEqual(observed["first_red_repeated_signatures"], 1)
        self.assertEqual(observed["first_red_manifestations"], 2)
        self.assertEqual(observed["first_red_signature_compression_fraction"], .5)
        self.assertAlmostEqual(observed["first_red_attribution_fraction"], 2 / 3)
        self.assertIsNone(result["accepted_bd_root_closures"])

    def test_order_invariance_of_unordered_native_observations(self):
        binding, p = inputs()
        semantic = {
            "workflow_path": ".github/workflows/other.yml",
            "job_name": "lint", "step_name": "validate", "step_number": 7,
        }
        fingerprint = first_red_digest(semantic)
        p["first_red_signatures"].append({
            "fingerprint": fingerprint, "manifestations": 1, **semantic,
        })
        p["first_red_manifestations"].append({
            "fingerprint": fingerprint,
            "run_id": 23, "run_attempt": 1, "job_id": 9, **semantic,
        })
        p["first_red_unique_signatures"] = 2
        p["red_jobs_without_attributed_first_step"] = 1
        before = consume(binding, p)
        p["first_red_signatures"].reverse()
        p["first_red_manifestations"].reverse()
        after = consume(binding, p)
        self.assertEqual(before, after)

    def test_zero_red_jobs_is_unknown_attribution_not_perfect(self):
        b, p = inputs()
        p["terminal_by_outcome"]["success"] = 20
        p["terminal_by_outcome"]["failure"] = 0
        p["first_red_signatures"] = []
        p["first_red_manifestations"] = []
        p["first_red_unique_signatures"] = 0
        p["first_red_repeated_signatures"] = 0
        p["red_jobs_without_attributed_first_step"] = 0
        result = consume(b, p)
        self.assertEqual(result["observed"]["red_jobs_total"], 0)
        self.assertIsNone(result["observed"]["first_red_attribution_fraction"])
        self.assertIsNone(
            result["observed"]["first_red_signature_compression_fraction"]
        )

    def test_falsify_source_fingerprint_and_native_job_identity(self):
        mutations = (
            lambda p: p["first_red_signatures"][0].update(step_name="not-pytest"),
            lambda p: p["first_red_signatures"][0].update(fingerprint="b" * 64),
            lambda p: p["first_red_manifestations"][0].update(step_number=True),
            lambda p: p["first_red_manifestations"][0].update(
                run_attempt=0
            ),
            lambda p: p["first_red_manifestations"][0].update(job_id=None),
            lambda p: p["first_red_manifestations"][0].update(
                fingerprint="d" * 64
            ),
            lambda p: p.update(red_jobs_without_attributed_first_step=1),
            lambda p: p.update(red_jobs_without_attributed_first_step=-1),
        )
        for mutate in mutations:
            with self.subTest(case=str(mutate)):
                b, p = inputs()
                mutate(p)
                with self.assertRaises(ValueError):
                    consume(b, p)

    def test_duplicate_event_rejected_even_if_totals_manipulated(self):
        b, p = inputs()
        p["first_red_manifestations"].append(
            copy.deepcopy(p["first_red_manifestations"][0])
        )
        p["first_red_signatures"][0]["manifestations"] = 2
        p["first_red_repeated_signatures"] = 1
        p["red_jobs_without_attributed_first_step"] = 1
        with self.assertRaisesRegex(ValueError, "duplicate native first-red job"):
            consume(b, p)

    def test_falsify_job_and_queue_denominators(self):
        mutations = (
            lambda p: p.update(jobs_observed=19),
            lambda p: p.update(nonterminal=1),
            lambda p: p["terminal_by_outcome"].update(failure=2),
            lambda p: p["terminal_by_outcome"].update(failure=True),
            lambda p: p["queue_source_counts"].update(job_created_at=True),
            lambda p: p.update(queue_samples=True),
            lambda p: p.update(queue_seconds_p95=None),
            lambda p: p.update(queue_seconds_p95=-1),
            lambda p: p.update(queue_seconds_p95=float("nan")),
            lambda p: p.update(queue_seconds_p95=float("inf")),
        )
        for mutate in mutations:
            with self.subTest(case=str(mutate)):
                b, p = inputs()
                mutate(p)
                with self.assertRaises(ValueError):
                    consume(b, p)

    def test_empty_queue_has_unknown_p95_and_native_fraction(self):
        b, p = inputs()
        p["queue_source_counts"] = {
            "job_created_at": 0,
            "workflow_run_created_at_fallback": 0,
        }
        p["queue_samples"] = 0
        p["queue_seconds_p95"] = None
        out = consume(b, p)
        self.assertIsNone(out["observed"]["queue_native_fraction"])
        self.assertIsNone(out["observed"]["queue_p95_seconds_source_reported"])

    def test_stress_100_disjoint_signatures_and_200_manifestations(self):
        b, p = inputs()
        p["first_red_signatures"] = []
        p["first_red_manifestations"] = []
        for i in range(100):
            semantic = {
                "workflow_path": ".github/workflows/checks.yml",
                "job_name": "matrix-python-" + str(i),
                "step_name": "pytest", "step_number": 3,
            }
            signature = first_red_digest(semantic)
            p["first_red_signatures"].append({
                "fingerprint": signature, "manifestations": 2, **semantic,
            })
            for attempt in (1, 2):
                p["first_red_manifestations"].append({
                    "fingerprint": signature,
                    "run_id": 1000 + i, "run_attempt": attempt,
                    "job_id": 2000 + i * 2 + attempt, **semantic,
                })
        p["first_red_unique_signatures"] = 100
        p["first_red_repeated_signatures"] = 100
        p["red_jobs_without_attributed_first_step"] = 0
        p["terminal_by_outcome"] = {
            **{name: 0 for name in p["terminal_by_outcome"]},
            "success": 20, "failure": 200,
        }
        p["jobs_observed"] = 220
        out = consume(b, p)
        self.assertEqual(out["observed"]["red_jobs_total"], 200)
        self.assertEqual(out["observed"]["first_red_attribution_fraction"], 1)
        self.assertEqual(out["observed"]["first_red_signature_compression_fraction"], .5)
        self.assertEqual(out["observed"]["first_red_unique_signatures"], 100)
        self.assertEqual(out["admission"], "HOLD")

    def test_output_file_hardlink_symlink_and_digest_integrity(self):
        b, p = inputs()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src, bind = root / "src.json", root / "bind.json"
            raw = json.dumps(p, sort_keys=True).encode()
            src.write_bytes(raw)
            b["producer_sha256"] = hashlib.sha256(raw).hexdigest()
            bind.write_text(json.dumps(b))
            other = root / "same-inode.json"
            os.link(src, other)
            with self.assertRaisesRegex(ValueError, "output aliases input"):
                main(["--binding", str(bind), "--producer", str(src),
                      "--out", str(other)])
            self.assertEqual(src.read_bytes(), raw)
            target = root / "output.json"
            self.assertEqual(main(["--binding", str(bind), "--producer",
                                   str(src), "--out", str(target)]), 0)
            original_projection = target.read_bytes()
            self.assertEqual(main(["--binding", str(bind), "--producer",
                                   str(src), "--out", str(target)]), 0)
            self.assertEqual(target.read_bytes(), original_projection)
            symlink = root / "output-link.json"
            try:
                symlink.symlink_to(target)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaisesRegex(ValueError, "symlink"):
                    main(["--binding", str(bind), "--producer",
                          str(src), "--out", str(symlink)])
            self.assertEqual(src.read_bytes(), raw)
            self.assertEqual(target.read_bytes(), original_projection)


    def test_atomic_failure_preserves_evidence_and_cleans_temp(self):
        from unittest.mock import patch
        b, p = inputs()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, binding, target = (
                root / "source.json", root / "binding.json", root / "projection.json"
            )
            raw = json.dumps(p, sort_keys=True).encode()
            source.write_bytes(raw)
            b["producer_sha256"] = hashlib.sha256(raw).hexdigest()
            binding.write_text(json.dumps(b))
            with patch("mip_source_consumer.os.replace",
                       side_effect=OSError("fixture denied rename")):
                with self.assertRaisesRegex(OSError, "denied rename"):
                    main(["--binding", str(binding), "--producer", str(source),
                          "--out", str(target)])
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".projection.json.*.tmp")), [])

    def test_direct_script_entrypoint_executes_without_impersonating_merge(self):
        import runpy
        import sys
        from unittest.mock import patch
        b, p = inputs()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, binding, target = (
                root / "source.json", root / "binding.json", root / "projection.json"
            )
            raw = json.dumps(p, sort_keys=True).encode()
            source.write_bytes(raw)
            b["producer_sha256"] = hashlib.sha256(raw).hexdigest()
            binding.write_text(json.dumps(b))
            argv = ["mip_source_consumer.py", "--binding", str(binding),
                    "--producer", str(source), "--out", str(target)]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as exit_status:
                    runpy.run_path(str(Path(__file__).with_name(
                        "mip_source_consumer.py")), run_name="__main__")
            self.assertEqual(exit_status.exception.code, 0)
            report = json.loads(target.read_text())
            self.assertFalse(report["merge_authorized"])
            self.assertEqual(report["admission"], "HOLD")


if __name__ == "__main__":
    unittest.main()
