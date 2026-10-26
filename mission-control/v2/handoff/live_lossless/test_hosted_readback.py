"""Mock HTTP parity tests; fixtures never establish real public deployment."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

import build_live_lossless
import hosted_readback as hosted

sys.path.insert(0,str(build_live_lossless.ROOT/"mission-control/federation-atlas"))
import pages_portal

URL="https://gbogeb.github.io/pipeline-automation-hub/"


def site(root):
    atlas=root/"atlas"
    atlas.mkdir(parents=True)
    (atlas/"index.html").write_text("<html><head><title>QA</title></head><body><h1>Atlas</h1></body></html>", encoding="utf-8", newline="\n")
    build_live_lossless.build(atlas/"live-lossless")
    result=pages_portal.build(atlas,root/"public","a"*40)
    return root/"public",result


def fetcher(root,corrupt=None,redirect=False):
    def fetch(url):
        rel=urlparse(url).path.split("/pipeline-automation-hub/",1)[1]
        response=(root/rel).read_bytes()
        if corrupt==rel:response=b"stale"
        return response,("https://evil.example/" if redirect else url)
    return fetch


class HostedLiveLosslessTests(unittest.TestCase):
    def test_repeated_exact_sha_matching(self):
        with tempfile.TemporaryDirectory() as d:
            p,manifest=site(Path(d))
            receipt=hosted.verify(p,URL,repeat=2,attempts=2,wait=0,fetch=fetcher(p))
            self.assertEqual(receipt["state"],"PASS")
            self.assertTrue(receipt["hosted_verified"])
            self.assertEqual(receipt["source_git_sha"],"a"*40)
            self.assertEqual(receipt["consecutive_full_matches"],2)
            self.assertFalse(receipt["authority_transfer"])
    def test_changed_hosted_snapshot_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=site(Path(d))
            outcome=hosted.verify(p,URL,repeat=2,attempts=2,wait=0,fetch=fetcher(p,"live-lossless/snapshot.json"))
            self.assertEqual(outcome["state"],"FAIL")
            self.assertIsNone(outcome["url"])
    def test_open_redirect_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=site(Path(d))
            self.assertEqual(hosted.verify(p,URL,2,2,0,fetcher(p,redirect=True))["state"],"FAIL")
    def test_wrong_site_origin_fails(self):
        with self.assertRaisesRegex(ValueError,"HOST_GUARD"):
            hosted.check_host("https://example.com/pipeline-automation-hub/")
    def test_http_insecure_fails(self):
        with self.assertRaises(ValueError):
            hosted.check_host("http://gbogeb.github.io/pipeline-automation-hub/")
    def test_subpath_route_cannot_be_requested_as_site_root(self):
        with self.assertRaises(ValueError):
            hosted.check_host("https://gbogeb.github.io/pipeline-automation-hub/live-lossless/")
    def test_candidate_manifest_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=site(Path(d));manifest=p/"site-manifest.json"
            d0=json.loads(manifest.read_text(encoding="utf-8"));d0["public_files_sha256"]["live-lossless/index.html"]="f"*64
            manifest.write_text(json.dumps(d0), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError,"site-manifest hash mismatch"):
                hosted.verify(p,URL,2,2,0,fetcher(p))
    def test_repeated_limit_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=site(Path(d))
            with self.assertRaises(ValueError):
                hosted.verify(p,URL,repeat=2,attempts=300,wait=0,fetch=fetcher(p))
    def test_no_compensating_merge_or_qps_credit(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=site(Path(d))
            result=hosted.verify(p,URL,2,2,0,fetcher(p))
            self.assertEqual(result["merge_admission"],"HOLD")
            self.assertNotIn("engineering_accepted",result)

if __name__=="__main__":
    unittest.main()
