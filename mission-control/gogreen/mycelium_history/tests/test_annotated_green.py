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



class NPlusOneBoundaryAndFaultTests(unittest.TestCase):
    """W10 N+1 disjoint adversarial cases, no source-test exclusions."""

    def test_branch_response_must_be_an_object(self):
        with self.assertRaisesRegex(ValueError, "branch response"):
            a.sha_of(None)

    def test_branch_commit_sha_missing_is_unknown_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "branch source head"):
            a.sha_of({"commit": {}})

    def test_invalid_merged_pr_limit_bool_not_an_integer(self):
        fetch, _ = fixture()
        with self.assertRaisesRegex(ValueError, "bounded PR limit"):
            a.list_merged(fetch, limit=True)

    def test_merged_pr_limit_above_five_rejected(self):
        fetch, _ = fixture()
        with self.assertRaisesRegex(ValueError, "bounded PR limit"):
            a.list_merged(fetch, limit=6)

    def test_merged_pr_selection_excludes_unmerged_and_foreign_base(self):
        fetch, _ = fixture()
        def extra(path):
            d = fetch(path)
            if "/pulls?" in path:
                d.append({"number": 1111, "head": {"sha": B},
                          "base": {"ref": "main"}, "merged_at": None})
                d.append({"number": 2222, "head": {"sha": B},
                          "base": {"ref": "dev"},
                          "merged_at": "2026-10-18T23:00:00Z"})
            return d
        self.assertEqual([x["number"] for x in a.list_merged(extra)], [1098,1097,1096])

    def test_merge_selection_sorts_out_of_order_response(self):
        fetch, _ = fixture()
        def reverse(path):
            d = fetch(path)
            return list(reversed(d)) if "/pulls?" in path else d
        self.assertEqual([x["number"] for x in a.list_merged(reverse)],
                         [1098,1097,1096])

    def test_invalid_merged_pr_boolean_number_rejected(self):
        fetch, _ = fixture()
        def changed(path):
            d = fetch(path)
            if "/pulls?" in path:
                d[0]["number"] = True
            return d
        with self.assertRaisesRegex(ValueError, "merged PR number"):
            a.list_merged(changed)

    def test_missing_pull_list_rejected(self):
        with self.assertRaisesRegex(ValueError, "closed PR return"):
            a.list_merged(lambda _: {"items":[]})

    def test_source_check_run_rejects_unknown_status(self):
        with self.assertRaisesRegex(ValueError, "unknown check status"):
            a.check_run(item(101, A, status="sleeping"), A)

    def test_source_check_run_rejects_bool_annotation_count(self):
        with self.assertRaisesRegex(ValueError, "annotation count invalid"):
            a.check_run(item(101, A, annotations=True), A)

    def test_untrusted_check_run_url_is_not_rendered(self):
        d = item(101, A)
        d["details_url"] = "https://attacker.example/job/5"
        self.assertIsNone(a.check_run(d, A)["url"])

    def test_trusted_exact_provider_url_is_retained(self):
        d = item(101, A)
        self.assertEqual(a.check_run(d, A)["url"], d["details_url"])

    def test_empty_source_check_population_is_measured_zero_not_fabricated(self):
        v = a.get_commit_checks(lambda _:{
            "total_count":0, "check_runs":[]}, A)
        self.assertEqual((v["api_total"], v["observed"]), (0,0))
        self.assertTrue(v["complete"])
        self.assertEqual(a.cohort_rollup(v)["successful_annotated_checks_observed"], 0)

    def test_exact_check_run_second_page_101_of_101(self):
        checks = [item(i, A, annotations=0) for i in range(1,102)]
        def fetch(path):
            return {"total_count":101,"check_runs":(
                checks[:100] if path.endswith("page=1") else checks[100:])}
        d = a.get_commit_checks(fetch,A)
        self.assertEqual((d["observed"], d["api_total"]), (101,101))
        self.assertTrue(d["complete"])

    def test_page_budget_four_marks_401_as_partial(self):
        checks = [item(i, A, annotations=0) for i in range(1,402)]
        def fetch(path):
            page = int(path.rsplit("page=",1)[1])
            return {"total_count":401, "check_runs":checks[(page-1)*100:page*100]}
        d = a.get_commit_checks(fetch,A)
        self.assertEqual((d["observed"], d["api_total"]), (400,401))
        self.assertFalse(d["complete"])

    def test_invalid_page_budget_false_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bounded check-run page count"):
            a.get_commit_checks(lambda _: {}, A, max_pages=False)

    def test_invalid_page_budget_above_four_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bounded check-run page count"):
            a.get_commit_checks(lambda _: {}, A, max_pages=5)

    def test_invalid_check_response_list_shape_rejected(self):
        with self.assertRaisesRegex(ValueError, "check-run population"):
            a.get_commit_checks(lambda _: {"total_count":1,"check_runs":{}}, A)

    def test_bool_check_total_is_not_an_integer(self):
        with self.assertRaisesRegex(ValueError, "check-run population"):
            a.get_commit_checks(lambda _: {"total_count":True,"check_runs":[]}, A)

    def test_detail_probe_boolean_limit_rejected(self):
        fetch, _ = fixture()
        c = a.get_commit_checks(fetch,A)
        with self.assertRaisesRegex(ValueError, "annotation detail probe cap"):
            a.read_level_sample(fetch,c,limit=False)

    def test_rate_limited_annotation_probe_is_explicit_unknown(self):
        fetch, _ = fixture()
        c = a.get_commit_checks(fetch,A)
        def rate_limited(path):
            if "/check-runs/" in path:
                raise HTTPError(path,429,"rate limit",None,io.BytesIO())
            return fetch(path)
        a.read_level_sample(rate_limited,c,limit=2)
        self.assertEqual(c["checks"][0]["annotation_severity"], "UNKNOWN_HTTP_429")
        self.assertIsNone(a.cohort_rollup(c)["total_failure_level_annotations"])

    def test_not_found_annotation_probe_is_explicit_unknown(self):
        fetch, _ = fixture()
        c = a.get_commit_checks(fetch,A)
        def not_found(path):
            if "/check-runs/" in path:
                raise HTTPError(path,404,"owner restricted",None,io.BytesIO())
            return fetch(path)
        a.read_level_sample(not_found,c,limit=2)
        self.assertEqual(c["checks"][0]["annotation_severity"], "UNKNOWN_HTTP_404")

    def test_service_failure_does_not_turn_into_green(self):
        fetch, _ = fixture()
        c = a.get_commit_checks(fetch,A)
        def outage(path):
            if "/check-runs/" in path:
                raise HTTPError(path,503,"provider unavailable",None,io.BytesIO())
            return fetch(path)
        with self.assertRaises(HTTPError):
            a.read_level_sample(outage,c,limit=2)

    def test_malformed_annotation_detail_response_rejected(self):
        fetch, _ = fixture()
        c = a.get_commit_checks(fetch,A)
        def tamper(path):
            return {"message":"not a list"} if "/check-runs/" in path else fetch(path)
        with self.assertRaisesRegex(ValueError,"annotation detail is not a list"):
            a.read_level_sample(tamper,c,limit=2)

    def test_priority_prefers_validate_over_security(self):
        v = [a.check_run(item(10,A,name="Security Scan"),A),
             a.check_run(item(11,A,name="Validate Manifest"),A)]
        self.assertEqual(sorted(v,key=a.priority)[0]["id"],11)

    def test_pending_does_not_count_as_terminal_red(self):
        fetch, _ = fixture()
        m = a.cohort_rollup(a.get_commit_checks(fetch,A))
        self.assertEqual(m["terminal_red_check_count"],1)
        self.assertEqual(m["unknown_or_pending_check_count"],1)

    def test_current_main_spoofing_rejected_even_when_sha_valid(self):
        fetch, _ = fixture()
        d = a.collect(fetch)
        d["hub_source_sha"] = A
        d["source_bound_cohorts"][0]["head_sha"] = B
        with self.assertRaisesRegex(ValueError, "current CODEX main source-binding"):
            a.validate(d,A)

    def test_forged_breadth_rejected_as_not_six_repo(self):
        fetch, _ = fixture()
        d = a.collect(fetch)
        d["hub_source_sha"] = A
        d["source_bound_breadth"]["six_repo_federation_breadth"] = 6
        with self.assertRaisesRegex(ValueError, "unsupported federation breadth"):
            a.validate(d,A)

    def test_negative_successful_count_rejected(self):
        fetch, _ = fixture()
        d = a.collect(fetch)
        d["hub_source_sha"] = A
        d["source_bound_cohorts"][0]["metrics"]["successful_checks"] = -1
        with self.assertRaisesRegex(ValueError, "nonnegative native census"):
            a.validate(d,A)

    def test_check_array_must_match_observed_count(self):
        fetch, _ = fixture()
        d = a.collect(fetch)
        d["hub_source_sha"] = A
        d["source_bound_cohorts"][0]["checks"] = []
        with self.assertRaisesRegex(ValueError, "invalid check denominator"):
            a.validate(d,A)

    def test_claimed_complete_with_smaller_check_population_rejected(self):
        fetch, _ = fixture()
        d = a.collect(fetch)
        d["hub_source_sha"] = A
        d["source_bound_cohorts"][0]["metrics"]["check_runs_api_total"] = 5
        with self.assertRaisesRegex(ValueError, "false complete check cohort"):
            a.validate(d,A)

    def test_w10_breadth_proves_only_codex_check_cohorts(self):
        fetch, _ = fixture()
        d = a.collect(fetch)
        d["hub_source_sha"] = A
        b = d["source_bound_breadth"]
        self.assertEqual((b["complete_check_cohorts_observed"],
                          b["check_cohorts_eligible"]),(4,4))
        self.assertIsNone(b["six_repo_federation_breadth"])
        self.assertTrue(a.validate(d,A))


if __name__ == "__main__":
    unittest.main()
