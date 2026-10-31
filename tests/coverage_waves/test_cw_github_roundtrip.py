"""Coverage wave: behavioural tests for mission-control/golden-thread/github_roundtrip.py.

Targets the GitHub Git-data client, the remote round-trip, the truth loader and
the CLI. All network traffic goes to an in-memory fake GitHub; no real token.
"""
import base64
import hashlib
import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "mission-control" / "golden-thread"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
_SPEC = importlib.util.spec_from_file_location("cw_github_roundtrip", MODULE_DIR / "github_roundtrip.py")
gr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gr)

TRUTH = {
    "schema": "missioncontrol.test_truth.v1",
    "semantic_generation_k": 3,
    "event_sequence_e": 9,
    "values": {"alpha": 1, "beta": [2, 3]},
    "authority_transfer": False,
}
SOURCE_SHA = "1" * 40
SOURCE_TREE = "2" * 40
TIMESTAMP = "2026-10-26T00:00:00Z"


class FakeResponse:
    def __init__(self, obj):
        self._raw = json.dumps(obj).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeGitHub:
    """Minimal in-memory GitHub Git-data API."""

    def __init__(self):
        self.requests = []
        self.blobs = {}
        self.trees = {}
        self.commits = {SOURCE_SHA: {"sha": SOURCE_SHA, "tree": {"sha": SOURCE_TREE}}}
        # Hooks to inject faults.
        self.commit_tree_override = None
        self.tree_mutator = None
        self.blob_mutator = None

    def __call__(self, req, timeout=None):
        url = req.full_url
        prefix = "https://api.github.com/repos/GBOGEB/demo"
        assert url.startswith(prefix), url
        path = url[len(prefix):]
        method = req.get_method()
        body = json.loads(req.data.decode("utf-8")) if req.data else None
        self.requests.append((method, path, body, timeout, dict(req.header_items())))
        if method == "GET" and path.startswith("/git/commits/"):
            sha = path.rsplit("/", 1)[1]
            commit = dict(self.commits[sha])
            if sha != SOURCE_SHA and self.commit_tree_override:
                commit["tree"] = {"sha": self.commit_tree_override}
            return FakeResponse(commit)
        if method == "POST" and path == "/git/blobs":
            assert body["encoding"] == "base64"
            data = base64.b64decode(body["content"])
            sha = hashlib.sha1(data).hexdigest()
            self.blobs[sha] = data
            return FakeResponse({"sha": sha})
        if method == "POST" and path == "/git/trees":
            sha = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
            entries = [{"path": e["path"], "sha": e["sha"], "type": e["type"], "mode": e["mode"]} for e in body["tree"]]
            entries.append({"path": "README.md", "sha": "f" * 40, "type": "blob", "mode": "100644"})
            self.trees[sha] = entries
            return FakeResponse({"sha": sha})
        if method == "POST" and path == "/git/commits":
            sha = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
            self.commits[sha] = {"sha": sha, "tree": {"sha": body["tree"]}}
            return FakeResponse({"sha": sha})
        if method == "GET" and path.startswith("/git/trees/"):
            sha = path[len("/git/trees/"):].split("?", 1)[0]
            assert path.endswith("?recursive=1")
            entries = [dict(e) for e in self.trees[sha]]
            if self.tree_mutator:
                entries = self.tree_mutator(entries)
            return FakeResponse({"sha": sha, "tree": entries})
        if method == "GET" and path.startswith("/git/blobs/"):
            sha = path.rsplit("/", 1)[1]
            data = self.blobs[sha]
            if self.blob_mutator:
                data = self.blob_mutator(data)
            enc = base64.b64encode(data).decode("ascii")
            wrapped = "\n".join(enc[i:i + 60] for i in range(0, len(enc), 60))
            return FakeResponse({"sha": sha, "encoding": "base64", "content": wrapped})
        raise AssertionError(f"unexpected request {method} {path}")


@pytest.fixture
def fake_github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(gr.urllib.request, "urlopen", fake)
    return fake


# --- pure helpers ---------------------------------------------------------

def test_sha256_bytes_prefix_and_digest():
    assert gr.sha256_bytes(b"abc") == "sha256:" + hashlib.sha256(b"abc").hexdigest()


@pytest.mark.parametrize("fmt", ["odt", "", "DOCX"])
def test_minimal_office_rejects_unsupported_format(fmt):
    with pytest.raises(gr.RoundTripError, match="^unsupported Office format: " + fmt + "$"):
        gr._minimal_office(fmt)


@pytest.mark.parametrize("fmt,main", [("docx", "word/document.xml"), ("xlsx", "xl/workbook.xml"), ("pptx", "ppt/presentation.xml")])
def test_minimal_office_packages_have_fixed_parts_and_dates(fmt, main):
    import zipfile

    data = gr._minimal_office(fmt)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == sorted(["[Content_Types].xml", "_rels/.rels", main])
        assert all(i.date_time == gr.FIXED_ZIP_DT for i in zf.infolist())
        assert ("/" + main).encode() in zf.read("[Content_Types].xml")
    assert gr._minimal_office(fmt) == data


# --- GitHubGitData.request -------------------------------------------------

def test_request_sends_authenticated_json_and_parses_response(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["req"] = req
        seen["timeout"] = timeout
        return FakeResponse({"ok": True})

    monkeypatch.setattr(gr.urllib.request, "urlopen", fake_urlopen)
    api = gr.GitHubGitData("GBOGEB/demo", "test-token")
    assert api.base == "https://api.github.com/repos/GBOGEB/demo"
    out = api.request("POST", "/git/x", {"k": 1})
    assert out == {"ok": True}
    req = seen["req"]
    assert seen["timeout"] == 30
    assert req.full_url == "https://api.github.com/repos/GBOGEB/demo/git/x"
    assert req.get_method() == "POST"
    assert json.loads(req.data) == {"k": 1}
    headers = dict(req.header_items())
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["X-github-api-version"] == "2022-11-28"
    assert headers["User-agent"] == "GBOGEB-Golden-Thread-P2"


def test_request_without_payload_sends_no_body(monkeypatch):
    seen = {}
    monkeypatch.setattr(gr.urllib.request, "urlopen", lambda req, timeout=None: seen.setdefault("r", req) and FakeResponse({}))
    gr.GitHubGitData("GBOGEB/demo", "test-token").request("GET", "/git/y")
    assert seen["r"].data is None
    assert seen["r"].get_method() == "GET"


def test_request_http_error_becomes_roundtrip_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b"no such \xffobject"))

    monkeypatch.setattr(gr.urllib.request, "urlopen", boom)
    api = gr.GitHubGitData("GBOGEB/demo", "test-token")
    with pytest.raises(gr.RoundTripError) as info:
        api.request("GET", "/git/commits/abc")
    assert str(info.value) == "GitHub API GET /git/commits/abc failed 404: no such �object"
    assert isinstance(info.value.__cause__, urllib.error.HTTPError)


# --- GitHubGitData verbs --------------------------------------------------

def test_create_blob_tree_commit_payloads(monkeypatch):
    calls = []

    def fake_request(self, method, path, payload=None):
        calls.append((method, path, payload))
        return {"sha": "s%d" % len(calls)}

    monkeypatch.setattr(gr.GitHubGitData, "request", fake_request)
    api = gr.GitHubGitData("GBOGEB/demo", "test-token")
    assert api.create_blob(b"hi") == "s1"
    assert calls[0] == ("POST", "/git/blobs", {"content": base64.b64encode(b"hi").decode(), "encoding": "base64"})
    assert api.create_tree("base", {"b.txt": "B", "a.txt": "A"}) == "s2"
    payload = calls[1][2]
    assert payload["base_tree"] == "base"
    assert [e["path"] for e in payload["tree"]] == [gr.ROUNDTRIP_PREFIX + "/a.txt", gr.ROUNDTRIP_PREFIX + "/b.txt"]
    assert all(e["mode"] == "100644" and e["type"] == "blob" for e in payload["tree"])
    assert api.create_commit("T", "P", TIMESTAMP) == "s3"
    commit = calls[2][2]
    assert commit["tree"] == "T" and commit["parents"] == ["P"]
    assert commit["author"] == commit["committer"]
    assert commit["author"]["date"] == TIMESTAMP


def test_get_commit_and_tree_paths(monkeypatch):
    calls = []
    monkeypatch.setattr(gr.GitHubGitData, "request", lambda self, m, p, payload=None: calls.append((m, p)) or {"x": 1})
    api = gr.GitHubGitData("GBOGEB/demo", "test-token")
    assert api.get_commit("abc") == {"x": 1}
    assert api.get_tree("def") == {"x": 1}
    assert calls == [("GET", "/git/commits/abc"), ("GET", "/git/trees/def?recursive=1")]


def test_get_blob_decodes_wrapped_base64(monkeypatch):
    enc = base64.b64encode(b"payload-bytes" * 10).decode()
    wrapped = enc[:20] + "\n" + enc[20:]
    monkeypatch.setattr(gr.GitHubGitData, "request", lambda self, m, p, payload=None: {"encoding": "base64", "content": wrapped})
    assert gr.GitHubGitData("GBOGEB/demo", "test-token").get_blob("s") == b"payload-bytes" * 10


@pytest.mark.parametrize("obj", [{"encoding": "utf-8", "content": "x"}, {"content": "eA=="}])
def test_get_blob_rejects_non_base64_encoding(monkeypatch, obj):
    monkeypatch.setattr(gr.GitHubGitData, "request", lambda self, m, p, payload=None: obj)
    with pytest.raises(gr.RoundTripError, match="^GitHub blob encoding is not base64$"):
        gr.GitHubGitData("GBOGEB/demo", "test-token").get_blob("s")


# --- remote_roundtrip -----------------------------------------------------

def test_remote_roundtrip_pass_receipt(fake_github):
    receipt = gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)
    files, manifest = gr.build_bundle(TRUTH)
    assert receipt["status"] == "PASS"
    assert receipt["schema"] == gr.SCHEMA
    assert receipt["source_tree_sha"] == SOURCE_TREE
    assert receipt["source_commit_sha"] == SOURCE_SHA
    assert set(receipt["blob_shas"]) == set(files)
    for name, sha in receipt["blob_shas"].items():
        assert fake_github.blobs[sha] == files[name]
    assert receipt["roundtrip_tree_sha"] in fake_github.trees
    assert fake_github.commits[receipt["roundtrip_commit_sha"]]["tree"]["sha"] == receipt["roundtrip_tree_sha"]
    assert receipt["local_bundle_digest"] == manifest["bundle_digest"]
    assert receipt["canonical_truth_digest"] == gr.gt.digest(TRUTH)
    assert receipt["rendition_count"] == 7
    assert receipt["ref_updated"] is False and receipt["authority_transfer"] is False
    body = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    assert receipt["receipt_digest"] == gr.gt.digest(body)
    methods = [r[0] + " " + r[1].split("/")[2] for r in fake_github.requests]
    assert methods.count("POST blobs") == 7 and methods.count("GET blobs") == 7
    # No ref endpoint was ever touched.
    assert not any("/git/refs" in r[1] for r in fake_github.requests)
    assert all(r[3] == 30 for r in fake_github.requests)


def test_remote_roundtrip_is_content_addressed_idempotent(fake_github):
    a = gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)
    b = gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)
    assert a == b


def test_remote_roundtrip_local_preflight_failure(monkeypatch, fake_github):
    monkeypatch.setattr(gr, "verify_bundle", lambda truth, files: {"status": "FAIL"})
    with pytest.raises(gr.RoundTripError, match="^local preflight rendition verification failed$"):
        gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)
    assert fake_github.requests == []


def test_remote_roundtrip_remote_semantic_failure(monkeypatch, fake_github):
    real = gr.verify_bundle
    calls = []

    def second_fails(truth, files):
        calls.append(1)
        out = real(truth, files)
        if len(calls) == 2:
            out["status"] = "FAIL"
        return out

    monkeypatch.setattr(gr, "verify_bundle", second_fails)
    with pytest.raises(gr.RoundTripError, match="^remote post-roundtrip semantic verification failed$"):
        gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)
    assert len(calls) == 2


def test_remote_roundtrip_commit_tree_mismatch(fake_github):
    fake_github.commit_tree_override = "9" * 40
    with pytest.raises(gr.RoundTripError, match="^remote commit tree identity mismatch$"):
        gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)


def _drop(name):
    return lambda entries: [e for e in entries if not e["path"].endswith("/" + name)]


def _alter(name, key, value):
    def mutate(entries):
        for e in entries:
            if e["path"].endswith("/" + name):
                e[key] = value
        return entries
    return mutate


@pytest.mark.parametrize(
    "mutator,name",
    [
        (_drop("GOLDEN_THREAD_TRUTH.docx"), "GOLDEN_THREAD_TRUTH.docx"),
        (_alter("GOLDEN_THREAD_TRUTH.html", "sha", "0" * 40), "GOLDEN_THREAD_TRUTH.html"),
        (_alter("GOLDEN_THREAD_TRUTH.json", "type", "tree"), "GOLDEN_THREAD_TRUTH.json"),
    ],
)
def test_remote_roundtrip_tree_identity_mismatch(fake_github, mutator, name):
    fake_github.tree_mutator = mutator
    with pytest.raises(gr.RoundTripError) as info:
        gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)
    assert str(info.value) == "tree/blob identity mismatch for " + name


def test_remote_roundtrip_tree_without_entries(fake_github):
    fake_github.tree_mutator = lambda entries: []
    with pytest.raises(gr.RoundTripError, match="^tree/blob identity mismatch for GOLDEN_THREAD_TRUTH.docx$"):
        gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)


def test_remote_roundtrip_blob_byte_mismatch(fake_github):
    fake_github.blob_mutator = lambda data: data + b"\n"
    with pytest.raises(gr.RoundTripError, match="^GitHub blob byte round-trip mismatch for GOLDEN_THREAD_TRUTH.docx$"):
        gr.remote_roundtrip(TRUTH, "GBOGEB/demo", SOURCE_SHA, "test-token", TIMESTAMP)


# --- _load_truth ----------------------------------------------------------

def test_load_truth_object(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps(TRUTH), encoding="utf-8")
    assert gr._load_truth(p) == TRUTH


@pytest.mark.parametrize("value", [[1, 2], "s", 3, None])
def test_load_truth_rejects_non_object(tmp_path, value):
    p = tmp_path / "t.json"
    p.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(gr.RoundTripError, match="^truth must be a JSON object$"):
        gr._load_truth(p)


# --- main -----------------------------------------------------------------

@pytest.fixture
def truth_file(tmp_path):
    p = tmp_path / "truth.json"
    p.write_text(json.dumps(TRUTH), encoding="utf-8")
    return p


def test_main_build_local_writes_bundle_and_reports(tmp_path, truth_file, capsys):
    outdir = tmp_path / "nested" / "out"
    assert gr.main(["build-local", str(truth_file), str(outdir)]) == 0
    files, manifest = gr.build_bundle(TRUTH)
    assert sorted(p.name for p in outdir.iterdir()) == sorted(files)
    for name, data in files.items():
        assert (outdir / name).read_bytes() == data
    out = json.loads(capsys.readouterr().out)
    assert out["manifest"] == manifest
    assert out["verification"]["status"] == "PASS"


def test_main_roundtrip_missing_token(truth_file, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    rc = gr.main(["roundtrip", str(truth_file), "--repo", "GBOGEB/demo", "--source-sha", SOURCE_SHA, "--timestamp", TIMESTAMP])
    assert rc == 2
    assert capsys.readouterr().err == "FAIL: missing token environment variable GITHUB_TOKEN\n"


def test_main_roundtrip_custom_token_env_empty(truth_file, monkeypatch, capsys):
    monkeypatch.setenv("CW_EMPTY_TOKEN", "")
    rc = gr.main(["roundtrip", str(truth_file), "--repo", "GBOGEB/demo", "--source-sha", SOURCE_SHA,
                  "--timestamp", TIMESTAMP, "--token-env", "CW_EMPTY_TOKEN"])
    assert rc == 2
    assert "missing token environment variable CW_EMPTY_TOKEN" in capsys.readouterr().err


def test_main_roundtrip_writes_out(tmp_path, truth_file, monkeypatch, fake_github, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    out = tmp_path / "receipt.json"
    rc = gr.main(["roundtrip", str(truth_file), "--repo", "GBOGEB/demo", "--source-sha", SOURCE_SHA,
                  "--timestamp", TIMESTAMP, "--out", str(out)])
    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert written == printed
    assert written["status"] == "PASS"
    assert fake_github.requests[0][4]["Authorization"] == "Bearer test-token"


def test_main_roundtrip_without_out_only_prints(tmp_path, truth_file, monkeypatch, fake_github, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    rc = gr.main(["roundtrip", str(truth_file), "--repo", "GBOGEB/demo", "--source-sha", SOURCE_SHA, "--timestamp", TIMESTAMP])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["roundtrip_tree_sha"] in fake_github.trees
    assert list(tmp_path.iterdir()) == [truth_file]


def test_main_roundtrip_http_error_returns_2(truth_file, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"Bad credentials"))

    monkeypatch.setattr(gr.urllib.request, "urlopen", boom)
    rc = gr.main(["roundtrip", str(truth_file), "--repo", "GBOGEB/demo", "--source-sha", SOURCE_SHA, "--timestamp", TIMESTAMP])
    assert rc == 2
    assert capsys.readouterr().err == "FAIL: GitHub API GET /git/commits/" + SOURCE_SHA + " failed 401: Bad credentials\n"


def test_main_missing_truth_file_returns_2(tmp_path, capsys):
    rc = gr.main(["build-local", str(tmp_path / "absent.json"), str(tmp_path / "o")])
    assert rc == 2
    assert capsys.readouterr().err.startswith("FAIL: ")
    assert not (tmp_path / "o").exists()


def test_main_invalid_json_returns_2(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert gr.main(["build-local", str(p), str(tmp_path / "o")]) == 2
    assert capsys.readouterr().err.startswith("FAIL: Expecting property name")


def test_main_non_object_truth_returns_2(tmp_path, capsys):
    p = tmp_path / "arr.json"
    p.write_text("[]", encoding="utf-8")
    assert gr.main(["build-local", str(p), str(tmp_path / "o")]) == 2
    assert capsys.readouterr().err == "FAIL: truth must be a JSON object\n"


def test_main_requires_subcommand():
    with pytest.raises(SystemExit) as info:
        gr.main([])
    assert info.value.code == 2
