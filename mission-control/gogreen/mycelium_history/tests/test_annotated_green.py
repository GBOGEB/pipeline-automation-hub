"""W10 annotated-green fail-closed and unknown-state unit contracts."""
from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import annotated_green as a

A, B, C, D = "a" * 40, "b" * 40, "c" * 40, "d" * 40


def item(ident, sha, conclusion="success", annotations=1, status="completed",
         name="test"):
    return {"id": ident, "head_sha": sha, "name": name, "status": status,
            "conclusion": conclusion,
            "output": {"annotations_count": annotations},
            "details_url": f"https://github.com/GBOGEB/CODEX/actions/runs/4/job/{ident}"}


def fixture(deny_level=False, main_second=None, bad_check=False):
    prs = [
        {"number": 1098, "head": {"sha": B}, "base": {"ref": "main"},
         "merged_at": "2026-10-18T17:05:18Z"},
        {"number": 1097, "head": {"sha": C}, "base": {"ref": "main"},
         "merged_at": "2026-10-18T17:02:51Z"},
        {"number": 1096, "head": {"sha": D}, "base": {"ref": "main"},
         "merged_at": "2026-10-18T16:10:42Z"},
    ]
    observed = []
    def fetch(path):
        observed.append(path)
        if path.endswith("/branches/main"):
            return {"commit": {"sha": main_second if main_second and
                               sum(x.endswith("/branches/main") for x in observed) > 1
                               else A}}
        if path.endswith("pulls?state=closed&sort=updated&direction=desc&per_page=100&page=1"):
            return prs
        if "/commits/" in path:
            sha = path.split("/commits/")[1].split("/")[0]
            tests = [
                item(101, sha, annotations=2, name="test"),
                item(102, sha, annotations=1, name="governance"),
                item(103, sha, conclusion="failure", annotations=1, name="security"),
                item(104, sha, conclusion=None, annotations=0,
                     status="queued", name="queue"),
            ]
            if bad_check:
                tests[0]["head_sha"] = D if sha != D else A
            return {"total_count": len(tests), "check_runs": tests}
        if "/check-runs/" in path:
            if deny_level:
                raise HTTPError(path, 403, "no cross-repo check access", None, io.BytesIO())
            ident = int(path.split("/check-runs/")[1].split("/")[0])
            return ([{"annotation_level": "failure"}, {"annotation_level": "notice"}]
                    if ident == 101 else [{"annotation_level": "warning"}])
        raise AssertionError("unexpected network path " + path)
    return fetch, observed


class CheckRunIdentity(unittest.TestCase):
    def test_success_with_annotation_is_not_failure_conclusion(self):
        x = a.check_run(item(1, A), A)
        self.assertEqual(x["conclusion"], "success")
        self.assertEqual(x["annotation_count"], 1)
        self.assertEqual(x["annotation_severity"], "UNKNOWN_NOT_INSPECTED")

    def test_explicit_zero_is_not_unknown(self):
        self.assertEqual(a.check_run(item(1,A,annotations=0),A)["annotation_count"],0)

    def test_absent_annotations_is_unknown(self):
        raw = item(1,A)
        del raw["output"]
        self.assertIsNone(a.check_run(raw,A)["annotation_count"])

    def test_check_id_boolean_rejected(self):
        raw = item(True,A)
        with self.assertRaisesRegex(ValueError,"check ID"):
            a.check_run(raw,A)

    def test_head_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,"HEAD"):
            a.check_run(item(1,B),A)

    def test_empty_name_rejected(self):
        raw=item(1,A)
        raw["name"]="  "
        with self.assertRaisesRegex(ValueError,"check name"):
            a.check_run(raw,A)

    def test_negative_annotation_count_rejected(self):
        with self.assertRaisesRegex(ValueError,"annotation count"):
            a.check_run(item(1,A,annotations=-1),A)

    def test_nonterminal_fake_success_rejected(self):
        with self.assertRaisesRegex(ValueError,"status-conclusion mismatch"):
            a.check_run(item(1,A,status="queued"),A)

    def test_terminal_missing_conclusion_rejected(self):
        with self.assertRaisesRegex(ValueError,"status-conclusion mismatch"):
            a.check_run(item(1,A,conclusion=None),A)

    def test_bad_source_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,"commit SHA"):
            a.get_commit_checks(lambda p:{}, "short")


class CheckRunCohort(unittest.TestCase):
    def test_complete_pages(self):
        fetch,_=fixture()
        d=a.get_commit_checks(fetch,A)
        self.assertTrue(d["complete"])
        self.assertEqual(d["api_total"],4)
        self.assertEqual(d["observed"],4)

    def test_annotated_green_is_a_success_count(self):
        fetch,_=fixture()
        c=a.get_commit_checks(fetch,A)
        a.read_level_sample(fetch,c,limit=2)
        m=a.cohort_rollup(c)
        self.assertEqual(m["successful_checks"],2)
        self.assertEqual(m["successful_annotated_checks_observed"],2)
        self.assertEqual(m["annotation_items_reported"],3)
        self.assertEqual(m["verified_failure_level_items_in_sample"],1)
        self.assertIsNone(m["total_failure_level_annotations"])

    def test_403_severity_unknown_does_not_cancel_check_count(self):
        fetch,_=fixture(deny_level=True)
        c=a.get_commit_checks(fetch,A)
        a.read_level_sample(fetch,c,limit=2)
        m=a.cohort_rollup(c)
        self.assertEqual(m["successful_annotated_checks_observed"],2)
        self.assertEqual(m["detail_severity_verified_check_count"],0)
        self.assertIsNone(m["total_failure_level_annotations"])
        self.assertFalse(m["sample_is_complete_annotation_severity"])

    def test_count_mismatch_does_not_invent_levels(self):
        fetch,_=fixture()
        c=a.get_commit_checks(fetch,A)
        c["checks"][0]["annotation_count"]=4
        a.read_level_sample(fetch,c,limit=2)
        self.assertEqual(c["checks"][0]["annotation_severity"],"UNKNOWN_COUNT_MISMATCH")

    def test_invalid_annotation_level_rejected(self):
        fetch,_=fixture()
        def tamper(path):
            x=fetch(path)
            return [{"annotation_level":"fatal"},{"annotation_level":"warning"}] if (
                "/check-runs/101/" in path) else x
        c=a.get_commit_checks(tamper,A)
        with self.assertRaisesRegex(ValueError,"annotation level"):
            a.read_level_sample(tamper,c,limit=2)

    def test_priority_targets_tests(self):
        rows=[a.check_run(item(50,A,name="other"),A),
              a.check_run(item(90,A,name="test"),A),
              a.check_run(item(55,A,name="security"),A)]
        self.assertEqual(sorted(rows,key=a.priority)[0]["name"],"test")

    def test_zero_detail_budget_keeps_unknown(self):
        fetch,_=fixture()
        c=a.get_commit_checks(fetch,A)
        a.read_level_sample(fetch,c,limit=0)
        self.assertEqual(a.cohort_rollup(c)["detail_severity_verified_check_count"],0)

    def test_excess_annotations_requires_bounded_probe(self):
        fetch,_=fixture()
        c=a.get_commit_checks(fetch,A)
        c["checks"][0]["annotation_count"]=101
        a.read_level_sample(fetch,c,limit=2)
        self.assertEqual(c["checks"][0]["annotation_severity"],
                         "UNKNOWN_TOO_MANY_ANNOTATIONS")

    def test_duplicate_check_run_fails(self):
        fetch,_=fixture()
        def dupe(p):
            v=fetch(p)
            if "/commits/" in p:
                v["check_runs"].append(copy.deepcopy(v["check_runs"][0]))
                v["total_count"]=5
            return v
        with self.assertRaisesRegex(ValueError,"duplicate check-run"):
            a.get_commit_checks(dupe,A)

    def test_changed_denominator_degrades_not_full(self):
        first={"n":0}
        rows=[item(i,A) for i in range(1,102)]
        def changing(p):
            first["n"]+=1
            if p.endswith("page=1"):
                return {"total_count":101,"check_runs":rows[:100]}
            return {"total_count":102,"check_runs":rows[100:]}
        v=a.get_commit_checks(changing,A)
        self.assertFalse(v["complete"])
        self.assertTrue(v["page_drift"])

    def test_invalid_annotation_total_rejected(self):
        with self.assertRaisesRegex(ValueError,"check-run population"):
            a.get_commit_checks(lambda _:{"total_count":None,"check_runs":[]},A)


class CaptureTests(unittest.TestCase):
    def test_latest_three_merge_heads_and_main(self):
        fetch,logs=fixture()
        d=a.collect(fetch)
        self.assertEqual(d["cohort_count"],4)
        self.assertEqual([v["pr"] for v in d["source_bound_cohorts"]],
                         [None,1098,1097,1096])
        self.assertEqual(d["main_sha_before"],A)
        self.assertTrue(d["main_head_unchanged_during_capture"])
        self.assertTrue(all(x["availability"]=="CHECK_RUN_API_OBSERVED"
                            for x in d["source_bound_cohorts"]))
        self.assertEqual(d["admission"],"HOLD")
        self.assertIsNone(d["worker_hours"])

    def test_merged_pr_head_prerequisite(self):
        fetch,_=fixture()
        def corrupt(p):
            x=fetch(p)
            if "/pulls?" in p:x[0]["head"]["sha"]="moving"
            return x
        with self.assertRaisesRegex(ValueError,"merged PR head"):
            a.collect(corrupt)

    def test_main_moves_is_flagged_not_comparable(self):
        fetch,_=fixture(main_second=B)
        d=a.collect(fetch)
        self.assertFalse(d["main_head_unchanged_during_capture"])
        self.assertEqual(d["main_sha_before"],A)
        self.assertEqual(d["main_sha_after"],B)

    def test_changed_check_head_fails_closed(self):
        fetch,_=fixture(bad_check=True)
        with self.assertRaisesRegex(ValueError,"check HEAD"):
            a.collect(fetch)

    def test_access_denied_retains_unknown_without_zero_counts(self):
        fetch,_=fixture()
        def denied(p):
            if "/commits/" in p:
                raise HTTPError(p,403,"blocked",None,io.BytesIO())
            return fetch(p)
        d=a.collect(denied)
        self.assertTrue(all(x["metrics"] is None
                            for x in d["source_bound_cohorts"]))
        self.assertTrue(all("BLOCKED_HTTP_403" in x["availability"]
                            for x in d["source_bound_cohorts"]))

    def test_full_annotation_error_denominator_remains_unknown(self):
        fetch,_=fixture()
        d=a.collect(fetch)
        self.assertFalse(d["error_level_annotation_population_complete"])
        self.assertTrue(all(x["metrics"]["total_failure_level_annotations"] is None
                            for x in d["source_bound_cohorts"]))

    def test_refuse_forged_merge_admission(self):
        fetch,_=fixture()
        d=a.collect(fetch)
        d["hub_source_sha"]=A
        d["merge_authorized"]=True
        with self.assertRaisesRegex(ValueError,"false admission"):
            a.validate(d,A)

    def test_refuse_forged_root_closure(self):
        fetch,_=fixture()
        d=a.collect(fetch)
        d["hub_source_sha"]=A
        d["accepted_root_closures"]=1
        with self.assertRaisesRegex(ValueError,"false admission"):
            a.validate(d,A)

    def test_refuse_capacity_zero_as_known(self):
        fetch,_=fixture()
        d=a.collect(fetch)
        d["hub_source_sha"]=A
        d["capacity_slots"]=0
        with self.assertRaisesRegex(ValueError,"falsified capacity"):
            a.validate(d,A)

    def test_refuse_mismatched_source_head_receipt(self):
        fetch,_=fixture()
        d=a.collect(fetch)
        d["hub_source_sha"]=B
        with self.assertRaisesRegex(ValueError,"exact hub head"):
            a.validate(d,A)

    def test_valid_census_receipt(self):
        fetch,_=fixture()
        d=a.collect(fetch)
        d["hub_source_sha"]=A
        self.assertTrue(a.validate(d,A))

    def test_no_token_fallback(self):
        with self.assertRaisesRegex(ValueError,"CROSS_REPO_READ_TOKEN"):
            a.native_get(a.ROOT+"/branches/main",None)

    def test_unsafe_external_target_rejected(self):
        with self.assertRaisesRegex(ValueError,"external API"):
            a.native_get("https://attacker.example", "token-only-in-test")


if __name__ == "__main__":
    unittest.main()
