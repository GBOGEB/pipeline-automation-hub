"""Offline tests for burndown_pulse.py and issue_pulse.py with a fake gh runner.

Run: python -m unittest discover -s tools/workstation/dashboards/pulse -p "test_*.py" -v
No network and no gh login are needed: `burndown_pulse.run` is replaced by FakeGh.
"""
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import uuid
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import burndown_pulse as bp  # noqa: E402
import issue_pulse as ip  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
PAH = "GBOGEB/pipeline-automation-hub"


def iso(days_ago, hours=0):
    return (NOW - dt.timedelta(days=days_ago, hours=hours)).isoformat().replace("+00:00", "Z")


class FakeGh:
    """Stands in for subprocess.run(["gh", ...]); answers from canned data and records each call."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def __call__(self, cmd, **kwargs):
        assert cmd[0] == "gh", cmd
        assert "GITHUB_TOKEN" not in kwargs["env"] and "GH_TOKEN" not in kwargs["env"]
        args = cmd[1:]
        self.calls.append(args)
        data = self.handler(args)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(data), stderr="")


def opt(args, name):
    return args[args.index(name) + 1] if name in args else None


def burndown_handler(args):
    repo = opt(args, "-R")
    if args[:2] == ["repo", "view"]:
        return {"defaultBranchRef": {"name": "master"}}
    if args[0] == "api" and "/commits/" in args[1]:
        return {"sha": "0123456789abcdef" if PAH in args[1] else "fedcba9876543210"}
    if args[:2] == ["pr", "list"] and opt(args, "--state") == "open":
        if repo != PAH:
            return []
        fpc = {"name": "first-pass-closure", "conclusion": "FAILURE"}
        ok = {"name": "tests", "conclusion": "SUCCESS"}
        return [
            dict(number=1, title="feat: a (do not merge unless green)", isDraft=False, mergeStateStatus="BLOCKED",
                 baseRefName="master", headRefName="feat/a", headRefOid="a" * 40,
                 statusCheckRollup=[fpc, ok], updatedAt=iso(0), createdAt=iso(2)),
            dict(number=2, title="feat: b", isDraft=True, mergeStateStatus="CLEAN", baseRefName="feat/a",
                 headRefName="feat/b", headRefOid="b" * 40, statusCheckRollup=[], updatedAt=iso(0), createdAt=iso(1)),
            dict(number=3, title="fix: c", isDraft=False, mergeStateStatus="CLEAN", baseRefName="master",
                 headRefName="fix/c", headRefOid="c" * 40, statusCheckRollup=[ok], updatedAt=iso(0), createdAt=iso(3)),
        ]
    if args[:2] == ["pr", "list"] and opt(args, "--state") == "merged":
        day = opt(args, "--search").split(":", 1)[1]
        if repo == PAH and day == NOW.date().isoformat():
            return [{"number": 9, "mergedAt": iso(0, hours=1),
                     "statusCheckRollup": [{"name": "first-pass-closure", "conclusion": "FAILURE"}]}]
        return []
    if args[:2] == ["run", "list"]:
        if repo != PAH:
            return []
        run = lambda c, h, i: dict(workflowName="CI", conclusion=c, status="completed",  # noqa: E731
                                   createdAt=iso(0, hours=h), headSha="d" * 40, event="push", databaseId=i)
        return [run("failure", 1, 3), run("failure", 2, 2), run("success", 3, 1),
                dict(workflowName="Docs", conclusion="success", status="completed", createdAt=iso(0),
                     headSha="e" * 40, event="push", databaseId=4)]
    raise AssertionError(f"unexpected gh call: {args}")


class ReadOnlyGuardTests(unittest.TestCase):
    def test_reads_pass(self):
        for args in (["repo", "view", PAH, "--json", "defaultBranchRef"],
                     ["pr", "list", "-R", PAH, "--state", "open"],
                     ["run", "list", "-R", PAH],
                     ["api", "repos/x/commits/master", "--jq", "{sha: .sha}"],
                     ["api", "-X", "GET", "search/issues", "-f", "q=repo:x", "-F", "page=1"],
                     ["api", "graphql", "-f", "query=query{viewer{login}}"]):
            bp.assert_read_only(args)

    def test_writes_are_refused(self):
        for args in (["pr", "merge", "1"], ["pr", "create"], ["issue", "comment", "1", "-b", "x"],
                     ["api", "-X", "POST", "repos/x/issues/1/comments"],
                     ["api", "--method=PATCH", "repos/x/issues/1"],
                     ["api", "repos/x/issues/1/labels", "-f", "labels[]=x"],
                     ["api", "graphql", "-f", "query=mutation{addComment(input:{}){clientMutationId}}"],
                     []):
            with self.assertRaises(ValueError, msg=args):
                bp.assert_read_only(args)

    def test_gh_refuses_before_running(self):
        fake = FakeGh(lambda a: None)
        with mock.patch.object(bp, "run", fake), self.assertRaises(ValueError):
            bp.gh("pr", "merge", "1")
        self.assertEqual(fake.calls, [])


class BurndownPulseTests(unittest.TestCase):
    def test_rows_and_next_steps(self):
        fake = FakeGh(burndown_handler)
        with tempfile.TemporaryDirectory() as out, mock.patch.object(bp, "run", fake), \
                contextlib.redirect_stdout(io.StringIO()):
            summary = bp.main(out, now=NOW)
            rows = json.load(open(summary["path"], encoding="utf-8"))
        meta = rows[0]
        self.assertEqual(meta["kind"], "meta")
        self.assertEqual(meta["heads"], "PAH@01234567; cryoplant@fedcba98; ABACUS@fedcba98")
        prs = {r["pr"]: r for r in rows if r["kind"] == "pr"}
        self.assertEqual(prs[1]["next_step"], "Codex review on exact head")
        self.assertEqual(prs[1]["fpc_red"], 1)
        self.assertEqual(prs[2]["next_step"], "Owner marks ready")
        self.assertEqual(prs[2]["stacked_on"], "PAH#1")
        self.assertEqual(prs[3]["next_step"], "Merge-ready (squash)")
        wf = [r for r in rows if r["kind"] == "wf"]
        self.assertEqual([(r["workflow"], r["streak"], r["streak_note"]) for r in wf], [("CI", 2, "")])
        repo = next(r for r in rows if r["kind"] == "repo" and r["repo"] == "PAH")
        self.assertEqual((repo["open_prs"], repo["merge_ready"], repo["merged_7d"], repo["merged_fpc_red_7d"]),
                         (3, 1, 1, 1))
        self.assertEqual(len([r for r in rows if r["kind"] == "day"]), 8 * len(bp.REPOS))
        for args in fake.calls:
            bp.assert_read_only(args)


def fake_register(issues_by_repo):
    reg = types.SimpleNamespace()
    reg.exact_count = lambda getter, full, kind, state: len(issues_by_repo.get(full, []))
    reg.retrieve_issue_register = lambda getter, full, state, expected: issues_by_repo.get(full, [])
    return reg


def issue(n, title, labels=(), idle_days=1):
    return dict(number=n, title=title, labels=list(labels), url=f"https://github.com/{PAH}/issues/{n}",
                created_at_utc=iso(40), updated_at_utc=iso(idle_days))


def issue_handler(args):
    if args[:2] == ["api", "graphql"]:
        name = opt(args, "-F") and next(a.split("=", 1)[1] for a in args if a.startswith("name="))
        nodes = []
        if name == "pipeline-automation-hub":
            pr_ref = lambda n, s: {"number": n, "state": s, "isDraft": False,  # noqa: E731
                                   "repository": {"nameWithOwner": PAH}}
            nodes = [
                {"number": 10, "assignees": {"nodes": [{"login": "someone"}]},
                 "closedByPullRequestsReferences": {"nodes": []}, "timelineItems": {"nodes": []}},
                {"number": 11, "assignees": {"nodes": []},
                 "closedByPullRequestsReferences": {"nodes": [pr_ref(5, "MERGED")]}, "timelineItems": {"nodes": []}},
            ]
        return {"data": {"repository": {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": nodes}}}}
    if args[:2] == ["pr", "list"]:
        if opt(args, "-R") != PAH:
            return []
        return [dict(number=20, title="fix: thing", body="Closes #10", isDraft=False,
                     statusCheckRollup=[{"name": "tests", "conclusion": "FAILURE"}], closingIssuesReferences=[],
                     createdAt=iso(1), url=f"https://github.com/{PAH}/pull/20"),
                dict(number=21, title="docs: see #12", body="", isDraft=False, statusCheckRollup=[],
                     closingIssuesReferences=[], createdAt=iso(1), url=f"https://github.com/{PAH}/pull/21")]
    if args[:4] == ["api", "-X", "GET", "search/issues"]:
        q = opt(args, "-f")
        if PAH not in q:
            return {"items": [], "total_count": 0}
        if "created:" in q:
            return {"items": [{"created_at": iso(1)}], "total_count": 1}
        return {"items": [{"closed_at": iso(2)}, {"closed_at": iso(2)}], "total_count": 2}
    raise AssertionError(f"unexpected gh call: {args}")


class IssuePulseTests(unittest.TestCase):
    def test_links_and_link_states(self):
        issues = {PAH: [issue(10, "bug"), issue(11, "done?"), issue(12, "related"),
                        issue(13, "parked", labels=["parked-intent"]), issue(14, "old", idle_days=45)]}
        fake = FakeGh(issue_handler)
        with tempfile.TemporaryDirectory() as out, mock.patch.object(bp, "run", fake), \
                contextlib.redirect_stdout(io.StringIO()):
            summary = ip.main(out, now=NOW, register=(fake_register(issues), "abcd1234"))
            rows = json.load(open(summary["path"], encoding="utf-8"))
        self.assertEqual(rows[0]["register"], f"pipeline-automation-hub@abcd1234:{ip.REGISTER}/recensus.py")
        state = {r["number"]: (r["link_state"], r["next_step"]) for r in rows if r["kind"] == "issue"}
        self.assertEqual(state[10], ("pr-red", "Fix checks on PR #20"))
        self.assertEqual(state[11], ("pr-merged", "Close or confirm: PR #5 merged"))
        self.assertEqual(state[12][0], "pr-related")
        self.assertEqual(state[13][0], "parked")
        self.assertEqual(state[14][0], "stale")
        prs = {r["pr"]: r["link"] for r in rows if r["kind"] == "pr"}
        self.assertEqual(prs, {20: "closes", 21: "related"})
        repo = next(r for r in rows if r["kind"] == "repo" and r["repo"] == "PAH")
        self.assertEqual((repo["opened_14d"], repo["closed_14d"], repo["net_14d"]), (1, 2, -1))
        for args in fake.calls:
            bp.assert_read_only(args)


class RegisterSourceTests(unittest.TestCase):
    def test_clone_precedence(self):
        with mock.patch.dict(os.environ, {"ISSUE_PULSE_PAH": "envclone"}):
            self.assertEqual(ip.pah_clone("argclone"), "argclone")
            self.assertEqual(ip.pah_clone(), "envclone")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ISSUE_PULSE_PAH", None)
            self.assertEqual(ip.pah_clone(), ip.HERE_CLONE)
        self.assertTrue(os.path.isfile(os.path.join(ip.HERE_CLONE, ip.REGISTER, "recensus.py")))

    def test_load_register_reads_the_ref_not_the_worktree(self):
        # Not mkdtemp/TemporaryDirectory: on Windows they set an owner-only ACL that some git setups
        # cannot enter (same workaround as test_build_dashboards.py).
        clone = os.path.join(tempfile.gettempdir(), "pulse-test-" + uuid.uuid4().hex[:12])
        os.makedirs(clone)
        self.addCleanup(shutil.rmtree, clone, ignore_errors=True)
        # Temp repos may be owned by another account (sandboxes, CI); trust them for this test only.
        with mock.patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                                          "GIT_CONFIG_VALUE_0": "*"}):
            git = lambda *a: subprocess.run(["git", "-C", clone, *a], check=True, capture_output=True)  # noqa: E731
            git("init", "-q")
            reg = os.path.join(clone, *ip.REGISTER.split("/"))
            os.makedirs(reg)
            with open(os.path.join(reg, "recensus.py"), "w") as f:
                f.write("MARK = 'committed'\n")
            with open(os.path.join(reg, "code_health.py"), "w") as f:
                f.write("\n")
            git("add", "-A")
            git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "stub")
            with open(os.path.join(reg, "recensus.py"), "w") as f:
                f.write("MARK = 'uncommitted'\n")
            mod, sha = ip.load_register(clone, "HEAD")
        self.assertEqual(mod.MARK, "committed")
        self.assertEqual(len(sha), 8)


class NoUserPathTests(unittest.TestCase):
    def test_scripts_carry_no_user_paths(self):
        for name in ("burndown_pulse.py", "issue_pulse.py", "README.md"):
            text = open(os.path.join(HERE, name), encoding="utf-8").read().replace("\\", "/")
            for needle in (":/Users/", "/home/", "OneDrive -", "Documents/Codex"):
                self.assertNotIn(needle, text, f"{name} contains {needle!r}")


if __name__ == "__main__":
    unittest.main()
