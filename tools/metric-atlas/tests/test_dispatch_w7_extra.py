"""W7 N+1 extra negative-path tests: only existing dispatch module, no network."""
import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from metric_atlas.census import request
from metric_atlas.dispatch import DispatchError, plan

H={"ABACUS":"a"*40,"CODEX":"b"*40,"QPS_ENGINEERING":"c"*40}

class W7DispatchExtra(unittest.TestCase):
    def test_secondary_guards_fail_even_if_primary_validator_replaced(self):
        manifest=request("W7R",H)
        for field,value in (("repo","else/rogue"),("state","DISPATCHED")):
            original=manifest["requests"][0][field]
            manifest["requests"][0][field]=value
            with patch("metric_atlas.dispatch._check_manifest",side_effect=lambda x:x):
                with self.subTest(field=field),self.assertRaises(DispatchError):plan(manifest)
            manifest["requests"][0][field]=original

    def test_actual_module_entrypoint_can_never_autodispatch(self):
        with tempfile.TemporaryDirectory() as work:
            src=Path(work)/"source.json";out=Path(work)/"receipt.json"
            src.write_text(json.dumps(request("W7R",H)),encoding="utf8")
            with patch.object(sys,"argv",["dispatch","--manifest",str(src),"--output",str(out)]),\
                 patch("urllib.request.urlopen",side_effect=AssertionError("NETWORK FORBIDDEN")),\
                 warnings.catch_warnings(),\
                 contextlib.redirect_stdout(io.StringIO()):
                warnings.simplefilter("ignore",RuntimeWarning)
                runpy.run_module("metric_atlas.dispatch",run_name="__main__")
            result=json.loads(out.read_text(encoding="utf8"))
            self.assertEqual(result["triggered"],0)
            self.assertEqual({x["state"] for x in result["events"]},{"DRY_RUN_NOT_TRIGGERED"})

if __name__=="__main__":unittest.main()
