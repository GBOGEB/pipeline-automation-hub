"""Explicit authorization and no-false-execution tests for QPS fanout."""
import copy
import unittest
from metric_atlas.census import request
from metric_atlas.dispatch import DispatchError, dispatch, plan

HEADS = {"ABACUS": "a"*40, "CODEX": "b"*40, "QPS_ENGINEERING": "c"*40}


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.m = request("N1", HEADS)

    def test_default_no_side_effects(self):
        def fail(*args, **kwargs):
            raise AssertionError("unexpected network")
        r = dispatch(self.m, opener=fail)
        self.assertEqual(r["triggered"], 0)
        self.assertTrue(all(v["state"] == "DRY_RUN_NOT_TRIGGERED" for v in r["events"]))

    def test_default_branch_authorization_required(self):
        with self.assertRaises(DispatchError):
            dispatch(self.m, execute=True, environment={})

    def test_secret_required(self):
        env = {"GITHUB_REPOSITORY": "GBOGEB/pipeline-automation-hub",
               "GITHUB_REF": "refs/heads/master", "GITHUB_EVENT_NAME": "workflow_dispatch",
               "QPS_DISPATCH_APPROVED": "YES"}
        with self.assertRaises(DispatchError):
            dispatch(self.m, execute=True, environment=env)

    def test_unapproved_repo(self):
        m = copy.deepcopy(self.m)
        m["requests"][0]["repo"] = "outsider/private"
        with self.assertRaises(DispatchError):
            plan(m)

    def test_no_dupe_targets(self):
        m = copy.deepcopy(self.m)
        m["requests"].append(m["requests"][0])
        with self.assertRaises(DispatchError):
            plan(m)

    def test_204_is_enqueue_not_result(self):
        class Response:
            status = 204
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        env = {"GITHUB_REPOSITORY": "GBOGEB/pipeline-automation-hub",
               "GITHUB_REF": "refs/heads/master", "GITHUB_EVENT_NAME": "workflow_dispatch",
               "QPS_DISPATCH_APPROVED": "YES", "QPS_TRIAGE_DISPATCH_TOKEN": "t"*40}
        urls = []
        def post(req, **kwargs):
            urls.append(req.full_url)
            return Response()
        result = dispatch(self.m, execute=True, environment=env, opener=post)
        self.assertEqual(result["triggered"], 3)
        self.assertTrue(all(u.endswith("/actions/workflows/qps-metric-census-receiver.yml/dispatches")
                            for u in urls))
        self.assertEqual({e["state"] for e in result["events"]},
                         {"HTTP_204_EVENT_ENQUEUED_NOT_PROVEN_EXECUTED"})
        self.assertIsNone(result["receiver_job_ids"])
        self.assertIsNone(result["receiver_results"])


if __name__ == "__main__":
    unittest.main()
