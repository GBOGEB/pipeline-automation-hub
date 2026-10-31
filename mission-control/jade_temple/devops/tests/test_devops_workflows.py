"""JADE N+9 workflow analysis and deploy contract DP1..DP10: parser, signals, gates, negative controls."""
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("workflows", HERE / "workflows.py")
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)

PIN = "11bd71901bbe5b1630ceea73d27597364c9af683"
GOOD = f"""
name: deploy site
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      ref: {{type: string}}
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@{PIN}
        with: {{ref: "${{{{ github.sha }}}}"}}
      - run: python -m pytest -q --cov=pkg --cov-fail-under=85
  build:
    needs: test
    runs-on: ubuntu-24.04
    steps:
      - run: python -m build && sha256sum dist/* > SHA256SUMS
      - uses: actions/upload-artifact@{PIN}
  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    environment: {{name: production, url: https://example.org}}
    concurrency: {{group: prod, cancel-in-progress: false}}
    permissions: {{contents: read, pages: write, id-token: write}}
    steps:
      - uses: actions/download-artifact@{PIN}
      - run: sha256sum -c SHA256SUMS
      - uses: actions/deploy-pages@{PIN}
      - run: curl --fail https://example.org/index.html
      - uses: actions/upload-artifact@{PIN}
"""


def parsed(text=GOOD, path=".github/workflows/x.yml"):
    return W.parse(text, path=path, blob_oid="a" * 40, repo="demo")


def gates(text):
    wf = parsed(text)
    return W.deploy_gates(wf, "deploy")


class Parse(unittest.TestCase):
    def test_on_key_boolean_and_trigger_shapes(self):
        wf = parsed()
        self.assertEqual(wf["triggers"], ["push", "workflow_dispatch"])
        self.assertEqual(wf["dispatch_inputs"], ["ref"])
        self.assertEqual(parsed("on: push\njobs: {a: {steps: []}}")["triggers"], ["push"])
        self.assertEqual(parsed("on: [push, pull_request]\njobs: {a: {steps: []}}")["triggers"], ["pull_request", "push"])
        self.assertEqual(parsed("on: 5\njobs: {a: {steps: []}}")["triggers"], [])

    def test_schedule_tags_paths_and_reusable(self):
        wf = parsed("on:\n  schedule: [{cron: '0 3 * * 1'}]\n  push: {tags: ['v*'], paths: ['src/**']}\n"
                    "  workflow_call: {}\njobs: {a: {steps: []}}")
        self.assertEqual(wf["schedules"], ["0 3 * * 1"])
        self.assertTrue(wf["push_tags"] and wf["paths_filtered"] and wf["reusable"])

    def test_permission_classes(self):
        for perms, want in ((None, "default"), ("write-all", "write-all"), ("read-all", "read"), ({}, "read"),
                            ({"contents": "read"}, "read"), ({"pages": "write", "contents": "write"}, "write:contents,pages"),
                            (7, "declared")):
            with self.subTest(perms=perms):
                self.assertEqual(W._perm_class(perms), want)

    def test_concurrency_shapes(self):
        self.assertIsNone(W._concurrency(None))
        self.assertEqual(W._concurrency("g"), {"group": "g", "cancel_in_progress": False})
        self.assertTrue(W._concurrency({"group": "g", "cancel-in-progress": True})["cancel_in_progress"])
        self.assertTrue(W._concurrency({"group": "g", "cancel-in-progress": "${{ x }}"})["cancel_in_progress"])
        self.assertIsNone(W._concurrency(3))

    def test_errors_are_recorded_not_raised(self):
        self.assertTrue(parsed("on: [push\njobs:").get("parse_error").startswith("YAML"))
        self.assertTrue(parsed("name: x\non: push").get("parse_error").startswith("SHAPE"))
        wf = parsed("on: push\njobs: {a: 3, b: {steps: [{run: echo}]}}")
        self.assertEqual(wf["jobs"][0]["parse_error"], "SHAPE: job is not a mapping")
        rec = W.analyse(wf)
        self.assertEqual(rec["jobs"][0]["parse_error"], "SHAPE: job is not a mapping")
        bad = W.analyse(parsed("on: [push\njobs:"))
        self.assertEqual((bad["jobs"], bad["sig"]), ([], {}))

    def test_job_dag_layers_dangling_and_cycle(self):
        wf = parsed()
        self.assertEqual(wf["dag"]["layers"], [["test"], ["build"], ["deploy"]])
        self.assertEqual(wf["dag"]["edges"], [["build", "deploy"], ["test", "build"]])
        self.assertFalse(wf["dag"]["cycle"])
        d = parsed("on: push\njobs: {a: {needs: [b], steps: []}, b: {needs: a, steps: []}, c: {needs: zz, steps: []}}")["dag"]
        self.assertTrue(d["cycle"])
        self.assertEqual(d["dangling"], ["c->zz"])

    def test_job_identity_is_descriptive_and_content_addressed(self):
        wf = parsed()
        job = next(j for j in wf["jobs"] if j["id"] == "deploy")
        self.assertEqual(job["oid"], "jade:job:demo:.github/workflows/x.yml#deploy")
        self.assertRegex(job["def_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(job["def_sha256"], next(j for j in wf["jobs"] if j["id"] == "test")["def_sha256"])
        self.assertEqual(job["def_sha256"], next(j for j in parsed()["jobs"] if j["id"] == "deploy")["def_sha256"])

    def test_action_refs(self):
        self.assertEqual(W.action_ref("./local")["pinned"], True)
        self.assertFalse(W.action_ref("./local")["third_party"])
        self.assertTrue(W.action_ref("docker://alpine@sha256:abc")["pinned"])
        self.assertFalse(W.action_ref("docker://alpine:3")["pinned"])
        self.assertEqual(W.action_ref("o/r/.github/workflows/w.yml@" + PIN)["kind"], "reusable")
        self.assertTrue(W.action_ref("actions/checkout@" + PIN)["pinned"])
        self.assertFalse(W.action_ref("actions/checkout@v4")["pinned"])


class Signals(unittest.TestCase):
    def sig(self, steps, **job):
        j = {"id": "j", "steps": steps, "continue_on_error": False, "if": "", "uses": None, "with": {}}
        j.update(job)
        return W.signals(j, {})

    def step(self, run="", uses=None, coe=False, with_=None):
        return {"name": "", "run": run, "uses": uses, "with": with_ or {}, "if": "", "continue_on_error": coe}

    def test_tests_coverage_and_guards(self):
        s = self.sig([self.step("python -m pytest --cov=x --cov-fail-under=91")])
        self.assertTrue(s["tests"] and s["pytest"] and s["coverage"] and s["implicit_zero_guard"])
        self.assertEqual(s["coverage_floor"], 91.0)
        s = self.sig([self.step("python -m unittest discover -s t 2>&1 | tee log\ngrep -Eq '^Ran [1-9][0-9]* tests?' log")])
        self.assertTrue(s["zero_test_guard"] and not s["implicit_zero_guard"])
        s = self.sig([self.step("pytest || true")])
        self.assertTrue(s["soft_fail_tests"] and not s["implicit_zero_guard"])
        self.assertTrue(self.sig([self.step("pytest", coe=True)])["soft_fail_tests"])
        self.assertTrue(self.sig([], uses="o/r/.github/workflows/jade-reusable-ci.yml@" + PIN)["zero_test_guard"])

    def test_coverage_floor_patterns(self):
        for text, want in (("coverage report --fail-under=77", [77.0]), ("fail_under = 66", [66.0]),
                           ("if t['percent_statements_covered']<90: raise", [90.0]),
                           ("--coverage-floor 55", [55.0]), ("coverage-floor: '80'", [80.0]), ("nothing", [])):
            with self.subTest(text=text):
                self.assertEqual(W.coverage_floors(text), want)

    def test_lint_type_precommit_build_security_provenance(self):
        s = self.sig([self.step("ruff check . && mypy src && pre-commit run -a && pip install -e . && "
                                "bandit -r src && cosign sign x")])
        for k in ("lint", "typecheck", "precommit", "build", "security", "provenance"):
            self.assertTrue(s[k], k)
        s = self.sig([self.step(uses="github/codeql-action/analyze@v3"),
                      self.step(uses="actions/attest-build-provenance@" + PIN)])
        self.assertTrue(s["security"] and s["provenance"])
        self.assertEqual((s["actions_pinned"], s["actions_total"]), (1, 2))

    def test_release_deploy_verify_alerting(self):
        self.assertTrue(self.sig([self.step("gh release create v1 dist/*")])["release"])
        self.assertTrue(self.sig([self.step(uses="softprops/action-gh-release@v2")])["release"])
        self.assertTrue(self.sig([self.step("kubectl apply -f k8s/")])["deploy"])
        self.assertTrue(self.sig([self.step(uses="docker/build-push-action@v6", with_={"push": True})])["deploy"])
        self.assertFalse(self.sig([self.step(uses="docker/build-push-action@v6", with_={"push": False})])["deploy"])
        self.assertTrue(self.sig([self.step("echo")], environment="staging")["deploy"])
        self.assertTrue(self.sig([self.step("curl -fsS https://x.org/health")])["verify"])
        s = self.sig([{"name": "", "run": "gh issue create -t red", "uses": None, "with": {}, "if": "failure()",
                       "continue_on_error": False}])
        self.assertTrue(s["alerting"])
        self.assertFalse(self.sig([self.step("gh issue create -t note")])["alerting"])


class DeployContract(unittest.TestCase):
    def test_good_deploy_passes_all_ten(self):
        self.assertEqual(set(gates(GOOD).values()), {"PASS"})

    def test_each_gate_has_a_negative_control(self):
        mutations = {
            "DP1": ("      - uses: actions/download-artifact@" + PIN + "\n", ""),
            "DP2": ("      - run: sha256sum -c SHA256SUMS\n", ""),
            "DP3": ("    environment: {name: production, url: https://example.org}\n", ""),
            "DP4": ("    concurrency: {group: prod, cancel-in-progress: false}\n", "    concurrency: {group: prod, cancel-in-progress: true}\n"),
            "DP5": ("    permissions: {contents: read, pages: write, id-token: write}\n", "    permissions: write-all\n"),
            "DP6": ("      - uses: actions/deploy-pages@" + PIN, "      - uses: actions/deploy-pages@v4"),
            "DP7": ("      - run: curl --fail https://example.org/index.html\n", ""),
            "DP8": ("      - run: curl --fail https://example.org/index.html\n      - uses: actions/upload-artifact@" + PIN + "\n",
                    "      - run: curl --fail https://example.org/index.html\n"),
            "DP9": ("      - run: python -m pytest -q --cov=pkg --cov-fail-under=85\n", "      - run: echo lint\n"),
            "DP10": (None, None),
        }
        for gate, (old, new) in mutations.items():
            if old is None:
                continue
            with self.subTest(gate=gate):
                self.assertIn(old, GOOD)
                g = gates(GOOD.replace(old, new))
                self.assertEqual(g[gate], "FAIL", g)
        text = GOOD.replace("    if: github.ref == 'refs/heads/main'\n", "").replace(
            '        with: {ref: "${{ github.sha }}"}\n', "")
        self.assertEqual(gates(text)["DP10"], "FAIL")
        self.assertEqual(gates(GOOD.replace("permissions:\n  contents: read\njobs:", "jobs:").replace(
            "    permissions: {contents: read, pages: write, id-token: write}\n", ""))["DP5"], "FAIL")

    def test_downstream_verify_job_satisfies_dp7_dp8(self):
        text = GOOD.replace("      - run: curl --fail https://example.org/index.html\n      - uses: actions/upload-artifact@" + PIN + "\n", "")
        text += ("  verify:\n    needs: deploy\n    runs-on: ubuntu-24.04\n    steps:\n"
                 "      - run: python -c 'import urllib.request'\n      - uses: actions/upload-artifact@" + PIN + "\n")
        g = gates(text)
        self.assertEqual((g["DP7"], g["DP8"]), ("PASS", "PASS"))

    def test_analyse_attaches_dp_only_to_deploy_jobs(self):
        rec = W.analyse(parsed())
        by = {j["id"]: j for j in rec["jobs"]}
        self.assertIn("dp", by["deploy"])
        self.assertNotIn("dp", by["test"])
        self.assertIn("tests", by["test"]["signals"])
        self.assertEqual(by["test"]["coverage_floor"], 85.0)
        self.assertEqual(rec["dag"]["layers"], [["test"], ["build"], ["deploy"]])


class Shipped(unittest.TestCase):
    """The hub's own reusable workflows and caller template are linted like any repo's workflow."""

    def lint(self, *paths, require=False):
        return W.lint([str(REPO / p) for p in paths], require)

    def test_reusable_deploy_and_caller_template_pass_every_gate(self):
        rc, report = self.lint(".github/workflows/jade-reusable-deploy.yml",
                               "mission-control/jade_temple/devops/templates/jade-cicd-caller.yml", require=True)
        self.assertEqual(rc, 0, report)
        self.assertEqual(sorted(r["job"] for r in report), ["deploy", "deploy-production", "deploy-staging"])

    def test_reusable_ci_is_fail_closed_and_hashes_its_artefact(self):
        wf = W.parse((REPO / ".github/workflows/jade-reusable-ci.yml").read_text(encoding="utf-8"), "ci")
        self.assertIsNone(wf["parse_error"])
        rec = W.analyse(wf)
        sig = rec["sig"]
        self.assertTrue(sig["test"]["tests"] and sig["test"]["zero_test_guard"] and sig["test"]["coverage"])
        self.assertTrue(sig["build"]["artifact_upload"] and sig["build"]["digest"])
        self.assertEqual(rec["permissions"], "read")
        for job, s in sig.items():
            self.assertEqual(s["actions_pinned"], s["actions_total"], job)

    def test_reusable_deploy_readback_quotes_served_paths(self):
        # Pages serves "# Notes.md" at "%23%20Notes.md"; an unquoted request asks for "/" and fails parity.
        import hashlib, http.server, os, re, subprocess, threading
        text = (REPO / ".github/workflows/jade-reusable-deploy.yml").read_text(encoding="utf-8")
        body = re.search(r"Read back served files.*?<<'PY'\n(.*?)\n\s*PY\n", text, re.S).group(1)
        script = "\n".join(line[10:] for line in body.splitlines())
        with tempfile.TemporaryDirectory() as tmp:
            site, work = Path(tmp, "site"), Path(tmp, "work")
            names = ["# Code Citations.md", "a b/c%d.txt", "index.html"]
            files = {}
            for n in names:
                (site / n).parent.mkdir(parents=True, exist_ok=True)
                (site / n).write_bytes(n.encode())
                files[n] = hashlib.sha256(n.encode()).hexdigest()
            manifest = json.dumps({"files": files}).encode()
            (work / "artifact").mkdir(parents=True)
            (work / "artifact/jade-manifest.json").write_bytes(manifest)
            (site / "jade-manifest.json").write_bytes(manifest)
            handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(site), **k)
            http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            env = dict(os.environ, BASE_URL=f"http://127.0.0.1:{srv.server_port}/", ENV_NAME="preview", TARGET="pages",
                       DIGEST=hashlib.sha256(manifest).hexdigest(), ATTEMPTS="1", GITHUB_REPOSITORY="o/r",
                       GITHUB_SHA="a" * 40, GITHUB_RUN_ID="1", GITHUB_RUN_ATTEMPT="1")
            try:
                r = subprocess.run([sys.executable, "-c", script], cwd=work, env=env, capture_output=True, text=True)
            finally:
                srv.shutdown()
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            receipt = json.loads((work / "jade-deploy-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual((receipt["verdict"], receipt["mismatches"], receipt["files_checked"]), ("PARITY", [], 4))

    def test_template_pins_are_the_documented_placeholder(self):
        text = (REPO / "mission-control/jade_temple/devops/templates/jade-cicd-caller.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count("@" + "0" * 40), 3)
        self.assertIn("Replace " + "0" * 40, text)

    def test_hub_pages_publisher_passes_full_deploy_contract(self):
        # Wave W1 exit: the hub's only production deploy passes DP1..DP10 (it failed only DP6 before pinning).
        rc, report = self.lint(".github/workflows/code-purple-method-atlas.yml", require=True)
        self.assertEqual(rc, 0, report)
        self.assertEqual([(r["job"], r["failed"]) for r in report], [("publish-pages", [])])

    def test_delegation_requires_a_sha_pinned_reusable_deploy(self):
        caller = ("on: push\npermissions: {contents: read}\njobs:\n  ci:\n"
                  "    uses: o/r/.github/workflows/jade-reusable-ci.yml@" + PIN + "\n"
                  "  d:\n    needs: ci\n    uses: o/r/.github/workflows/jade-reusable-deploy.yml@REF\n"
                  "    with: {environment: production, artifact-name: a, manifest-sha256: x, tests-ran: 1}\n")
        pinned = W.deploy_gates(parsed(caller.replace("@REF", "@" + PIN)), "d")
        self.assertEqual(set(pinned.values()), {"PASS"})
        loose = W.deploy_gates(parsed(caller.replace("@REF", "@v1")), "d")
        self.assertEqual(sorted(k for k, v in loose.items() if v == "FAIL"), ["DP10", "DP4", "DP6", "DP7", "DP8"])


class Cli(unittest.TestCase):
    def run_main(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = W.main(list(argv))
        return rc, json.loads(buf.getvalue())

    def test_lint_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            good = Path(td, "good.yml")
            good.write_text(GOOD, encoding="utf-8", newline="\n")
            plain = Path(td, "plain.yml")
            plain.write_text("on: push\njobs: {a: {steps: [{run: echo}]}}", encoding="utf-8", newline="\n")
            broken = Path(td, "broken.yml")
            broken.write_text("on: [push\n", encoding="utf-8", newline="\n")
            self.assertEqual(self.run_main("lint", str(good))[0], 0)
            rc, out = self.run_main("lint", str(plain), "--require-deploy")
            self.assertEqual((rc, out["verdict"]), (1, "DEPLOY_CONTRACT_FIRST_RED"))
            self.assertEqual(self.run_main("lint", str(broken))[0], 1)
            bad = Path(td, "bad.yml")
            bad.write_text(GOOD.replace("@" + PIN, "@v4"), encoding="utf-8", newline="\n")
            rc, out = self.run_main("lint", str(bad))
            self.assertEqual(rc, 1)
            self.assertIn("DP6", out["result"][0]["failed"])

    def test_secrets_lint_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            leak = Path(td, "leak.yml")
            leak.write_text(PR_JOB.format(cond="", val="${{ secrets.READ_TOKEN }}"), encoding="utf-8", newline="\n")
            rc, out = self.run_main("secrets-lint", str(leak))
            self.assertEqual((rc, out["verdict"], out["result"][0]["store_ref"]), (1, "PR_SECRET_EXPOSURE", "READ_TOKEN"))
            good = Path(td, "good.yml")
            good.write_text(GOOD, encoding="utf-8", newline="\n")
            self.assertEqual(self.run_main("secrets-lint", str(good))[:1], (0,))


PR_JOB = """
on:
  pull_request:
  workflow_dispatch:
jobs:
  scan:
    runs-on: ubuntu-24.04
    steps:
      - name: read
        {cond}
        env:
          TOKEN: {val}
        run: python scan.py
"""


def exposure(cond="", val="${{ secrets.READ_TOKEN }}", text=None):
    return W.pr_exposure(text if text is not None else PR_JOB.format(cond=cond, val=val), path="w.yml")


class PrSecretExposure(unittest.TestCase):
    def test_unguarded_step_secret_is_reachable_from_a_pr(self):
        self.assertEqual(exposure(), [{"path": "w.yml", "job": "scan", "step": "read", "store_ref": "READ_TOKEN"}])

    def test_step_condition_or_expression_that_rejects_prs_guards_it(self):
        self.assertEqual(exposure(cond="if: github.event_name != 'pull_request'"), [])
        self.assertEqual(exposure(val="${{ github.event_name != 'pull_request' && secrets.READ_TOKEN || '' }}"), [])

    def test_condition_that_admits_only_non_pr_events_guards_it(self):
        self.assertEqual(exposure(cond="if: github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'"), [])
        self.assertEqual(len(exposure(cond="if: github.event_name == 'pull_request' || github.event_name == 'schedule'")), 1)
        self.assertEqual(len(exposure(cond="if: always()")), 1)

    def test_job_level_guard_covers_its_steps(self):
        text = PR_JOB.format(cond="", val="${{ secrets.READ_TOKEN }}").replace(
            "    runs-on:", "    if: github.event_name == 'workflow_dispatch'\n    runs-on:")
        self.assertEqual(exposure(text=text), [])

    def test_secret_in_run_text_and_job_env_are_found(self):
        text = PR_JOB.format(cond="", val="plain").replace("run: python scan.py", "run: echo ${{ secrets.RUN_TOKEN }}")
        text = text.replace("    runs-on:", "    env: {J: '${{ secrets.JOB_TOKEN }}'}\n    runs-on:")
        self.assertEqual(sorted(f["store_ref"] for f in exposure(text=text)), ["JOB_TOKEN", "RUN_TOKEN"])

    def test_github_token_and_non_pr_workflows_are_not_exposures(self):
        self.assertEqual(exposure(val="${{ secrets.GITHUB_TOKEN }}"), [])
        self.assertEqual(exposure(text=PR_JOB.format(cond="", val="${{ secrets.READ_TOKEN }}").replace("pull_request:", "push:")), [])
        self.assertEqual(exposure(text="on: [pull_request\n"), [])
        self.assertEqual(exposure(text="on: pull_request\njobs: [a]\n"), [])

    def test_pull_request_target_and_inherited_secrets_are_flagged(self):
        text = "on: pull_request_target\njobs:\n  call:\n    uses: o/r/.github/workflows/x.yml@" + PIN + "\n    secrets: inherit\n"
        self.assertEqual(exposure(text=text), [{"path": "w.yml", "job": "call", "step": None, "store_ref": "INHERIT"}])

    def test_shipped_hub_workflows_expose_no_secret_to_prs(self):
        files = sorted((REPO / ".github" / "workflows").glob("*.yml"))
        self.assertGreater(len(files), 100)
        rc, report = W.exposure_lint([str(f) for f in files])
        self.assertEqual((rc, report), (0, []))


if __name__ == "__main__":
    unittest.main()
