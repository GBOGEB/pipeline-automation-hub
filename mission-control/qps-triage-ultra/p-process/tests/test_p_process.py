"""Offline tests for the P process (Code Purple x EVERRED): no network, no secrets.

Run: python -m unittest discover -s mission-control/qps-triage-ultra/p-process/tests -v
"""
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

P = Path(__file__).resolve().parents[1]
REPO = P.parents[2]


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, P / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


readback = load("p_readback", "kit/readback.py")
harvest = load("p_harvest", "everred/harvest.py")
build_rulesets = load("p_build_rulesets", "rulesets/build_rulesets.py")
verify_rulesets = load("p_verify_rulesets", "rulesets/verify_rulesets.py")
p_decide = load("p_decide", "p_decide.py")
refresh = load("p_refresh", "refresh.py")


class GhTransport(unittest.TestCase):
    """gh helpers retry network blips only, and decode UTF-8 (Windows defaults to cp1252)."""

    def _fake(self, results):
        calls = []

        def run(cmd, **kw):
            calls.append(kw)
            rc, out, err = results[min(len(calls), len(results)) - 1]
            return subprocess.CompletedProcess(cmd, rc, out, err)
        return run, calls

    def _patched(self, mod, results):
        from unittest import mock
        run, calls = self._fake(results)
        return mock.patch.object(mod.subprocess, "run", run), mock.patch.object(mod.time, "sleep", lambda s: None), calls

    def test_transient_error_is_retried_then_succeeds(self):
        for mod, call in ((readback, lambda: readback.gh("repos/x/pulls/1")),
                          (verify_rulesets, lambda: verify_rulesets.gh("repos/x/rulesets"))):
            with self.subTest(mod=mod.__name__):
                p1, p2, calls = self._patched(mod, [(1, "", "net/http: TLS handshake timeout"), (0, '{"ok": 1}', "")])
                with p1, p2:
                    self.assertEqual(call(), {"ok": 1})
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(kw.get("encoding") == "utf-8" for kw in calls))

    def test_http_404_is_not_retried(self):
        p1, p2, calls = self._patched(readback, [(1, "", "gh: Not Found (HTTP 404)")])
        with p1, p2, self.assertRaises(RuntimeError):
            readback.gh("repos/x/pulls/404")
        self.assertEqual(len(calls), 1)

    def test_persistent_outage_gives_up_and_never_reads_as_clean(self):
        p1, p2, calls = self._patched(verify_rulesets, [(1, "", "dial tcp: connectex: timed out")])
        with p1, p2:
            self.assertIn("_error", verify_rulesets.gh("repos/x/rulesets"))
        self.assertEqual(len(calls), 5)

    def test_harvest_retries_and_caches(self):
        harvest.CACHE.pop("repos/x/runs", None)
        p1, p2, calls = self._patched(harvest, [(1, "", "HTTP 502"), (0, "[1]", "")])
        with p1, p2:
            self.assertEqual(harvest.gh("repos/x/runs"), [1])
            self.assertEqual(harvest.gh("repos/x/runs"), [1])
        self.assertEqual(len(calls), 2)

    def test_one_retry_policy_across_helpers(self):
        # #858 and #860 retried different error sets; the consolidated helpers share one pattern.
        self.assertEqual({m.TRANSIENT.pattern for m in (harvest, readback, verify_rulesets)}, {harvest.TRANSIENT.pattern})
        for err in ("dial tcp: connection attempt failed", "HTTP 500: Internal Server Error", "HTTP 503", "TLS handshake timeout"):
            self.assertTrue(harvest.TRANSIENT.search(err), err)
        for err in ("HTTP 401: Bad credentials", "gh: Not Found (HTTP 404)", "HTTP 403: rate limit", "gh auth login"):
            self.assertFalse(harvest.TRANSIENT.search(err), err)

    def test_harvest_auth_error_fails_at_once_and_is_not_cached(self):
        # An unknown error is an answer to fail on, not a blip to retry; a retry that never succeeds raises too.
        harvest.CACHE.pop("repos/x/auth", None)
        p1, p2, calls = self._patched(harvest, [(1, "", "HTTP 401: Bad credentials (https://api.github.com/)")])
        with p1, p2, self.assertRaises(RuntimeError):
            harvest.gh("repos/x/auth")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("repos/x/auth", harvest.CACHE)
        harvest.CACHE.pop("repos/x/down", None)
        p1, p2, calls = self._patched(harvest, [(1, "", "HTTP 502: Bad Gateway")])
        with p1, p2, self.assertRaises(RuntimeError):
            harvest.gh("repos/x/down")
        self.assertEqual(len(calls), 5)

    def test_privacy_lookup_with_auth_failure_is_private(self):
        # Fail closed through the real gh(): a 401 on repos/<r> must not publish that repo's rows.
        harvest.CACHE.pop("repos/GBOGEB/unknown", None)
        p1, p2, _ = self._patched(harvest, [(1, "", "HTTP 401: Bad credentials")])
        with p1, p2:
            self.assertTrue(harvest.is_private("GBOGEB/unknown"))


class CodePurpleKit(unittest.TestCase):
    def test_empty_ruleset_is_not_clean(self):
        # 13 Oct lesson: a ruleset with zero rules passed L2. It must report every expected rule as absent.
        exp = [{"type": "deletion"}, {"type": "required_status_checks", "contexts": ["PR Feedback Gate"], "strict": True}]
        self.assertEqual(readback.missing_rules([], exp), ["deletion rule absent", "required_status_checks rule absent"])

    def test_partial_restore_still_reports_gate(self):
        actual = [{"type": "deletion"}, {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "smoke"}]}}]
        exp = [{"type": "deletion"}, {"type": "required_status_checks", "contexts": ["PR Feedback Gate"], "strict": True}]
        self.assertEqual(readback.missing_rules(actual, exp), ["required check 'PR Feedback Gate' absent", "strict up-to-date policy off"])

    def test_gate_state_is_taken_at_merge_time(self):
        runs = [{"name": "PR Feedback Gate", "conclusion": "failure", "completed_at": "2026-10-13T10:00:00Z"},
                {"name": "PR Feedback Gate", "conclusion": "success", "completed_at": "2026-10-13T12:00:00Z"}]
        self.assertEqual(readback.gate_at_merge(runs, "PR Feedback Gate", "2026-10-13T11:00:00Z"), "failure", "a green rerun after the merge must not count")
        self.assertEqual(readback.gate_at_merge(runs, "PR Feedback Gate", "2026-10-13T13:00:00Z"), "success")
        self.assertEqual(readback.gate_at_merge(runs[1:], "PR Feedback Gate", "2026-10-13T11:00:00Z"), "in_progress")
        self.assertEqual(readback.gate_at_merge([], "PR Feedback Gate", "2026-10-13T11:00:00Z"), "none")

    def test_classify_inherited_vs_source(self):
        c = readback.classify(["coverage", "lint"], ["coverage"])
        self.assertEqual(c, {"inherited": ["coverage"], "source_defect_candidates": ["lint"]})

    def test_incident_l2_declares_rule_content(self):
        inc = yaml.safe_load((P / "kit/incident.yaml").read_text())
        l2 = next(x for x in inc["lift_criteria"] if x["id"] == "L2")
        self.assertTrue(l2["ref"]["expected_rules"], "L2 must compare rule content, not only enforcement")
        self.assertIn("L5", {x["id"] for x in inc["lift_criteria"]})


class Rulesets(unittest.TestCase):
    def setUp(self):
        self.man = json.loads((P / "rulesets/manifest.json").read_text())

    def test_every_ruleset_is_basic_and_safe(self):
        for repo, m in self.man.items():
            rs = json.loads((P / "rulesets" / m["file"]).read_text())
            with self.subTest(repo=repo):
                self.assertEqual(rs["bypass_actors"], [], "break glass adds a bypass actor at the time; never ship one")
                self.assertEqual(rs["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
                types = [r["type"] for r in rs["rules"]]
                for t in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
                    self.assertIn(t, types)
                rsc = next(r for r in rs["rules"] if r["type"] == "required_status_checks")["parameters"]["required_status_checks"]
                self.assertEqual([c["context"] for c in rsc], m["checks"])
                self.assertTrue(all(c["integration_id"] == build_rulesets.ACTIONS for c in rsc))

    def test_generator_matches_committed_files(self):
        for repo, cfg in build_rulesets.REPOS.items():
            name = repo.split("/")[1]
            committed = json.loads((P / "rulesets" / f"{name}.basic.json").read_text())
            self.assertEqual(build_rulesets.basic(repo, cfg), committed, f"{name}.basic.json is stale: run build_rulesets.py")

    def test_hub_required_checks_are_not_path_filtered(self):
        jobs = build_rulesets.path_filtered_jobs(REPO / ".github/workflows")
        for c in self.man["GBOGEB/pipeline-automation-hub"]["checks"]:
            job = build_rulesets.STATUS_PRODUCERS.get(c, (None, c))[1]
            self.assertIn(job, jobs, f"{c} is not a PR job (or produced by one) in this repo")
            self.assertFalse(jobs[job], f"{c} is path-filtered: as a required check it would block unrelated PRs")

    def test_required_status_contexts_are_published_by_their_producer(self):
        for context, (wf, job) in build_rulesets.STATUS_PRODUCERS.items():
            with self.subTest(context=context):
                text = (REPO / ".github/workflows" / wf).read_text(encoding="utf-8")
                d = yaml.safe_load(text)
                self.assertIn(job, d["jobs"], f"{wf} has no job {job}")
                self.assertIn("pull_request_target", d.get(True, d.get("on")), "the status must come from the trusted base-side event")
                self.assertIn(f"context='{context}'", text, f"{wf} does not publish {context}")

    def test_published_ruleset_copies_match_source(self):
        # The P-process workflow packages site/ as committed; refresh.py is what copies rulesets/ there.
        for f in sorted((P / "rulesets").glob("*.json")):
            if f.name == "survey.json":
                continue
            with self.subTest(file=f.name):
                self.assertEqual((P / "site/rulesets" / f.name).read_bytes(), f.read_bytes(),
                                 f"site/rulesets/{f.name} is stale: copy it (refresh.py) and update site/manifest.json")

    def test_path_filter_detection(self):
        tmp = P / "build" / "wf_test"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        (tmp / "a.yml").write_text("on:\n  pull_request:\n    paths: ['x/**']\njobs:\n  audit:\n    runs-on: x\n")
        (tmp / "b.yml").write_text("on: [pull_request]\njobs:\n  t:\n    name: smoke\n    runs-on: x\n")
        j = build_rulesets.path_filtered_jobs(tmp)
        self.assertTrue(j["audit"])
        self.assertFalse(j["smoke"])
        shutil.rmtree(tmp)

    def test_drift_gaps(self):
        exp = json.loads((P / "rulesets/ABACUS.basic.json").read_text())
        eff = [{"type": "deletion"}, {"type": "pull_request", "parameters": {"required_review_thread_resolution": True}}, {"type": "non_fast_forward"}]
        self.assertEqual(verify_rulesets.gaps(eff, exp), ["required_status_checks missing"])
        self.assertEqual(len(verify_rulesets.gaps([], exp)), 4)

    def test_drift_detects_wrong_app(self):
        exp = json.loads((P / "rulesets/gg_MATH.basic.json").read_text())
        good = [{"type": t} for t in ("deletion", "non_fast_forward")] + [
            {"type": "pull_request", "parameters": {"required_review_thread_resolution": True}},
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "first-kernel", "integration_id": 15368}, {"context": "monte-carlo-reference", "integration_id": 15368}]}}]
        self.assertEqual(verify_rulesets.gaps(good, exp), [])
        good[3]["parameters"]["required_status_checks"][0]["integration_id"] = 999
        self.assertEqual(verify_rulesets.gaps(good, exp), ["required check 'first-kernel' pinned to another app (expected integration 15368)"])


class Everred(unittest.TestCase):
    def setUp(self):
        self.ledger = yaml.safe_load((P / "everred/roots.yaml").read_text())

    def test_signature_normalisation(self):
        self.assertEqual(harvest.split_env("tests (Python 3.12, ubuntu-latest)"), ("tests", "Python 3.12, ubuntu-latest"))
        self.assertEqual(harvest.norm("shard-007 at 1a2b3c4d5e"), "shard-* at <sha>")

    def test_probe_fails_closed(self):
        root = {"id": "X", "match": [{"probe": "ruleset_drift", "repo": "GBOGEB/none"}]}
        self.assertTrue(harvest.probe_root(root, {})["red"], "a repo missing from the drift census must not read green")
        green = harvest.probe_root(root, {"GBOGEB/none": {"red": False, "gaps": [], "effective_rules": ["deletion"]}})
        self.assertFalse(green["red"])
        self.assertIsNone(harvest.probe_root({"id": "Y", "match": [{"job": "lint"}]}, {}))

    def _stub_gh(self, answer):
        """Offline gh(): answer(path) -> body; every served path is recorded. CACHE is cleared around the test."""
        from unittest import mock
        served = []
        harvest.CACHE.clear()
        self.addCleanup(harvest.CACHE.clear)

        def fake(path):
            served.append(path)
            return answer(path)
        patcher = mock.patch.object(harvest, "gh", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return served

    @staticmethod
    def _page(path):
        return int(re.search(r"[?&]page=(\d+)", path).group(1))

    def test_failed_jobs_reads_past_the_first_page(self):
        # 2026-10-24: ABACUS main had 121 check runs; the single per_page=100 read missed failures 101-121.
        repo, sha = "GBOGEB/stub", "a" * 40
        url = "https://github.com/GBOGEB/stub/actions/runs/1/job/{}"
        runs = [{"id": i, "conclusion": "failure" if i in (7, 105, 121) else "success", "html_url": url.format(i)} for i in range(1, 122)]

        def answer(path):
            if "/check-runs?" in path:
                n = self._page(path)
                return {"total_count": 121, "check_runs": runs[(n - 1) * 100:n * 100]}
            return {"id": int(path.rsplit("/", 1)[1]), "name": "job"}
        served = self._stub_gh(answer)
        self.assertEqual([j["id"] for j in harvest.failed_jobs_for_sha(repo, sha)], [7, 105, 121])
        self.assertEqual(sum("/check-runs?" in p for p in served), 4, "two stable passes of two pages for 121 runs")

    def test_check_run_pages_fail_closed(self):
        repo, sha = "GBOGEB/stub", "b" * 40
        runs = [{"id": i, "conclusion": "failure", "html_url": "https://x/actions/runs/1/job/1"} for i in range(1, 101)]
        # page 2 comes back empty although total_count says 121: never return a short list
        served = self._stub_gh(lambda path: {"total_count": 121, "check_runs": runs if self._page(path) == 1 else []})
        with self.assertRaisesRegex(RuntimeError, "read 100 distinct of total_count 121"):
            harvest.failed_jobs_for_sha(repo, sha)
        self.assertFalse(any("/actions/jobs/" in p for p in served), "no job is read from a short census")

    def test_check_run_population_changing_mid_read_fails_closed(self):
        # Codex review on #858: counts that add up do not prove a consistent snapshot. Here run 1 lands
        # after page 1 is read, so every pass sees ids 2-102 and never run 1. If run 1 is a failure, accepting
        # that read would undercount it, so a census whose population moves during pagination is never accepted.
        repo, sha = "GBOGEB/stub", "c" * 40
        runs = [{"id": i, "conclusion": "success", "html_url": ""} for i in range(1, 103)]
        pages = {1: (101, runs[1:101]), 2: (102, runs[100:102]), 3: (102, [])}
        self._stub_gh(lambda path: dict(zip(("total_count", "check_runs"), pages[self._page(path)])))
        with self.assertRaisesRegex(RuntimeError, "no two consecutive stable reads agreed; last read 101 distinct of total_count 101/102"):
            harvest.check_runs_for_sha(repo, sha)

    def test_check_run_growth_that_settles_is_read_whole(self):
        # A live head grows during the first pass (2026-10-25: ABACUS main 807 -> 811), then settles: the
        # read repeats until two consecutive passes agree, and the run that landed mid-read (id 1) is held.
        repo, sha = "GBOGEB/stub", "e" * 40
        runs = [{"id": i, "conclusion": "failure" if i == 1 else "success", "html_url": ""} for i in range(1, 103)]
        growing = {1: (101, runs[1:101]), 2: (102, runs[100:102]), 3: (102, [])}
        settled = {1: (102, runs[:100]), 2: (102, runs[100:102])}
        passes = []

        def answer(path):
            if self._page(path) == 1:
                passes.append(path)
            return dict(zip(("total_count", "check_runs"), (growing if len(passes) == 1 else settled)[self._page(path)]))
        self._stub_gh(answer)
        got = harvest.check_runs_for_sha(repo, sha)
        self.assertEqual(sorted(r["id"] for r in got), list(range(1, 103)))
        self.assertEqual(len(passes), 3, "one moving pass, then two agreeing stable passes")

    def test_check_run_total_falling_mid_read_restarts_then_fails_closed(self):
        # A run vanished mid-read (e.g. superseded by a rerun): later pages shift back and a run can be skipped.
        repo, sha = "GBOGEB/stub", "d" * 40
        runs = [{"id": i, "conclusion": "success", "html_url": ""} for i in range(1, 103)]
        pages = {1: (102, runs[:100]), 2: (101, runs[101:102]), 3: (101, [])}  # run 101 skipped by the shift
        served = self._stub_gh(lambda path: dict(zip(("total_count", "check_runs"), pages[self._page(path)])))
        with self.assertRaisesRegex(RuntimeError, "read 101 distinct of total_count 102/101"):
            harvest.check_runs_for_sha(repo, sha, attempts=2)
        self.assertEqual(sum(p.endswith("page=1") for p in served), 2, "the read restarts from page 1")

    def test_gh_retries_transport_errors_but_not_4xx(self):
        from types import SimpleNamespace
        from unittest import mock
        harvest.CACHE.clear()
        self.addCleanup(harvest.CACHE.clear)
        flaky = [SimpleNamespace(returncode=1, stdout="", stderr="dial tcp: connection attempt failed"),
                 SimpleNamespace(returncode=0, stdout='{"ok": 1}', stderr="")]
        with mock.patch.object(harvest.subprocess, "run", side_effect=flaky) as run, mock.patch.object(harvest.time, "sleep"):
            self.assertEqual(harvest.gh("repos/x/flaky"), {"ok": 1})
        self.assertEqual(run.call_count, 2)
        gone = SimpleNamespace(returncode=1, stdout="", stderr="gh: Not Found (HTTP 404)")
        with mock.patch.object(harvest.subprocess, "run", return_value=gone) as run, mock.patch.object(harvest.time, "sleep"):
            with self.assertRaises(RuntimeError):
                harvest.gh("repos/x/gone")
        self.assertEqual(run.call_count, 1, "a 404 is an answer, not a transient error")

    @staticmethod
    def _occ(repo, pr, sha, step, run_id):
        url = f"https://github.com/{repo}/actions/runs/{run_id}/job/{run_id + 1}"
        return {"repo": repo, "sha": sha, "pr": pr, "source": "open-pr", "workflow": "CI", "job": "tests", "env": "",
                "step": step, "step_number": 3, "run_id": run_id, "run_attempt": 1, "job_id": run_id + 1, "url": url,
                "completed_at": "2026-10-25T10:00:00Z", "runner": f"runner-{run_id}", "signature": f"CI :: tests :: {step}"}

    def _private_fixture(self):
        roots = [{"id": "PUB-RC-2026-0001", "title": "lint root", "class": "PRODUCT_DEFECT", "state": "TRIAGED", "dims": {},
                  "match": [{"step": "lint"}]}]
        pub, priv = "GBOGEB/pubrepo", "GBOGEB/secretrepo"
        occ = [self._occ(pub, 11, "a" * 40, "lint", 900001), self._occ(pub, 12, "b" * 40, "public-unmatched-step", 900003),
               self._occ(priv, 7771, "c" * 40, "lint", 800001), self._occ(priv, 7772, "d" * 40, "secret-step-text", 800003),
               self._occ(priv, 7773, "e" * 40, "secret-step-text", 800005)]
        secrets = ["7771", "7772", "7773", "c" * 40, "d" * 40, "e" * 40, "800001", "800003", "800005",
                   "secret-step-text", "runner-800", f"{priv}/actions", f"{priv}/pull"]
        return roots, occ, pub, priv, secrets

    def test_private_repo_rows_never_reach_any_output(self):
        roots, occ, pub, priv, secrets = self._private_fixture()
        rep, rows = harvest.build_report([pub, priv], roots, occ, {}, "2026-10-25T00:00:00+00:00", {priv})
        outputs = {"everred.json": json.dumps(rep), "occurrences.json": json.dumps(rows), "register.md": harvest.render(rep),
                   "rex_return.yaml": yaml.safe_dump(harvest.rex_return(rep, rep["generated_at"]))}
        for name, text in outputs.items():
            for s in secrets:
                with self.subTest(output=name, secret=s):
                    self.assertNotIn(s, text)
        # ...while every count still includes the private occurrences
        m = rep["metrics"]
        self.assertEqual((m["occurrences_total"], m["distinct_signatures"], m["unmatched_signatures"]), (5, 3, 2))
        root = rep["roots"][0]
        self.assertEqual((root["occurrences"], root["affected_shas"], root["affected_prs"]), (2, 2, [11]))
        self.assertEqual(rep["private_rows"], "AGGREGATE_ONLY")
        self.assertEqual(rep["private_aggregate"], {priv: {"occurrences": 3, "distinct_signatures": 2, "unmatched_signatures": 1,
                                                           "linked_roots": {"PUB-RC-2026-0001": 1}}})
        self.assertEqual([u["signature"] for u in rep["unmatched"]], ["CI :: tests :: public-unmatched-step"])
        self.assertEqual({o["repo"] for o in rows}, {pub})
        self.assertIn(priv, outputs["register.md"], "the private repo is named with its counts")

    def test_public_behaviour_unchanged_without_private_repos(self):
        roots, occ, pub, priv, _ = self._private_fixture()
        rep, rows = harvest.build_report([pub, priv], roots, occ, {}, "2026-10-25T00:00:00+00:00", set())
        self.assertEqual(len(rows), 5)
        self.assertEqual(rep["private_aggregate"], {})
        self.assertEqual(rep["roots"][0]["affected_prs"], [11, 7771])
        self.assertEqual({u["signature"]: u["occurrences"] for u in rep["unmatched"]},
                         {"CI :: tests :: secret-step-text": 2, "CI :: tests :: public-unmatched-step": 1})

    def test_privacy_is_read_from_the_source_and_fails_closed(self):
        def answer(path):
            if path.endswith("/gone"):
                raise RuntimeError("gh api: HTTP 404")
            return {"repos/GBOGEB/open": {"private": False}, "repos/GBOGEB/closed": {"private": True}}.get(path, {})
        self._stub_gh(answer)
        self.assertFalse(harvest.is_private("GBOGEB/open"))
        self.assertTrue(harvest.is_private("GBOGEB/closed"))
        self.assertTrue(harvest.is_private("GBOGEB/gone"), "a failed lookup is private")
        self.assertTrue(harvest.is_private("GBOGEB/nofield"), "no explicit private: false is private")

    def test_probe_is_not_a_signature_match(self):
        self.assertFalse(harvest.matches({"repo": "r", "workflow": "w", "job": "j", "step": "s"}, {"probe": "ruleset_drift"}))

    def test_root_ledger_schema(self):
        L = self.ledger
        self.assertEqual(L["schema"], "everred.roots/3.0")
        ids = [r["id"] for r in L["roots"]]
        self.assertEqual(len(ids), len(set(ids)), "root IDs are never reused")
        for r in L["roots"]:
            with self.subTest(root=r["id"]):
                self.assertRegex(r["id"], r"^[A-Z]+-RC-\d{4}-\d{4}$")
                self.assertIn(r["state"], L["lifecycle"])
                self.assertIn(r["class"], L["classes"])
                self.assertEqual(set(r["dims"]), set(L["dimensions"]), "all seven dimensions, every root")
                for k, v in r["dims"].items():
                    self.assertIn(v, L["dimensions"][k] + ["NA"])
                if r["class"] == "CONTROL_PLANE_DRIFT":
                    self.assertTrue(any(m.get("probe") == "ruleset_drift" for m in r.get("match", [])), "drift is found by probe, not by a red job")
                if r.get("split_from"):
                    self.assertIn(r["split_from"], ids)

    def test_probe_scope_covers_manifest(self):
        man = json.loads((P / "rulesets/manifest.json").read_text())
        self.assertEqual(set(self.ledger["probe_scope"]), set(man))


class Decide(unittest.TestCase):
    ROOTS = [{"id": "ABACUS-RC-2026-0001", "severity": "P0", "state": "BLOCKED_AUTHORITY", "probe": {"red": True}},
             {"id": "CODEX-RC-2026-0003", "severity": "P1", "state": "BLOCKED_AUTHORITY", "probe": {"red": True}}]

    def test_open_case_and_p0_drift_escalate(self):
        st = p_decide.decide({"lifted": False, "lift": [{"ok": True}, {"ok": False}]}, {"roots": self.ROOTS},
                             {"repos": {"GBOGEB/ABACUS": {"red": True}, "GBOGEB/CODEX": {"red": True}}}, ["GBOGEB/ABACUS"])
        a, c = st["repos"]["GBOGEB/ABACUS"], st["repos"]["GBOGEB/CODEX"]
        self.assertEqual(a["mode"], "CODE_PURPLE")
        self.assertEqual([r[:2] for r in a["reasons"]], ["E2", "E1"])
        self.assertEqual(c["mode"], "EVERRED", "P1 drift is an EVERRED lane, not an escalation")

    def test_lifted_case_hands_off(self):
        st = p_decide.decide({"lifted": True, "lift": []}, {"roots": []}, {"repos": {}}, ["GBOGEB/ABACUS"])
        self.assertEqual(st["repos"]["GBOGEB/ABACUS"]["mode"], "EVERRED")
        self.assertEqual(st["repos"]["GBOGEB/ABACUS"]["ruleset"], "UNKNOWN", "no drift row is UNKNOWN, never GREEN")


class Site(unittest.TestCase):
    def test_census_markers_rewrite(self):
        page = P / "build" / "cp_test.html"
        page.parent.mkdir(exist_ok=True)
        page.write_text("<div>\n<!-- census:begin x -->\nOLD\n<!-- census:end -->\n</div>", encoding="utf-8")
        c = {"lifted": False, "lift": [{"ok": True}, {"ok": False}], "generated_at": "2026-10-17T20:25:00+00:00",
             "repos": {"GBOGEB/ABACUS": {"open_prs": 9}}, "merges_since_unblock": 3}
        refresh.stamp_code_purple(page, c)
        t = page.read_text(encoding="utf-8")
        self.assertNotIn("OLD", t)
        self.assertIn("NOT LIFTED · 1 of 2 lift criteria", t)
        self.assertIn("ABACUS: 9 open PRs", t)
        page.unlink()

    def test_committed_site_matches_manifest(self):
        man = json.loads((P / "site/manifest.json").read_text())
        for rel, h in man["files_sha256"].items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((P / "site" / rel).read_bytes()).hexdigest(), h)

    def test_manifest_paths_are_posix(self):
        # a refresh on Windows once wrote 'rulesets\\x.json', which Linux CI cannot open
        man = json.loads((P / "site/manifest.json").read_text())
        self.assertEqual([k for k in man["files_sha256"] if "\\" in k], [])

    def test_manifest_never_claims_carried_over_files_as_current(self):
        man = json.loads((P / "site/manifest.json").read_text(encoding="utf-8"))
        for rel, origin in man.get("carried_over", {}).items():
            with self.subTest(file=rel):
                self.assertIn(rel, refresh.CENSUS_DATED)
                self.assertIn(rel, man["files_sha256"])
                self.assertNotEqual(origin, man["census_at"], "a carried-over file must name its own census")
        md = (P / "site/code-purple/code-purple.md").read_text(encoding="utf-8")
        stamp = re.search(r"readback (\d{4}-\d{2}-\d{2})", md).group(1)
        if not man["census_at"].startswith(stamp):
            self.assertIn("code-purple/code-purple.md", man.get("carried_over", {}),
                          "code-purple.md is from another census but the manifest presents it as current")

    def test_carried_over_rules(self):
        prev = {"census_at": "2026-10-18T00:00:00+00:00", "files_sha256": {"P-process-deck.pdf": "a", "code-purple/code-purple.md": "b"}}
        now = {"P-process-deck.pdf": "a", "code-purple/code-purple.md": "CHANGED", "index.html": "x"}
        self.assertEqual(refresh.carried_over(prev, now, rebuilt=True), {})
        self.assertEqual(refresh.carried_over(prev, now, rebuilt=False),
                         {"P-process-deck.pdf": "2026-10-18T00:00:00+00:00", "code-purple/code-purple.md": None})
        chained = {**prev, "census_at": "2026-10-25T00:00:00+00:00", "carried_over": {"P-process-deck.pdf": "2026-10-18T00:00:00+00:00"}}
        self.assertEqual(refresh.carried_over(chained, {"P-process-deck.pdf": "a"}, rebuilt=False),
                         {"P-process-deck.pdf": "2026-10-18T00:00:00+00:00"}, "origin survives repeated --no-pdf runs")

    def test_pages_link_together_and_census_is_current(self):
        idx = (P / "site/index.html").read_text()
        for href in ("code-purple/index.html", "everred/index.html", "P-process-deck.pdf"):
            self.assertIn(href, idx)
            self.assertTrue((P / "site" / href).is_file(), href)
        census = json.loads((P / "site/code-purple/kit/census.json").read_text())
        cp = (P / "site/code-purple/index.html").read_text()
        self.assertIn("read back " + census["generated_at"][:16].replace("T", " "), cp, "Code Purple header not stamped from the census")


@unittest.skipUnless(shutil.which("node"), "node not installed")
class Model(unittest.TestCase):
    def test_model_integrity(self):
        r = subprocess.run(["node", str(P / "tools/check_model.mts")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])

    def test_broken_model_fails(self):
        src = (P / "code-purple/assets/model.js").read_text()
        bad = P / "build" / "model_bad.js"
        bad.parent.mkdir(exist_ok=True)
        bad.write_text(src.replace('f:"N01"', 'f:"N99"', 1))
        r = subprocess.run(["node", str(P / "tools/check_model.mts")], capture_output=True, text=True, env={"CP_MODEL_JS": str(bad), "PATH": "/usr/bin:/bin:" + str(Path(shutil.which("node")).parent)})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(re.search(r"N99 is not a node", r.stderr))
        bad.unlink()


if __name__ == "__main__":
    unittest.main()
