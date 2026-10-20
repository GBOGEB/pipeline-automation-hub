"""Unit controls for tools/bd_workflow_frequency.py (previously run only against live API).

Offline: the API is replaced by recorded run rows. Asserts the measurement contract
(input tuples, observable no-ops, same-SHA repeats, family fan-out) and fail-closed CLI
argument handling.
"""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import bd_workflow_frequency as bd  # noqa: E402

A, B = ".github/workflows/a.yml", ".github/workflows/b.yml"


def run(path, sha, conclusion="success", event="push", branch="master", number=1):
    return {"path": path, "head_sha": sha, "conclusion": conclusion, "event": event,
            "head_branch": branch, "run_number": number}


RUNS = [run(A, "s1", number=1), run(A, "s1", event="schedule", number=2), run(A, "s1", number=3),
        run(A, "s2", "skipped", number=4), run(B, "s1", number=7), run(B, "s3", "failure", number=8),
        run(".github/workflows/other.yml", "s1")]


class Family(unittest.TestCase):
    def test_parse_family(self):
        self.assertEqual(bd.parse_family("fam=a.yml, b.yml"), ("fam", ["a.yml", "b.yml"]))
        for bad in ("noequals", "=a.yml", "fam=", "fam= , "):
            with self.subTest(bad=bad), self.assertRaises(argparse.ArgumentTypeError):
                bd.parse_family(bad)

    def test_ratio_never_divides_by_zero(self):
        self.assertEqual(bd.ratio(1, 0), 0.0)
        self.assertEqual(bd.ratio(1, 3), 0.333333)


class Metrics(unittest.TestCase):
    def setUp(self):
        self.m = bd.metrics_for_family("fam", [A, B], RUNS)

    def test_totals_exclude_other_families(self):
        self.assertEqual(self.m["total_invocations"], 6)

    def test_input_tuples_and_noops(self):
        # (A,push,s1,master) repeats once; schedule on s1 is a distinct tuple
        self.assertEqual(self.m["unique_input_tuples"], 5)
        self.assertEqual(self.m["invocations_per_unique_input"], 1.2)
        self.assertEqual(self.m["observable_noop_invocations"], 1)

    def test_same_sha_repeat_and_family_fanout(self):
        # workflow/sha pairs: (A,s1) (A,s2) (B,s1) (B,s3) -> 6-4 repeats
        self.assertEqual(self.m["same_sha_repeat_invocations"], 2)
        # family head SHAs: s1 s2 s3 -> 6-3
        self.assertEqual(self.m["family_sha_fanout_invocations"], 3)
        self.assertEqual(self.m["family_sha_fanout_rate"], 0.5)

    def test_per_workflow(self):
        a, b = self.m["per_workflow"]
        self.assertEqual((a["invocations"], a["unique_head_shas"], a["same_sha_repeat_invocations"]), (4, 2, 2))
        self.assertEqual(a["conclusions"], {"skipped": 1, "success": 3})
        self.assertEqual((b["latest_run_number"], b["conclusions"]), (8, {"failure": 1, "success": 1}))

    def test_empty_family_is_zero_not_error(self):
        m = bd.metrics_for_family("none", [".github/workflows/x.yml"], RUNS)
        self.assertEqual((m["total_invocations"], m["unique_input_tuple_ratio"], m["invocations_per_unique_input"]),
                         (0, 0.0, 0.0))

    def test_markdown_states_the_contract(self):
        md = bd.render_markdown({"repository": "o/r", "sampled_runs": 7, "generated_at": "t",
                                 "families": [self.m]})
        self.assertIn("| fam | 6 |", md)
        self.assertIn("do not grant engineering or release credit", md)


class Fetch(unittest.TestCase):
    def test_pagination_stops_at_short_page_and_limit(self):
        pages = [{"workflow_runs": [run(A, str(i)) for i in range(100)]},
                 {"workflow_runs": [run(A, "x")] * 30}]
        with mock.patch.object(bd, "api_json", side_effect=pages) as api:
            got = bd.fetch_runs("o/r", "t", 500)
        self.assertEqual((len(got), api.call_count), (130, 2))
        with mock.patch.object(bd, "api_json", side_effect=pages) as api:
            self.assertEqual(len(bd.fetch_runs("o/r", "t", 50)), 50)
            self.assertEqual(api.call_count, 1)


class CLI(unittest.TestCase):
    def main(self, *argv, token="tok"):
        env = {"GITHUB_TOKEN": token} if token else {}
        with mock.patch.dict("os.environ", env, clear=True), mock.patch.object(sys, "argv", ["bd", *argv]):
            return bd.main()

    def test_fail_closed_arguments(self):
        base = ("--family", f"f={A}", "--out-json", "x.json", "--out-md", "x.md")
        with self.assertRaisesRegex(SystemExit, "GITHUB_TOKEN"):
            self.main("--repo", "o/r", *base, token=None)
        with self.assertRaisesRegex(SystemExit, "owner/name"):
            self.main("--repo", "bad", *base)
        with self.assertRaisesRegex(SystemExit, "between 1 and 1000"):
            self.main("--repo", "o/r", "--limit", "0", *base)

    def test_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(bd, "fetch_runs", return_value=RUNS):
            code = self.main("--repo", "o/r", "--family", f"f={A},{B}", "--out-json", f"{d}/m.json",
                             "--out-md", f"{d}/s.md")
            self.assertEqual(code, 0)
            payload = json.loads(Path(d, "m.json").read_text())
            self.assertEqual(payload["sampled_runs"], 7)
            self.assertEqual(payload["measurement_contract"]["authority"], "operational_bd_only")
            self.assertIn("BD Workflow Frequency Telemetry", Path(d, "s.md").read_text())


if __name__ == "__main__":
    unittest.main()
