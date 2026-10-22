import importlib.util, unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"scan.py"
s=importlib.util.spec_from_file_location("scan",P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
H="a"*40
def pr():return {"number":1,"title":"merged","merged_at":"2026-10-17T10:00:00Z",
 "head":{"sha":H},"merge_commit_sha":"b"*40}
def run(i=1,conclusion="success",head=H,status="completed",attempt=1):
 return {"id":i,"run_attempt":attempt,"head_sha":head,"status":status,
         "conclusion":conclusion,"name":"native"}
class Native(unittest.TestCase):
 def test_success(self):self.assertEqual(m.classify(pr(),[run()],1)["verdict"],"ALL_OBSERVED_SUCCESS")
 def test_failed(self):self.assertEqual(m.classify(pr(),[run(conclusion="failure")],1)["verdict"],"MIXED_OR_RED")
 def test_cancelled(self):self.assertEqual(m.classify(pr(),[run(conclusion="cancelled")],1)["verdict"],"MIXED_OR_RED")
 def test_pending(self):self.assertEqual(m.classify(pr(),[run(status="queued")],1)["verdict"],"PENDING")
 def test_missing(self):self.assertEqual(m.classify(pr(),[],0)["verdict"],"NO_RUN_EVIDENCE")
 def test_partial_page(self):self.assertEqual(m.classify(pr(),[run()],2)["verdict"],"INCOMPLETE_PAGE")
 def test_skipped(self):self.assertEqual(m.classify(pr(),[run(conclusion="skipped")],1)["verdict"],"PARTIAL_TERMINAL")
 def test_duplicate(self):
  with self.assertRaises(ValueError):m.classify(pr(),[run(),run()],2)
 def test_attempt_distinct(self):self.assertEqual(m.classify(pr(),[run(attempt=1),run(attempt=2)],2)["run_count"],2)
 def test_wrong_sha(self):
  with self.assertRaises(ValueError):m.classify(pr(),[run(head="c"*40)],1)
 def test_merged_not_admitted(self):self.assertFalse(m.classify(pr(),[run()],1)["required_checks_verified"])
 def test_root_unverified(self):self.assertEqual(m.classify(pr(),[run(conclusion="failure")],1)["everred_candidates"][0]["first_red"],"NOT_FETCHED")
 def test_invalid_roster(self):
  with self.assertRaises(ValueError):m.execute(["GBOGEB/X"],"not-used",1)
