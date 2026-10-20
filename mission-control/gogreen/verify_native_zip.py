#!/usr/bin/env python3
"""G1 offline ZIP-byte validator; external metadata remains caller asserted.

No GitHub authentication, merge authority, remote writes or child acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
REQUIRED = frozenset({"manifest.json", "execution_provenance.json", "evidence.json",
                      "federation_hooks.json", "scout_packets.json", "summary.md"})
MAX_MEMBERS = 40
MAX_MEMBER_BYTES = 2_000_000
MAX_TOTAL_BYTES = 8_000_000

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0

def verify(archive: bytes, binding: dict) -> dict:
    """Check uploaded bytes and source binding without attributing trust to caller metadata."""
    if not isinstance(binding, dict) or binding.get("schema") != "gogreen.external-binding.v1":
        raise ValueError("invalid external binding schema")
    for key in ("run_id", "run_attempt", "job_id", "artifact_id"):
        if not _positive_int(binding.get(key)):
            raise ValueError(f"invalid {key}")
    if not isinstance(binding.get("repository"), str) or not REPO.fullmatch(binding["repository"]):
        raise ValueError("invalid repository")
    if not isinstance(binding.get("source_sha"), str) or not SHA.fullmatch(binding["source_sha"]):
        raise ValueError("invalid exact source SHA")
    if not isinstance(binding.get("archive_sha256"), str) or not DIGEST.fullmatch(binding["archive_sha256"]):
        raise ValueError("invalid archive digest")
    actual = sha256(archive)
    if actual != binding["archive_sha256"]:
        raise ValueError("archive byte digest mismatch")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        entries = z.infolist()
        names = [x.filename for x in entries]
        if len(entries) > MAX_MEMBERS or len(set(names)) != len(names) or not REQUIRED.issubset(names):
            raise ValueError("ZIP member census invalid")
        total = 0
        for x in entries:
            p = PurePosixPath(x.filename)
            mode = x.external_attr >> 16
            if (p.is_absolute() or ".." in p.parts or "\\" in x.filename or x.is_dir()
                    or x.flag_bits & 1 or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or p.as_posix() != x.filename
                    or x.file_size > MAX_MEMBER_BYTES):
                raise ValueError("unsafe ZIP member")
            total += x.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("ZIP expansion budget exceeded")
        data = {name: z.read(name) for name in names}  # z.read checks each member CRC
    member_sha256 = {name: sha256(data[name]) for name in sorted(names)}
    manifest = json.loads(data["manifest.json"])
    if manifest.get("schema") != "gogreen.manifest.v1" or manifest.get("authority_transfer") is not False:
        raise ValueError("invalid inner manifest contract")
    digests = manifest.get("sha256")
    if not isinstance(digests, dict) or set(digests) != {
            "evidence.json", "federation_hooks.json", "scout_packets.json", "summary.md"}:
        raise ValueError("invalid inner producer file census")
    for name, expected in digests.items():
        if not isinstance(expected, str) or not DIGEST.fullmatch(expected) or sha256(data[name]) != expected:
            raise ValueError(f"inner byte digest mismatch: {name}")
    provenance = json.loads(data["execution_provenance.json"])
    if provenance.get("schema") != "gogreen.execution-provenance.v1" or any([
            provenance.get("repository") != binding["repository"],
            provenance.get("checked_out_sha") != binding["source_sha"],
            provenance.get("run_id") != binding["run_id"],
            provenance.get("run_attempt") != binding["run_attempt"],
            provenance.get("manifest_file_sha256") != sha256(data["manifest.json"]),
            provenance.get("authority_transfer") is not False,
            provenance.get("source_claims_not_admission") is not True,
            provenance.get("execution_proof") != "EXACT_CHECKOUT_CONFIRMED",
        ]):
        raise ValueError("forged or mismatched execution provenance")
    evidence = json.loads(data["evidence.json"])
    hooks = json.loads(data["federation_hooks.json"])
    if (evidence.get("schema") != "gogreen.fleet.positive-evidence.v1"
            or evidence.get("authority_transfer") is not False
            or evidence.get("merge_authorized") is not False
            or hooks.get("authority_transfer") is not False
            or hooks.get("child_acceptance") != "DEFER"):
        raise ValueError("forbidden authority or producer schema")
    return {
        "schema": "gogreen.native-zip-byte-check.v1", "result": "PASS",
        "repository": binding["repository"], "source_sha": binding["source_sha"],
        "run_id": binding["run_id"], "run_attempt": binding["run_attempt"],
        "job_id": binding["job_id"], "artifact_id": binding["artifact_id"],
        "archive_sha256": actual, "verified_inner_files": len(digests),
        "member_sha256": member_sha256, "zip_crc_verified": True,
        "artifact_bytes_verified": True, "metadata_origin_authenticated": False,
        "native_green_admission": "HOLD", "owner_acceptance": "DEFER",
        "source_class": "OFFLINE_BYTES_WITH_CALLER_ASSERTED_METADATA",
    }

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--binding", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    receipt = verify(a.archive.read_bytes(), json.loads(a.binding.read_text()))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    main()
