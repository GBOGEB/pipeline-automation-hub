"""Fail-closed offline tests for the bounded FPC owner rule-suite join."""
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fpc_rule_suite_join as j

HEAD = "a" * 40
MERGE = "b" * 40
TIME = "2026-11-11T21:41:15Z"
RUN = "https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/43104849231"


def cohort(state="FAILURE"):
    return {"schema": j.EVENT_SCHEMA, "repository": j.REPO, "ref": j.REF,
            "events": [{"pr": 1152, "head_sha": HEAD, "merge_commit_sha": MERGE,
                        "merged_at": TIME, "cohort": "historical_27", "fpc": {
                            "state": state,
                            "status_id": 58674157189 if state != "ABSENT" else None,
                            "run_url": RUN if state != "ABSENT" else None}}]}


def forbidden():
    return {"schema": j.SOURCE_SCHEMA, "repository": j.REPO, "ref": j.REF,
            "state": "FORBIDDEN", "http_status": 403, "suites": []}


def complete():
    return {"schema": j.SOURCE_SCHEMA, "repository": j.REPO, "ref": j.REF,
            "state": "COMPLETE", "filter": "bypass", "pagination_complete": True,
            "details_complete": True, "metadata_truncated": False,
            "window_start": "2026-11-11T20:00:00Z", "window_end": "2026-11-12T07:00:00Z", "suites": []}


def match(**overrides):
    s = {"id": 21, "actor_id": 12, "actor_name": "owner",
         "after_sha": MERGE, "ref": j.REF, "pushed_at": TIME, "result": "bypass",
         "rule_evaluations": [{"rule_source": {"type": "ruleset", "id": j.SOFT_RULESET},
                               "enforcement": "active", "result": "fail",
                               "rule_type": "required_status_checks",
                               "details": "Required check failed: " + j.FPC_CONTEXT}]}
    s.update(overrides)
    return s


class RuleSuiteReplay(unittest.TestCase):
    def test_403_is_not_clean_or_authorized(self):
        r = j.replay(cohort(), forbidden())
        self.assertEqual(r["observed_events"], 1)
        self.assertEqual(r["events"][0]["rule_suite_verdict"], "ADMIN_READ_403_UNRESOLVED")
        self.assertEqual(r["fpc_observations"]["FAILURE"], 1)
        self.assertEqual(r["authorized_bypasses"], 0)
        self.assertEqual(r["formal_root_closures"], 0)
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_matching_fpc_bypass_is_observed_not_owner_approved(self):
        s = complete()
        s["suites"] = [match()]
        r = j.replay(cohort(), s)
        self.assertEqual(r["fpc_bypass_observed"], 1)
        self.assertEqual(r["events"][0]["rule_suite_ids"], [21])
        self.assertFalse(r["events"][0]["authorized_bypass"])
        self.assertEqual(r["events"][0]["rule_suite_verdict"],
                         "FPC_BYPASS_OBSERVED_OWNER_DECISION_REQUIRED")

    def test_wrong_after_sha_wrong_ref_and_time_do_not_match(self):
        for changed in ({"after_sha": "c"*40}, {"ref": "refs/heads/staging"},
                        {"pushed_at": "2026-11-11T22:30:00Z"}):
            with self.subTest(changed=changed):
                s = complete()
                s["suites"] = [match(**changed)]
                self.assertEqual(j.replay(cohort(), s)["events"][0]["rule_suite_ids"], [])

    def test_bypass_of_other_check_not_claimed_as_fpc(self):
        s = complete()
        item = match()
        item["rule_evaluations"][0]["details"] = "CodeQL failed"
        s["suites"] = [item]
        r = j.replay(cohort(), s)
        self.assertEqual(r["fpc_bypass_observed"], 0)
        self.assertEqual(r["events"][0]["rule_suite_verdict"],
                         "BYPASS_OBSERVED_FPC_SCOPE_UNPROVEN")

    def test_wrong_ruleset_identity_is_not_fpc(self):
        s = complete()
        item = match()
        item["rule_evaluations"][0]["rule_source"]["id"] = 25789280
        s["suites"] = [item]
        self.assertEqual(j.replay(cohort(), s)["fpc_bypass_observed"], 0)

    def test_no_details_unverified_not_closure(self):
        s = complete()
        s["suites"] = [match(rule_evaluations=None)]
        self.assertEqual(j.replay(cohort(), s)["events"][0]["rule_suite_verdict"],
                         "BYPASS_OBSERVED_RULE_EVALUATIONS_MISSING")

    def test_pagination_incomplete_with_bypass_must_not_promote(self):
        s = complete()
        s["pagination_complete"] = False
        s["suites"] = [match()]
        self.assertEqual(j.replay(cohort(), s)["fpc_bypass_observed"], 0)
        self.assertEqual(j.replay(cohort(), s)["events"][0]["rule_suite_verdict"],
                         "SOURCE_INCOMPLETE_UNRESOLVED")

    def test_source_window_does_not_cover_merge(self):
        s = complete()
        s["window_start"] = "2026-11-11T22:00:00Z"
        self.assertEqual(j.replay(cohort(), s)["rule_suite_source_state"], "INCOMPLETE")

    def test_no_matching_suite_is_not_success(self):
        r = j.replay(cohort(), complete())
        self.assertEqual(r["events"][0]["rule_suite_verdict"],
                         "NO_MATCHING_RULE_SUITE_OBSERVED_UNRESOLVED")
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_duplicate_suite_or_merge_event_rejected(self):
        c = cohort()
        c["events"].append(copy.deepcopy(c["events"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_MERGE_EVENT"):
            j.replay(c, complete())
        s = complete()
        s["suites"] = [match(), match()]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RULE_SUITE_ID"):
            j.replay(cohort(), s)

    def test_two_distinct_suites_for_same_merge_are_unresolved(self):
        s = complete()
        s["suites"] = [match(), match(id=22)]
        r = j.replay(cohort(), s)
        self.assertEqual(r["events"][0]["rule_suite_verdict"],
                         "MULTIPLE_MATCHING_RULE_SUITES_UNRESOLVED")

    def test_observed_success_not_owner_approval(self):
        c = cohort("SUCCESS")
        s = complete()
        s["suites"] = [match(result="pass")]
        r = j.replay(c, s)
        self.assertEqual(r["fpc_observations"]["SUCCESS"], 1)
        self.assertEqual(r["authorized_bypasses"], 0)
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_absent_status_does_not_break_provenance_join(self):
        r = j.replay(cohort("ABSENT"), forbidden())
        self.assertEqual(r["fpc_observations"]["ABSENT"], 1)
        self.assertEqual(r["events"][0]["rule_suite_verdict"], "ADMIN_READ_403_UNRESOLVED")

    def test_fake_absence_receipt_and_invalid_head_rejected(self):
        c = cohort("ABSENT")
        c["events"][0]["fpc"]["status_id"] = 42
        with self.assertRaisesRegex(ValueError, "ABSENT_WITH_RECEIPT"):
            j.replay(c, forbidden())
        c = cohort()
        c["events"][0]["head_sha"] = "abc"
        with self.assertRaisesRegex(ValueError, "HEAD_NOT_EXACT_SHA"):
            j.replay(c, forbidden())

    def test_reordered_cohort_gives_identical_receipt(self):
        c = cohort()
        two = copy.deepcopy(c["events"][0])
        two.update(pr=1153, head_sha="c"*40, merge_commit_sha="d"*40,
                   merged_at="2026-11-11T21:41:20Z")
        c["events"].append(two)
        first = j.replay(c, forbidden())
        c["events"].reverse()
        second = j.replay(c, forbidden())
        self.assertEqual(first, second)
        self.assertEqual(first["new_semantic_roots"], 0)

    def test_forbidden_cannot_carry_fake_suites(self):
        s = forbidden()
        s["suites"] = [match()]
        with self.assertRaisesRegex(ValueError, "FORBIDDEN_SOURCE_CONTRADICTION"):
            j.replay(cohort(), s)

    def test_native_29_event_fixture_and_403_receipt(self):
        root = pathlib.Path(__file__).resolve().parent / "evidence"
        import json
        events = json.loads((root / "FPC_MERGE_COHORT_29_20261112.json").read_text())
        source = json.loads((root / "OWNER_RULE_SUITES_403_20261112.json").read_text())
        result = j.replay(events, source)
        self.assertEqual(result["observed_events"], 29)
        self.assertEqual(result["historical_events"], 27)
        self.assertEqual(result["positive_controls"], 2)
        self.assertEqual(result["fpc_observations"],
                         {"FAILURE": 26, "ABSENT": 1, "SUCCESS": 2})
        self.assertEqual(result["rule_suite_source_state"], "FORBIDDEN")
        self.assertEqual(result["digest_sha256"],
                         "e3224092839fcb46467e19e86111a2cba6dcc178ed65f701eac7b51937b1b115")
        self.assertTrue(all(x["rule_suite_verdict"] == "ADMIN_READ_403_UNRESOLVED"
                            for x in result["events"]))
        self.assertEqual(result["authorized_bypasses"], 0)
        self.assertEqual(result["new_semantic_roots"], 0)

    def test_synthetic_29_event_owner_replay_never_auto_authorizes(self):
        root = pathlib.Path(__file__).resolve().parent / "evidence"
        import json
        events = json.loads((root / "FPC_MERGE_COHORT_29_20261112.json").read_text())
        s = complete()
        s["suites"] = []
        for i, event in enumerate(events["events"]):
            if event["fpc"]["state"] == "ABSENT":
                continue
            s["suites"].append(match(id=100+i,
                                     after_sha=event["merge_commit_sha"],
                                     pushed_at=event["merged_at"],
                                     result="pass" if event["fpc"]["state"] == "SUCCESS" else "bypass"))
        result = j.replay(events, s)
        self.assertEqual(result["fpc_bypass_observed"], 26)
        self.assertEqual(result["authorized_bypasses"], 0)
        self.assertEqual(result["formal_root_closures"], 0)
        self.assertEqual(result["merge_admission"], "HOLD")



class OwnerExportReplay(unittest.TestCase):
    """Real owner export (12 Nov 2026, Hub #336) and the collector's fail-closed decision."""

    PACK = pathlib.Path(__file__).resolve().parent / "evidence" / "owner_rule_suites_20261112"

    def _load(self, name):
        import json
        return json.loads((self.PACK / name).read_text(encoding="utf-8"))

    def _events(self):
        import json
        root = pathlib.Path(__file__).resolve().parent / "evidence"
        return json.loads((root / "FPC_MERGE_COHORT_29_20261112.json").read_text(encoding="utf-8"))

    def test_sha256sums_match_committed_source_bytes(self):
        import hashlib
        lines = (self.PACK / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 53)
        for line in lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((self.PACK / name).read_bytes()).hexdigest(), digest, name)

    def test_export_receipts_bind_every_raw_response(self):
        import hashlib
        export = self._load("OWNER_RULE_SUITES_EXPORT.json")
        self.assertEqual(len(export["receipts"]), 52)
        for r in export["receipts"]:
            self.assertTrue(r["endpoint"].startswith("GET /repos/GBOGEB/pipeline-automation-hub/rulesets/rule-suites"))
            self.assertEqual(hashlib.sha256((self.PACK / r["file"]).read_bytes()).hexdigest(), r["sha256"])

    def test_owner_export_replays_to_recorded_receipt(self):
        result = j.replay(self._events(), self._load("OWNER_RULE_SUITES_EXPORT.json"))
        recorded = self._load("REPLAY.json")
        self.assertEqual(result, recorded)
        self.assertEqual(result["rule_suite_source_state"], "COMPLETE")
        self.assertEqual(result["digest_sha256"],
                         "638c46737baa8cc2b3a6f3ecb72584672998758aab4b1476d928223eb405e5c8")
        verdicts = {}
        for row in result["events"]:
            verdicts.setdefault(row["rule_suite_verdict"], []).append(row["pr"])
        self.assertEqual(len(verdicts["FPC_BYPASS_OBSERVED_OWNER_DECISION_REQUIRED"]), 22)
        self.assertEqual(sorted(verdicts["NO_MATCHING_RULE_SUITE_OBSERVED_UNRESOLVED"]),
                         [1135, 1152, 1185, 1206, 1207])
        self.assertEqual(sorted(verdicts["RULE_SUITE_PASS_OBSERVED_NO_ADMISSION_PROOF"]), [1219, 1220])
        self.assertEqual(result["authorized_bypasses"], 0)
        self.assertEqual(result["merge_admission"], "HOLD")
        self.assertFalse(result["authority_transfer"])
        self.assertFalse(any(r["authorized_bypass"] for r in result["events"]))

    def _collector_inputs(self):
        export = self._load("OWNER_RULE_SUITES_EXPORT.json")
        pages = [self._load("raw/list_p1.json")]
        details = {s["id"]: s for s in export["suites"]}
        return pages, details, self._events()["events"]

    def test_collector_assess_reproduces_complete_export(self):
        import fpc_rule_suite_collect as c
        pages, details, events = self._collector_inputs()
        got = c.assess(pages, details, events)
        export = self._load("OWNER_RULE_SUITES_EXPORT.json")
        for key in ("state", "pagination_complete", "details_complete", "metadata_truncated",
                    "window_start", "window_end", "suites"):
            self.assertEqual(got[key], export[key], key)

    def test_collector_fails_closed_on_each_gap(self):
        import fpc_rule_suite_collect as c
        pages, details, events = self._collector_inputs()
        first = pages[0][0]["id"]
        gaps = {
            "missing_detail": (pages, {**details, first: None}, None),
            "full_last_page": ([pages[0] + [{**pages[0][0], "id": 10**12 + i} for i in range(c.PER_PAGE - len(pages[0]))]],
                               {**details, **{10**12 + i: details[first] for i in range(c.PER_PAGE - len(pages[0]))}}, None),
            "list_403": (pages, details, "list page 1: HTTP 403"),
            "window_not_covered": ([[r for r in pages[0] if c._ts(r["pushed_at"]) > c._ts("2026-11-11T22:00:00Z")]], details, None),
            "metadata_cap": (pages, {**details, first: {**details[first], "rule_evaluations": [{}] * c.METADATA_CAP}}, None),
        }
        for name, (pg, dt, err) in gaps.items():
            with self.subTest(gap=name):
                got = c.assess(pg, dt, events, err)
                self.assertEqual(got["state"], "INCOMPLETE")
                self.assertTrue(got["limitations"])
                if name != "full_last_page":  # synthetic duplicate rows: the join rejects those outright
                    self.assertEqual(j.replay(self._events(), got)["rule_suite_source_state"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
