"""Isolated G5 consumer tests; do not alter the 44-test coverage cohort."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import consumer_g1 as m

SOURCE = "6" * 40
RUN = 38726158685
JOB = 116392416193


def evidence():
    report = {"schema": "gogreen.federation.rollup.v1",
              "breadth_depth": {"repositories": 6, "target_repo_surface_cells": 66,
                                "source_discovered_cells": 13, "native_status_verified_cells": 0,
                                "artifact_bytes_verified_cells": 0, "unknown_cells": 53},
              "authority_transfer": False, "merge_authorized": False}
    member = {"rollup.json": json.dumps(report).encode(),
              "rollup.html": f"<html><body>{SOURCE} 13/66 HOLD DEFER</body></html>".encode(),
              "source_tests.log": b"Ran 28 tests in 1.0s\n\nOK\n",
              "html_tests.log": b"Ran 8 tests in 1.0s\n\nOK\n"}
    manifest = {"schema": "gogreen.federation.rollup.manifest.v1",
                "producer_source_sha": SOURCE, "native_run_id": RUN, "native_attempt": 1,
                "evidence_class": "PRODUCER_NATIVE_NOT_CONSUMER_ACCEPTED",
                "authority_transfer": False, "merge_authorized": False,
                "independent_downloaded_bytes_verified": False,
                "sha256": {x: hashlib.sha256(member[x]).hexdigest()
                           for x in ("rollup.json", "rollup.html")}}
    member["manifest.json"] = json.dumps(manifest).encode()
    return member


def pack(members):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in sorted(members.items()):
            z.writestr(name, value)
    return raw.getvalue()


def check(raw, sha=None):
    return m.validate_archive(raw, expected_archive_sha256=sha or hashlib.sha256(raw).hexdigest(),
                              expected_source_sha=SOURCE, expected_run_id=RUN,
                              expected_job_id=JOB)


class ConsumerReplayTests(unittest.TestCase):
    def test_valid_bytes_are_consumer_proof_not_qps(self):
        out = check(pack(evidence()))
        self.assertEqual(out["verified_producer_to_consumer_links"], 1)
        self.assertEqual(out["cross_repository_federation_links"], 0)
        self.assertEqual(out["qps_recipient_accepted_links"], 0)
        self.assertFalse(out["merge_authorized"])

    def test_mutated_downloaded_zip_rejected(self):
        b = pack(evidence())
        with self.assertRaisesRegex(ValueError, "downloaded ZIP SHA256"):
            check(b + b"tampered", hashlib.sha256(b).hexdigest())

    def test_inner_rollup_hash_tampering_rejected(self):
        files = evidence()
        files["rollup.json"] = files["rollup.json"] + b" "
        with self.assertRaisesRegex(ValueError, "inner-member digest"):
            check(pack(files))

    def test_source_sha_mismatch_rejected(self):
        files = evidence()
        j = json.loads(files["manifest.json"])
        j["producer_source_sha"] = "a"*40
        files["manifest.json"] = json.dumps(j).encode()
        with self.assertRaisesRegex(ValueError, "exact head/run"):
            check(pack(files))

    def test_missing_member_rejected(self):
        files = evidence()
        files.pop("rollup.html")
        with self.assertRaisesRegex(ValueError, "ZIP members"):
            check(pack(files))

    def test_traversal_member_rejected(self):
        files = evidence()
        files["../hidden.txt"] = b"no"
        with self.assertRaisesRegex(ValueError, "ZIP members"):
            check(pack(files))

    def test_fabricated_accepted_status_rejected(self):
        files = evidence()
        doc = json.loads(files["manifest.json"])
        doc["merge_authorized"] = True
        files["manifest.json"] = json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            check(pack(files))

    def test_denominator_drift_rejected(self):
        files = evidence()
        body = json.loads(files["rollup.json"])
        body["breadth_depth"]["source_discovered_cells"] = 14
        files["rollup.json"] = json.dumps(body).encode()
        doc = json.loads(files["manifest.json"])
        doc["sha256"]["rollup.json"] = hashlib.sha256(files["rollup.json"]).hexdigest()
        files["manifest.json"] = json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError, "denominator"):
            check(pack(files))

    def test_wrong_html_view_rejected(self):
        files = evidence()
        files["rollup.html"] = b"<html>no-source-id</html>"
        doc = json.loads(files["manifest.json"])
        doc["sha256"]["rollup.html"] = hashlib.sha256(files["rollup.html"]).hexdigest()
        files["manifest.json"] = json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError, "view parity"):
            check(pack(files))

    def test_emit_hash_determinism_and_hold(self):
        receipt = check(pack(evidence()))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            first = m.emit(receipt, out)
            self.assertEqual(first, m.emit(receipt, out))
            self.assertEqual(first, hashlib.sha256((out / "g1_consumer_receipt.json").read_bytes()).hexdigest())
            self.assertIn("QPS ACCEPT: **0**", (out / "g1_consumer_receipt.md").read_text(encoding="utf-8"))
            html=(out / "g1_consumer_receipt.html").read_text(encoding="utf-8")
            self.assertIn("Same-repository consumer proof", html)
            self.assertIn("QPS accepted links", html)
            self.assertIn("viewport", html)
            self.assertIn(SOURCE, html)


if __name__ == "__main__":
    unittest.main()
