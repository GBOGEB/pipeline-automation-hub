"""Negative-first controls for the canonical EVERRED consumer/root packetizer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recovery_frontier as rf  # noqa: E402

NOW = datetime(2026, 10, 26, 14, tzinfo=timezone.utc)
OLD = (NOW - timedelta(days=8)).isoformat()
CURRENT = (NOW - timedelta(hours=1)).isoformat()


def root(n, *, repo="ABACUS", state="TRIAGED", severity="P1", family="TEST_OR_MEASUREMENT_DEFECT",
         security="NA", occ=7, prs=None):
    return {"id": f"{repo}-RC-2026-{n:04d}", "severity": severity,
            "state": state, "class": family, "occurrences": occ,
            "affected_prs": prs if prs is not None else [10, 11],
            "consumers": ["one", "two"],
            "dims": {"security": security}}


def source(*, generated=CURRENT, roots=None, unmatched=None):
    return {"schema": rf.SOURCE_SCHEMA, "generated_at": generated,
            "roots": roots if roots is not None else [root(1)],
            "unmatched": unmatched if unmatched is not None else []}


class FrontierSafety(unittest.TestCase):
    def test_security_and_owner_noncompensation(self):
        x = source(roots=[
            root(1, severity="P0", family="SECURITY_OR_POLICY", security="RED"),
            root(2, state="BLOCKED_AUTHORITY", severity="P0", family="CONTROL_PLANE_DRIFT"),
            root(3, state="VERIFIED_FIXED", severity="P2")])
        result = rf.build(x, now=NOW)
        packets = [p for w in result["waves"] for p in w["packets"]]
        by = {p["id"]: p for p in packets}
        self.assertEqual(by["ABACUS-RC-2026-0001"]["family"], rf.MAROON)
        self.assertEqual(by["ABACUS-RC-2026-0002"]["family"], rf.OWNER)
        self.assertEqual(by["ABACUS-RC-2026-0003"]["family"], rf.CONTROL)
        self.assertEqual(by["ABACUS-RC-2026-0002"]["action"], "OWNER_DECISION")
        self.assertEqual(by["ABACUS-RC-2026-0003"]["action"], "REPEAT_DISTINCT_SHA")
        self.assertFalse(result["worker_dispatch"])
        self.assertFalse(result["merge_authorized"])
        self.assertEqual(result["formal_closure_credit"], 0)

    def test_bounded_diverse_waves_and_single_assignment(self):
        rs = [root(i, repo="ABACUS") for i in range(1, 13)]
        rs += [root(i, repo="CODEX") for i in range(1, 13)]
        x = rf.build(source(roots=rs), now=NOW, capacity=8, per_repo=2, max_waves=4)
        self.assertGreaterEqual(len(x["waves"]), 4)
        all_ids = []
        for w in x["waves"]:
            self.assertLessEqual(w["count"], 8)
            counts = {}
            for p in w["packets"]:
                counts[p["repo"]] = counts.get(p["repo"], 0) + 1
                all_ids.append(p["id"])
                self.assertEqual(p["path_lease"], "UNVERIFIED_NO_WRITE")
                self.assertEqual(p["formal_closure_credit"], 0)
            self.assertTrue(all(n <= 2 for n in counts.values()))
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(x["candidate_count"], 24)
        self.assertGreater(x["remaining_candidate_count"], 0)

    def test_unmatched_is_scout_not_root_closure(self):
        x = source(roots=[], unmatched=[
            {"signature": "Unit Tests :: failing step", "repos": ["GBOGEB/ABACUS"],
             "occurrences": 54, "prs": [1, 2, 2]}])
        v = rf.build(x, now=NOW)
        packet = v["waves"][0]["packets"][0]
        self.assertEqual(packet["family"], rf.FIRST)
        self.assertEqual(packet["observed_occurrences"], 54)
        self.assertEqual(packet["affected_pr_count"], 2)
        self.assertEqual(packet["first_red_line"], "NEEDS_NATIVE_JOB_LOG")
        self.assertNotIn("Unit Tests :: failing step", json.dumps(v))
        self.assertEqual(packet["formal_closure_credit"], 0)

    def test_private_and_mixed_source_never_escape(self):
        x = source(roots=[root(1, repo="ABACUS"),
                          dict(root(2, repo="CRYO"), title="PRIVATE_BIDDER_ROW_ABC")],
                   unmatched=[
                       {"signature": "PRIVATE_PASSWORD_LABEL", "repos": ["GBOGEB/cryoplant-project"],
                        "occurrences": 21, "prs": [400]},
                       {"signature": "CROSS_PRIVATE_JOIN", "repos": ["GBOGEB/ABACUS",
                                                                     "GBOGEB/cryoplant-project"],
                        "occurrences": 5, "prs": []}
                   ])
        result = rf.build(x, now=NOW)
        payload = json.dumps(result)
        for forbidden in ("PRIVATE_BIDDER_ROW_ABC", "PRIVATE_PASSWORD_LABEL", "CROSS_PRIVATE_JOIN",
                          "GBOGEB/cryoplant-project", "CRYO-RC", "#400"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(result["private_or_unmapped_suppressed"], 3)

    def test_stale_and_future_fail_closed(self):
        self.assertEqual(rf.build(source(generated=OLD), now=NOW)["status"],
                         "STALE_SOURCE_NEEDS_RECENSUS")
        with self.assertRaisesRegex(ValueError, "SOURCE_FROM_FUTURE"):
            rf.build(source(generated=(NOW + timedelta(days=1)).isoformat()), now=NOW)

    def test_invalid_identity_and_duplicate_fail_closed(self):
        r = root(1)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_IDENTITY"):
            rf.build(source(roots=[r, r]), now=NOW)
        r = dict(r, occurrences=-2)
        with self.assertRaisesRegex(ValueError, "INVALID_NONNEGATIVE_COUNT"):
            rf.build(source(roots=[r]), now=NOW)
        r = dict(r, occurrences=2, severity="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SEVERITY"):
            rf.build(source(roots=[r]), now=NOW)

    def test_schema_missingness_and_caps_fail_closed(self):
        for bad in (source(roots="not-array"), dict(source(), schema="other")):
            with self.assertRaises(ValueError):
                rf.build(bad, now=NOW)
        for caps in ({"max_waves": 0}, {"capacity": 0}, {"per_repo": 0}):
            with self.assertRaises(ValueError):
                rf.build(source(), now=NOW, **caps)

    def test_real_canonical_register_is_historical_and_suppresses_private(self):
        file = (Path(__file__).resolve().parents[2] /
                "qps-triage-ultra/p-process/site/everred/data/everred.json")
        raw = json.loads(file.read_text(encoding="utf-8"))
        # The committed register is refreshed by p-process pulses, so a fixed NOW can fall
        # before its generated_at (SOURCE_FROM_FUTURE). Read it just past the 48 h window.
        historical = datetime.fromisoformat(raw["generated_at"]) + timedelta(hours=49)
        report = rf.build(raw, now=historical, max_waves=20, capacity=8, per_repo=2)
        self.assertGreater(report["candidate_count"], 4)
        self.assertGreaterEqual(len(report["waves"]), 4)
        self.assertEqual(report["status"], "STALE_SOURCE_NEEDS_RECENSUS")
        self.assertFalse(report["worker_dispatch"])
        self.assertNotIn("GBOGEB/cryoplant-project", json.dumps(report))


    def test_aggressive_n_plus_eleven_is_staged_once_without_dispatch(self):
        """Twelve diverse bounded waves do not create twelve worker executions."""
        roots = [root(i, repo="ABACUS") for i in range(1, 25)]
        result = rf.build(source(roots=roots), now=NOW, max_waves=16,
                          capacity=8, per_repo=2)
        self.assertEqual(len(result["waves"]), 12)
        self.assertEqual(result["waves"][-1]["wave"], "N+11")
        self.assertEqual(sum(w["count"] for w in result["waves"]), 24)
        self.assertEqual(len({p["id"] for w in result["waves"]
                              for p in w["packets"]}), 24)
        self.assertEqual(result["remaining_candidate_count"], 0)
        self.assertTrue(all(w["status"] == "STAGED_NOT_DISPATCHED"
                            for w in result["waves"]))
        self.assertFalse(result["worker_dispatch"])

    def test_strict_wave_cap_defers_unassigned_candidates(self):
        """A cap is a real upper bound; overflow remains pending without credit."""
        roots = [root(i) for i in range(1, 20)]
        report = rf.build(source(roots=roots), now=NOW,
                          max_waves=3, capacity=5, per_repo=2)
        self.assertEqual([w["wave"] for w in report["waves"]],
                         ["N", "N+1", "N+2"])
        self.assertEqual(sum(w["count"] for w in report["waves"]), 6)
        self.assertEqual(report["remaining_candidate_count"], 13)
        self.assertEqual(report["formal_closure_credit"], 0)

    def test_security_priority_is_not_offset_by_occurrence_volume(self):
        """A P0 MAROON root remains ahead of a high-volume P3 recurrence."""
        critical = root(1, severity="P0", family="SECURITY_OR_POLICY",
                        security="RED", occ=1, prs=[])
        low = root(2, severity="P3", occ=5000, prs=list(range(1, 60)))
        out = rf.build(source(roots=[low, critical]), now=NOW,
                       max_waves=1, capacity=2, per_repo=2)
        self.assertEqual(out["waves"][0]["packets"][0]["id"], critical["id"])
        self.assertEqual(out["waves"][0]["packets"][0]["family"], rf.MAROON)
        self.assertFalse(out["merge_authorized"])

    def test_invalid_boolean_counts_fail_closed(self):
        """Python bool must not masquerade as an integer occurrence count."""
        for count in (True, False, -1, 1.5, "2"):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "INVALID_NONNEGATIVE_COUNT"):
                    rf.build(source(roots=[root(1, occ=count)]), now=NOW)

    def test_invalid_pr_references_and_consumers_fail_closed(self):
        """Bad source identities cannot enter a source-owned repair packet."""
        for prs in ([True], [0], [-1], ["42"], None):
            with self.subTest(prs=prs):
                bad = dict(root(1), affected_prs=prs)
                with self.assertRaises(ValueError):
                    rf.build(source(roots=[bad]), now=NOW)
        with self.assertRaisesRegex(ValueError, "INVALID_CONSUMERS"):
            rf.build(source(roots=[dict(root(1), consumers="not-a-list")]),
                     now=NOW)

    def test_private_unmatched_is_suppressed_before_signature_inspection(self):
        """Even malformed private log signatures stay private, with no packets."""
        private = {"repos": ["GBOGEB/cryoplant-project"],
                   "signature": {"secret": "MUST_NOT_ESCAPE"},
                   "occurrences": -1, "prs": [313]}
        result = rf.build(source(roots=[], unmatched=[private]), now=NOW)
        self.assertEqual(result["private_or_unmapped_suppressed"], 1)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["waves"], [])
        self.assertNotIn("MUST_NOT_ESCAPE", json.dumps(result))

    def test_duplicate_signature_is_not_counted_twice(self):
        """Two identical unmatched source signatures do not become two roots."""
        item = {"repos": ["GBOGEB/CODEX"], "signature": "same-head rerun",
                "occurrences": 10, "prs": [1]}
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_IDENTITY"):
            rf.build(source(roots=[], unmatched=[item, item]), now=NOW)

    def test_missing_timezone_proof_fails_closed(self):
        """A naive producer clock or naive comparison clock is inadmissible."""
        with self.assertRaisesRegex(ValueError, "SOURCE_CLOCK_NO_OFFSET"):
            rf.build(source(generated="2026-10-26T13:00:00"), now=NOW)
        with self.assertRaisesRegex(ValueError, "NOW_MISSING_OFFSET"):
            rf.build(source(), now=datetime(2026, 10, 26, 14))

    def test_invalid_caps_and_empty_source_never_summon_workers(self):
        """Capacity may not be a bool, and an empty census creates no work."""
        for bad in ({"capacity": True}, {"max_waves": 65}, {"per_repo": 9,
                                                             "capacity": 8}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    rf.build(source(), now=NOW, **bad)
        report = rf.build(source(roots=[], unmatched=[]), now=NOW)
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(report["waves"], [])
        self.assertFalse(report["worker_dispatch"])

    def test_matched_replay_is_deterministic_and_never_closure_proof(self):
        """Same source clock and membership must produce byte-identical output."""
        census = source(roots=[root(i, repo="CODEX") for i in range(1, 8)])
        one = rf.build(census, now=NOW, max_waves=8, per_repo=2)
        two = rf.build(census, now=NOW, max_waves=8, per_repo=2)
        self.assertEqual(json.dumps(one, sort_keys=True),
                         json.dumps(two, sort_keys=True))
        self.assertEqual(one["formal_closure_credit"], 0)
        self.assertTrue(all(p["path_lease"] == "UNVERIFIED_NO_WRITE"
                            for w in one["waves"] for p in w["packets"]))


if __name__ == "__main__":
    unittest.main()
