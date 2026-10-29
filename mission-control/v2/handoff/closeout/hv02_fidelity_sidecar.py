#!/usr/bin/env python3
"""HV-02: additive, fail-closed fidelity metadata validation for CP.CLOSE.

Never produces conversation text, grants merge approval, or claims that a
user-supplied export is provider-attested. Existing CP.CLOSE/ABACUS V2 formats
are not altered. Source and artifact bytes are supplied locally, never fetched.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SCHEMA = "gbo.handover.fidelity-sidecar-instance.v1"
STATES = {"VERIFIED", "SOURCE_DECLARED", "PARTIAL", "UNKNOWN", "UNAVAILABLE", "STALE", "DENIED"}
SOURCES = {"GITHUB_OBSERVED", "AUTHORIZED_EXPORT", "USER_SUPPLIED", "RECONSTRUCTED", "UNKNOWN"}
SCOPES = {"CURRENT_VISIBLE", "AUTHORIZED_EXPORT", "SANITIZED_SUBSET", "UNKNOWN"}
COMPLETENESS = {"VERIFIED_PROVIDER_ATTESTED", "USER_DECLARED", "PARTIAL", "UNKNOWN"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,80}$")
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")
SECRET = re.compile(
    r"(?i)(ghp_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|"
    r"sk-proj-[a-z0-9_-]{20,}|authorization\s*:\s*bearer\s+\S+|"
    r"[?&](?:token|access_token|sig|signature|x-amz-signature)=)"
)
PRIVATE_KEYS = {"messages", "message_text", "raw_transcript", "raw_messages",
                "conversation_text", "password", "api_key", "private_reasoning",
                "secret", "credential", "access_token"}

def fail(reason: str) -> None:
    raise ValueError("HV02_HOLD: " + reason)

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def validate_metadata_tree(obj: object) -> None:
    """Forbid raw-message payloads and credential-bearing strings at any depth."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str) or key.lower() in PRIVATE_KEYS:
                fail("raw/private content field")
            validate_metadata_tree(value)
    elif isinstance(obj, list):
        for value in obj:
            validate_metadata_tree(value)
    elif isinstance(obj, str) and SECRET.search(obj):
        fail("credential or signed URL")

def is_sha(value: object) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None

def check_utc(value: object) -> bool:
    if value == "UNKNOWN":
        return True
    if not isinstance(value, str):
        return False
    try:
        time = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return time.tzinfo is not None and time.utcoffset() == timezone.utc.utcoffset(time)
    except ValueError:
        return False

def public_locator(value: object) -> bool:
    if value == "UNKNOWN":
        return True
    if not isinstance(value, str):
        return False
    p = urlsplit(value)
    return (p.scheme == "https" and p.netloc.lower() == "github.com"
            and p.path.startswith("/GBOGEB/") and not p.username
            and not p.password and not p.query and not p.fragment)

def validate(obj: dict, *, source_bytes: bytes | None = None,
             artifact_bytes: dict[str, bytes] | None = None,
             public: bool = True) -> dict:
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        fail("sidecar instance schema")
    validate_metadata_tree(obj)
    required = {"session_alias", "capture_utc", "source_class", "source_locator",
                "source_sha256", "source_state", "scope", "completeness",
                "message_count", "artifact_refs", "evidence",
                "merge_admission", "authority_transfer"}
    if not required.issubset(obj):
        fail("required metadata absent")
    if not isinstance(obj["session_alias"], str) or not ALIAS.fullmatch(obj["session_alias"]):
        fail("session alias")
    if not check_utc(obj["capture_utc"]):
        fail("UTC timestamp")
    if obj["source_class"] not in SOURCES or obj["scope"] not in SCOPES:
        fail("invalid source class/scope")
    if obj["completeness"] not in COMPLETENESS or obj["source_state"] not in STATES:
        fail("invalid fidelity/source state")
    if obj["merge_admission"] != "HOLD" or obj["authority_transfer"] is not False:
        fail("cannot grant authority")
    if public and not public_locator(obj["source_locator"]):
        fail("unapproved public locator")
    if not isinstance(obj["source_locator"], str) or not obj["source_locator"]:
        fail("missing locator")
    if obj["completeness"] == "VERIFIED_PROVIDER_ATTESTED":
        fail("provider-level completeness not supported by this validator")
    if obj["source_class"] == "RECONSTRUCTED" and obj["completeness"] == "USER_DECLARED":
        fail("reconstructed context is not a declared transcript")
    sha = obj["source_sha256"]
    if sha is not None and not is_sha(sha):
        fail("invalid source digest")
    if obj["source_state"] == "VERIFIED":
        if sha is None or source_bytes is None or digest(source_bytes) != sha:
            fail("source bytes not independently matched")
    if source_bytes is not None and sha is not None and digest(source_bytes) != sha:
        fail("source digest mismatch")
    count = obj["message_count"]
    refs = obj.get("message_refs")
    if count is not None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            fail("invalid message count")
        if (obj["source_class"] != "AUTHORIZED_EXPORT" or obj["scope"] != "AUTHORIZED_EXPORT"
                or obj["completeness"] != "USER_DECLARED"
                or obj["source_state"] != "VERIFIED" or source_bytes is None):
            fail("unverified message population")
        if not isinstance(refs, list) or len(refs) != count or len(set(refs)) != count:
            fail("message population references")
        if any(not isinstance(r, str) or not IDENTITY.fullmatch(r) for r in refs):
            fail("unsafe message reference")
    elif refs not in (None, []):
        fail("message refs without count")
    if not isinstance(obj["artifact_refs"], list) or not isinstance(obj["evidence"], list):
        fail("artifact/evidence list")
    seen = set()
    for item in obj["artifact_refs"]:
        if not isinstance(item, dict) or not {"id", "media_type", "bytes", "sha256",
                "custody", "access_class", "state"}.issubset(item):
            fail("artifact record shape")
        id_ = item["id"]
        if not isinstance(id_, str) or not IDENTITY.fullmatch(id_) or id_ in seen:
            fail("unsafe/duplicate artifact id")
        seen.add(id_)
        if item["state"] not in STATES or item["access_class"] not in {"PRIVATE", "PUBLIC_APPROVED"}:
            fail("artifact state/access")
        if not isinstance(item["media_type"], str) or "/" not in item["media_type"]:
            fail("artifact media type")
        if item["custody"] not in {"LOCAL_PRIVATE", "AUTHORIZED_VAULT", "UNKNOWN"}:
            fail("artifact custody")
        n, h = item["bytes"], item["sha256"]
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 0):
            fail("artifact byte length")
        if h is not None and not is_sha(h):
            fail("artifact digest")
        if item["state"] == "VERIFIED":
            b = (artifact_bytes or {}).get(id_)
            if not isinstance(b, bytes) or n != len(b) or h != digest(b):
                fail("artifact bytes not verified")
        elif (artifact_bytes or {}).get(id_) is not None:
            b = artifact_bytes[id_]
            if h is not None and digest(b) != h:
                fail("artifact hash mismatch")
    for event in obj["evidence"]:
        if not isinstance(event, dict) or event.get("state") not in STATES:
            fail("evidence state")
        if event["state"] == "STALE" and obj.get("merge_admission") != "HOLD":
            fail("stale evidence cannot admit")
        if "run_sha" in event and event["run_sha"] is not None:
            if not isinstance(event["run_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", event["run_sha"]):
                fail("run source SHA")
        if event.get("state") == "VERIFIED":
            fail("independently authenticated run evidence unsupported here")
    return {
        "schema": SCHEMA,
        "source_state": obj["source_state"],
        "completeness": obj["completeness"],
        "message_count": count,
        "artifacts_declared": len(obj["artifact_refs"]),
        "artifacts_verified": sum(a["state"] == "VERIFIED" for a in obj["artifact_refs"]),
        "merge_admission": "HOLD",
        "verbatim_completeness_attested": False,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate local HV-02 fidelity sidecar; no network or publish")
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-file", type=Path, help="Explicit private input bytes; never emitted")
    parser.add_argument("--artifact-root", type=Path, help="Private local byte directory keyed by artifact id")
    parser.add_argument("--private", action="store_true", help="Allow private locator only for local validation")
    args = parser.parse_args(argv)
    obj = json.loads(args.sidecar.read_text(encoding="utf-8"))
    asset_bytes = {}
    if args.artifact_root:
        root = args.artifact_root.resolve(strict=True)
        for item in obj.get("artifact_refs", []):
            if item.get("state") == "VERIFIED":
                name = item.get("id", "")
                if not isinstance(name, str) or not IDENTITY.fullmatch(name):
                    fail("artifact unsafe filename")
                path = root / name
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    fail("artifact path escape")
                asset_bytes[name] = path.read_bytes()
    source = args.source_file.read_bytes() if args.source_file else None
    receipt = validate(obj, source_bytes=source, artifact_bytes=asset_bytes, public=not args.private)
    print(json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc))
