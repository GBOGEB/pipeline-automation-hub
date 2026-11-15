#!/usr/bin/env python3
"""Read-only DOCX TypeScript native receipt intake; never self-approve a peer.

This complements, not replaces, the 5-repo canonical exact_head_receipts.py
owner. It is a typed component witness, not full DOCX orchestration acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA64=re.compile(r"^[0-9a-f]{64}$")
SCHEMA="method-atlas.n32.docx-peer-candidate-review.v1"
DOCX="GBOGEB/DOCX_RTM_Automation"
INPUT="docx.n32.typecript-queue-candidate.v1"
LOCK="orchestration_ts/package-lock.json"
SOURCE="orchestration_ts/src/queue/JobQueue.ts"
COMPILED="orchestration_ts/dist/queue/JobQueue.js"
FILES={"docx-n32-tests.log","docx-n32/manifest.json","docx-n32/owner_receipt.json"}


def require(ok,msg):
    if not ok:raise ValueError(msg)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def inspect_archive(path,head,native=None):
    data=Path(path).read_bytes()
    require(len(data)<=5_000_000,"OVERSIZE_ARCHIVE")
    require(isinstance(head,str) and SHA40.fullmatch(head),"SOURCE_SHA_NOT_EXACT")
    with zipfile.ZipFile(path) as z:
        entries=z.infolist()
        names={x.filename for x in entries}
        require(len(entries)==len(FILES) and names==FILES,
                "UNEXPECTED_OR_MISSING_ARCHIVE_MEMBERS")
        for info in entries:
            require(not info.flag_bits&1 and info.file_size<=2_000_000
                    and info.compress_size>0,"ENCRYPTED_OR_OVERSIZE_MEMBER")
            mode=(info.external_attr>>16)&0xffff
            require(not stat.S_ISLNK(mode),"SYMLINK_ARCHIVE_MEMBER")
        raw=z.read("docx-n32/owner_receipt.json")
        manifest=json.loads(z.read("docx-n32/manifest.json"))
        receipt=json.loads(raw)
        log=z.read("docx-n32-tests.log").decode("utf-8")
    require(manifest.get("schema")=="docx.n32.owner-member-manifest.v1" and
            manifest.get("source_head")==head and
            manifest.get("authorized_federation_admission") is False and
            manifest.get("files_sha256")=={"owner_receipt.json":sha(raw)},
            "OWNER_MEMBER_SHA_OR_AUTHORITY_MISMATCH")
    require(receipt.get("schema")==INPUT and receipt.get("repository")==DOCX
            and receipt.get("source_head")==head and receipt.get("owner_component")==SOURCE
            and receipt.get("execution_type")=="COMPILED_TYPESCRIPT_QUEUE_ACTUAL",
            "TYPED_SOURCE_OWNER_CONTRACT_MISMATCH")
    digests=receipt.get("source_sha256")
    require(isinstance(digests,dict) and set(digests)=={LOCK,SOURCE,COMPILED}
            and all(isinstance(v,str) and SHA64.fullmatch(v) for v in digests.values()),
            "SOURCE_DEPENDENCY_SHA_INCOMPLETE")
    proof=receipt.get("observed",{})
    expected=["Q"+str(i).zfill(3) for i in range(1,33)]
    require(proof.get("submitted")==32 and proof.get("completed")==32 and
            proof.get("accepted_order")==expected and
            receipt.get("independent_replay_identical") is True,
            "REAL_TYPED_EXECUTION_OR_REPLAY_INVALID")
    checks=proof.get("checks")
    require(checks=={"positive_fifo":True,"empty_dequeue_guard":True,
                     "adapter_duplicate_id_rejected":True,
                     "deliberate_bad_order_rejected":True},
            "NEGATIVE_ORACLE_MISSING")
    caveats=receipt.get("caveats",{})
    for f in ("full_federation_process_covered","cross_repository_owner_approved",
              "native_job_authenticated","outbound_private_data",
              "remote_dispatch_authorized","merge_authorized"):
        require(caveats.get(f) is False,"OWNER_AUTHORITY_ESCALATION_"+f)
    require(caveats.get("engineering_credit_delta")==0 and
            caveats.get("javascript_branch_coverage_pct") is None and
            caveats.get("duplicate_id_rejected_by")==
              "OWNER_PROBE_ADAPTER_NOT_NATIVE_QUEUE",
            "FALSE_NATIVE_QUEUE_OR_COVERAGE_CREDIT")
    require("# pass 6" in log and "# fail 0" in log,
            "NATIVE_TEST_RESULT_LOG_MISMATCH")
    candidate={"schema":SCHEMA,"owner_repository":DOCX,"owner_head":head,
               "typed_queue_jobs":32,"native_compiled_component_observed":True,
               "owner_receipt_sha256":sha(raw),"artifact_zip_sha256":sha(data),
               "owner_source_sha256":digests,
               "test_log_sha256":sha(log.encode()),"negative_guards":3,
               "javascript_branch_coverage_pct":None,
               "full_docx_pipeline_coverage":None,
               "owner_admission":"PENDING_INDEPENDENT_ACCEPTANCE",
               "native_readback":"NOT_AUTHENTICATED_BY_OFFLINE_VALIDATOR",
               "public_hub_operational_credit":0,
               "remote_dispatch_authorized":False,
               "merge_authorized":False}
    if native is not None:
        require(isinstance(native,dict) and native.get("repository")==DOCX
                and native.get("head_sha")==head and
                type(native.get("run_id")) is int and native["run_id"]>0
                and type(native.get("job_id")) is int and native["job_id"]>0
                and type(native.get("attempt")) is int and native["attempt"]>0
                and type(native.get("steps")) is int and native["steps"]>0
                and native.get("conclusion")=="success"
                and native.get("artifact_zip_sha256")==sha(data),
                "PROVIDER_READBACK_INPUT_MISMATCH")
        candidate["provider_supplied_run"]={
            "run_id":native["run_id"],"job_id":native["job_id"],
            "attempt":native["attempt"],"steps":native["steps"],
            "status":"SOURCE_MATCHED_UNVERIFIED_EXTERNAL_REPORT"}
    return candidate


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip",type=Path,required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--native",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    native=json.loads(args.native.read_text()) if args.native else None
    result=inspect_archive(args.zip,args.head,native)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(canonical(result))
    print(json.dumps({"classification":"TYPED_COMPONENT_BYTES_VERIFIED_OWNER_HOLD",
                     "owner_head":result["owner_head"],
                     "full_federation_admitted":False},sort_keys=True))


if __name__=="__main__":
    main()
