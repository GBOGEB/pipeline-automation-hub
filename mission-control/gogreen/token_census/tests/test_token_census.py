import contextlib, io
import json, pathlib, sys, tempfile, unittest
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
MODULE = HERE.parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(MODULE))
import token_census as tc  # noqa: E402

SET = "2026-10-23T10:00:00Z"
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
SECRET_VALUE = "github_pat_" + "x" * 40


def run(i, at, conclusion, status="completed", event="schedule"):
    return {"id": i, "created_at": at, "status": status, "conclusion": conclusion, "event": event,
            "html_url": "https://github.com/run/%d" % i}


def registry(**over):
    reg = {
        "schema": "gogreen.token.registry.v1", "owner": "GBOGEB", "observed_at": SET,
        "hub": "GBOGEB/hub", "private_repos": ["GBOGEB/private"], "private_readers": ["READ"],
        "tokens": [{"id": 1, "name": "reader", "repos": [], "permissions": {}, "expires_days": 180},
                   {"id": 4, "name": "writer", "repos": [], "permissions": {}, "expires_days": 90}],
        "secrets": [
            {"name": "READ", "repo": "GBOGEB/hub", "token": 1, "set_at": SET,
             "consumers": [{"repo": "GBOGEB/hub", "workflow": "live.yml", "branch": "master", "without": "SOFT_DEFERRED"}]},
            {"name": "WRITE", "repo": "GBOGEB/app", "token": 4, "set_at": SET,
             "consumers": [{"repo": "GBOGEB/app", "workflow": "pub.yml", "branch": "main", "events": ["push"], "without": "RED"}]},
            {"name": "OPT", "repo": "GBOGEB/private", "token": 1, "set_at": None, "optional": True,
             "consumers": [{"repo": "GBOGEB/private", "workflow": "console.yml", "branch": "main", "without": "BUILTIN_TOKEN"}]},
        ]}
    reg.update(over)
    return reg


class Fake:
    """Routes GET URLs to canned (status, body, location) and records which token each saw."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, token=None, timeout=30):
        self.calls.append((url, token))
        status, body, location = self.routes.get(url, (404, b"{}", None))
        return status, body if isinstance(body, bytes) else json.dumps(body).encode(), location


def runs_url(repo, wf, branch, page=1):
    return "%s/repos/%s/actions/workflows/%s/runs?branch=%s&per_page=100&page=%d" % (tc.API, repo, wf, branch, page)


def jobs_url(repo, rid):
    return "%s/repos/%s/actions/runs/%d/jobs?per_page=100" % (tc.API, repo, rid)


class Paging(unittest.TestCase):
    consumer = {"repo": "GBOGEB/hub", "workflow": "live.yml", "branch": "master", "without": "SOFT_DEFERRED"}

    def test_follows_pages_until_the_pre_save_baseline(self):
        newer = [run(1000 + i, "2026-10-24T%02d:%02d:00Z" % (i // 60, i % 60), "success") for i in range(100)]
        fake = Fake({runs_url("GBOGEB/hub", "live.yml", "master", 1): (200, {"workflow_runs": newer}, None),
                     runs_url("GBOGEB/hub", "live.yml", "master", 2):
                         (200, {"workflow_runs": [run(1, "2026-10-23T09:00:00Z", "failure")]}, None)})
        gh = tc.GitHub("public", "", [], fake)
        runs, complete = tc.list_runs(gh, self.consumer, tc.parse_time(SET))
        self.assertTrue(complete)
        out = tc.lane_verdict(tc.parse_time(SET), runs)
        self.assertEqual((out["verdict"], out["runs_since_set"]), ("FIXED", 100))

    def test_page_cap_marks_the_baseline_incomplete(self):
        full = [run(i, "2026-10-24T10:00:00Z", "success") for i in range(100)]
        fake = Fake({runs_url("GBOGEB/hub", "live.yml", "master", p): (200, {"workflow_runs": full}, None)
                     for p in (1, 2)})
        runs, complete = tc.list_runs(tc.GitHub("public", "", [], fake), self.consumer, tc.parse_time(SET), max_pages=2)
        self.assertEqual((len(runs), complete), (200, False))

    def test_short_page_means_history_is_complete(self):
        fake = Fake({runs_url("GBOGEB/hub", "live.yml", "master", 1):
                     (200, {"workflow_runs": [run(5, "2026-10-23T11:00:00Z", "success")]}, None)})
        runs, complete = tc.list_runs(tc.GitHub("public", "", [], fake), self.consumer, tc.parse_time(SET))
        self.assertEqual((len(runs), complete, len(fake.calls)), (1, True, 1))


class JobView(unittest.TestCase):
    def view(self, jobs_by_run, runs):
        fake = Fake({jobs_url("GBOGEB/hub", rid): (200, {"jobs": jobs}, None) for rid, jobs in jobs_by_run.items()})
        return tc.job_view(tc.GitHub("public", "", [], fake), "GBOGEB/hub", runs, "dispatch", tc.parse_time(SET))

    def test_green_workflow_with_skipped_job_does_not_count(self):
        runs = [run(7, "2026-10-23T11:00:00Z", "success")]
        out = self.view({7: [{"name": "plan", "status": "completed", "conclusion": "success"},
                             {"name": "dispatch", "status": "completed", "conclusion": "skipped"}]}, runs)
        self.assertEqual(out, [])
        self.assertEqual(tc.action_for(dict(tc.lane_verdict(tc.parse_time(SET), out), token=3))[0], "WAIT")

    def test_the_named_job_decides_the_run(self):
        runs = [run(7, "2026-10-23T11:00:00Z", "failure"), run(6, "2026-10-23T09:00:00Z", "success")]
        out = self.view({7: [{"name": "dispatch", "status": "completed", "conclusion": "success"},
                             {"name": "w7", "status": "completed", "conclusion": "failure"}],
                         6: [{"name": "dispatch", "status": "completed", "conclusion": "failure"}]}, runs)
        self.assertEqual([(r["id"], r["conclusion"]) for r in out], [(7, "success"), (6, "failure")])
        self.assertEqual(tc.lane_verdict(tc.parse_time(SET), out)["verdict"], "FIXED")


class Verdicts(unittest.TestCase):
    def v(self, runs, set_at=SET):
        return tc.lane_verdict(tc.parse_time(set_at) if set_at else None, runs)

    def test_red_before_green_after_is_fixed(self):
        out = self.v([run(1, "2026-10-23T05:00:00Z", "failure"), run(2, "2026-10-23T10:05:00Z", "success")])
        self.assertEqual((out["verdict"], out["runs_since_set"], out["green_since_set"]), ("FIXED", 1, 1))

    def test_green_before_red_after_is_broke(self):
        out = self.v([run(1, "2026-10-23T09:00:00Z", "success"), run(2, "2026-10-23T10:30:00Z", "failure")])
        self.assertEqual((out["verdict"], out["latest"]), ("BROKE", "RED"))

    def test_other_pairs(self):
        g, r = "success", "failure"
        cases = {(g, g): "GREEN", (r, r): "STILL_RED"}
        for (a, b), want in cases.items():
            self.assertEqual(self.v([run(1, "2026-10-23T09:00:00Z", a), run(2, "2026-10-23T11:00:00Z", b)])["verdict"], want)
        self.assertEqual(self.v([run(2, "2026-10-23T11:00:00Z", g)])["verdict"], "NEW_GREEN")
        self.assertEqual(self.v([run(1, "2026-10-23T09:00:00Z", g)])["verdict"], "NO_RUN_SINCE_SET")

    def test_cancelled_skipped_and_running_runs_are_ignored(self):
        out = self.v([run(1, "2026-10-23T09:00:00Z", "failure"), run(2, "2026-10-23T10:10:00Z", "cancelled"),
                      run(3, "2026-10-23T10:20:00Z", None, status="in_progress"),
                      run(4, "2026-10-23T10:30:00Z", "skipped")])
        self.assertEqual(out["verdict"], "NO_RUN_SINCE_SET")

    def test_unset_optional_secret_still_reports_latest_state(self):
        out = self.v([run(1, "2026-10-23T09:00:00Z", "failure")], set_at=None)
        self.assertEqual((out["verdict"], out["latest"], out["latest_run"]["id"]), ("NOT_SET", "RED", 1))


class Signals(unittest.TestCase):
    def test_auth_forbidden_setting_and_missing(self):
        self.assertEqual(tc.classify_log('{"http_status": 401, "repository": "ABACUS"}'), "AUTH_INVALID")
        self.assertEqual(tc.classify_log("gh: Bad credentials (HTTP 401)"), "AUTH_INVALID")
        self.assertEqual(tc.classify_log("Resource not accessible by personal access token"), "FORBIDDEN")
        self.assertEqual(tc.classify_log("GraphQL: GitHub Actions is not permitted to create or approve "
                                         "pull requests (createPullRequest)"), "REPO_SETTING")
        self.assertEqual(tc.classify_log("::error::METRICS_PR_TOKEN is required for governed PR"), "SECRET_MISSING")

    def test_test_names_and_plain_reds_are_not_token_signals(self):
        self.assertEqual(tc.classify_log("test_hard_404_raises ... ok\nAssertionError: uncovered_branches"), "NONE")


class Probes(unittest.TestCase):
    def test_states_and_unset(self):
        self.assertEqual(tc.probe("", Fake({})), "UNSET")
        url = tc.API + "/repos/" + tc.PROBE_REPO
        for status, want in ((200, "VALID"), (401, "INVALID"), (403, "FORBIDDEN"), (404, "NOT_SELECTED"), (500, "HTTP_OTHER")):
            fake = Fake({url: (status, b"{}", None)})
            self.assertEqual(tc.probe(SECRET_VALUE, fake), want)
            self.assertEqual(fake.calls, [(url, SECRET_VALUE)])

    def test_log_redirect_is_followed_without_the_token(self):
        log_url = tc.API + "/repos/GBOGEB/hub/actions/jobs/7/logs"
        blob = "https://blob.example/log?sig=1"
        fake = Fake({log_url: (302, b"", blob), blob: (200, b"line", None)})
        gh = tc.GitHub("public", "private", [], fake)
        self.assertEqual(gh.log("GBOGEB/hub", 7), "line")
        self.assertEqual(fake.calls, [(log_url, "public"), (blob, None)])

    def test_private_repos_use_the_private_reader(self):
        fake = Fake({tc.API + "/repos/GBOGEB/private/x": (200, {}, None)})
        tc.GitHub("public", "private", ["GBOGEB/private"], fake).json("GBOGEB/private", "/x")
        self.assertEqual(fake.calls[0][1], "private")


def world(live_runs, live_log=b"", pub_runs=None, console_runs=None, console_log=b""):
    jobs = lambda repo, rid: "%s/repos/%s/actions/runs/%d/jobs?per_page=100" % (tc.API, repo, rid)
    logs = lambda repo, jid: "%s/repos/%s/actions/jobs/%d/logs" % (tc.API, repo, jid)
    return {
        runs_url("GBOGEB/hub", "live.yml", "master"): (200, {"workflow_runs": live_runs}, None),
        jobs("GBOGEB/hub", 2): (200, {"jobs": [{"id": 20, "conclusion": "failure"}]}, None),
        logs("GBOGEB/hub", 20): (200, live_log, None),
        runs_url("GBOGEB/app", "pub.yml", "main"): (200, {"workflow_runs": pub_runs or []}, None),
        runs_url("GBOGEB/private", "console.yml", "main"): (200, {"workflow_runs": console_runs or []}, None),
        jobs("GBOGEB/private", 9): (200, {"jobs": [{"id": 90, "conclusion": "failure"}]}, None),
        logs("GBOGEB/private", 90): (200, console_log, None),
    }


class Census(unittest.TestCase):
    def build(self, routes, probes=None):
        gh = tc.GitHub("public", "private", ["GBOGEB/private"], Fake(routes))
        return tc.census(tc.load_registry_from(registry()), gh, probes or {"READ": "VALID"}, NOW)

    def lane(self, receipt, secret):
        return next(l for l in receipt["lanes"] if l["secret"] == secret)

    def test_401_after_save_is_owner_action_and_unhealthy(self):
        r = self.build(world([run(1, "2026-10-23T09:00:00Z", "success"), run(2, "2026-10-23T10:30:00Z", "failure")],
                             live_log=b'{"http_status": 401}'))
        lane = self.lane(r, "READ")
        self.assertEqual((lane["verdict"], lane["signal"], lane["action"]), ("BROKE", "AUTH_INVALID", "OWNER"))
        self.assertEqual(r["token_health"], "ACTION_REQUIRED")
        self.assertEqual(r["threads_needed"], [])

    def test_non_token_red_asks_for_a_thread_per_stack(self):
        r = self.build(world([run(1, "2026-10-23T09:00:00Z", "success"), run(2, "2026-10-23T10:30:00Z", "failure")],
                             live_log=b"AssertionError: uncovered_branches"))
        self.assertEqual(self.lane(r, "READ")["action"], "THREAD")
        self.assertEqual(r["threads_needed"], [{"stack": "GBOGEB/hub", "lanes": ["live.yml"]}])
        self.assertEqual(r["token_health"], "HEALTHY")

    def test_event_filter_setting_signal_expiry_and_no_credit(self):
        r = self.build(world([run(1, "2026-10-23T10:30:00Z", "success")],
                             pub_runs=[run(3, "2026-10-23T08:00:00Z", "failure", event="push"),
                                       run(4, "2026-10-23T09:30:00Z", "success", event="workflow_run"),
                                       run(5, "2026-10-23T10:15:00Z", "success", event="push")],
                             console_runs=[run(9, "2026-10-23T06:00:00Z", "failure")],
                             console_log=b"GitHub Actions is not permitted to create or approve pull requests"))
        self.assertEqual(self.lane(r, "WRITE")["verdict"], "FIXED")
        console = self.lane(r, "OPT")
        self.assertEqual((console["verdict"], console["signal"], console["action"]), ("NOT_SET", "REPO_SETTING", "OWNER"))
        self.assertEqual(r["token_health"], "HEALTHY")
        writer = next(t for t in r["tokens"] if t["id"] == 4)
        self.assertEqual((writer["expires_estimate"], writer["days_left"]), ("2027-01-21", 89))
        self.assertEqual((r["formal_root_closure_credit"], r["merge_authorized"]), (0, False))
        self.assertEqual(r["totals"]["fixed"], 1)

    def test_invalid_probe_and_unread_workflow_are_owner_actions(self):
        routes = world([run(1, "2026-10-23T10:30:00Z", "success")])
        del routes[runs_url("GBOGEB/app", "pub.yml", "main")]
        r = self.build(routes, probes={"READ": "INVALID"})
        self.assertEqual(self.lane(r, "READ")["action"], "OWNER")
        self.assertEqual((self.lane(r, "WRITE")["verdict"], self.lane(r, "WRITE")["read_status"]), ("UNREAD", 404))
        self.assertEqual(r["token_health"], "ACTION_REQUIRED")


class Registry(unittest.TestCase):
    def test_rejects_bad_registries(self):
        bad = registry()
        bad["secrets"][0]["token"] = 9
        with self.assertRaisesRegex(ValueError, "unknown token"):
            tc.load_registry_from(bad)
        bad = registry()
        bad["secrets"][1]["set_at"] = None
        with self.assertRaisesRegex(ValueError, "no save time"):
            tc.load_registry_from(bad)
        bad = registry()
        bad["secrets"].append(dict(bad["secrets"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            tc.load_registry_from(bad)
        bad = registry(private_readers=["NOPE"])
        with self.assertRaisesRegex(ValueError, "private reader"):
            tc.load_registry_from(bad)

    def test_real_registry_matches_hub_workflows(self):
        reg = tc.load_registry(MODULE / "REGISTRY.json")
        self.assertEqual({t["id"] for t in reg["tokens"]}, {1, 2, 3, 4})
        hub = [(s["name"], c) for s in reg["secrets"] for c in s["consumers"] if c["repo"] == reg["hub"]]
        self.assertTrue(hub)
        for name, c in hub:
            text = (ROOT / ".github" / "workflows" / c["workflow"]).read_text(encoding="utf-8")
            self.assertIn("secrets." + name, text, "%s no longer reads %s" % (c["workflow"], name))
            if c.get("job"):
                self.assertIn("\n  %s:\n" % c["job"], text, "%s has no job %s" % (c["workflow"], c["job"]))
        census_wf = (ROOT / ".github" / "workflows" / "gogreen-token-census.yml").read_text(encoding="utf-8")
        for s in reg["secrets"]:
            if s["repo"] == reg["hub"]:
                self.assertIn("PROBE_%s: ${{ secrets.%s }}" % (s["name"], s["name"]), census_wf)


class Main(unittest.TestCase):
    def run_main(self, environ, routes):
        with tempfile.TemporaryDirectory() as d:
            reg = pathlib.Path(d, "r.json")
            reg.write_text(json.dumps(registry()), encoding="utf-8", newline="\n")
            code = tc.main(["--registry", str(reg), "--out", d], environ, Fake(routes), NOW)
            receipt = pathlib.Path(d, "token_census.json").read_text(encoding="utf-8")
            summary = pathlib.Path(d, "token_census.md").read_text(encoding="utf-8")
        return code, json.loads(receipt), receipt + summary

    def test_probe_drives_exit_code_and_values_never_leak(self):
        probe_url = tc.API + "/repos/" + tc.PROBE_REPO
        routes = world([run(1, "2026-10-23T10:30:00Z", "success")])
        code, receipt, text = self.run_main({"GH_TOKEN": "public", "PROBE_READ": SECRET_VALUE},
                                            dict(routes, **{probe_url: (200, b"{}", None)}))
        self.assertEqual((code, receipt["probes"]["READ"]), (0, "VALID"))
        self.assertNotIn(SECRET_VALUE, text)
        code, receipt, _ = self.run_main({"GH_TOKEN": "public", "PROBE_READ": SECRET_VALUE},
                                         dict(routes, **{probe_url: (401, b"{}", None)}))
        self.assertEqual((code, receipt["probes"]["READ"]), (1, "INVALID"))

    def test_owner_findings_become_annotations_without_values(self):
        probe_url = tc.API + "/repos/" + tc.PROBE_REPO
        routes = world([run(1, "2026-10-23T10:30:00Z", "success")])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code, receipt, _ = self.run_main({"GH_TOKEN": "public", "PROBE_READ": SECRET_VALUE, "GITHUB_ACTIONS": "true"},
                                             dict(routes, **{probe_url: (404, b"{}", None)}))
        lines = [l for l in out.getvalue().splitlines() if l.startswith("::")]
        self.assertEqual(code, 1)
        self.assertTrue(any(l.startswith("::error title=token census: READ::") and "NOT_SELECTED" in l for l in lines))
        self.assertEqual(sum(l.startswith("::error title=token census: READ::") for l in lines), 1)  # one per secret
        self.assertTrue(all("\n" not in l and SECRET_VALUE not in l for l in lines))
        self.assertEqual(tc.annotations(dict(receipt, tokens=[], lanes=[])), [])
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet):  # offline (no GITHUB_ACTIONS): no annotations
            self.run_main({"GH_TOKEN": "public", "PROBE_READ": SECRET_VALUE},
                          dict(routes, **{probe_url: (404, b"{}", None)}))
        self.assertNotIn("::error", quiet.getvalue())

    def test_annotations_stay_below_the_per_step_limit(self):
        lanes = [{"secret": "S%02d" % i, "token": 1, "repo": "o/r", "workflow": "w%d.yml" % i, "action": "OWNER",
                  "why": "re-save"} for i in range(13)]
        lanes += [{"secret": "S00", "token": 1, "repo": "o/r", "workflow": "t%d.yml" % i, "action": "THREAD",
                   "why": "other"} for i in range(12)]
        out = tc.annotations({"tokens": [{"id": 1, "name": "t", "probes": {}}], "lanes": lanes})
        errors = [l for l in out if l.startswith("::error")]
        warnings = [l for l in out if l.startswith("::warning")]
        self.assertEqual((len(errors), len(warnings)), (10, 10))
        self.assertIn("4 more findings", errors[-1])
        self.assertIn("3 more findings", warnings[-1])

    def test_local_run_without_probe_env_is_not_probed(self):
        code, receipt, text = self.run_main({"GH_TOKEN": "public"}, world([run(1, "2026-10-23T10:30:00Z", "success")]))
        self.assertEqual((code, receipt["probes"]["READ"]), (0, "NOT_PROBED"))
        self.assertIn("Token health: **HEALTHY**", text)


if __name__ == "__main__":
    unittest.main()
