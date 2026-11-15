"""N3.2 owner peer candidate: archive integrity and negative federation contracts."""
from __future__ import annotations
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("n32_docx_peer_gate_under_test",HERE/"n32_docx_peer_intake.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
HEAD="a"*40
SOURCE="orchestration_ts/src/queue/JobQueue.ts"
COMPILED="orchestration_ts/dist/queue/JobQueue.js"
LOCK="orchestration_ts/package-lock.json"


def sample():
    return {"schema":"docx.n32.typecript-queue-candidate.v1",
       "repository":m.DOCX,"source_head":HEAD,"owner_component":SOURCE,
       "execution_type":"COMPILED_TYPESCRIPT_QUEUE_ACTUAL",
       "source_sha256":{SOURCE:"b"*64,COMPILED:"c"*64,LOCK:"d"*64},
       "independent_replay_identical":True,
       "observed":{"submitted":32,"completed":32,
          "accepted_order":["Q"+str(i).zfill(3) for i in range(1,33)],
          "checks":{"positive_fifo":True,"empty_dequeue_guard":True,
                    "adapter_duplicate_id_rejected":True,
                    "deliberate_bad_order_rejected":True}},
       "caveats":{"full_federation_process_covered":False,
             "cross_repository_owner_approved":False,
             "native_job_authenticated":False,
             "outbound_private_data":False,
             "remote_dispatch_authorized":False,"merge_authorized":False,
             "engineering_credit_delta":0,"javascript_branch_coverage_pct":None,
             "duplicate_id_rejected_by":"OWNER_PROBE_ADAPTER_NOT_NATIVE_QUEUE"}}


def pack(out,receipt=None,bad_sha=False,bad_names=False):
    d=sample() if receipt is None else receipt
    raw=(json.dumps(d,sort_keys=True)+"\n").encode()
    sha="f"*64 if bad_sha else m.sha(raw)
    manifest={"schema":"docx.n32.owner-member-manifest.v1",
              "source_head":HEAD,"authorized_federation_admission":False,
              "files_sha256":{"owner_receipt.json":sha}}
    name="unexpected/name.json" if bad_names else "docx-n32/owner_receipt.json"
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr(name,raw)
        z.writestr("docx-n32/manifest.json",json.dumps(manifest))
        z.writestr("docx-n32-tests.log","# tests 6\n# pass 6\n# fail 0\n")
    return out


class TypedPeerIntake(unittest.TestCase):
    def test_valid_candidate_remains_owner_hold(self):
        with tempfile.TemporaryDirectory() as td:
            p=pack(Path(td)/"owner.zip")
            r=m.inspect_archive(p,HEAD)
            self.assertEqual(r["typed_queue_jobs"],32)
            self.assertTrue(r["native_compiled_component_observed"])
            self.assertIsNone(r["javascript_branch_coverage_pct"])
            self.assertIsNone(r["full_docx_pipeline_coverage"])
            self.assertEqual(r["owner_admission"],"PENDING_INDEPENDENT_ACCEPTANCE")
            self.assertEqual(r["public_hub_operational_credit"],0)

    def test_wrong_head_and_witness_source_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=pack(Path(td)/"owner.zip")
            with self.assertRaisesRegex(ValueError,"SOURCE_SHA_NOT_EXACT"):
                m.inspect_archive(p,"garbage")
            with self.assertRaisesRegex(ValueError,"OWNER_MEMBER_SHA_OR_AUTHORITY_MISMATCH"):
                m.inspect_archive(p,"e"*40)

    def test_missing_extra_archive_members_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pack(Path(td)/"owner.zip",bad_names=True)
            with self.assertRaisesRegex(ValueError,"UNEXPECTED_OR_MISSING_ARCHIVE_MEMBERS"):
                m.inspect_archive(p,HEAD)

    def test_source_repair_must_preserve_current_member_checksum(self):
        with tempfile.TemporaryDirectory() as td:
            p=pack(Path(td)/"owner.zip",bad_sha=True)
            with self.assertRaisesRegex(ValueError,"OWNER_MEMBER_SHA_OR_AUTHORITY_MISMATCH"):
                m.inspect_archive(p,HEAD)

    def test_fake_fifo_or_count_cannot_claim_actual_execution(self):
        for field in ("accepted_order","completed"):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as td:
                d=sample()
                if field=="accepted_order":d["observed"][field]=list(reversed(d["observed"][field]))
                else:d["observed"][field]=31
                p=pack(Path(td)/"owner.zip",d)
                with self.assertRaisesRegex(ValueError,"REAL_TYPED_EXECUTION_OR_REPLAY_INVALID"):
                    m.inspect_archive(p,HEAD)

    def test_native_queue_not_credited_with_adapter_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            d=sample()
            d["caveats"]["duplicate_id_rejected_by"]="NATIVE_QUEUE"
            p=pack(Path(td)/"owner.zip",d)
            with self.assertRaisesRegex(ValueError,"FALSE_NATIVE_QUEUE_OR_COVERAGE_CREDIT"):
                m.inspect_archive(p,HEAD)

    def test_forged_owner_approval_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=sample();d["caveats"]["cross_repository_owner_approved"]=True
            p=pack(Path(td)/"owner.zip",d)
            with self.assertRaisesRegex(ValueError,"OWNER_AUTHORITY_ESCALATION"):
                m.inspect_archive(p,HEAD)

    def test_provider_report_must_match_artifact_and_head(self):
        with tempfile.TemporaryDirectory() as td:
            p=pack(Path(td)/"owner.zip")
            native={"repository":m.DOCX,"head_sha":HEAD,"run_id":11,
                    "attempt":1,"job_id":22,"steps":8,"conclusion":"success",
                    "artifact_zip_sha256":m.sha(p.read_bytes())}
            r=m.inspect_archive(p,HEAD,native)
            self.assertEqual(r["provider_supplied_run"]["run_id"],11)
            self.assertEqual(r["native_readback"],"NOT_AUTHENTICATED_BY_OFFLINE_VALIDATOR")
            native["artifact_zip_sha256"]="f"*64
            with self.assertRaisesRegex(ValueError,"PROVIDER_READBACK_INPUT_MISMATCH"):
                m.inspect_archive(p,HEAD,native)

    def test_missing_js_branch_coverage_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            d=sample();d["caveats"]["javascript_branch_coverage_pct"]=0
            p=pack(Path(td)/"owner.zip",d)
            with self.assertRaisesRegex(ValueError,"FALSE_NATIVE_QUEUE_OR_COVERAGE_CREDIT"):
                m.inspect_archive(p,HEAD)


if __name__=="__main__":
    unittest.main()
