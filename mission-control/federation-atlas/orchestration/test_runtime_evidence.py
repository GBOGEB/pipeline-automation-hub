"""Adversarial checks for actual artifact consumption, separate from dispatch."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("runtime_evidence_test_owner", HERE / "runtime_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class EvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root, self.run = self.base / "source", self.base / "run"
        self.root.mkdir()
        self.run.mkdir()
        self.atlas = evidence.owner()

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, directory, name, value):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(evidence.canonical(value) if isinstance(value, dict) else value)
        return path

    def test_duplicate_and_nonfinite_json_receipts_are_rejected(self):
        path = self.run / "receipt.json"
        for raw in [b'{"success":false,"success":true}', b'{"duration":NaN}', b'{"duration":Infinity}']:
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    evidence.load(path)

    def test_missing_and_symlink_output_directories_are_rejected(self):
        with self.assertRaises(ValueError):
            evidence.file_map(self.run / "missing")
        outside = self.write(self.base, "outside.json", {"private": True})
        (self.run / "link.json").symlink_to(outside)
        with self.assertRaises(ValueError):
            evidence.file_map(self.run)

    def products_fixture(self):
        names = ("method", "control", "superstitch", "convergence", "orchestration", "portal")
        blocks, tasks, rows = [], [], {"validate": {"state": "succeeded"}, "assemble": {"state": "succeeded"}}
        for name in names:
            port = {"id": "result", "path": "result.json", "kind": "json", "required": True, "schema": "example/v1"}
            blocks.append({"id": name, "outputs": [port]})
            tasks.append({"id": name, "block_id": name})
            self.write(self.run / name, "result.json", {"schema": "example/v1", "producer": name})
            observed = self.atlas.validate_artifact(self.run / name, port)
            rows[name] = {"state": "succeeded", "result": {"artifacts": [observed]}}
        # Contract-specific local assembler copies top-level control over method.
        self.write(self.run / "assemble", "result.json", (self.run / "control/result.json").read_bytes())
        for name in ("superstitch", "convergence", "orchestration"):
            self.write(self.run / "assemble", name + "/result.json", (self.run / name / "result.json").read_bytes())
        self.write(self.run / "portal", "site-manifest.json", {"source_git_sha": "a" * 40,
                    "public_files_sha256": {"result.json": evidence.digest((self.run / "portal/result.json").read_bytes())}})
        tasks.append({"id": "assemble", "block_id": None})
        rows["assemble"]["result"] = {}
        for name, row in rows.items():
            if name != "validate":
                row["result"]["output_files_sha256"] = evidence.file_map(self.run / name)
        return {"blocks": blocks}, {"source_sha": "a" * 40, "tasks": rows}, tasks

    def check_products(self, profile, receipt, tasks):
        with mock.patch.object(self.atlas, "tasks", return_value=tasks), mock.patch.object(self.atlas, "verify_bundle"):
            return evidence.verify_products(self.atlas, self.root, self.run, profile, receipt)

    def test_matching_producer_assembly_and_package_bytes_are_observed(self):
        profile, receipt, tasks = self.products_fixture()
        result = self.check_products(profile, receipt, tasks)
        self.assertTrue(result["assembly_consumed_exact_producer_bytes"])
        self.assertTrue(result["package_member_verification"])
        self.assertEqual(len(result["declared_output_ports_checked"]), 6)

    def test_changed_producer_bytes_cannot_keep_success_receipt(self):
        profile, receipt, tasks = self.products_fixture()
        self.write(self.run / "method", "result.json", {"schema": "example/v1", "producer": "altered"})
        with self.assertRaisesRegex(ValueError, "sealed product"):
            self.check_products(profile, receipt, tasks)

    def test_missing_required_output_cannot_keep_zero_exit_success(self):
        profile, receipt, tasks = self.products_fixture()
        (self.run / "convergence/result.json").unlink()
        with self.assertRaisesRegex(ValueError, "sealed product"):
            self.check_products(profile, receipt, tasks)

    def test_correct_producers_but_wrong_consumer_bytes_are_rejected(self):
        profile, receipt, tasks = self.products_fixture()
        self.write(self.run / "assemble", "superstitch/result.json", {"schema": "example/v1", "producer": "stale"})
        with self.assertRaisesRegex(ValueError, "sealed product"):
            self.check_products(profile, receipt, tasks)

    def test_unexpected_assembly_member_is_rejected(self):
        profile, receipt, tasks = self.products_fixture()
        self.write(self.run / "assemble", "unexpected.txt", b"not a declared producer member")
        with self.assertRaisesRegex(ValueError, "sealed product"):
            self.check_products(profile, receipt, tasks)

    def test_wrong_package_sha_and_tampered_member_are_rejected(self):
        for mutation in ("sha", "member"):
            with self.subTest(mutation=mutation):
                profile, receipt, tasks = self.products_fixture()
                path = self.run / "portal/site-manifest.json"
                manifest = evidence.load(path)
                if mutation == "sha":
                    manifest["source_git_sha"] = "b" * 40
                else:
                    manifest["public_files_sha256"]["result.json"] = "0" * 64
                path.write_bytes(evidence.canonical(manifest))
                receipt["tasks"]["portal"]["result"]["output_files_sha256"] = evidence.file_map(self.run / "portal")
                with self.assertRaisesRegex(ValueError, "packaged"):
                    self.check_products(profile, receipt, tasks)

    def test_package_path_traversal_is_rejected(self):
        profile, receipt, tasks = self.products_fixture()
        self.write(self.run / "portal", "site-manifest.json", {"source_git_sha": "a" * 40,
                   "public_files_sha256": {"../outside.json": "a" * 64}})
        with self.assertRaises(ValueError):
            self.check_products(profile, receipt, tasks)

    def test_failed_and_blocked_tasks_are_not_counted_as_observed_outputs(self):
        profile, receipt, tasks = self.products_fixture()
        receipt["tasks"]["convergence"]["state"] = "failed"
        receipt["tasks"]["assemble"]["state"] = "blocked"
        receipt["tasks"]["portal"]["state"] = "blocked"
        result = self.check_products(profile, receipt, tasks)
        self.assertFalse(result["assembly_consumed_exact_producer_bytes"])
        self.assertFalse(result["package_member_verification"])
        self.assertNotIn("convergence", {port["task"] for port in result["declared_output_ports_checked"]})

    def test_legacy_receipt_cannot_claim_complete_product_verification(self):
        profile, receipt, tasks = self.products_fixture()
        del receipt["tasks"]["method"]["result"]["output_files_sha256"]
        with self.assertRaisesRegex(ValueError, "complete product seal missing"):
            self.check_products(profile, receipt, tasks)

    def test_support_file_tampering_is_rejected_even_outside_declared_ports(self):
        profile, receipt, tasks = self.products_fixture()
        self.write(self.run / "superstitch", "app.js", b"unexpected supporting code")
        with self.assertRaisesRegex(ValueError, "sealed product"):
            self.check_products(profile, receipt, tasks)

    def test_resealed_but_incomplete_package_manifest_is_rejected(self):
        profile, receipt, tasks = self.products_fixture()
        self.write(self.run / "portal", "extra.txt", b"must be accounted for")
        receipt["tasks"]["portal"]["result"]["output_files_sha256"] = evidence.file_map(self.run / "portal")
        with self.assertRaisesRegex(ValueError, "packaged manifest population"):
            self.check_products(profile, receipt, tasks)

    def test_replay_removes_arbitrary_result_and_exception_payloads(self):
        row = {"state": "failed", "result": {"private": "private result", "output_files_sha256": {}},
               "events": [{"state": "failed", "at_seconds": 1.0, "private": "private event"}],
               "error": {"phase": "handler", "type": "ValueError", "message": "private exception"}}
        replay = evidence.replay_tasks({"task": row})
        self.assertNotIn("private", json.dumps(replay))
        self.assertEqual(replay["task"]["error"], {"phase": "handler", "type": "ValueError"})

    def test_html_embedded_receipt_cannot_inject_script_or_claim_live_run(self):
        report = {"source_sha": "a" * 40, "payload": "</script><script>alert(1)</script>"}
        markup = evidence.render(report)
        self.assertNotIn(report["payload"], markup)
        self.assertIn("\\u003c/script>", markup)
        self.assertIn("Replay uses recorded events", markup)
        self.assertIn("does not launch work", markup)

    def test_cli_refuses_output_that_overlaps_source_or_run(self):
        for out in (self.root / "reports", self.run / "reports", self.base):
            with self.subTest(out=out), mock.patch("builtins.print"):
                self.assertEqual(evidence.main(["--root", str(self.root), "--run-dir", str(self.run), "--out", str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
