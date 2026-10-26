import importlib.util, pathlib, unittest, copy
p=pathlib.Path(__file__).with_name("triway_burndown.py")
s=importlib.util.spec_from_file_location("triway",p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
A="GBOGEB/ABACUS"; B="GBOGEB/pipeline-automation-hub"; T="2026-10-26T03:00:00Z"
def sample():
 def row(repo,n,created,body,priority):
  return dict(repo=repo,number=n,state="open",title=priority+" task",body=body,labels=[priority],created_at=created,updated_at=T)
 return dict(schema=m.CENSUS,observed_at=T,authority_transfer=False,formal_credit_delta=0,repositories=[A,B],source_heads={A:"a"*40,B:"b"*40},counts={A:dict(issues=2,prs=1),B:dict(issues=1,prs=0)},issues=[row(A,1,"2026-10-20T00:00:00Z","## DoD\n- [x] code\n- [ ] proof\n## DoV\n- [ ] native\nblocked by #2","P0"),row(A,2,"2026-10-21T00:00:00Z","see #1","P2"),row(B,3,"2026-10-25T00:00:00Z","see GBOGEB/ABACUS#1","P1")],pull_requests=[dict(repo=A,number=4,state="open",body="Fixes #1",head_sha="d"*40)])
class Tests(unittest.TestCase):
 def test_rank_and_progress(self):
  p=m.project(sample());n=p["issues"][A+"#1"];self.assertEqual(n["DoD"]["progress"]["checked"],1);self.assertEqual(n["DoD"]["progress"]["total"],2);self.assertIsNone(n["qualified_DoD"]);self.assertIsNone(p["issues"][A+"#2"]["DoD"]["progress"]);self.assertEqual(p["views"]["golden_oldest_first"][0],A+"#1");self.assertEqual(p["views"]["mycelium_newest_first"][0],B+"#3");self.assertEqual(p["views"]["owner_review_pressure"][0],A+"#1");self.assertEqual(n["open_pr_overlap"][0]["kind"],"PR_CLOSURE_CLAIM")
 def test_edges_unverified(self):
  p=m.project(sample());self.assertTrue(any(x["kind"]=="DECLARED_BLOCKER_CANDIDATE" for x in p["edges"]));self.assertTrue(all(not x["verified"] for x in p["edges"]))
 def test_fail_closed(self):
  for case in ["duplicate","sha","time","credit","count","closed","naive"]:
   with self.subTest(case=case):
    c=sample()
    if case=="duplicate":c["issues"].append(copy.deepcopy(c["issues"][0]));c["counts"][A]["issues"]+=1
    if case=="sha":c["source_heads"][A]="bad"
    if case=="time":c["issues"][0]["created_at"]=None
    if case=="credit":c["formal_credit_delta"]=1
    if case=="count":c["counts"][A]["issues"]+=1
    if case=="closed":c["issues"][0]["state"]="closed"
    if case=="naive":c["issues"][0]["created_at"]="2026-10-26T03:00:00"
    with self.assertRaises(ValueError):m.project(c)
 def test_deltas_are_not_closures(self):
  c=sample();a=m.project(c);self.assertEqual(a,m.project(c));d=copy.deepcopy(c);d["issues"].pop();d["counts"][B]["issues"]=0
  z=m.project(d,a)["open_identity_delta"];self.assertEqual(z["absent_from_open_not_necessarily_closed"],[B+"#3"]);self.assertIsNone(z["verified_causal_root_closure"])
 def test_code_fences_ignored(self):
  self.assertEqual([r["target"] for r in m.references("~~~\nblocked by #2\n~~~\nsee #1",A)],[A+"#1"])
 def test_csv(self):
  self.assertIn("dod_checked",m.csv_view(m.project(sample())))
if __name__=="__main__":unittest.main()
