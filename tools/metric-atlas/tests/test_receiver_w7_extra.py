"""W7 N+1 extra receiver branches, bounded-adversarial metadata and CLI proof."""
import contextlib
import io
import json
import runpy
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from metric_atlas.receiver import (check_request,request_id,github_json,
                                   bounded_github_rows,collect)

SHA="a"*40;REPO="GBOGEB/ABACUS"
def env(selector="all"):
    return {"GITHUB_REPOSITORY":REPO,"GITHUB_SHA":SHA,"QPS_EXPECTED_SHA":SHA,
            "QPS_WAVE":"W7R","QPS_SELECTOR":selector,
            "QPS_REQUEST_ID":request_id("W7R","ABACUS",REPO,SHA,selector),
            "GITHUB_RUN_ID":"42","GITHUB_RUN_ATTEMPT":"1", "QPS_JOB_NAME":"native-check",
            "GH_TOKEN":"safe-local-mock"}

class W7ReceiverExtra(unittest.TestCase):
    def test_bad_selector_route_and_source_id_reject(self):
        e=env();e["QPS_SELECTOR"]="curl"
        with self.assertRaisesRegex(ValueError,"selector"):check_request(e,"native_checks")
        with self.assertRaisesRegex(ValueError,"route"):check_request(env(),"system")
        e=env();e["QPS_REQUEST_ID"]="invalid"
        with self.assertRaisesRegex(ValueError,"request ID"):check_request(e,"native_checks")

    def test_bounded_api_refuses_invalid_route_shape_and_exhausted_page_budget(self):
        with patch("metric_atlas.receiver.github_json") as fetch:
            with self.assertRaisesRegex(ValueError,"route"):
                bounded_github_rows(env(),"repos/test","unknown")
            fetch.assert_not_called()
        with patch("metric_atlas.receiver.github_json",return_value=["not an object"]):
            with self.assertRaisesRegex(ValueError,"untrusted"):
                bounded_github_rows(env(),"repos/test","jobs")
        with patch("metric_atlas.receiver.MAX_API_PAGES",0):
            with self.assertRaisesRegex(ValueError,"exceeded"):
                bounded_github_rows(env(),"repos/test","jobs")

    def test_real_http_wrapper_is_read_only_and_requires_token(self):
        e=env();e.pop("GH_TOKEN")
        with self.assertRaisesRegex(ValueError,"token"):github_json(e,"repos/abc")
        result={"total_count":0,"jobs":[]}
        with patch("metric_atlas.receiver.urllib.request.urlopen",return_value=io.BytesIO(json.dumps(result).encode())) as fetch:
            self.assertEqual(github_json(env(),"repos/safe/actions/runs/42/jobs"),result)
            a,k=fetch.call_args
            self.assertEqual(a[0].get_method(),"GET")
            self.assertEqual(k["timeout"],25)

    def test_native_checks_over_100_never_fakes_test_counts(self):
        rows=[{"id":i,"name":"check","status":"completed","conclusion":"success"} for i in range(1,102)]
        def mock_get(e,url):
            page=int(url.rsplit("page=",1)[1]);return {"total_count":101,"check_runs":rows[(page-1)*100:page*100]}
        with patch("metric_atlas.receiver.platform_job",return_value=11),\
             patch("metric_atlas.receiver.github_json",side_effect=mock_get) as fetch:
            receipt=collect(env(),"native_checks")
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(receipt["observation"]["observed_check_runs"],101)
        self.assertTrue(receipt["observation"]["pagination_complete"])
        self.assertIsNone(receipt["observation"]["first_red_root_ids"])
        self.assertEqual(receipt["tests"],{})
        self.assertEqual(receipt["coverage"],{})
        self.assertFalse(receipt["engineering_acceptance"])

    def test_coverage_catalog_route_is_source_catalog_only_without_network(self):
        listing=subprocess.CompletedProcess(["git","ls-files"],0,
            stdout="pkg/core.py\ntests/test_core.py\nweb/app.test.js\npyproject.toml\n")
        with patch("metric_atlas.receiver.platform_job",return_value=12),\
             patch("metric_atlas.receiver.subprocess.run",return_value=listing) as git,\
             patch("metric_atlas.receiver.github_json",side_effect=AssertionError("NETWORK FORBIDDEN")) as fetch,\
             patch("urllib.request.urlopen",side_effect=AssertionError("NETWORK FORBIDDEN")) as http:
            receipt=collect(env("coverage_catalog"),"coverage_catalog")
        fetch.assert_not_called();http.assert_not_called()
        self.assertEqual(git.call_args[0][0],["git","ls-files"])
        catalog=receipt["observation"]
        self.assertEqual(receipt["route"],"coverage_catalog")
        self.assertEqual(receipt["job_id"],12)
        self.assertEqual(catalog["tracked_source_files"],4)
        self.assertEqual(catalog["tracked_test_paths"],["tests/test_core.py","web/app.test.js"])
        self.assertEqual(catalog["coverage_config_paths"],["pyproject.toml"])
        self.assertIsNone(catalog["executed_test_count"])
        self.assertIsNone(catalog["branch_coverage"])
        self.assertIn("no test execution",catalog["disclaimer"])
        self.assertNotIn("observed_check_runs",catalog)
        self.assertEqual(receipt["tests"],{})
        self.assertEqual(receipt["coverage"],{})
        self.assertEqual(receipt["merge_admission"],"HOLD")

    def test_receiver_main_success_then_controlled_error(self):
        from metric_atlas import receiver
        with tempfile.TemporaryDirectory() as work:
            out=Path(work)/"sub"/"receipt.json"
            with patch.object(sys,"argv",["receiver","--route","native_checks","--output",str(out)]),\
                 patch("metric_atlas.receiver.collect",return_value={"tests":{},"coverage":{}}),\
                 contextlib.redirect_stdout(io.StringIO()):receiver.main()
            self.assertEqual(json.loads(out.read_text())["tests"],{})
            out.unlink()
            with patch.object(sys,"argv",["receiver","--route","native_checks","--output",str(out)]),\
                 patch("metric_atlas.receiver.collect",side_effect=ValueError("invalid")),\
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ex:receiver.main()
            self.assertEqual(ex.exception.code,2)
            self.assertFalse(out.exists())

    def test_module_entrypoint_refuses_invalid_source_before_network(self):
        with tempfile.TemporaryDirectory() as work:
            out=Path(work)/"receipt.json"
            with patch.object(sys,"argv",["receiver","--route","native_checks","--output",str(out)]),\
                 patch.dict("os.environ",{"GITHUB_REPOSITORY":"unauthorized/other"},clear=True),\
                 patch("urllib.request.urlopen",side_effect=AssertionError("NETWORK FORBIDDEN")),\
                 warnings.catch_warnings(),contextlib.redirect_stderr(io.StringIO()):
                warnings.simplefilter("ignore",RuntimeWarning)
                with self.assertRaises(SystemExit) as ex:
                    runpy.run_module("metric_atlas.receiver",run_name="__main__")
            self.assertEqual(ex.exception.code,2)
            self.assertFalse(out.exists())

if __name__=="__main__":unittest.main()
