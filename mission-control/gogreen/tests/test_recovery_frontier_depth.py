"""N+6 slow-burn staging and zero-covered negative control families.

These tests exercise the existing read-only packetizer, not GitHub mutation,
worker launches, security waivers or fabricated operational waves.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recovery_frontier as rf  # noqa: E402

T = datetime(2026, 10, 26, 14, tzinfo=timezone.utc)


def root(i, *, prefix="ABACUS", **kwargs):
    r = {"id": f"{prefix}-RC-2026-{i:04d}", "severity": "P1",
         "state": "TRIAGED", "class": "TEST_OR_MEASUREMENT_DEFECT",
         "occurrences": 10, "affected_prs": [1, 2],
         "consumers": ["A"], "dims": {"security": "NA"}}
    r.update(kwargs)
    return r


def census(roots=None, unmatched=None, *, stamp=None):
    return {"schema": rf.SOURCE_SCHEMA, "generated_at": stamp or T.isoformat(),
            "roots": [root(1)] if roots is None else roots,
            "unmatched": [] if unmatched is None else unmatched}


def plan(*args, **kwargs):
    return rf.build(*args, now=T, **kwargs)


class NegativeSourceFamilies(unittest.TestCase):
    def test_root_row_rejects_nonobject(self):
        with self.assertRaisesRegex(ValueError, "INVALID_ROOT_ROW"):
            plan(census(roots=["not-an-object"]))

    def test_root_id_rejects_malformed_or_nontext(self):
        for ident in (None, 1, "", "ABACUS/RC-2026-0001", "ABACUS-RC-2026-01"):
            with self.subTest(ident=ident):
                with self.assertRaisesRegex(ValueError, "INVALID_ROOT_ID"):
                    plan(census(roots=[root(1, id=ident)]))

    def test_root_observed_count_rejects_boolean_and_fractional(self):
        for count in (True, 1.1, None, -1):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "INVALID_NONNEGATIVE_COUNT"):
                    plan(census(roots=[root(1, occurrences=count)]))

    def test_affected_pr_population_rejects_invalid_or_false_ids(self):
        for prs in (None, "4", [0], [True], [1, "2"]):
            with self.subTest(prs=prs):
                with self.assertRaisesRegex(ValueError, "INVALID_AFFECTED_PRS"):
                    plan(census(roots=[root(1, affected_prs=prs)]))

    def test_invalid_security_dims_and_consumers_raise(self):
        for changed, err in (({"dims": "SECRET"}, "INVALID_ROOT_DIMS"),
                             ({"consumers": 5}, "INVALID_CONSUMERS")):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, err):
                    plan(census(roots=[root(1, **changed)]))

    def test_private_precedence_does_not_expose_invalid_private_fields(self):
        r = root(1, prefix="CRYO", severity=None, occurrences="hidden")
        result = plan(census(roots=[r]))
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["private_or_unmapped_suppressed"], 1)
        self.assertNotIn("CRYO", json.dumps(result))

    def test_mismatched_security_unknown_goes_to_maroon_not_green(self):
        r = root(1, state="PRODUCER_GREEN", dims={"security": "UNKNOWN"})
        packet = plan(census(roots=[r]))["waves"][0]["packets"][0]
        self.assertEqual(packet["family"], rf.MAROON)
        self.assertEqual(packet["action"], "SECURITY_ADJUDICATION")
        self.assertEqual(packet["formal_closure_credit"], 0)

    def test_green_producer_recurs_not_root_closure(self):
        x = plan(census(roots=[root(1, state="PRODUCER_GREEN")]))
        p = x["waves"][0]["packets"][0]
        self.assertEqual(p["family"], rf.CONTROL)
        self.assertEqual(p["action"], "REPEAT_DISTINCT_SHA")
        self.assertEqual(x["formal_closure_credit"], 0)

    def test_unmatched_rejects_bad_repo_shapes(self):
        for repos in ([], None, "GBOGEB/ABACUS", [7]):
            with self.subTest(repos=repos):
                row = {"repos": repos, "signature": "x", "occurrences": 2, "prs": [1]}
                with self.assertRaisesRegex(ValueError, "INVALID_UNMATCHED_REPOS"):
                    plan(census(roots=[], unmatched=[row]))

    def test_unmatched_rejects_empty_signature_and_nonpositive_pr(self):
        base = {"repos": ["GBOGEB/ABACUS"], "occurrences": 2, "prs": [1]}
        for signature in (None, 0, "", "  "):
            with self.subTest(signature=signature):
                with self.assertRaisesRegex(ValueError, "INVALID_SIGNATURE"):
                    plan(census(roots=[], unmatched=[dict(base, signature=signature)]))
        for prs in ([True], [0], ["1"], "1"):
            with self.subTest(prs=prs):
                with self.assertRaisesRegex(ValueError, "INVALID_UNMATCHED_PRS"):
                    plan(census(roots=[], unmatched=[dict(base, signature="x", prs=prs)]))

    def test_duplicate_unmatched_signature_fails_closed(self):
        row = {"repos": ["GBOGEB/ABACUS"], "signature": "shared first-red",
               "occurrences": 5, "prs": [2]}
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_IDENTITY"):
            plan(census(roots=[], unmatched=[row, dict(row)]))

    def test_opaque_id_is_stable_but_partitioned_by_public_repo(self):
        seed = {"signature": "same error", "occurrences": 3, "prs": [1]}
        a = plan(census(roots=[], unmatched=[dict(seed, repos=["GBOGEB/ABACUS"])]))
        b = plan(census(roots=[], unmatched=[dict(seed, repos=["GBOGEB/CODEX"])]))
        ia = a["waves"][0]["packets"][0]["id"]
        ib = b["waves"][0]["packets"][0]["id"]
        self.assertNotEqual(ia, ib)
        self.assertTrue(ia.startswith("SIG-"))
        self.assertNotIn(seed["signature"], json.dumps(a))

    def test_empty_register_is_explicit_zero_candidates_not_zero_failures(self):
        x = plan(census(roots=[], unmatched=[]))
        self.assertEqual(x["candidate_count"], 0)
        self.assertEqual(x["waves"], [])
        self.assertFalse(x["worker_dispatch"])
        self.assertFalse(x["merge_authorized"])

    def test_seven_plus_waves_are_bounded_staged_not_launched(self):
        roots = [root(i) for i in range(1, 11)]
        x = plan(census(roots=roots), max_waves=8, capacity=1, per_repo=1)
        self.assertEqual(len(x["waves"]), 8)
        self.assertEqual(x["waves"][-1]["wave"], "N+7")
        self.assertEqual(x["remaining_candidate_count"], 2)
        self.assertTrue(all(w["count"] == 1 for w in x["waves"]))
        self.assertTrue(all(w["status"] == "STAGED_NOT_DISPATCHED" for w in x["waves"]))
        self.assertFalse(x["worker_dispatch"])

    def test_invalid_cap_types_never_enable_unbounded_work(self):
        for field in ("max_waves", "capacity", "per_repo"):
            for val in (True, 0, 65):
                with self.subTest(field=field, value=val):
                    if field == "per_repo" and val == 65:
                        pass
                    with self.assertRaises(ValueError):
                        plan(census(), **{field: val})

    def test_source_clock_rejects_missing_naive_or_malformed(self):
        for stamp in ("2026-10-26T12:00:00", "nonsense", 33):
            with self.subTest(stamp=stamp):
                with self.assertRaises(ValueError):
                    plan(census(stamp=stamp))

    def test_source_freshness_boundary_is_not_inferred_as_closure(self):
        older = T - timedelta(hours=48, minutes=1)
        x = plan(census(stamp=older.isoformat()))
        self.assertFalse(x["source"]["fresh"])
        self.assertEqual(x["status"], "STALE_SOURCE_NEEDS_RECENSUS")
        self.assertEqual(x["formal_closure_credit"], 0)

    def test_naive_runtime_now_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "NOW_MISSING_OFFSET"):
            rf.build(census(), now=datetime(2026, 10, 26, 14))
 
if __name__ == "__main__":
    unittest.main()
