"""Fail-closed browser contract tests; no browser or network needed."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("cpq_browser_check", HERE / "cpq_browser_check.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

class CensusContracts(unittest.TestCase):
    def report(self):
        return {"schema":"missioncontrol.code_purple.cpq_convergence_n5.v1",
                "admission":"HOLD","formal_credit_delta":0,
                "metrics":{"open":10,"done":9,"active":2,"canonical_rows":19}}

    def test_non_nine_open_population(self):
        self.assertEqual(mod.census_counts(self.report()),
                         {"open":10,"done":9,"active":2,"canonical_rows":19})

    def test_forbid_stale_or_inconsistent_populations(self):
        for key, value in (("open",9),("done",8),("active",11),("canonical_rows",18),
                           ("open",True),("open",None),("open",-1)):
            with self.subTest(key=key,value=value):
                r=self.report();r["metrics"][key]=value
                with self.assertRaises(AssertionError):
                    mod.census_counts(r)

    def test_reject_false_admission(self):
        for k,v in (("admission","PASS"),("formal_credit_delta",1),
                    ("schema","other")):
            r=self.report();r[k]=v
            with self.assertRaises(AssertionError):
                mod.census_counts(r)

if __name__ == "__main__":
    unittest.main()
