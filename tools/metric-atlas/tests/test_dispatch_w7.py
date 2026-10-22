"""W7 DISPATCH disjoint native negative / reverse TestFlight. No live network."""
import copy
import itertools
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from metric_atlas.census import ALLOWED_REPOS, request
from metric_atlas.dispatch import DispatchError, dispatch, plan

H = {lane: format(i+1, "x")*40 for i, lane in enumerate(ALLOWED_REPOS)}
ENV = {"GITHUB_REPOSITORY":"GBOGEB/pipeline-automation-hub",
       "GITHUB_REF":"refs/heads/master", "GITHUB_EVENT_NAME":"workflow_dispatch",
       "QPS_DISPATCH_APPROVED":"YES", "QPS_TRIAGE_DISPATCH_TOKEN":"t"*40}

class W7DispatchNative(unittest.TestCase):
    def setUp(self): self.m = request("W7", H)

    def test_72_matrix_preserves_three_lane_conservation(self):
        n=0
        for avail in itertools.product((False, True),repeat=3):
            for cap in (1,2,3):
                for selector in ("all","native_checks","coverage_catalog"):
                    heads={lane:(H[lane] if yes else None) for lane,yes in zip(ALLOWED_REPOS,avail)}
                    m=request("W7X",heads,max_fanout=cap,selector=selector)
                    with self.subTest(avail=avail,cap=cap,selector=selector):
                        self.assertEqual(len(plan(m)),min(cap,sum(avail)))
                        self.assertEqual(len(plan(m))+len(m["not_dispatched"]),3)
                        self.assertEqual(dispatch(m)["triggered"],0)
                    n+=1
        self.assertEqual(n,72)

    def test_forged_manifest_and_authority_never_touch_network(self):
        changes=("request_id","expected_sha","selector","wave","dispatch_enabled",
                 "authority_transfer","engineering_acceptance","max_fanout",
                 "not_dispatched","eligible_repos","state","foreign_repo")
        for key in changes:
            m=copy.deepcopy(self.m); q=m["requests"][0]
            if key=="request_id": q[key]="QPS-"+"f"*20
            elif key=="expected_sha": q[key]="f"*40
            elif key=="selector": q[key]="native_checks"
            elif key=="wave": q[key]="W7-FOREIGN"
            elif key in ("dispatch_enabled","authority_transfer","engineering_acceptance"): m[key]=True
            elif key=="max_fanout": m[key]=True
            elif key=="not_dispatched": m.pop(key)
            elif key=="eligible_repos": m[key]=1
            elif key=="state": q[key]="DISPATCHED"
            elif key=="foreign_repo": q["repo"]="else/foreign"
            spy=Mock(side_effect=AssertionError("NETWORK FORBIDDEN"))
            with self.subTest(key=key),self.assertRaises(DispatchError):
                dispatch(m,execute=True,environment=ENV,opener=spy)
            spy.assert_not_called()

    def test_bad_manifest_shapes_fail_controlled(self):
        for m in (None,[],{},{"schema":"foreign"}):
            with self.subTest(m=m),self.assertRaises(DispatchError): plan(m)

    def test_no_credential_or_unapproved_ref(self):
        for field,val in (("GITHUB_REF","refs/heads/feature"),("QPS_DISPATCH_APPROVED","NO"),
                          ("QPS_TRIAGE_DISPATCH_TOKEN","short")):
            env=dict(ENV);env[field]=val
            spy=Mock(side_effect=AssertionError("network"))
            with self.subTest(field=field),self.assertRaises(DispatchError):
                dispatch(self.m,execute=True,environment=env,opener=spy)
            spy.assert_not_called()

    def test_204_enqueues_but_is_never_native_receipt(self):
        class OK:
            status=204
            def __enter__(self): return self
            def __exit__(self,*args): return False
        urls=[]
        def post(req,timeout):
            urls.append(req.full_url);self.assertEqual(timeout,20)
            self.assertEqual(req.get_method(),"POST")
            self.assertEqual(json.loads(req.data)["event_type"],"qps-metric-census-v1")
            return OK()
        proof=dispatch(self.m,execute=True,environment=ENV,opener=post)
        self.assertEqual(len(set(urls)),3)
        self.assertEqual(proof["triggered"],3)
        self.assertIsNone(proof["receiver_job_ids"])
        self.assertIsNone(proof["receiver_results"])

    def test_negative_http_and_cli_invalid_source(self):
        class BAD:
            status=202
            def __enter__(self): return self
            def __exit__(self,*args): return False
        with self.assertRaisesRegex(DispatchError,"204"):
            dispatch(self.m,execute=True,environment=ENV,opener=lambda *a,**k:BAD())
        from metric_atlas import dispatch as module
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"src.json";out=Path(d)/"receipt.json"
            src.write_text(json.dumps(self.m))
            with patch.object(sys,"argv",["dispatch","--manifest",str(src),"--output",str(out)]):
                module.main()
            self.assertEqual(json.loads(out.read_text())["triggered"],0)
            m=copy.deepcopy(self.m);m["requests"][0]["request_id"]="QPS-"+"0"*20
            src.write_text(json.dumps(m));out.unlink()
            with patch.object(sys,"argv",["dispatch","--manifest",str(src),"--output",str(out)]):
                with self.assertRaises(SystemExit) as ex:module.main()
            self.assertEqual(ex.exception.code,2)
            self.assertFalse(out.exists())

    def test_layer_two_guard_rejects_invalid_even_when_producer_is_replaced(self):
        from metric_atlas import dispatch as module
        cases=[]
        for field,val in (("mode","EXECUTE"),("requests",None)):
            m=copy.deepcopy(self.m);m[field]=val;cases.append(m)
        m=copy.deepcopy(self.m);m["requests"][1]["repo"]=m["requests"][0]["repo"];cases.append(m)
        with patch.object(module,"_check_manifest",side_effect=lambda m:m):
            for m in cases:
                with self.subTest(m=str(m)[:100]),self.assertRaises(DispatchError):module.plan(m)

if __name__=="__main__":unittest.main()
