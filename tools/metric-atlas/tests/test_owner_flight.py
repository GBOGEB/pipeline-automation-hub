"""Negative controls for the source-owned opt-in census flight."""
import unittest

from metric_atlas.owner_flight import APPROVAL, OwnerFlightError, run_flight

CODEX = "b" * 40
QPS = "c" * 40


class FixtureGH:
    def __init__(self, changed=False, denied=False):
        self.calls = []
        self.changed = changed
        self.denied = denied
        self.head_calls = {}

    def __call__(self, argv):
        self.calls.append(argv)
        if argv[0] == "api":
            if self.denied and "cryoplant-project" in argv[1]:
                raise RuntimeError("HTTP 403")
            repo = argv[1].split("/")[1] + "/" + argv[1].split("/")[2]
            count = self.head_calls.get(repo, 0) + 1
            self.head_calls[repo] = count
            if repo.endswith("CODEX"):
                return "a" * 40 if self.changed and count == 2 else CODEX
            return QPS
        if argv[:2] == ["workflow", "run"]:
            return "Workflow dispatch created"
        raise AssertionError("Unexpected command")


class OwnerFlightTests(unittest.TestCase):
    def test_dry_run_is_source_pinned_and_has_no_dispatch(self):
        cli = FixtureGH()
        out = run_flight("N2", gh=cli)
        self.assertEqual(out["manifest"]["eligible_repos"], 3)
        self.assertEqual(len(out["manifest"]["requests"]), 2)
        self.assertEqual(out["expected_receiver_jobs"], 4)
        self.assertEqual(out["events_submitted"], 0)
        self.assertIsNone(out["actual_receiver_runs"])
        self.assertTrue(all(x[0] == "api" for x in cli.calls))
        self.assertEqual(out["manifest"]["unknown_head_repos"], 1)

    def test_execute_requires_owner_acknowledgement_before_network(self):
        cli = FixtureGH()
        with self.assertRaises(OwnerFlightError):
            run_flight("N2", execute=True, gh=cli)
        self.assertEqual(cli.calls, [])

    def test_stale_sha_prevents_all_dispatches(self):
        cli = FixtureGH(changed=True)
        with self.assertRaisesRegex(OwnerFlightError, "STALE_SOURCE_HEAD"):
            run_flight("N2", execute=True, approval=APPROVAL, gh=cli)
        self.assertFalse(any(x[0] == "workflow" for x in cli.calls))

    def test_private_source_read_denial_prevents_dispatch(self):
        cli = FixtureGH(denied=True)
        with self.assertRaisesRegex(OwnerFlightError, "authorized source read"):
            run_flight("N2", execute=True, approval=APPROVAL, gh=cli)
        self.assertFalse(any(x[0] == "workflow" for x in cli.calls))

    def test_submission_never_counts_as_native_proof(self):
        cli = FixtureGH()
        out = run_flight("N2", execute=True, approval=APPROVAL, gh=cli)
        self.assertEqual(out["events_submitted"], 2)
        self.assertEqual(len([x for x in cli.calls if x[0] == "workflow"]), 2)
        self.assertTrue(all("NOT_RECEIVER_PROOF" in x["state"] for x in out["events"]))
        self.assertIsNone(out["actual_artifact_bytes"])
        self.assertIsNone(out["coverage"])
        self.assertEqual(out["admission"], "HOLD")


if __name__ == "__main__":
    unittest.main()
