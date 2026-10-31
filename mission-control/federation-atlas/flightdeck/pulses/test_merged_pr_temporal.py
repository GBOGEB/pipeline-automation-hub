"""Controls for merged PR temporal history and fail-closed lineage."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE/"MERGED_PR_TEMPORAL_20261016.json"
SPEC=importlib.util.spec_from_file_location("merged_pr_temporal",HERE/"merged_pr_temporal.py")
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class TemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_source_and_main_vs_feature_destinations(self):
        MOD.validate(self.data)
        self.assertEqual(2,sum(e["destination_kind"]=="MAIN" for e in self.data["merge_edges"]))
        self.assertEqual(2,sum(e["destination_kind"]=="FEATURE" for e in self.data["merge_edges"]))

    def test_render_reproducibly_and_keep_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=MOD.build(SOURCE,tmp)
            b=MOD.build(SOURCE,tmp)
            self.assertEqual(a,b)
            page=(Path(tmp)/"index.html").read_text(encoding="utf-8")
            self.assertIn("UNKNOWN",page)
            self.assertIn("RECURSIVE_DOWNSTREAM_REPLAY",page)
            self.assertIn("40e3c128ccdc",page)

    def test_refuse_forged_authority(self):
        for k,v in [("merge_admission","PASS"),("security_waiver",True),
                    ("authority_transfer",True),("accepted_root_closed",4)]:
            with self.subTest(k=k):
                d=copy.deepcopy(self.data)
                d["authority"][k]=v
                with self.assertRaises(ValueError): MOD.validate(d)

    def test_refuse_duplicate_or_unqualified_merge(self):
        d=copy.deepcopy(self.data)
        d["merge_edges"].append(copy.deepcopy(d["merge_edges"][0]))
        with self.assertRaises(ValueError): MOD.validate(d)
        d=copy.deepcopy(self.data)
        d["merge_edges"][0]["post_merge_run_qualification"]="PASS"
        with self.assertRaises(ValueError): MOD.validate(d)

    def test_refuse_bad_sha_or_fake_counts(self):
        d=copy.deepcopy(self.data)
        d["merge_edges"][0]["merge_sha"]="bad"
        with self.assertRaises(ValueError): MOD.validate(d)
        d=copy.deepcopy(self.data)
        d["merge_edges"][0]["associated_runs"]["success"]=-1
        with self.assertRaises(ValueError): MOD.validate(d)


if __name__=="__main__":unittest.main()
