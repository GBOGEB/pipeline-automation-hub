"""G1 archive-byte integrity and forged-metadata negative controls."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
import pathlib
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_native_zip", ROOT / "verify_native_zip.py")
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)
SHA = "7b6dff9f31c5fb0937cc8ddcb8267804739e1ffc"

def fixture():
    proof = {"schema": "gogreen.execution-provenance.v1",
             "repository": "GBOGEB/pipeline-automation-hub", "checked_out_sha": SHA,
             "run_id": 38701154720, "run_attempt": 1, "execution_proof": "EXACT_CHECKOUT_CONFIRMED",
             "source_claims_not_admission": True, "authority_transfer": False}
    files = {
        "evidence.json": json.dumps({"schema": "gogreen.fleet.positive-evidence.v1",
                                     "authority_transfer": False, "merge_authorized": False}).encode(),
        "federation_hooks.json": json.dumps({"authority_transfer": False,
                                             "child_acceptance": "DEFER"}).encode(),
        "scout_packets.json": b"{}", "summary.md": b"# G1 test fixture\n",
    }
    manifest = {"schema": "gogreen.manifest.v1", "authority_transfer": False,
                "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    files["manifest.json"] = json.dumps(manifest).encode()
    proof["manifest_file_sha256"] = hashlib.sha256(files["manifest.json"]).hexdigest()
    files["execution_provenance.json"] = json.dumps(proof).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    return out.getvalue()

def binding(raw):
    return {"schema": "gogreen.external-binding.v1",
            "repository": "GBOGEB/pipeline-automation-hub", "source_sha": SHA,
            "run_id": 38701154720, "run_attempt": 1, "job_id": 116309381910,
            "artifact_id": 11955883209, "archive_sha256": hashlib.sha256(raw).hexdigest()}

def rewrite(raw, replacements):
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in src.namelist():
            z.writestr(name, replacements.get(name, src.read(name)))
    return out.getvalue()

class G1ZipTests(unittest.TestCase):
    def test_synthetic_archive_is_accepted_as_bytes_not_native_admission(self):
        raw = fixture()
        result = V.verify(raw, binding(raw))
        self.assertTrue(result["artifact_bytes_verified"])
        self.assertFalse(result["metadata_origin_authenticated"])
        self.assertEqual("HOLD", result["native_green_admission"])

    def test_wrong_trusted_zip_digest_rejected(self):
        raw = fixture()
        b = binding(raw)
        b["archive_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "archive byte digest"):
            V.verify(raw, b)

    def test_wrong_source_sha_rejected(self):
        raw = fixture()
        b = binding(raw)
        b["source_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "execution provenance"):
            V.verify(raw, b)

    def test_wrong_run_rejected(self):
        raw = fixture()
        b = binding(raw)
        b["run_id"] = 1
        with self.assertRaisesRegex(ValueError, "execution provenance"):
            V.verify(raw, b)

    def test_manifest_tamper_rehashed_zip_rejected(self):
        raw = fixture()
        edited = rewrite(raw, {"summary.md": b"FORGED"})
        with self.assertRaisesRegex(ValueError, "inner byte digest"):
            V.verify(edited, binding(edited))

    def test_forged_provenance_rehashed_zip_rejected(self):
        raw = fixture()
        src = zipfile.ZipFile(io.BytesIO(raw))
        p = json.loads(src.read("execution_provenance.json"))
        p["checked_out_sha"] = "0" * 40
        edited = rewrite(raw, {"execution_provenance.json": json.dumps(p).encode()})
        with self.assertRaisesRegex(ValueError, "execution provenance"):
            V.verify(edited, binding(edited))

    def test_duplicate_archive_entry_rejected(self):
        raw = fixture()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            with zipfile.ZipFile(io.BytesIO(raw)) as src:
                for n in src.namelist():
                    z.writestr(n, src.read(n))
                z.writestr("summary.md", b"OVERRIDE")
        edited = out.getvalue()
        with self.assertRaisesRegex(ValueError, "member census"):
            V.verify(edited, binding(edited))

    def test_authority_forgery_rehashed_inner_manifest_rejected(self):
        raw = fixture()
        src = zipfile.ZipFile(io.BytesIO(raw))
        h = json.loads(src.read("federation_hooks.json"))
        h["child_acceptance"] = "ACCEPT"
        changed = json.dumps(h).encode()
        m = json.loads(src.read("manifest.json"))
        m["sha256"]["federation_hooks.json"] = hashlib.sha256(changed).hexdigest()
        new_manifest = json.dumps(m).encode()
        p = json.loads(src.read("execution_provenance.json"))
        p["manifest_file_sha256"] = hashlib.sha256(new_manifest).hexdigest()
        edited = rewrite(raw, {"federation_hooks.json": changed, "manifest.json": new_manifest,
                               "execution_provenance.json": json.dumps(p).encode()})
        with self.assertRaisesRegex(ValueError, "forbidden authority"):
            V.verify(edited, binding(edited))

if __name__ == "__main__":
    unittest.main()
