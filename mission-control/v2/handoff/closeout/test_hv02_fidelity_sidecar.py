"""HV-02 negative controls and CP.CLOSE backwards-compatible metadata replay."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import cp_close
import hv02_fidelity_sidecar as hv02

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LEGACY = HERE / "intakes" / "CP-G3P-HTMLQA-20261017.json"
BD = ROOT / "mission-control" / "federation-atlas" / "CODE_PURPLE_BD_QUEUE_v1.json"

def fixture():
    return {
        "schema": hv02.SCHEMA, "session_alias": "HV02-FIXTURE",
        "capture_utc": "UNKNOWN", "source_class": "GITHUB_OBSERVED",
        "source_locator": "UNKNOWN", "source_sha256": None,
        "source_state": "UNKNOWN", "scope": "CURRENT_VISIBLE",
        "completeness": "UNKNOWN", "message_count": None,
        "artifact_refs": [], "evidence": [],
        "merge_admission": "HOLD", "authority_transfer": False,
    }

class HV02Tests(unittest.TestCase):
    def test_s1_legacy_closeout_untouched(self):
        inp = json.loads(LEGACY.read_text(encoding="utf-8"))
        cp_close.validate(inp)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "record"
            original = cp_close.build(LEGACY, BD, out)
            self.assertEqual(original["artifact_count"], 9)
            self.assertEqual(cp_close.build(LEGACY, BD, out, check=True), original)
        self.assertEqual(hv02.validate(fixture())["merge_admission"], "HOLD")

    def test_s2_provider_complete_not_supported(self):
        obj = fixture()
        obj["completeness"] = "VERIFIED_PROVIDER_ATTESTED"
        with self.assertRaisesRegex(ValueError, "provider-level"):
            hv02.validate(obj)

    def test_s3_reconstruction_not_a_complete_transcript(self):
        obj = fixture()
        obj.update(source_class="RECONSTRUCTED", completeness="USER_DECLARED")
        with self.assertRaisesRegex(ValueError, "reconstructed"):
            hv02.validate(obj)

    def test_s4_unknown_stays_null(self):
        result = hv02.validate(fixture())
        self.assertIsNone(result["message_count"])
        self.assertFalse(result["verbatim_completeness_attested"])

    def test_s5_digest_without_bytes_is_only_source_declared(self):
        obj = fixture()
        obj["artifact_refs"] = [{
            "id": "file001", "media_type": "application/pdf", "bytes": 3,
            "sha256": hashlib.sha256(b"abc").hexdigest(),
            "custody": "UNKNOWN", "access_class": "PRIVATE",
            "state": "SOURCE_DECLARED",
        }]
        self.assertEqual(hv02.validate(obj)["artifacts_verified"], 0)

    def test_s6_stale_evidence_is_holding_not_pass(self):
        obj = fixture()
        obj["evidence"] = [{"state": "STALE", "run_sha": "a" * 40}]
        self.assertEqual(hv02.validate(obj)["merge_admission"], "HOLD")
        obj["merge_admission"] = "PASS"
        with self.assertRaisesRegex(ValueError, "authority"):
            hv02.validate(obj)

    def test_s7_private_payload_and_url_fail(self):
        for injected in ({"raw_transcript": "private"},
                         {"extras": {"messages": ["secret"]}},
                         {"source_locator": "file:///Users/private/secret.json"},
                         {"source_locator": "https://github.com/GBOGEB/a?token=abc"}):
            with self.subTest(injected=injected):
                obj = fixture()
                obj.update(injected)
                with self.assertRaises(ValueError):
                    hv02.validate(obj)

    def test_s8_future_unknown_field_additive(self):
        obj = fixture()
        obj["future_v2_addendum"] = {"nonsecret_metadata": {"type": "novel"}}
        self.assertIsNone(hv02.validate(obj)["message_count"])

    def test_user_declared_bound_population_remains_unattested(self):
        source = b'{"export":"user-owned-local-test"}'
        obj = fixture()
        obj.update(source_class="AUTHORIZED_EXPORT", scope="AUTHORIZED_EXPORT",
                   source_state="VERIFIED", source_sha256=hashlib.sha256(source).hexdigest(),
                   completeness="USER_DECLARED", message_count=2,
                   message_refs=["m001", "m002"])
        receipt = hv02.validate(obj, source_bytes=source)
        self.assertEqual(receipt["message_count"], 2)
        self.assertFalse(receipt["verbatim_completeness_attested"])

    def test_export_requires_actual_matching_source_bytes(self):
        source = b"local"
        obj = fixture()
        obj.update(source_class="AUTHORIZED_EXPORT", scope="AUTHORIZED_EXPORT",
                   source_state="VERIFIED", source_sha256=hashlib.sha256(source).hexdigest(),
                   completeness="USER_DECLARED", message_count=1,
                   message_refs=["m001"])
        for supplied in (None, b"tampered"):
            with self.subTest(supplied=supplied):
                with self.assertRaises(ValueError):
                    hv02.validate(obj, source_bytes=supplied)

    def test_artifact_verified_requires_matching_bytes(self):
        original = b"binary"
        obj = fixture()
        obj["artifact_refs"] = [{
            "id": "file001", "media_type": "application/pdf", "bytes": len(original),
            "sha256": hashlib.sha256(original).hexdigest(),
            "custody": "LOCAL_PRIVATE", "access_class": "PRIVATE",
            "state": "VERIFIED",
        }]
        with self.assertRaisesRegex(ValueError, "not verified"):
            hv02.validate(obj)
        self.assertEqual(hv02.validate(obj, artifact_bytes={"file001": original})["artifacts_verified"], 1)
        with self.assertRaisesRegex(ValueError, "not verified"):
            hv02.validate(obj, artifact_bytes={"file001": b"tamper"})

    def test_duplicate_ids_and_invalid_time_rejected(self):
        obj = fixture()
        obj["capture_utc"] = "2026-10-29T13:00:00+01:00"
        with self.assertRaisesRegex(ValueError, "UTC"):
            hv02.validate(obj)
        obj = fixture()
        a = {"id": "x", "media_type": "application/pdf", "bytes": None,
             "sha256": None, "custody": "UNKNOWN", "access_class": "PRIVATE",
             "state": "UNKNOWN"}
        obj["artifact_refs"] = [a, copy.deepcopy(a)]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            hv02.validate(obj)

if __name__ == "__main__":
    unittest.main()
