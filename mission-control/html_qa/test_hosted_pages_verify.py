"""Mock-hosted parity: never claim a live URL from fixtures."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from urllib.parse import urlparse
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from hosted_pages_verify import verify,check_base,REQUIRED
BASE="https://gbogeb.github.io/pipeline-automation-hub/"
def sample(root):
    hashes={}
    for name in REQUIRED:
        if name=="site-manifest.json":continue
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text("<html>G3P</html>" if name.endswith(".html") else '{"HOLD":true}')
        hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    (root/"site-manifest.json").write_text(json.dumps({
        "schema":"codepurple.pages.readonly/v1","source_git_sha":"a"*40,
        "merge_authorized":False,"security_waiver":False,"public_files_sha256":hashes}))
def native_url(root,url):
    return root/urlparse(url).path.split("/pipeline-automation-hub/",1)[1]
class PagesHostTests(unittest.TestCase):
    def test_repeat_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sample(root)
            def fetch(u):return native_url(root,u).read_bytes(),u
            r=verify(root,BASE,repeat=2,max_attempts=2,wait_seconds=0,fetch=fetch)
            self.assertEqual(r["status"],"PASS")
            self.assertEqual(r["consecutive_matched"],2)
            self.assertTrue(r["hosted_http_verified"])
            self.assertEqual(r["merge_admission"],"HOLD")
    def test_wrong_digest_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sample(root)
            def fetch(u):
                return (b"wrong" if u.endswith("g3p/index.html") else native_url(root,u).read_bytes()),u
            r=verify(root,BASE,repeat=2,max_attempts=2,wait_seconds=0,fetch=fetch)
            self.assertEqual(r["status"],"FAIL")
            self.assertIsNone(r["published_route"])
    def test_good_then_bad_no_stability(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sample(root);calls=[0]
            def fetch(u):
                calls[0]+=1
                return (native_url(root,u).read_bytes() if calls[0]<=len(REQUIRED) else b"stale"),u
            self.assertEqual(verify(root,BASE,repeat=2,max_attempts=2,wait_seconds=0,fetch=fetch)["status"],"FAIL")
    def test_bad_host(self):
        with self.assertRaises(ValueError):check_base("https://evil.example/pipeline-automation-hub/")
    def test_http_not_allowed(self):
        with self.assertRaises(ValueError):check_base("http://gbogeb.github.io/pipeline-automation-hub/")
    def test_bad_path(self):
        with self.assertRaises(ValueError):check_base("https://gbogeb.github.io/")
    def test_bad_manifest_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sample(root)
            p=root/"site-manifest.json";m=json.loads(p.read_text())
            m["public_files_sha256"]["g3p/index.html"]="f"*64;p.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"hash"):
                verify(root,BASE,repeat=2,max_attempts=2,wait_seconds=0,fetch=lambda u:(b"",u))
    def test_unbounded_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sample(root)
            with self.assertRaisesRegex(ValueError,"repeat"):
                verify(root,BASE,max_attempts=99,fetch=lambda u:(b"",u))
if __name__=="__main__":unittest.main()
