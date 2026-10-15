"""Source-owned side-load Atlas GUI: positive, negative and identity controls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sideload_k8s


class SideloadK8sGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(sideload_k8s.SOURCE.read_text())

    def test_three_repos_eight_assets(self):
        s = copy.deepcopy(self.source)
        sideload_k8s.validate(s)
        self.assertEqual(len(s["adapters"]), 3)
        self.assertEqual(len(s["rows"]), 8)

    def test_native_runtime_unknown_not_zero(self):
        for x in ("authenticated_four_hop_receipts", "real_k8s_runtime_sessions",
                  "matched_coverage_delta"):
            self.assertIsNone(self.source["measurements"][x])

    def test_reject_fake_merge(self):
        d = copy.deepcopy(self.source)
        d["adapters"][0]["state"] = "MERGED"
        with self.assertRaisesRegex(ValueError, "candidate adapter"):
            sideload_k8s.validate(d)

    def test_reject_fake_workload_or_root_closure(self):
        d = copy.deepcopy(self.source)
        d["rows"][0]["workload_verified"] = True
        with self.assertRaisesRegex(ValueError, "native/cluster"):
            sideload_k8s.validate(d)
        d = copy.deepcopy(self.source)
        d["measurements"]["root_closures_credited"] = 1
        with self.assertRaisesRegex(ValueError, "closed a root"):
            sideload_k8s.validate(d)

    def test_reject_invalid_source_sha_or_locator(self):
        d = copy.deepcopy(self.source)
        d["rows"][0]["source_sha"] = "short"
        with self.assertRaisesRegex(ValueError, "kind/SHA"):
            sideload_k8s.validate(d)
        d = copy.deepcopy(self.source)
        d["rows"][0]["source_url"] = "https://example.invalid/"
        with self.assertRaisesRegex(ValueError, "untrusted"):
            sideload_k8s.validate(d)

    def test_reject_unknown_population_and_authority(self):
        d = copy.deepcopy(self.source)
        d["rows"].pop()
        with self.assertRaisesRegex(ValueError, "population"):
            sideload_k8s.validate(d)
        d = copy.deepcopy(self.source)
        d["gates"]["engineering_credit_delta"] = 1
        with self.assertRaisesRegex(ValueError, "authority"):
            sideload_k8s.validate(d)

    def test_deterministic_build_and_manifest(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ma, mb = sideload_k8s.build(a), sideload_k8s.build(b)
            self.assertEqual(ma, mb)
            p = Path(a)
            manifest = json.loads((p / "sideload-k8s.sha256.json").read_text())
            for path, digest in manifest["files"].items():
                source = (p / path).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), digest)
                self.assertEqual(source, (Path(b) / path).read_bytes())
            content = (p / "sideload-k8s.html").read_text()
            for tag in ('id="repo"', 'id="kind"', 'id="query"',
                        'data-repo="DOW"', 'data-repo="KEB"', 'data-repo="QPS"'):
                self.assertIn(tag, content)

    def test_global_feedback_only_next_pulse(self):
        with tempfile.TemporaryDirectory() as t:
            sideload_k8s.build(t)
            source = (Path(t) / "sideload-k8s.mmd").read_text()
            self.assertIn("next pulse only", source)
