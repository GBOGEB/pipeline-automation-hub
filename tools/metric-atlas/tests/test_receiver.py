"""Portable receiver negative tests for QPS source-bound dispatch."""
import unittest
from metric_atlas.census import request
from metric_atlas.receiver import check_request, request_id

H = {"ABACUS": "a"*40, "CODEX": "b"*40, "QPS_ENGINEERING": "c"*40}


def env_for(repo="GBOGEB/ABACUS", sha="a"*40, selector="all"):
    mapping = {"GBOGEB/ABACUS": "ABACUS", "GBOGEB/CODEX": "CODEX",
               "GBOGEB/cryoplant-project": "QPS_ENGINEERING"}
    return {"GITHUB_REPOSITORY": repo, "GITHUB_SHA": sha,
            "QPS_EXPECTED_SHA": sha, "QPS_WAVE": "N1", "QPS_SELECTOR": selector,
            "QPS_REQUEST_ID": request_id("N1", mapping[repo], repo, sha, selector),
            "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}


class ReceiverTests(unittest.TestCase):
    def test_cross_repo_request_compatibility(self):
        m = request("N1", H)
        for q in m["requests"]:
            with self.subTest(repo=q["repo"]):
                self.assertEqual(
                    q["request_id"],
                    request_id("N1", q["lane"], q["repo"], q["expected_sha"], "all")
                )

    def test_valid_request(self):
        self.assertEqual(check_request(env_for(), "native_checks"), "ABACUS")

    def test_mismatched_sha_refused(self):
        env = env_for()
        env["GITHUB_SHA"] = "f"*40
        with self.assertRaisesRegex(ValueError, "STALE"):
            check_request(env, "native_checks")

    def test_forged_id_refused(self):
        env = env_for()
        env["QPS_REQUEST_ID"] = "QPS-" + "0"*20
        with self.assertRaisesRegex(ValueError, "request ID"):
            check_request(env, "native_checks")

    def test_no_arbitrary_command(self):
        env = env_for()
        env["QPS_SELECTOR"] = "pytest --disable-warnings"
        with self.assertRaisesRegex(ValueError, "selector"):
            check_request(env, "native_checks")

    def test_request_route_selector(self):
        env = env_for(selector="native_checks")
        with self.assertRaisesRegex(ValueError, "unrequested"):
            check_request(env, "coverage_catalog")

    def test_unauthorized_repo(self):
        env = env_for()
        env["GITHUB_REPOSITORY"] = "some/other"
        with self.assertRaises(ValueError):
            check_request(env, "native_checks")


if __name__ == "__main__":
    unittest.main()
