"""FOCUS5 evidence channels H03/H09/H10/H11/H12: PASS only on live, exact-head,
owner-or-independent evidence; every forgeable or partial shape stays UNKNOWN."""
import importlib.util
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate_evidence", ROOT / "tools" / "gate_evidence.py")
ge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ge)
spec2 = importlib.util.spec_from_file_location("focus5_pulse", ROOT / "tools" / "focus5_pulse.py")
fp = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(fp)

HEAD, OTHER, PRHEAD = "a" * 40, "b" * 40, "c" * 40
R = "O/R"


def user(login, kind="User"):
    return {"login": login, "type": kind}


def review(login, state, commit=PRHEAD, kind="User"):
    return {"user": user(login, kind), "state": state, "commit_id": commit, "html_url": f"https://x/{login}"}


def fake(pulls=(), reviews=(), tag_objs=None, releases=None):
    """tag_objs: name -> git tag object (None = lightweight); releases: name -> release."""
    tag_objs, releases = tag_objs or {}, releases or {}

    def lookup(path):
        if path == f"repos/{R}/commits/{HEAD}/pulls":
            return list(pulls)
        if path.startswith(f"repos/{R}/pulls/") and "/reviews" in path:
            return list(reviews) if "page=1" in path else []
        if path.startswith(f"repos/{R}/git/ref/tags/"):
            name = path.rsplit("/tags/", 1)[1]
            obj = tag_objs[name]
            return {"object": {"type": "commit", "sha": HEAD}} if obj is None else {"object": {"type": "tag", "sha": "t-" + name}}
        if path.startswith(f"repos/{R}/git/tags/t-"):
            return tag_objs[path.rsplit("/t-", 1)[1]]
        if path.startswith(f"repos/{R}/releases/tags/"):
            name = path.rsplit("/tags/", 1)[1]
            if name not in releases:
                raise subprocess.CalledProcessError(1, ["gh"])
            return releases[name]
        raise AssertionError(path)
    return lookup


def tag(name, sha=HEAD):
    return {"name": name, "commit": {"sha": sha}}


def tobj(sha=HEAD, verified=True, message=""):
    return {"object": {"sha": sha}, "verification": {"verified": verified, "reason": "valid" if verified else "unsigned"},
            "message": message, "tagger": {"name": "owner"}}


MERGED = {"number": 7, "user": user("owner"), "head": {"sha": PRHEAD}, "merged_at": "2026-11-20T00:00:00Z",
          "merge_commit_sha": HEAD}


class H09(unittest.TestCase):
    def status(self, **kw):
        return ge.evaluate_h09(R, HEAD, fake(**kw))

    def test_independent_approval_on_final_head_passes(self):
        self.assertEqual(self.status(pulls=[MERGED], reviews=[review("alice", "APPROVED")])[0], "PASS")

    def test_head_not_from_merged_pr_is_unknown(self):
        self.assertEqual(self.status(pulls=[])[0], "UNKNOWN")
        unmerged = dict(MERGED, merged_at=None)
        self.assertEqual(self.status(pulls=[unmerged], reviews=[review("alice", "APPROVED")])[0], "UNKNOWN")
        other = dict(MERGED, merge_commit_sha=OTHER)
        self.assertEqual(self.status(pulls=[other], reviews=[review("alice", "APPROVED")])[0], "UNKNOWN")

    def test_author_bot_and_comment_reviews_never_count(self):
        for rv in (review("owner", "APPROVED"), review("codex[bot]", "APPROVED", kind="Bot"),
                   review("alice", "COMMENTED")):
            st, _, why = self.status(pulls=[MERGED], reviews=[rv])
            self.assertEqual(st, "UNKNOWN", rv)
            self.assertIn("no APPROVED review", why)

    def test_stale_approval_and_later_change_request_block(self):
        st, _, why = self.status(pulls=[MERGED], reviews=[review("alice", "APPROVED", commit=OTHER)])
        self.assertEqual(st, "UNKNOWN")
        self.assertIn("not on the final head", why)
        st, _, why = self.status(pulls=[MERGED], reviews=[review("alice", "APPROVED"), review("bob", "CHANGES_REQUESTED")])
        self.assertEqual(st, "UNKNOWN")
        self.assertIn("bob", why)
        # the same reviewer's later approval supersedes their change request
        self.assertEqual(self.status(pulls=[MERGED], reviews=[review("bob", "CHANGES_REQUESTED"),
                                                               review("bob", "APPROVED")])[0], "PASS")


class H03(unittest.TestCase):
    def test_signed_scope_tag_with_token_passes(self):
        st, url, _ = ge.evaluate_h03(R, HEAD, [tag("jade-scope/r1")], fake(tag_objs={"jade-scope/r1": tobj(message="JADE-H03 in scope")}))
        self.assertEqual(st, "PASS")
        self.assertIn("jade-scope/r1", url)

    def test_forgeable_or_partial_scope_tags_stay_unknown(self):
        cases = [
            ({"jade-scope/r1": None}, "lightweight"),
            ({"jade-scope/r1": tobj(verified=False, message="JADE-H03")}, "not verified"),
            ({"jade-scope/r1": tobj(message="no token")}, "no jade-scope"),
            ({"jade-scope/r1": tobj(sha=OTHER, message="JADE-H03")}, "does not point"),
        ]
        for objs, expect in cases:
            st, _, why = ge.evaluate_h03(R, HEAD, [tag("jade-scope/r1")], fake(tag_objs=objs))
            self.assertEqual(st, "UNKNOWN", expect)
        st, _, why = ge.evaluate_h03(R, HEAD, [tag("v1")], fake())
        self.assertIn("no jade-scope/* tag", why)
        st, _, _ = ge.evaluate_h03(R, HEAD, [tag("jade-scope/r1", OTHER)], fake())
        self.assertEqual(st, "UNKNOWN")


class H12(unittest.TestCase):
    REL = {"html_url": "https://x/rel", "draft": False, "prerelease": False, "assets": [{"name": "a.zip"}],
           "body": "Notes\nRollback: v0.9\n"}

    def run_h12(self, objs=None, rel=None, tags=(tag("v1.0"), tag("v0.9", OTHER))):
        objs = {"v1.0": tobj()} if objs is None else objs
        rels = {} if rel is False else {"v1.0": rel or self.REL}
        return ge.evaluate_h12(R, HEAD, list(tags), fake(tag_objs=objs, releases=rels))

    def test_signed_published_release_with_assets_and_rollback_passes(self):
        self.assertEqual(self.run_h12()[0], "PASS")

    def test_each_missing_part_is_named(self):
        REL = self.REL
        cases = [
            (dict(objs={"v1.0": None}), "lightweight"),
            (dict(objs={"v1.0": tobj(verified=False)}), "not verified"),
            (dict(rel=False), "no release"),
            (dict(rel=dict(REL, draft=True)), "draft"),
            (dict(rel=dict(REL, assets=[])), "no assets"),
            (dict(rel=dict(REL, body="no line")), "Rollback"),
            (dict(rel=dict(REL, body="Rollback: v1.0")), "not another existing tag"),
            (dict(rel=dict(REL, body="Rollback: v0.1")), "not another existing tag"),
        ]
        for kw, expect in cases:
            st, _, why = self.run_h12(**kw)
            self.assertEqual(st, "UNKNOWN", expect)
            self.assertIn(expect, why)

    def test_scope_tags_are_not_release_tags(self):
        st, _, why = ge.evaluate_h12(R, HEAD, [tag("jade-scope/r1")], fake(tag_objs={"jade-scope/r1": tobj()}))
        self.assertEqual(st, "UNKNOWN")
        self.assertIn("no tag on this SHA", why)


class Registry(unittest.TestCase):
    BASE = {"schema": "jade.focus5.gate_evidence_registry.v1"}

    def entry(self, wf=".github/workflows/qa.yml"):
        return [{"workflow": wf, "proves": "negative tests under a matched coverage floor"}]

    def test_h10_h11_may_be_declared_but_owner_gates_may_not(self):
        reg = fp.validate_registry(dict(self.BASE, repos={"O/R": {"H10": self.entry(), "H11": self.entry()}}))
        self.assertEqual(reg["O/R"]["H10"], [".github/workflows/qa.yml"])
        for gid in ("H03", "H07", "H08", "H09", "H12"):
            with self.assertRaises(ValueError, msg=gid):
                fp.validate_registry(dict(self.BASE, repos={"O/R": {gid: self.entry()}}))


if __name__ == "__main__":
    unittest.main()
