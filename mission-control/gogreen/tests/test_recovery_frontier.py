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
        report = rf.build(raw, now=NOW, max_waves=20, capacity=8, per_repo=2)
        self.assertGreater(report["candidate_count"], 4)
        self.assertGreaterEqual(len(report["waves"]), 4)
        self.assertEqual(report["status"], "STALE_SOURCE_NEEDS_RECENSUS")
        self.assertFalse(report["worker_dispatch"])
        self.assertNotIn("GBOGEB/cryoplant-project", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
