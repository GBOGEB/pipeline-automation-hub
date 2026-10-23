"""Mocked-gh tests for scripts/owner/apply_rulesets.py (no network, no writes)."""
import contextlib
import copy
import importlib.util
import io
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "apply_rulesets.py"
spec = importlib.util.spec_from_file_location("apply_rulesets", SCRIPT)
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

HUB = "GBOGEB/pipeline-automation-hub"
HUB_FILE = json.loads((ar.RULESETS_DIR / "pipeline-automation-hub.basic.json").read_text(encoding="utf-8"))
ABACUS_HARD = json.loads((ar.RULESETS_DIR / "ABACUS.hard.json").read_text(encoding="utf-8"))
UNTARGETED = {"id": 25252917, "name": "QPS TRAIGE project", "source_type": "Repository",
              "enforcement": "active", "target": "branch",
              "conditions": {"ref_name": {"include": [], "exclude": []}},
              "rules": [{"type": "deletion"}], "bypass_actors": []}


def effective_from(ruleset):
    return [{"type": r["type"], "parameters": r.get("parameters") or {}} for r in ruleset["rules"]]


class FakeGh:
    """Records every call; serves a tiny in-memory GitHub."""

    def __init__(self, rulesets=None, fail=None):
        self.calls = []
        self.sets = {rs["id"]: copy.deepcopy(rs) for rs in (rulesets or [])}
        self.fail = fail or {}
        self.next_id = 900

    @property
    def writes(self):
        return [c for c in self.calls if c[1] != "GET"]

    def __call__(self, path, method="GET", body=None):
        self.calls.append((path, method, body))
        for frag, err in self.fail.items():
            if frag in path:
                return None, err
        repo = "/".join(path.split("/")[1:3])
        base = path.split("?")[0]
        if method == "POST" and base.endswith("/rulesets"):
            rid = self.next_id
            self.next_id += 1
            self.sets[rid] = {**copy.deepcopy(body), "id": rid, "source_type": "Repository", "source": repo}
            return self.sets[rid], None
        if method == "PUT" and "/rulesets/" in base:
            rid = int(base.rsplit("/", 1)[1])
            self.sets[rid].update(copy.deepcopy(body))
            return self.sets[rid], None
        if base.endswith("/rulesets"):
            return [{k: v for k, v in s.items() if k in ("id", "name", "enforcement", "source_type", "target")}
                    for s in self.sets.values()], None
        if "/rulesets/" in base:
            rid = int(base.rsplit("/", 1)[1])
            return copy.deepcopy(self.sets[rid]), None
        if "/rules/branches/" in base:
            eff = []
            for s in self.sets.values():
                inc = s.get("conditions", {}).get("ref_name", {}).get("include")
                if s.get("enforcement") == "active" and inc:
                    eff += effective_from(s)
            return eff, None
        if "/branches/" in base:
            return {"name": base.rsplit("/", 1)[1], "protected": bool(self.sets)}, None
        return None, f"unexpected path {path}"


def run(argv, gh):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = ar.main(argv, gh=gh)
    return rc, out.getvalue()


class PlanTests(unittest.TestCase):
    def test_create_when_name_absent(self):
        gh = FakeGh([UNTARGETED])
        p = ar.plan_repo(HUB, HUB_FILE, gh)
        self.assertEqual(p["action"], "CREATE")
        self.assertIn("25252917 'QPS TRAIGE project' (active)", p["other_rulesets"])
        self.assertEqual(gh.writes, [])

    def test_noop_when_live_matches_even_with_extra_server_params(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository", "node_id": "x",
                "_links": {}, "current_user_can_bypass": "never"}
        for r in live["rules"]:
            if r["type"] == "pull_request":
                r["parameters"]["required_reviewers"] = []  # server-added default
        p = ar.plan_repo(HUB, HUB_FILE, FakeGh([live]))
        self.assertEqual(p["action"], "NOOP", p.get("diff"))

    def test_update_by_name_shows_diff(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository", "enforcement": "disabled"}
        live["rules"] = [r for r in live["rules"] if r["type"] != "required_status_checks"]
        live["rules"].append({"type": "creation"})
        p = ar.plan_repo(HUB, HUB_FILE, FakeGh([live]))
        self.assertEqual(p["action"], "UPDATE")
        self.assertEqual(p["id"], 7)
        joined = "\n".join(p["diff"])
        self.assertIn('enforcement: "disabled" -> "active"', joined)
        self.assertIn("rules[required_status_checks]: add", joined)
        self.assertIn("rules[creation]: present live", joined)

    def test_check_list_change_is_a_diff(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository"}
        for r in live["rules"]:
            if r["type"] == "required_status_checks":
                r["parameters"]["required_status_checks"] = r["parameters"]["required_status_checks"][:1]
        p = ar.plan_repo(HUB, HUB_FILE, FakeGh([live]))
        self.assertEqual(p["action"], "UPDATE")
        self.assertTrue(any("required_status_checks" in d for d in p["diff"]))

    def test_duplicate_names_is_error_not_guess(self):
        a = {**copy.deepcopy(HUB_FILE), "id": 1, "source_type": "Repository"}
        b = {**copy.deepcopy(HUB_FILE), "id": 2, "source_type": "Repository"}
        self.assertEqual(ar.plan_repo(HUB, HUB_FILE, FakeGh([a, b]))["action"], "ERROR")

    def test_list_failure_is_error(self):
        gh = FakeGh(fail={"/rulesets": "HTTP 404"})
        self.assertEqual(ar.plan_repo(HUB, HUB_FILE, gh)["action"], "ERROR")


class DryRunTests(unittest.TestCase):
    def test_dry_run_never_writes_all_repos(self):
        gh = FakeGh([UNTARGETED])
        rc, out = run([], gh)
        self.assertEqual(gh.writes, [])
        self.assertIn("DRY-RUN", out)
        self.assertIn("Nothing was changed", out)
        self.assertEqual(rc, 0)

    def test_dry_run_with_pending_update_never_writes(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository", "enforcement": "evaluate"}
        gh = FakeGh([live])
        rc, out = run(["--repo", "pipeline-automation-hub"], gh)
        self.assertEqual(gh.writes, [])
        self.assertIn("UPDATE", out)
        self.assertIn("1 ruleset write(s) pending", out)


class ApplyTests(unittest.TestCase):
    def test_apply_creates_then_verifies(self):
        gh = FakeGh([UNTARGETED])
        rc, out = run(["--apply", "--repo", HUB, "--json"], gh)
        self.assertEqual([(c[0], c[1]) for c in gh.writes], [(f"repos/{HUB}/rulesets", "POST")])
        self.assertEqual(gh.writes[0][2], HUB_FILE)
        res = json.loads(out)["repos"][0]
        self.assertEqual(res["action"], "CREATE")
        self.assertTrue(res["write"]["written"])
        self.assertEqual(res["verify"]["ruleset_state"], "ACTIVE")
        self.assertTrue(res["verify"]["ok"])
        # the pre-existing untargeted ruleset is never deleted and is still reported, so the
        # EVERRED drift probe stays honest until the owner disables or retargets it
        self.assertEqual(res["verify"]["probe_status"], "CONFIRMED_DRIFT")
        self.assertTrue(res["verify"]["untargeted_rulesets"])
        self.assertIn(25252917, gh.sets)
        self.assertEqual(rc, 0)

    def test_apply_updates_by_name_with_put(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository", "enforcement": "disabled"}
        gh = FakeGh([live])
        rc, out = run(["--apply", "--repo", HUB, "--json"], gh)
        self.assertEqual([(c[0], c[1]) for c in gh.writes], [(f"repos/{HUB}/rulesets/7", "PUT")])
        res = json.loads(out)["repos"][0]
        self.assertEqual(res["verify"]["ruleset_state"], "ACTIVE")
        self.assertEqual(res["verify"]["probe_status"], "VERIFIED_EFFECTIVE")
        self.assertTrue(res["verify"]["ok"])
        self.assertEqual(rc, 0)

    def test_apply_noop_makes_no_write(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository"}
        gh = FakeGh([live])
        rc, _ = run(["--apply", "--repo", HUB], gh)
        self.assertEqual(gh.writes, [])
        self.assertEqual(rc, 0)

    def test_failed_write_sets_nonzero(self):
        gh = FakeGh([UNTARGETED])
        real = gh.__call__

        def failing(path, method="GET", body=None):
            if method == "POST":
                gh.calls.append((path, method, body))
                return None, "HTTP 403: Resource not accessible by integration"
            return real(path, method, body)

        rc, out = run(["--apply", "--repo", HUB], failing)
        self.assertIn("WRITE FAILED", out)
        self.assertEqual(rc, 1)

    def test_hard_tier_uses_hard_file_and_skips_repos_without_one(self):
        gh = FakeGh([])
        rc, out = run(["--tier", "hard", "--json"], gh)
        repos = {r["repo"]: r for r in json.loads(out)["repos"]}
        self.assertEqual(repos["GBOGEB/ABACUS"]["action"], "CREATE")
        self.assertEqual(repos["GBOGEB/ABACUS"]["name"], ABACUS_HARD["name"])
        self.assertEqual(repos[HUB]["action"], "SKIP")
        self.assertEqual(gh.writes, [])

    def test_wrapper_refuses_delete(self):
        with self.assertRaises(ValueError):
            ar.gh_api("repos/x/y/rulesets/1", "DELETE")
        with self.assertRaises(ValueError):
            ar.gh_api("repos/x/y/rulesets/1", "PATCH")


class VerifyTests(unittest.TestCase):
    def test_verify_absent_is_red_and_read_only(self):
        gh = FakeGh([UNTARGETED])
        rc, out = run(["--verify", "--repo", HUB], gh)
        self.assertEqual(gh.writes, [])
        self.assertIn("ruleset=ABSENT", out)
        self.assertIn("targets no branch", out)
        self.assertIn("0/1 repos", out)
        self.assertEqual(rc, 1)

    def test_verify_active_is_ok(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository"}
        rc, out = run(["--verify", "--repo", HUB], FakeGh([live]))
        self.assertIn("OK", out)
        self.assertIn("1/1 repos", out)
        self.assertEqual(rc, 0)

    def test_verify_disabled_is_red(self):
        live = {**copy.deepcopy(HUB_FILE), "id": 7, "source_type": "Repository", "enforcement": "disabled"}
        rc, out = run(["--verify", "--repo", HUB], FakeGh([live]))
        self.assertIn("PRESENT_DISABLED", out)
        self.assertEqual(rc, 1)

    def test_verify_api_failure_is_unknown_not_missing(self):
        gh = FakeGh(fail={"/rulesets": "HTTP 404", "/rules/branches/": "HTTP 404", "/branches/": "HTTP 404"})
        rc, out = run(["--verify", "--repo", HUB, "--json"], gh)
        v = json.loads(out)["repos"][0]
        self.assertEqual(v["ruleset_state"], "UNKNOWN")
        self.assertEqual(v["probe_status"], "UNKNOWN_API_READBACK")
        self.assertEqual(v["gaps"], [])
        self.assertEqual(rc, 1)

    def test_apply_and_verify_are_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ar.main(["--apply", "--verify"], gh=FakeGh())


class SourceFolderIsReadOnly(unittest.TestCase):
    def test_no_writes_to_p_process(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("write_text", src)
        self.assertNotIn(".open(", src)


if __name__ == "__main__":
    unittest.main()
