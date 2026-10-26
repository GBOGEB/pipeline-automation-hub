"""W7 RECEIVER disjoint native paging, adversarial and non-credit TestFlight."""
import json
import subprocess
import unittest
from urllib.parse import parse_qs
from unittest.mock import patch
from metric_atlas.receiver import (bounded_github_rows, platform_job, collect,
    source_catalog, check_request, request_id, github_json)

SHA="a"*40; REPO="GBOGEB/ABACUS"
def env(selector="all"):
    return {"GITHUB_REPOSITORY":REPO,"GITHUB_SHA":SHA,"QPS_EXPECTED_SHA":SHA,
      "QPS_WAVE":"W7","QPS_SELECTOR":selector,
      "QPS_REQUEST_ID":request_id("W7","ABACUS",REPO,SHA,selector),
      "GITHUB_RUN_ID":"40","GITHUB_RUN_ATTEMPT":"2",
      "QPS_JOB_NAME":"native-check","GH_TOKEN":"mock-not-real"}

def fake(n,field,at=None,malform=None):
    all_rows=[{"id":i,"name":"native-check" if i==at else "other"+str(i)} for i in range(1,n+1)]
    def get(env_,url):
        page=int(parse_qs(url.split("?",1)[1]).get("page",["1"])[0])
        items=all_rows[(page-1)*100:page*100]
        total=n
        if malform=="boolean_total":total=True
        if malform=="drift" and page==2:total=n+1
        if malform=="duplicate" and page==2 and items:items[0]=dict(items[0],id=1)
        if malform=="missing" and page==2:items=[]
        if malform=="short" and page==1 and items:items=items[:1]
        if malform=="bad_id" and page==1 and items:items[0]=dict(items[0],id=True)
        if malform=="list":items="corrupt"
        return {"total_count":total,field:items}
    return get

class W7ReceiverNative(unittest.TestCase):
    def test_six_critical_page_sizes_both_endpoints(self):
        for n in (0,1,100,101,201,400):
            for field in ("jobs","check_runs"):
                with self.subTest(n=n,field=field),patch("metric_atlas.receiver.github_json",side_effect=fake(n,field)):
                    rows,total=bounded_github_rows(env(),"repos/controlled/endpoint",field)
                    self.assertEqual((len(rows),total),(n,n))
                    self.assertEqual(len({x["id"] for x in rows}),n)

    def test_unique_job_on_page_2_3_4(self):
        for n in (101,201,400):
            with self.subTest(n=n),patch("metric_atlas.receiver.github_json",side_effect=fake(n,"jobs",at=n)) as seen:
                self.assertEqual(platform_job(env()),n)
                self.assertEqual(seen.call_count,(n+99)//100)

    def test_duplicate_named_jobs_must_hold(self):
        def repeated(e,u):
            x=fake(101,"jobs",at=101)(e,u)
            if "page=1" in u:x["jobs"][0]["name"]="native-check"
            return x
        with patch("metric_atlas.receiver.github_json",side_effect=repeated):
            with self.assertRaisesRegex(ValueError,"uniquely"):platform_job(env())

    def test_partial_duplicate_drift_and_bad_page_are_not_native_success(self):
        for mode in ("boolean_total","drift","duplicate","missing","short","bad_id","list"):
            with self.subTest(mode=mode),patch("metric_atlas.receiver.github_json",side_effect=fake(101,"jobs",malform=mode)):
                with self.assertRaises(ValueError):
                    bounded_github_rows(env(),"repos/fake/list","jobs")

    def test_401_rows_refuses_paging_fanout(self):
        with patch("metric_atlas.receiver.github_json",side_effect=fake(401,"jobs",at=401)) as remote:
            with self.assertRaisesRegex(ValueError,"unbounded"):
                bounded_github_rows(env(),"repos/fake/list","jobs")
            self.assertEqual(remote.call_count,1)

    def test_full_check_census_metadata_not_test_count_or_approval(self):
        with patch("metric_atlas.receiver.platform_job",return_value=200),patch(
              "metric_atlas.receiver.github_json",side_effect=fake(101,"check_runs")):
            result=collect(env(),"native_checks")
        self.assertEqual(result["observation"]["observed_check_runs"],101)
        self.assertTrue(result["observation"]["pagination_complete"])
        self.assertEqual(result["tests"],{})
        self.assertEqual(result["coverage"],{})
        self.assertEqual(result["merge_admission"],"HOLD")
        self.assertFalse(result["authority_transfer"])

    def test_missing_final_check_page_holds(self):
        with patch("metric_atlas.receiver.platform_job",return_value=200),patch(
              "metric_atlas.receiver.github_json",side_effect=fake(101,"check_runs",malform="missing")):
            with self.assertRaises(ValueError):collect(env(),"native_checks")

    def test_reverse_source_and_selector_guard(self):
        original=env("native_checks")
        for field,value in (("GITHUB_SHA","b"*40),("QPS_EXPECTED_SHA","b"*40),
                 ("QPS_REQUEST_ID","QPS-"+"0"*20),("QPS_WAVE","/"),
                 ("GITHUB_RUN_ID","0"),("GITHUB_RUN_ATTEMPT","-1"),
                 ("GITHUB_REPOSITORY","unknown/owner")):
            e=dict(original);e[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                check_request(e,"native_checks")
        with self.assertRaisesRegex(ValueError,"unrequested"):
            check_request(original,"coverage_catalog")

    def test_source_catalog_does_not_invent_executed_tests(self):
        paths=["tests/test_"+str(i)+".py" for i in range(104)]
        value=subprocess.CompletedProcess(["git","ls-files"],0,stdout="\n".join(paths))
        with patch("metric_atlas.receiver.subprocess.run",return_value=value):
            census=source_catalog()
        self.assertEqual(census["candidate_test_files"],104)
        self.assertEqual(len(census["tracked_test_paths"]),100)
        self.assertTrue(census["test_paths_truncated"])
        self.assertIsNone(census["executed_test_count"])

    def test_no_job_name_and_no_token_fails_before_network(self):
        e=env();e.pop("QPS_JOB_NAME")
        with patch("metric_atlas.receiver.github_json") as g:
            with self.assertRaisesRegex(ValueError,"job name"):platform_job(e)
            g.assert_not_called()
        e=env();e.pop("GH_TOKEN")
        with self.assertRaisesRegex(ValueError,"token"):github_json(e,"repos/test")

if __name__=="__main__":unittest.main()
