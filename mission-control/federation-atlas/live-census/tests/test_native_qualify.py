"""Negative/positive controls for the five-source authenticated receiver."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
import live_census as census
from native_qualify import qualify

DATA = ROOT / "data" / "observed_fixture.json"
HEAD = "a" * 40


def synthetic_bundle(directory, *, origin="NATIVE_GITHUB_READ"):
    fixture = json.loads(DATA.read_text(encoding="utf-8"))
    s = census.build(fixture)
    s["origin"] = origin
    s["observation_quality"] = "NATIVE_READ_ONLY_NOT_ARTIFACT_VERIFIED"
    for row in s["repositories"]:
        if row["name"] == "pipeline-automation-hub":
            row["sha"] = HEAD
    # The file bundle is synthetic and test-local; never counted as native.
    return census.write_outputs(s, directory)


class QualifyFiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        synthetic_bundle(self.folder)

    def call(self, sha=HEAD):
        return qualify(self.folder, expected_master=sha, run_id=321, attempt=1)

    def test_synthetic_positive_contract_never_claims_six_or_admission(self):
        q = self.call()
        self.assertEqual(q["member_count"], 5)
        self.assertEqual(len(q["rechecked_repositories"]), 5)
        self.assertIsNone(q["six_repo_canonical_breadth"])
        self.assertIsNone(q["accepted_causal_root_closures"])
        self.assertEqual(q["merge_admission"], "HOLD")

    def test_offline_fixture_cannot_promote(self):
        synthetic_bundle(self.folder, origin="OFFLINE_FIXTURE")
        with self.assertRaisesRegex(ValueError, "not native"):
            self.call()

    def test_wrong_master_head_rejected(self):
        with self.assertRaisesRegex(ValueError, "head changed"):
            self.call("b" * 40)

    def test_missing_member_rejected(self):
        (self.folder / "edges.json").unlink()
        with self.assertRaisesRegex(ValueError, "member digest"):
            self.call()

    def test_tampered_member_rejected(self):
        (self.folder / "nodes.json").write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "member digest"):
            self.call()

    def test_manifest_digest_forgery_rejected(self):
        f = self.folder / "manifest.json"
        m = json.loads(f.read_text(encoding="utf-8"))
        m["source_digest"] = "b" * 64
        f.write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source/manifest"):
            self.call()

    def test_authority_forgery_rejected(self):
        f = self.folder / "snapshot.json"
        s = json.loads(f.read_text(encoding="utf-8"))
        s["authority"]["merge_authorized"] = True
        f.write_text(json.dumps(s), encoding="utf-8")
        m = json.loads((self.folder / "manifest.json").read_text())
        m["files_sha256"]["snapshot.json"] = hashlib.sha256(
            f.read_bytes()).hexdigest()
        (self.folder / "manifest.json").write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "authority"):
            self.call()

    def test_run_attempt_is_required(self):
        with self.assertRaisesRegex(ValueError, "run/attempt"):
            qualify(self.folder, expected_master=HEAD, run_id=321, attempt=0)


if __name__ == "__main__":
    unittest.main()
