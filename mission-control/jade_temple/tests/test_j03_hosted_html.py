"""J03 hosted-HTML pilot probe: offline, mocked host, temp git repo; UNKNOWN stays UNKNOWN."""
import contextlib, hashlib, importlib.util, json, os, shutil, subprocess, tempfile, unittest, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("j03", ROOT / "tools/j03_hosted_html.py")
j03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j03)
BASE = j03.DEFAULT_BASE
INDEX = b'<html><body><a href="a/page.html">p</a><a href="site-manifest.json">m</a></body></html>'
PAGE = b'<html><body><img src="img.png" alt="i"></body></html>'


# Temp repos can be owned by another SID on managed Windows hosts; trust them for this
# process only (GIT_CONFIG_* env, never a global config write).
_ENV = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"}
_SAVED = {}


def setUpModule():
    for k, v in _ENV.items():
        _SAVED[k] = os.environ.get(k)
        os.environ[k] = v


def tearDownModule():
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@contextlib.contextmanager
def scratch():
    # Not tempfile.TemporaryDirectory: on Windows Python >= 3.12.4 its 0o700 ACL can deny a
    # git child process; a plain mkdir keeps the test portable.
    path = Path(tempfile.gettempdir()) / ("j03-" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def h(b):
    return hashlib.sha256(b).hexdigest()


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
                           *args], check=True, capture_output=True, input=data).stdout


def make_repo(tmp):
    repo = Path(tmp) / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs/index.html").write_bytes(b"<p>docs</p>")
    (repo / "src").mkdir()
    (repo / "src/page.html").write_bytes(PAGE)
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "x")
    return repo, git(repo, "rev-parse", "HEAD").decode().strip()


class FakeHost:
    def __init__(self, sha, *, img=True, page_bytes=PAGE, manifest=True):
        self.sha = sha
        declared = {"index.html": h(INDEX), "a/page.html": h(PAGE)}
        self.files = {"": INDEX, "index.html": INDEX, "a/page.html": page_bytes}
        if manifest:
            self.files["site-manifest.json"] = json.dumps(
                {"schema": "codepurple.pages.readonly/v1", "source_git_sha": sha,
                 "public_files_sha256": declared}).encode()
        if img:
            self.files["a/img.png"] = b"png"

    def __call__(self, url):
        rel = url[len(BASE):]
        if rel in self.files:
            return 200, self.files[rel], url
        return 404, None, url


class J03Tests(unittest.TestCase):
    def run_probe(self, host_kwargs=None, dep_sha=None):
        with scratch() as tmp:
            repo, sha = make_repo(tmp)
            hv = j03.owner()
            hv.fetch_status = FakeHost(sha, **(host_kwargs or {}))
            return sha, j03.probe(BASE, {"sha": dep_sha or sha, "id": 1}, repo, hv=hv)

    def test_git_blobs_and_index(self):
        with scratch() as tmp:
            repo, sha = make_repo(tmp)
            blobs = j03.git_blobs(repo, sha)
            self.assertEqual(blobs["src/page.html"], PAGE)
            self.assertEqual(j03.sha_index(blobs)[h(PAGE)], ["src/page.html"])

    def test_clean_site_is_partial_pending_viewports(self):
        sha, r = self.run_probe()
        self.assertEqual(r["schema"], "jade.temple.j03_hosted_html.v1")
        self.assertEqual(r["served_sha"], sha)
        self.assertTrue(r["served_sha_equals_deployment_sha"])
        self.assertEqual(r["criteria"], {"http_status": "PASS", "served_sha": "PASS",
                                         "content_parity": "PASS", "asset_links": "PASS",
                                         "viewports": None})
        self.assertEqual(r["verdict"], "UNKNOWN")
        self.assertEqual(r["j03_pilot_status"], "PARTIAL")
        self.assertEqual(r["html_qa_ladder"]["level"], "PAGES_HOSTED")
        self.assertIsNone(r["html_qa_ladder"]["owner_review"])
        self.assertIsNone(r["viewports"])
        self.assertIn(BASE + "a/page.html", r["hosted_urls_passing_parity"])
        page = [x for x in r["portal"]["results"] if x["path"] == "a/page.html"][0]
        self.assertEqual(page["git_blob_paths_at_deployment"], ["src/page.html"])
        docs = r["committed_docs_html"]["results"]
        self.assertEqual([d["git_source"] for d in docs], ["docs/index.html"])
        self.assertEqual(docs[0]["parity"], "MISMATCH")  # portal index served, not docs/
        self.assertFalse(r["docs_tree_deployed"])
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_broken_asset_link_is_not_qualified(self):
        _, r = self.run_probe({"img": False})
        self.assertEqual(r["criteria"]["asset_links"], "FAIL")
        self.assertEqual(r["broken_links"], [{"page": "a/page.html", "link": "a/img.png", "status": 404}])
        self.assertEqual(r["verdict"], "NOT_QUALIFIED")
        self.assertEqual(r["j03_pilot_status"], "PENDING")
        self.assertEqual(r["html_qa_ladder"]["level"], "PAGES_HOSTED")

    def test_stale_bytes_fail_parity(self):
        _, r = self.run_probe({"page_bytes": b"stale"})
        self.assertEqual(r["criteria"]["content_parity"], "FAIL")
        self.assertEqual(r["html_qa_ladder"]["level"], "HOSTED_NOT_PROVEN")

    def test_deployment_sha_differs(self):
        _, r = self.run_probe(dep_sha="b" * 40)
        self.assertFalse(r["served_sha_equals_deployment_sha"])
        self.assertEqual(r["criteria"]["served_sha"], "FAIL")
        self.assertFalse(r["git_commit_available"])
        self.assertEqual(r["committed_docs_html"]["summary"]["paths"], 0)
        self.assertTrue(all(x["git_blob_paths_at_deployment"] is None for x in r["portal"]["results"]))

    def test_missing_manifest_served_sha_unknown(self):
        _, r = self.run_probe({"manifest": False})
        self.assertIsNone(r["served_sha"])
        self.assertIsNone(r["criteria"]["served_sha"])
        self.assertEqual(r["verdict"], "NOT_QUALIFIED")  # manifest 404 fails http_status

    def test_bad_deployment_sha_refused(self):
        with scratch() as tmp:
            repo, _ = make_repo(tmp)
            with self.assertRaises(ValueError):
                j03.probe(BASE, {"sha": "nope"}, repo, hv=j03.owner())

    def test_committed_receipt_shape(self):
        r = json.loads((ROOT / "data/J03_HOSTED_HTML_PAH_20261025.json").read_text(encoding="utf-8"))
        self.assertEqual(r["schema"], j03.SCHEMA)
        self.assertEqual(r["bd_item"], "J03")
        self.assertIsNone(r["viewports"])
        self.assertIn(r["verdict"], {"QUALIFIED", "NOT_QUALIFIED", "UNKNOWN"})
        self.assertEqual(r["deployment"]["sha"], r["served_sha"])
        self.assertEqual(r["merge_admission"], "HOLD")
        self.assertFalse(r["authority_transfer"])


if __name__ == "__main__":
    unittest.main()
