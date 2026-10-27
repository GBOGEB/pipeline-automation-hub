"""JADE N+9 DevOps census: classification, test inventory, probes and an end-to-end run on a local git remote.

The end-to-end case builds a throwaway repository, serves it over file:// with partial-clone filters enabled,
and runs fetch -> scan -> check exactly as against GitHub. No network access is used.
"""
import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parents[1]
JADE = HERE.parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("census", HERE / "census.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
L, W = C.L, C.W

PIN = "11bd71901bbe5b1630ceea73d27597364c9af683"
GIT = shutil.which("git")


def scratch_dir(prefix):
    # tempfile.mkdtemp() on Windows (Python >= 3.12.4) sets an owner-only ACL that git for Windows cannot
    # traverse; a plain mkdir under the temp root keeps default permissions on every platform.
    d = Path(tempfile.gettempdir()) / f"{prefix}{os.getpid()}-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True)
    return d


def git(cwd, *args, date="2026-10-18T10:00:00+00:00"):
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date, GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    p = subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                        *args], cwd=cwd, env=env, capture_output=True)
    if p.returncode:
        raise RuntimeError(f"git {args[0]}: {p.stderr.decode(errors='replace')}")
    return p.stdout.decode().strip()


WORKFLOW = f"""name: CI and Pages
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@{PIN}
      - run: python -m unittest discover -s tests 2>&1 | tee log && grep -Eq '^Ran [1-9][0-9]* tests?' log
  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    environment: github-pages
    concurrency: {{group: pages, cancel-in-progress: false}}
    permissions: {{contents: read, pages: write, id-token: write}}
    steps:
      - uses: actions/download-artifact@{PIN}
      - run: sha256sum -c SUMS
      - uses: actions/deploy-pages@v4
"""
BASE_FILES = {
    "README.md": "# demo\n",
    "CODEOWNERS": "* @owner\n",
    ".github/workflows/ci.yml": WORKFLOW,
    "pkg/core.py": "def add(a, b):\n    return a + b\n\n\nclass Box:\n    def get(self):\n        return 1\n",
    "pkg/orphan.py": "def lonely():\n    return 0\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass T(unittest.TestCase):\n"
                          "    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n",
    "requirements.txt": "pyyaml==6.0.3\n",
    "tests/fixtures/package.json": "{}\n",
}
HEAD_FILES = {
    "tests/test_empty.py": "import unittest\n",
    "tests/test_dyn.py": "import importlib.util\nspec = importlib.util.spec_from_file_location('loader', 'pkg/loader.py')\n"
                         "def test_loader():\n    assert spec\n",
    "pkg/loader.py": "def load():\n    return 1\n",
    "CHANGELOG.md": "## 1.0\n",
    "docs/RUNBOOK.md": "rollback: redeploy previous run\n",
}


@unittest.skipUnless(GIT, "git is required")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Windows may assign scratch directories to the Administrators group; git's safe.directory check
        # would then refuse them (also inside upload-pack), so trust them via command-scope config.
        cls._env = {k: os.environ.get(k) for k in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0")}
        os.environ.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0="*")
        cls.tmp = scratch_dir("jade-census-")
        src = cls.tmp / "src"
        src.mkdir()
        git(src, "init", "-q")
        for rel, text in BASE_FILES.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text, encoding="utf-8", newline="\n")
        git(src, "add", "-A")
        git(src, "commit", "-q", "-m", "feat: initial service")
        cls.base = git(src, "rev-parse", "HEAD")
        for rel, text in HEAD_FILES.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text, encoding="utf-8", newline="\n")
        git(src, "add", "-A")
        git(src, "commit", "-q", "-m", "test: dynamic loader coverage", date="2026-10-20T10:00:00+00:00")
        (src / "pkg/core.py").write_text(BASE_FILES["pkg/core.py"] + "\n\ndef sub(a, b):\n    return a - b\n",
                                         encoding="utf-8", newline="\n")
        git(src, "commit", "-q", "-am", "fix(core): add sub", date="2026-10-21T10:00:00+00:00")
        git(src, "tag", "v1.0.0")
        git(src, "tag", "-a", "v1.2.0", "-m", "release")
        cls.head = git(src, "rev-parse", "HEAD")
        for k in ("uploadpack.allowFilter", "uploadpack.allowAnySHA1InWant"):
            git(src, "config", k, "true")
        cls.url = (src.resolve().as_uri())
        cls.roster = cls.tmp / "roster.json"
        cls.roster.write_text(json.dumps({"repositories": [
            {"rank": 1, "repo": "demo/service", "branch": "main", "cohort_lane": "CORE", "role": "demo",
             "commit_sha_observed": cls.base},
            {"rank": 2, "repo": "demo/missing", "branch": "main", "cohort_lane": "SUPPORT", "role": "absent",
             "commit_sha_observed": None}]}), encoding="utf-8", newline="\n")
        cls.cache = cls.tmp / "cache"
        cls.cache.mkdir()
        cls.fetch = C.fetch_repo(cls.cache, "demo/service", "main", cls.base, url=cls.url)
        cls.missing = C.fetch_repo(cls.cache, "demo/missing", "main", None, url=(cls.tmp / "nope").as_uri())
        cls.src = src

        def fake_get(url):
            if url.endswith("site-manifest.json"):
                return 200, json.dumps({"source_git_sha": cls.head}).encode()
            if urlparse(url).hostname == "api.github.com":
                if url.endswith("/branches/main"):
                    return 200, b'{"protected": true}'
                if url.endswith("/environments"):
                    return 200, b'{"environments": [{"name": "github-pages", "protection_rules": [{"type": "branch_policy"}]}]}'
                if "/deployments" in url:
                    return 200, json.dumps([{"sha": cls.head}]).encode()
            return 200, b"<html></html>"
        cls.get = staticmethod(fake_get)
        cls.census, cls.objects = C.scan(cls.cache, cls.roster, "2026-10-23T00:00:00Z", get=fake_get,
                                         fetch_log={"demo/missing": cls.missing})
        cls.repo = cls.census["repos"][0]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_fetch_is_blobless_and_reports_baseline(self):
        self.assertTrue(self.fetch["ok"] and self.fetch["baseline_fetched"])
        self.assertEqual(self.fetch["head"], self.head)
        self.assertGreater(self.fetch["blobs_fetched"], 0)
        self.assertFalse(self.missing["ok"])
        cfg = subprocess.run(["git", "--git-dir", str(C.cache_dir(self.cache, "demo/service")), "config",
                              "remote.origin.partialclonefilter"], capture_output=True).stdout.decode().strip()
        self.assertEqual(cfg, "blob:none")

    def test_failed_tag_read_is_unknown_not_zero(self):
        d = self.tmp / "tags-probe.git"
        shutil.copytree(C.cache_dir(self.cache, "demo/service"), d)
        self.assertTrue(C.refresh_tags(d))
        self.assertTrue((d / "jade-tags.txt").read_text(encoding="utf-8"))
        git(self.tmp, "--git-dir", str(d), "remote", "set-url", "origin", (self.tmp / "gone").as_uri())
        self.assertFalse(C.refresh_tags(d))
        self.assertFalse((d / "jade-tags.txt").exists())
        info = C.tag_info(self.tmp, "x/y")
        self.assertIsNone(info["count"])

    def test_refetch_is_idempotent(self):
        again = C.fetch_repo(self.cache, "demo/service", "main", self.base, url=self.url)
        self.assertEqual((again["ok"], again["head"]), (True, self.head))

    def test_identity_is_exact_git_objects(self):
        r = self.repo
        self.assertEqual(r["head_sha"], self.head)
        self.assertEqual(r["tree_oid"], git(self.src, "rev-parse", "HEAD^{tree}"))
        readme = next(e for e in r["evidence"]["S0_PLAN"] if e["path"] == "README.md")
        self.assertEqual(readme["blob_oid"], git(self.src, "rev-parse", "HEAD:README.md"))
        self.assertEqual(readme["oid"], "jade:file:service:README.md")
        wf = r["workflows"][0]
        self.assertEqual(wf["blob_oid"], git(self.src, "rev-parse", "HEAD:.github/workflows/ci.yml"))
        self.assertEqual(r["blobs_unread"], 0)

    def test_tests_inventory_and_zero_test_artifacts(self):
        t = self.repo["tests"]
        self.assertEqual((t["files"], t["cases"], t["zero_case_files"]), (3, 2, 1))
        self.assertEqual((t["py_modules"], t["py_tested"], t["py_untested"]), (3, 2, 1))
        z = self.repo["zero_test"]
        self.assertEqual([x["path"] for x in z["zero_case_files"]], ["tests/test_empty.py"])
        self.assertEqual([x["path"] for x in z["untested_modules_top"]], ["pkg/orphan.py"])
        self.assertEqual(z["untested_modules_top"][0]["oid"], "jade:py:service:pkg.orphan")
        self.assertEqual(z["unguarded_test_jobs"], [])
        objs = {m[0]: m for m in self.objects["repos"]["demo/service"]["py_modules"]}
        self.assertEqual(objs["pkg/core.py"][3:7], [3, 1, True, "import"])
        self.assertEqual(objs["pkg/loader.py"][6], "path")
        self.assertNotIn("tests/fixtures/package.json", [e["path"] for e in self.repo["evidence"]["S2_BUILD"]])

    def test_workflow_dag_and_deploy_contract(self):
        wf = self.repo["workflows"][0]
        self.assertEqual(wf["dag"]["layers"], [["test"], ["deploy"]])
        dep = next(j for j in wf["jobs"] if j["id"] == "deploy")
        self.assertEqual(sorted(k for k, v in dep["dp"].items() if v == "FAIL"), ["DP6", "DP7", "DP8"])
        f = self.repo["workflow_facts"]
        self.assertEqual((f["deploy"], f["deploy_env"], f["deploy_contract_core"]), (1, 1, 0))

    def test_stage_scores_follow_probes_and_evidence(self):
        r = self.repo
        self.assertEqual(r["probes"]["plan.codeowners"]["state"], L.PASS)
        self.assertIn("jade:file:service:CODEOWNERS", r["probes"]["plan.codeowners"]["evidence"])
        self.assertEqual(r["probes"]["plan.protection"]["state"], L.PASS)
        self.assertEqual(r["probes"]["operate.protected_env"]["state"], L.PASS)
        self.assertEqual(r["probes"]["monitor.live_parity"]["state"], L.PASS)
        self.assertEqual(r["probes"]["deploy.contract"]["state"], L.FAIL)
        self.assertEqual(r["stages"]["S6_DEPLOY"]["level"], 3)
        self.assertEqual(r["stages"]["S6_DEPLOY"]["next_blocker"], {"probe": "deploy.contract", "state": L.FAIL})
        self.assertEqual(r["tags"]["latest_semver"], "v1.2.0")
        self.assertEqual(r["tags"]["latest_semver_sha"], self.head)

    def test_baseline_delta_counts_fixed_expanded_tested(self):
        d = self.repo["delta"]
        self.assertTrue(d["reachable"] and not d["same_as_head"])
        self.assertEqual(d["commits"], 2)
        self.assertEqual(d["by_type"], {"fix": 1, "test": 1})
        self.assertEqual(d["tests"], {"files": 2, "cases": 1, "zero_case_files": 1, "py_modules": 1, "py_untested": 0})
        self.assertEqual(d["files"], {"A": 5, "M": 1})
        o = d["outcomes"]
        self.assertEqual((o["fixed"], o["tested"], o["test_cases_added_net"], o["zero_case_files_net"]), (1, 1, 1, 1))

    def test_unreachable_repo_is_unknown_never_pass(self):
        r = self.census["repos"][1]
        self.assertFalse(r["reachable"])
        self.assertEqual({p["state"] for p in r["probes"].values()}, {L.UNKNOWN})
        self.assertTrue(all(s["level"] == 0 for s in r["stages"].values()))

    def test_check_passes_and_is_deterministic(self):
        self.assertEqual(C.check(self.census, self.objects), [])
        again, _ = C.scan(self.cache, self.roster, "2026-10-23T00:00:00Z", get=self.get,
                          fetch_log={"demo/missing": self.missing})
        self.assertEqual(again["digest_sha256"], self.census["digest_sha256"])
        roundtrip = json.loads(json.dumps(self.census))
        self.assertEqual(C.check(roundtrip, self.objects), [])

    def test_check_negative_controls(self):
        def broken(mut):
            c = copy.deepcopy(self.census)
            mut(c)
            c["digest_sha256"] = C.hashlib.sha256(C.canonical({k: v for k, v in c.items() if k != "digest_sha256"})).hexdigest()
            return C.check(c, self.objects)
        self.assertIn("DIGEST_DRIFT", C.check(dict(self.census, iteration="N10"), self.objects))
        self.assertIn("AUTHORITY_BEARING", broken(lambda c: c["authority"].update(deploy_authorized=True)))
        self.assertIn("SCHEMA", broken(lambda c: c.update(schema="x")))
        self.assertIn("STAGE_KEYS", broken(lambda c: c["lifecycle"]["stages"].reverse()))
        self.assertIn("FLEET_REACHABLE", broken(lambda c: c["fleet"].update(reachable=9)))

        def pass_without_evidence(c):
            c["repos"][0]["probes"]["plan.codeowners"]["evidence"] = []
        self.assertTrue(any("PASS without evidence" in e for e in broken(pass_without_evidence)))

        def inflate(c):
            c["repos"][0]["stages"]["S6_DEPLOY"]["level"] = 5
        self.assertTrue(any("do not follow" in e for e in broken(inflate)))

        def claim(c):
            c["repos"][1]["probes"]["plan.readme_root"]["state"] = L.PASS
        self.assertTrue(any("unreachable" in e for e in broken(claim)))

        def bad_oid(c):
            c["repos"][0]["evidence"]["S0_PLAN"][0]["blob_oid"] = "nope"
            c["repos"][0]["workflows"][0]["blob_oid"] = "nope"
            c["repos"][0]["head_sha"] = "x"
            c["repos"][0]["stages"].pop("S0_PLAN")
            c["repos"][0]["probes"]["plan.templates"]["state"] = "MAYBE"
            c["repos"][0]["tests"]["py_tested"] += 1
        errs = broken(bad_oid)
        for frag in ("evidence blob_oid", "workflow blob_oid", "head_sha", "stages", "state", "reconciliation"):
            self.assertTrue(any(frag in e for e in errs), (frag, errs))
        objs = copy.deepcopy(self.objects)
        objs["repos"]["demo/service"]["test_files"].pop()
        objs["census_digest_sha256"] = "0" * 64
        errs = C.check(self.census, objs)
        self.assertIn("OBJECTS_DIGEST_DRIFT", errs)
        self.assertTrue(any("objects file drift" in e for e in errs))

    def test_pulse_over_pulse_baseline_and_report(self):
        base = C.census_baseline(self.census)
        self.assertEqual(base["label"], "census N9 heads (2026-10-23T00:00:00Z)")
        self.assertEqual(base["heads"], {"demo/service": self.head})
        nxt, _obj = C.scan(self.cache, self.roster, "2026-10-24T00:00:00Z", get=self.get,
                           fetch_log={"demo/missing": self.missing}, iteration="N10", baseline=base)
        self.assertEqual(C.check(nxt, None), [])
        self.assertEqual(nxt["iteration"], "N10")
        self.assertEqual(nxt["sources"]["baseline"],
                         {"kind": "census", "iteration": "N9", "digest_sha256": self.census["digest_sha256"],
                          "label": base["label"]})
        d = nxt["repos"][0]["delta"]
        self.assertEqual((d["baseline_sha"], d["same_as_head"], d["commits"], d["baseline_label"]),
                         (self.head, True, 0, base["label"]))
        self.assertNotIn("delta", nxt["repos"][1])  # unreachable repos carry no delta at all
        text = C.report(nxt, self.census)
        for frag in ("# JADE N+10 DevOps census reading", "`data/DEVOPS_CENSUS_N10.json`",
                     "## Change since the census N9 heads (2026-10-23T00:00:00Z)", "## Pulse over pulse: N9 → N10",
                     "| service | same | none |", "| none | | | |"):
            self.assertIn(frag, text)
        self.assertNotIn("## Pulse over pulse", C.report(nxt))
        prev = copy.deepcopy(self.census)
        r0 = prev["repos"][0]
        r0["head_sha"] = "0" * 40
        r0["probes"]["plan.codeowners"]["state"] = L.FAIL
        r0["stages"]["S0_PLAN"]["level"] = 0
        prev["repos"].pop()
        text = C.report(nxt, prev)
        self.assertIn(f"| service | moved | S0 0→{nxt['repos'][0]['stages']['S0_PLAN']['level']} |", text)
        self.assertIn("| `plan.codeowners` | FAIL | PASS | 1 |", text)
        self.assertNotIn("| missing |", text.split("## Pulse over pulse")[1])
        self.assertEqual([x.name for x in C.paths("N10")],
                         ["DEVOPS_CENSUS_N10.json", "DEVOPS_OBJECTS_N10.json", "DEVOPS_CENSUS_N10_READING.md"])

    def test_report_renders_every_section_deterministically(self):
        text = C.report(self.census)
        self.assertEqual(text, C.report(json.loads(json.dumps(self.census))))
        for heading in ("## Stage maturity across the fleet", "## Repository × stage level (L0–L5)",
                        "## Deploy contract DP1–DP10 across every deploy job", "## Zero-test artefacts",
                        "## Change since the TOP21 baseline (2026-10-18 heads)", "## Probe states across reachable repositories"):
            self.assertIn(heading, text)
        self.assertIn("| 1 | demo/service | CORE |", text)
        self.assertIn("| 2 | demo/missing | SUPPORT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | UNREACHABLE |", text)
        self.assertIn("| DP6 | PINNED | 1 |", text)
        self.assertIn("- `jade:job:service:.github/workflows/ci.yml#deploy`: fails DP6, DP7, DP8", text)
        self.assertIn("| `deploy.contract` | L4 | 0 | 1 | 0 |", text)
        self.assertNotIn("| service |", text.split("## Red-trace crosswalk")[1].split("## Probe states")[0])

    def test_cli_fetch_scan_check(self):
        out = self.tmp / "cli"
        out.mkdir(exist_ok=True)
        buf = io.StringIO()
        cache = out / "cache"
        row = {"rank": 1, "repo": "demo/service", "branch": "main", "cohort_lane": "CORE", "role": "demo",
               "commit_sha_observed": self.head}
        roster = out / "roster.json"
        roster.write_text(json.dumps({"repositories": [row]}), encoding="utf-8", newline="\n")
        cache.mkdir()
        shutil.copytree(C.cache_dir(self.cache, "demo/service"), C.cache_dir(cache, "demo/service"))
        with redirect_stdout(buf):
            rc_fetch = C.main(["fetch", "--cache", str(cache), "--roster", str(roster), "--only", "demo/service"])
            rc_scan = C.main(["scan", "--cache", str(cache), "--roster", str(roster), "--out", str(out / "c.json"),
                              "--objects", str(out / "o.json"), "--no-pages", "--no-api",
                              "--observed-at", "2026-10-23T00:00:00Z"])
            rc_check = C.main(["check", "--census", str(out / "c.json"), "--objects", str(out / "o.json")])
        self.assertEqual((rc_fetch, rc_scan, rc_check), (0, 0, 0), buf.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(C.main(["fetch", "--cache", str(cache), "--roster", str(roster), "--only", "demo/service",
                                     "--baseline-census", str(out / "c.json")]), 0)
            self.assertEqual(C.main(["scan", "--cache", str(cache), "--roster", str(roster), "--out", str(out / "c10.json"),
                                     "--objects", str(out / "o10.json"), "--no-pages", "--no-api", "--iteration", "N10",
                                     "--baseline-census", str(out / "c.json"), "--observed-at", "2026-10-24T00:00:00Z"]), 0)
            self.assertEqual(C.main(["report", "--census", str(out / "c10.json"), "--previous", str(out / "c.json"),
                                     "--out", str(out / "r10.md")]), 0)
        self.assertIn("## Pulse over pulse: N9 → N10", (out / "r10.md").read_text(encoding="utf-8"))
        c = json.loads((out / "c.json").read_text(encoding="utf-8"))
        self.assertEqual(c["repos"][0]["delta"]["same_as_head"], True)
        self.assertEqual(c["sources"]["api"]["mode"], "off")
        md = out / "reading.md"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(C.main(["report", "--census", str(out / "c.json"), "--out", str(md)]), 0)
            self.assertEqual(C.main(["report", "--census", str(out / "c.json"), "--out", str(md), "--check"]), 0)
            md.write_text(md.read_text(encoding="utf-8") + "drift\n", encoding="utf-8", newline="\n")
            self.assertEqual(C.main(["report", "--census", str(out / "c.json"), "--out", str(md), "--check"]), 1)
        c["iteration"] = "tampered"
        (out / "c.json").write_text(json.dumps(c), encoding="utf-8", newline="\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(C.main(["check", "--census", str(out / "c.json"), "--objects", str(out / "o.json")]), 1)


class Classification(unittest.TestCase):
    def test_paths_to_kinds(self):
        table = {
            "README.md": ["readme_root"], "docs/README.md": [], ".github/CODEOWNERS": ["codeowners"],
            ".github/workflows/ci.yml": ["workflow"], ".github/workflows/sub/ci.yml": [],
            ".github/ISSUE_TEMPLATE/bug.yml": ["issue_template"], ".github/pull_request_template.md": ["pr_template"],
            "docs/adr/0001-x.md": ["register"], "pyproject.toml": ["build_manifest"], "uv.lock": ["lockfile"],
            ".pre-commit-config.yaml": ["precommit"], "ruff.toml": ["lint_config"],
            "tests/conftest.py": ["test_config"], ".github/dependabot.yml": ["dependency_bot"],
            "SECURITY.md": ["security_policy"], "CHANGELOG.md": ["changelog"],
            "docker-compose.yml": ["deploy_descriptor", "runtime_descriptor"],
            "Dockerfile": ["build_manifest"], "k8s/app.yaml": ["deploy_descriptor", "runtime_descriptor"],
            "docs/RUNBOOK.md": ["runbook"], "tools/hosted_parity.py": ["healthcheck"],
            "mission/red_trace.json": ["observability", "control_ledger"], "qa/QA_RECEIPT.json": ["control_ledger"],
            "node_modules/x/package.json": [], "tests/fixtures/package.json": [], "examples/Dockerfile": [],
        }
        for path, kinds in table.items():
            with self.subTest(path=path):
                self.assertEqual(C.classify(path), kinds)

    def test_test_file_patterns(self):
        for path, lang in (("tests/test_a.py", "python"), ("a_test.py", "python"), ("pkg/tests.py", "python"),
                           ("tests/helpers.py", None), ("tests/conftest.py", None), ("src/a.spec.ts", "js"),
                           ("src/__tests__/a.js", "js"), ("x_test.go", "go"), ("a.Tests.ps1", "powershell"),
                           ("tests/it.rs", "rust"), ("App.Tests/T.cs", "csharp"), ("main.py", None)):
            with self.subTest(path=path):
                self.assertEqual(C.test_lang(path), lang)

    def test_wanted_skips_vendored_and_python_fixtures(self):
        self.assertTrue(C.wanted("pkg/a.py"))
        self.assertFalse(C.wanted("node_modules/a/index.py"))
        self.assertFalse(C.wanted("tests/fixtures/sample.py"))
        self.assertTrue(C.wanted("tests/test_x.py"))


class ContentAnalysis(unittest.TestCase):
    def test_count_cases_per_language(self):
        py = "def test_a():\n    pass\n\nclass T:\n    def test_b(self):\n        pass\n    def helper(self):\n        pass\n"
        self.assertEqual(C.count_cases("python", py), 2)
        self.assertEqual(C.count_cases("python", "def test_a(:\n  def test_b():"), 2)
        self.assertEqual(C.count_cases("js", "it('a', () => {})\n  test.each([1])('b', x => x)\nrunFormatTest(import.meta, [])"), 3)
        self.assertEqual(C.count_cases("go", "func TestA(t *testing.T) {}\nfunc helper() {}\nfunc BenchmarkB(b *testing.B) {}"), 2)
        self.assertEqual(C.count_cases("powershell", "Describe 'x' {\n  It 'works' { }\n}"), 1)
        self.assertEqual(C.count_cases("rust", "#[test]\nfn a() {}\n#[tokio::test]\nasync fn b() {}"), 2)
        self.assertEqual(C.count_cases("csharp", "[Fact]\npublic void A() {}\n[TestMethod] void B() {}"), 2)
        self.assertEqual(C.count_cases("cobol", "anything"), 0)

    def test_py_info_imports_paths_and_dynamic_idents(self):
        info = C.py_info("import a.b\nfrom c import d\nfrom . import e\nfrom .f import g\nX='pkg/h.py'\nY='m.n'\nZ='plain'\n")
        self.assertTrue({"a.b", "c", "c.d", "e", "f", "g", "m.n"} <= info["imports"])
        self.assertEqual(info["strings"], {"pkg/h.py"})
        self.assertEqual(info["idents"], set())
        dyn = C.py_info("import importlib\nimportlib.import_module('x')\nname='loader'\n")
        self.assertIn("loader", dyn["idents"])
        self.assertTrue(C.py_info("def broken(:")["parse_error"])

    def test_module_parts_and_mapping(self):
        self.assertEqual(C.module_parts("src/pkg/mod.py"), ("pkg", "mod"))
        mods = {"pkg/a.py": ("pkg", "a"), "tools/b.py": ("tools", "b"), "c.py": ("c",)}
        refs = {"tests/test_x.py": ({"pkg.a"}, {"tools/b.py"}), "tests/test_y.py": (set(), set())}
        m = C.map_tests(mods, refs)
        self.assertEqual(m, {"pkg/a.py": ("import", 1), "tools/b.py": ("path", 1), "c.py": ("none", 0)})

    def test_src_prefixed_import_maps_to_the_module(self):
        # tests import `src.golden_thread` while module_parts strips src/ (census N+10 false 'untested').
        mods = {"src/golden_thread.py": C.module_parts("src/golden_thread.py"), "src/other.py": ("other",)}
        m = C.map_tests(mods, {"tests/test_g.py": ({"src.golden_thread", "src.golden_thread.replay"}, set())})
        self.assertEqual(m, {"src/golden_thread.py": ("import", 1), "src/other.py": ("none", 0)})

    def test_archived_copies_are_counted_apart_from_live_code(self):
        sc = {"test_files": [["tests/test_a.py", "1" * 40, "python", 3],
                             ["triage/w366/x/recovered/history/test_all.py", "2" * 40, "python", 0],
                             ["triage/w367/archive_incubator/p/selfsmoke_test.py", "3" * 40, "python", 0],
                             ["tests/test_empty.py", "4" * 40, "python", 0]],
              "modules": [["src/live.py", "5" * 40, "live", 3, 0, False, "none", 0, []],
                          ["src/done.py", "6" * 40, "done", 3, 0, True, "import", 1, []],
                          ["docs/a.zip.d/gen.py", "7" * 40, "gen", 9, 0, False, "none", 0, []]]}
        t = C.tests_summary(sc)
        self.assertEqual((t["files"], t["zero_case_files"], t["py_modules"], t["py_untested"]), (4, 3, 3, 2))
        self.assertEqual((t["live_zero_case_files"], t["live_py_modules"], t["live_py_untested"]), (1, 2, 1))
        self.assertEqual((t["archived_test_files"], t["archived_py_modules"]), (2, 1))
        for live in ("src/archive_tools.py", "tools/recovery.py", "qps/recovered_state.py"):
            self.assertIsNone(C.ARCHIVED.search(live), live)

    def test_provenance_backed_snapshots_are_archived_and_bare_names_are_not(self):
        # A3: tender_library/abacus_snapshot/ is a byte-identical copy of another repository, recorded in
        # tender_library/PROVENANCE.csv. A "_snapshot" name without a PROVENANCE.csv stays live code.
        paths = ["tender_library/PROVENANCE.csv", "tender_library/abacus_snapshot/qplant/calc.py",
                 "vendor/x_snapshot/PROVENANCE.csv", "vendor/x_snapshot/tool.py",
                 "codex/A10_snapshot_publication/publish.py", "triage/w86_child_snapshot/scripts/check.py",
                 "src/snapshot_tools.py"]
        self.assertEqual(C.snapshot_prefixes(paths), ["tender_library/abacus_snapshot/", "vendor/x_snapshot/"])
        sc = {"snapshot_prefixes": C.snapshot_prefixes(paths),
              "test_files": [["tender_library/abacus_snapshot/tests/test_calc.py", "1" * 40, "python", 0]],
              "modules": [[p, "2" * 40, "m", 3, 0, False, "none", 0, []] for p in paths if p.endswith(".py")]}
        t = C.tests_summary(sc)
        self.assertEqual((t["archived_py_modules"], t["live_py_modules"], t["live_py_untested"]), (2, 3, 3))
        self.assertEqual((t["archived_test_files"], t["live_zero_case_files"]), (1, 0))
        self.assertEqual(t["snapshot_prefixes"], ["tender_library/abacus_snapshot/", "vendor/x_snapshot/"])
        for live in ("codex/A10_snapshot_publication/publish.py", "triage/w86_child_snapshot/scripts/check.py",
                     "src/snapshot_tools.py"):
            self.assertFalse(C.is_archived(sc, live), live)
        self.assertTrue(C.is_archived({}, "a/recovered/b.py"))
        self.assertEqual(C.snapshot_prefixes(["PROVENANCE.csv", "top_snapshot/a.py"]), ["top_snapshot/"])

    def test_floors_health_and_commit_types(self):
        self.assertEqual(C.toml_floor("[tool.coverage.report]\nfail_under = 85\n"), 85.0)
        self.assertIsNone(C.toml_floor("x = 1"))
        self.assertTrue(C.healthcheck_in("FROM x\nHEALTHCHECK CMD curl -f http://l/"))
        self.assertFalse(C.healthcheck_in("FROM x"))
        for subj, want in (("Merge pull request #1 from GBOGEB/fix/thing", "fix"),
                           ("Merge pull request #2 from GBOGEB/feat/x", "feat"), ("ci(hub): pin", "ci"),
                           ("refactor!: x", "maintenance"), ("Repair the gate", "fix"), ("Add coverage", "test"),
                           ("Implement thing", "feat"), ("update workflow", "ci"), ("misc", "other"),
                           ("Merge pull request #3 from o/wip-x", "other"),
                           ("Merge pull request #4 from GBOGEB/claude/code-purple-xss-dom-fix", "fix"),
                           ("Merge pull request #5 from GBOGEB/codex/add-coverage-lanes", "test"),
                           ("Merge pull request #6 from GBOGEB/code-purple/w77-breadth-legacy12", "control"),
                           ("Merge pull request #7 from GBOGEB/dependabot/github_actions/x", "deps"),
                           ("metrics: update repository metrics for abc [skip ci]", "automation"),
                           ("Merge pull request #8 from GBOGEB/w364-record-merged-2040", "other"),
                           ("Merge pull request #9 from o/w53-mip-firstred-census", "control")):
            with self.subTest(subj=subj):
                self.assertEqual(C.classify_subject(subj), want)


class Probes(unittest.TestCase):
    def test_pages_probe(self):
        head = "a" * 40

        def get_factory(site, manifest):
            def get(url):
                if url.endswith("site-manifest.json"):
                    return manifest
                return site
            return get
        p = C.probe_pages("GBOGEB/x", head, get_factory((404, b""), None))
        self.assertEqual((p["url"], p["status"], p["source_sha_match"]), ("https://gbogeb.github.io/x/", 404, None))
        p = C.probe_pages("GBOGEB/x", head, get_factory((200, b""), (200, json.dumps({"source_git_sha": head}).encode())))
        self.assertTrue(p["source_sha_match"])
        p = C.probe_pages("GBOGEB/x", head, get_factory((200, b""), (200, json.dumps({"source_git_sha": "b" * 40}).encode())))
        self.assertFalse(p["source_sha_match"])
        p = C.probe_pages("GBOGEB/x", head, get_factory((200, b""), (200, b"not json")))
        self.assertIsNone(p["source_sha_match"])
        p = C.probe_pages("GBOGEB/x", head, get_factory((200, b""), (404, b"")))
        self.assertIsNone(p["manifest"])

    def test_api_probe_budget_and_refusal(self):
        calls = []

        def get(url):
            calls.append(url)
            return 403, b""
        budget = [5, 0, None]
        out = C.probe_api("o/r", "main", budget, get)
        self.assertEqual(out["protected"], None)
        self.assertEqual((budget[0], budget[2], len(calls)), (0, 403, 1))
        self.assertIsNone(C.probe_api("o/r", "main", [0, 0, None], get)["environments"])

        def ok(url):
            if url.endswith("/branches/main"):
                return 200, b'{"protected": false}'
            if url.endswith("/environments"):
                return 200, b'{"environments": [{"name": "staging"}]}'
            return 200, b"bad json"
        out = C.probe_api("o/r", "main", [9, 0, None], ok)
        self.assertEqual((out["protected"], out["environments"], out["protected_production"], out["deployments"]),
                         (False, ["staging"], False, None))

    def test_http_get_maps_errors(self):
        import urllib.error

        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n):
                return b"ok"
        seen = {}

        def opener(req, timeout):
            seen["auth"] = req.get_header("Authorization")
            return Resp()
        self.assertEqual(C.http_get("https://api.github.com/x", opener=opener, token="t"), (200, b"ok"))
        self.assertEqual(seen["auth"], "Bearer t")
        C.http_get("https://example.org/", opener=opener, token="t")
        self.assertIsNone(seen["auth"])

        def http_error(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

        def url_error(req, timeout):
            raise urllib.error.URLError("down")
        self.assertEqual(C.http_get("https://x/", opener=http_error), (404, b""))
        self.assertEqual(C.http_get("https://x/", opener=url_error), (None, b""))

    def test_tag_info_without_cache_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(C.tag_info(Path(td), "o/r")["count"])

    def test_red_trace_crosswalk_from_committed_ledger(self):
        fed = json.loads((JADE / "data/RED_TRACE_FEDERATION_N8.json").read_text(encoding="utf-8"))
        idx = C.red_trace_index(fed)
        self.assertEqual(len(idx), 5)
        hub = idx["GBOGEB/pipeline-automation-hub"]
        self.assertEqual(hub["currently_red"], len(hub["first_red_roots"]) if hub["currently_red"] <= 12 else 12)
        self.assertIsNotNone(hub["ci_mttr_hours_median"])
        self.assertEqual(C.red_trace_index(None), {})
        one = {"repositories": [{"repository": "o/r", "counts": {}, "currently_red": 0, "currently_red_stale": 0,
                                 "observed_at_utc": "t", "non_green": [
                                     {"class": "RED_TO_GREEN", "current": "GREEN", "path": "p", "stale": False,
                                      "pinned": False, "window": {"red_hours": h}} for h in (1.0, 3.0)]}]}
        self.assertEqual(C.red_trace_index(one)["o/r"]["ci_mttr_hours_median"], 2.0)


class CommittedCensus(unittest.TestCase):
    """Every committed fleet pulse must satisfy every invariant the scanner enforces. Earlier pulses stay immutable."""

    ITER, PREV = "N9", None

    @classmethod
    def setUpClass(cls):
        cls.out, cls.out_obj, cls.out_md = C.paths(cls.ITER)
        cls.census = json.loads(cls.out.read_text(encoding="utf-8"))
        cls.objects = json.loads(cls.out_obj.read_text(encoding="utf-8"))
        cls.previous = json.loads(C.paths(cls.PREV)[0].read_text(encoding="utf-8")) if cls.PREV else None

    def test_check_passes(self):
        self.assertEqual(C.check(self.census, self.objects), [])

    def test_roster_order_and_identity(self):
        roster = json.loads((JADE / C.ROSTER).read_text(encoding="utf-8"))
        want = [r["repo"] for r in sorted(roster["repositories"], key=lambda r: r["rank"])]
        self.assertEqual([r["repo"] for r in self.census["repos"]], want)
        for r in self.census["repos"]:
            if r["reachable"]:  # a private repo's head is PB.MARK (counts only)
                self.assertRegex(r["head_sha"], r"^(?:[0-9a-f]{40}|" + C.PB.MARK + ")$")
                self.assertEqual(r["oid"], "jade:repo:" + r["repo"])

    def test_fleet_totals_reconcile(self):
        live = [r for r in self.census["repos"] if r["reachable"]]
        t = self.census["fleet"]["totals"]
        self.assertEqual(t["tests_files"], sum(r["tests"]["files"] for r in live))
        self.assertEqual(t["tests_py_untested"], sum(r["tests"]["py_untested"] for r in live))
        self.assertEqual(t["wf_workflows"], sum(r["workflow_facts"]["workflows"] for r in live))
        self.assertEqual(t["jobs"], sum(len(w["jobs"]) for r in live for w in r["workflows"]))
        for k, v in self.census["fleet"]["stages"].items():
            self.assertEqual(sum(v["levels"].values()), len(live), k)

    def test_committed_reading_matches_census(self):
        self.assertEqual(self.census["iteration"], self.ITER)
        self.assertEqual(self.out_md.read_text(encoding="utf-8").replace("\r\n", "\n"),
                         C.report(self.census, self.previous),
                         "run: python mission-control/jade_temple/devops/census.py report")

    def test_no_authority_and_lifecycle_contract(self):
        a = self.census["authority"]
        self.assertEqual(a["merge_admission"], "HOLD")
        self.assertFalse(a["deploy_authorized"] or a["release_authorized"] or a["merge_authorized"])
        self.assertEqual([s["key"] for s in self.census["lifecycle"]["stages"]], L.STAGE_KEYS)
        self.assertEqual(self.census["lifecycle"]["deploy_gates"], W.DP_GATES)


class CommittedCensusN10(CommittedCensus):
    ITER, PREV = "N10", "N9"

    def test_baseline_is_the_n9_pulse(self):
        b = self.census["sources"]["baseline"]
        self.assertEqual((b["kind"], b["iteration"], b["digest_sha256"]),
                         ("census", "N9", self.previous["digest_sha256"]))
        n9 = {r["repo"]: r["head_sha"] for r in self.previous["repos"]}
        for r in self.census["repos"]:
            self.assertEqual(r["delta"]["baseline_sha"], n9.get(r["repo"]), r["repo"])

    def test_n9_snapshot_is_unchanged(self):
        # Re-sealed once (2026-10-25) when the private repo was projected to counts only
        # (tools/private_boundary.py); unchanged since.
        self.assertEqual(self.previous["digest_sha256"],
                         "fb1aa7de748a1a94c0581e37907b14233a300116bb22b8442893bf081d3e79f4")

if __name__ == "__main__":
    unittest.main()
