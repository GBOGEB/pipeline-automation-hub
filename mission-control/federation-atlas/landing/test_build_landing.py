"""Source-projection, SIPOC recurrence and user-landing QA regression tests."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("build_landing",HERE/"build_landing.py")
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
SHA="a"*40


class FederationLandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,cls.hashes=MOD.input_data()

    def test_existing_authority_and_population(self):
        MOD.validate(self.data)
        d=MOD.projection(self.data,self.hashes,SHA)
        self.assertEqual(10,d["population"]["lanes"])
        self.assertEqual(39,d["population"]["stages"])
        self.assertEqual(10,d["population"]["beams"])
        self.assertEqual(13,d["population"]["edges"])
        self.assertEqual(5,d["population"]["repositories"])
        self.assertIsNone(d["admission"]["current_main_coverage"])
        self.assertEqual("HOLD",d["admission"]["merge"])

    def test_sipoc_unrolls_next_pulse_not_same_pulse_cycle(self):
        d=MOD.projection(self.data,self.hashes,SHA)
        self.assertEqual({"S","I","P","O","C"},{x["key"] for x in d["sipoc"]})
        self.assertEqual("FEEDBACK(N) -> input(N+1)",d["methodology"]["next_wave"])
        self.assertTrue(all(e["type"] in ("FEEDFORWARD","FEEDBACK")
                            for e in d["graph"]["edges"]))

    def test_historical_scopes_no_global_credit(self):
        d=MOD.projection(self.data,self.hashes,SHA)
        q=d["history"]["qps_wormhole"]
        self.assertEqual([0,1,2],[x["pulse"] for x in q])
        self.assertTrue(all(x["comparable"] for x in q))
        self.assertEqual([93,132,135],[x["line"]["covered"] for x in q])
        self.assertEqual([135,135,135],[x["line"]["eligible"] for x in q])
        c=d["history"]["c2_pr_matched_historical"]
        self.assertEqual(180,c["after"]["covered"]-c["before"]["covered"])
        self.assertIsNone(c["current_main"])
        self.assertTrue(all(x["hosted_verified"] is None for x in d["repos"]))

    def test_deterministic_html_manifest_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=MOD.produce(tmp,SHA)
            original=(Path(tmp)/"index.html").read_bytes()
            b=MOD.produce(tmp,SHA)
            self.assertEqual(a,b)
            self.assertEqual(original,(Path(tmp)/"index.html").read_bytes())
            self.assertIn(b"Recursive neighborhood",original)
            self.assertIn(b"graph-data",original)
            self.assertIn(b"HOSTED UNVERIFIED",original)
            for file,digest in a["artifact_sha256"].items():
                self.assertEqual(digest,hashlib.sha256((Path(tmp)/file).read_bytes()).hexdigest())

    def test_fail_closed_authority_and_invalid_graph(self):
        bad=copy.deepcopy(self.data)
        bad["bd"]["authority"]["security_waiver"]=True
        with self.assertRaisesRegex(ValueError,"authority"):MOD.validate(bad)
        bad=copy.deepcopy(self.data)
        bad["dag"]["edges"][0]["to"]="UNDECLARED"
        with self.assertRaisesRegex(ValueError,"invalid edge"):MOD.validate(bad)
        bad=copy.deepcopy(self.data)
        bad["dag"]["beams"].append(copy.deepcopy(bad["dag"]["beams"][0]))
        with self.assertRaisesRegex(ValueError,"duplicated beams"):MOD.validate(bad)

    def test_reject_missing_exact_sha_and_population_drift(self):
        with self.assertRaisesRegex(ValueError,"exact checkout"):
            MOD.projection(self.data,self.hashes,"short")
        bad=copy.deepcopy(self.data)
        bad["bd"]["matched_historical_coverage"]["after"]["eligible"]+=1
        with self.assertRaisesRegex(ValueError,"coverage scope"):
            MOD.projection(bad,self.hashes,SHA)

    def test_unmatched_python_versions_are_not_invented(self):
        hist=copy.deepcopy(self.data["history"]["observations"])
        rows=[r for r in hist if r.get("repo")=="GBOGEB/cryoplant-project" and r.get("pulse")==2]
        self.assertGreater(len(rows),1)
        rows[0]["line"]["eligible"]+=1
        q=MOD._qps_waves(hist)
        self.assertFalse(next(x for x in q if x["pulse"]==2)["comparable"])


if __name__=="__main__":
    unittest.main()
