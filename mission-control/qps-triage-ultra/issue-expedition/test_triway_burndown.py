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
 def test_recursive_title_family_does_not_override_issue(self):
  c=sample()
  c["issues"][0]["title"]="feat(test W51-C0): producer"
  c["issues"][1]["body"]="See #1"
  c["issues"][0]["labels"]=["P0","CODE PURPLE"]
  p=m.project(c)
  parent=p["issues"][A+"#1"]["title_taxonomy"]
  child=p["issues"][A+"#2"]["title_taxonomy"]
  self.assertEqual(parent["path"],"feat/test/W51/C0")
  self.assertIn("code-purple",parent["topic_families"])
  self.assertEqual(child["family"],"UNCLASSIFIED")
  self.assertIn("feat",[x["family"] for x in child["related_families"]])
  self.assertTrue(all(x["grade"]=="UNVERIFIED_ASSOCIATION_ONLY" for x in child["related_families"]))
 def test_code_fences_ignored(self):
  self.assertEqual([r["target"] for r in m.references("~~~\nblocked by #2\n~~~\nsee #1",A)],[A+"#1"])
 def test_csv(self):
  self.assertIn("dod_checked",m.csv_view(m.project(sample())))
class ParserN2(unittest.TestCase):
 """N+2 parser: superset of master issue_rank.parse_checklist/extract_refs (reference behaviour)."""
 BODY="## Purpose\nShip it.\n## Definition of Done\n- [x] tests green\n- [ ] reviewed\n## DoV\n- [X] exact-head run\n## Steps\n1. [ ] write code\n- [~] dropped item\n- [ ] DoD: inline label wins\n```\n- [ ] inside code fence\n```\n<!-- - [ ] inside comment -->\n"
 def refs(self,text,home=B,pr=False):
  return [(r["target"],r["kind"]) for r in m.references(text,home,pr)]
 def test_sections_counts_and_basis(self):
  c=m.checklist(self.BODY);d,v,s=c["DoD"],c["DoV"],c["STEPS"]
  self.assertEqual((d["progress"]["checked"],d["progress"]["total"]),(1,3))
  self.assertEqual((v["progress"]["checked"],v["progress"]["total"]),(1,1))
  self.assertEqual((s["progress"]["total"],s["progress"]["withdrawn"]),(1,1))
  self.assertEqual([x["basis"] for x in d["items"]],["EXPLICIT_HEADING","EXPLICIT_HEADING","INLINE_LABEL"])
  self.assertTrue(d["heading_seen"] and v["heading_seen"])
  self.assertIsNone(c["OTHER"]["progress"])
 def test_synonyms_bold_numbered_plus(self):
  c=m.checklist("**Done when**\n+ [x] a\n2) [ ] b\n## Verification\n> - [x] c\n## Execution steps\n- [ ] d")
  self.assertEqual((c["DoD"]["progress"]["checked"],c["DoD"]["progress"]["total"]),(1,2))
  self.assertEqual(c["DoD"]["items"][0]["basis"],"SYNONYM_HEADING")
  self.assertEqual(c["DoV"]["progress"]["total"],1);self.assertEqual(c["STEPS"]["progress"]["total"],1)
 def test_untracked_criteria_are_never_done(self):
  c=m.checklist("## Done when\n- CI green\n- owner signs\n## Acceptance\nThe canary is recorded\nand closed.\n\nRelated: #4\n## Notes\n- not a criterion")
  self.assertIsNone(c["DoD"]["progress"]);self.assertEqual(c["DoD"]["untracked"],3)
  self.assertEqual([x["form"] for x in c["DoD"]["declared"]],["BULLET","BULLET","PROSE"])
  self.assertEqual(c["OTHER"]["untracked"],0)
 def test_struck_item_withdrawn(self):
  c=m.checklist("## DoD\n- [ ] ~~old scope~~\n- [x] kept")
  self.assertEqual((c["DoD"]["progress"]["total"],c["DoD"]["progress"]["withdrawn"]),(1,1))
 def test_forms_aliases_and_chains(self):
  got=self.refs("see #5, GBOGEB/ABACUS#7, https://github.com/GBOGEB/CODEX/pull/9 and other/x#1 &#35; GitHub #3")
  self.assertEqual(sorted(t for t,_ in got),sorted([B+"#5",A+"#7","GBOGEB/CODEX#9",B+"#3"]))
  self.assertEqual(self.refs("Related: QPS parent #1920",home=A),[("GBOGEB/cryoplant-project#1920","DECLARED_PARENT_CANDIDATE")])
  self.assertEqual(sorted(t for t,_ in self.refs("ABACUS #1860/#2471 and ABACUS#1996/PR#2041")),[A+"#1860",A+"#1996",A+"#2041",A+"#2471"])
  self.assertEqual(self.refs("Mission Control PR #589",home=A)[0][0],B+"#589")
  r=m.references("blocked by #3",B)[0];self.assertEqual((r["repo"],r["number"]),(B,3))
 def test_typed_direction_and_binding(self):
  k=lambda t:self.refs(t)[0][1]
  self.assertEqual(k("Blocked by #3"),"DECLARED_BLOCKER_CANDIDATE");self.assertEqual(k("This blocks #4"),"DECLARED_BLOCKS_CANDIDATE")
  self.assertEqual(k("Superseded by #7"),"DECLARED_SUCCESSOR");self.assertEqual(k("Residuals routed to #7"),"DECLARED_SUCCESSOR")
  self.assertEqual(k("Supersedes #8"),"DECLARED_PREDECESSOR");self.assertEqual(k("successor of #9"),"DECLARED_PREDECESSOR")
  self.assertEqual(k("Parent: #6"),"DECLARED_PARENT_CANDIDATE");self.assertEqual(k("duplicate of #2"),"DECLARED_DUPLICATE_OF")
  self.assertEqual(k("lane (not part of #1857 hotfix)"),"TEXT_ASSOCIATION")
  self.assertEqual(self.refs("blocked by #3, #4 and #5, see #6"),[(B+"#3","DECLARED_BLOCKER_CANDIDATE"),(B+"#4","DECLARED_BLOCKER_CANDIDATE"),(B+"#5","DECLARED_BLOCKER_CANDIDATE"),(B+"#6","TEXT_ASSOCIATION")])
  self.assertEqual(self.refs("Fixes #1, #2; see #3",pr=True),[(B+"#1","PR_CLOSURE_CLAIM"),(B+"#2","PR_CLOSURE_CLAIM"),(B+"#3","PR_ASSOCIATION")])
 def test_checklist_children_live_boxes_only(self):
  r=m.references("- [x] #11 done\n- [ ] #12 open\n- [~] #13 dropped",B)
  self.assertEqual([(x["number"],x["kind"],x.get("ticked")) for x in r],[(11,"DECLARED_CHILD_CANDIDATE",True),(12,"DECLARED_CHILD_CANDIDATE",False),(13,"TEXT_ASSOCIATION",None)])
 def test_code_comments_and_zero_skipped(self):
  self.assertEqual(self.refs("`#99` and\n```\n#98\n```\n<!-- #97 -->\n#0"),[])
 def test_blocks_reversed_and_parked_in_project(self):
  c=sample();c["issues"][1]["body"]="This blocks #1\n<!-- parked-intent:v1 {\"id\":\"U12\",\"sessions\":[]} -->"
  p=m.project(c);self.assertEqual(p["issues"][A+"#1"]["blocker_candidates"],1)  # both sides declare one pair;self.assertEqual(p["issues"][A+"#2"]["dependent_candidates"],1)
  self.assertEqual(p["issues"][A+"#2"]["parked_intent"]["id"],"U12");self.assertIsNone(p["issues"][A+"#1"]["parked_intent"])
  self.assertEqual(m.parked_intent("<!-- parked-intent:v1 {bad json} -->")["valid"],False)
 def test_wrapped_criteria_not_double_counted(self):
  c=m.checklist("## DoD\n- [ ] Implement foo\n  with native test\n- Deploy to staging\n  and run smoke tests")
  self.assertEqual(c["DoD"]["progress"]["total"],1)
  self.assertEqual(c["DoD"]["untracked"],1)
  self.assertIn("native test",c["DoD"]["items"][0]["text"])
  self.assertIn("smoke tests",c["DoD"]["declared"][0]["text"])
 def test_fence_length_alias_join_and_negated_closure(self):
  self.assertEqual(self.refs("````\n#99\n```\n#98\n````\nsee #1"),[(B+"#1","TEXT_ASSOCIATION")])
  self.assertEqual(self.refs("blocked by ABACUS #1 and CODEX #2"),
      [(A+"#1","DECLARED_BLOCKER_CANDIDATE"),("GBOGEB/CODEX#2","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("Does not fix #12",pr=True),[(B+"#12","PR_ASSOCIATION")])
  self.assertEqual(self.refs("Close #13",pr=True),[(B+"#13","PR_CLOSURE_CLAIM")])
 def test_nested_parked_intent(self):
  mark='<!-- parked-intent:v1 {"id":"U12","sessions":[{"id":"S1"}]} -->'
  self.assertEqual(m.parked_intent(mark)["id"],"U12")
  self.assertTrue(m.parked_intent(mark)["valid"])
 def test_codex_p2_fixes(self):
  self.assertEqual(self.refs("> ```\n> blocked by #2\n> ```\nsee #1"),[(B+"#1","TEXT_ASSOCIATION")])
  self.assertIsNone(m.checklist("> ```\n> - [ ] quoted example\n> ```")["OTHER"]["progress"])
  self.assertEqual(self.refs("example: ``blocked by #3`` and ```x `#4` y```, see #5"),[(B+"#5","TEXT_ASSOCIATION")])
  c=sample();c["issues"][0]["body"]="";c["issues"][1]["body"]="This blocks #1"
  self.assertEqual(m.project(c)["metrics"]["candidate_dependency_links_in_scope"],1)
 def test_withdrawn_items_declare_nothing(self):
  got=self.refs("- [~] depends on #15\n- [-] blocks #17\n- [~] superseded by #18\n- [ ] ~~depends on #19~~",home=A)
  self.assertEqual({k for _,k in got},{"TEXT_ASSOCIATION"})
  self.assertEqual(self.refs("- [-] closes #16",home=A,pr=True),[(A+"#16","PR_ASSOCIATION")])
 def test_multiline_inline_code_never_declares_edges(self):
  self.assertEqual(self.refs("`blocked by #3\\nand #4` See #5"),[(B+"#5","TEXT_ASSOCIATION")])
 def test_negation_and_relation_scoped_to_current_clause(self):
  self.assertEqual(self.refs("Not urgent. Blocked by #2"),[(B+"#2","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("This blocks nothing. See #2"),[(B+"#2","TEXT_ASSOCIATION")])
  self.assertEqual(self.refs("Does not fix #12",pr=True),[(B+"#12","PR_ASSOCIATION")])
 def test_alias_relation_does_not_leak_across_sentence(self):
  self.assertEqual(self.refs("blocked by ABACUS #1. See CODEX #2"),[(A+"#1","DECLARED_BLOCKER_CANDIDATE"),("GBOGEB/CODEX#2","TEXT_ASSOCIATION")])
 def test_n5_sentence_final_abbreviation_does_not_carry_relation(self):
  self.assertEqual(self.refs("Blocked by old rollout, etc. See #3"),[(B+"#3","TEXT_ASSOCIATION")])
  self.assertEqual(self.refs("Fixes old bug, etc. See #12",pr=True),[(B+"#12","PR_ASSOCIATION")])
  self.assertEqual(self.refs("Blocked by e.g. rollout in #3"),[(B+"#3","DECLARED_BLOCKER_CANDIDATE")])
 def test_n5_dotted_versions_nearest_closure_and_direction(self):
  self.assertEqual(self.refs("Blocked by v2.0 work in #2"),[(B+"#2","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("Blocked by e.g. rollout in #3"),[(B+"#3","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("Does not fix old behavior, but closes #12",pr=True),[(B+"#12","PR_CLOSURE_CLAIM")])
  self.assertEqual(self.refs("Fix old behavior, but does not close #12",pr=True),[(B+"#12","PR_ASSOCIATION")])
  self.assertEqual(self.refs("This depends on rollout but now blocks #2"),[(B+"#2","DECLARED_BLOCKS_CANDIDATE")])
 def test_n5_contrastive_negation_and_coordinated_closures(self):
  self.assertEqual(self.refs("Does not depend on old rollout, but now blocks #2"),[(B+"#2","DECLARED_BLOCKS_CANDIDATE")])
  self.assertEqual(self.refs("Does not close or resolve #12",pr=True),[(B+"#12","PR_ASSOCIATION")])
  self.assertEqual(self.refs("Never fixes or resolves #12",pr=True),[(B+"#12","PR_ASSOCIATION")])
  self.assertEqual(self.refs("Does not fix old behavior, but closes #12",pr=True),[(B+"#12","PR_CLOSURE_CLAIM")])
 def test_n6_contrast_scope_and_repeated_relations(self):
  self.assertEqual(self.refs("We depend on #7"),[(B+"#7","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("We do not depend on #7"),[(B+"#7","TEXT_ASSOCIATION")])
  self.assertEqual(self.refs("Does not depend on old rollout, but requires #3"),[(B+"#3","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("Requires old work, but does not depend on #3"),[(B+"#3","TEXT_ASSOCIATION")])
  self.assertEqual(self.refs("Does not depend on old rollout, however now blocks #4"),[(B+"#4","DECLARED_BLOCKS_CANDIDATE")])
  self.assertEqual(self.refs("Does not depend on old rollout, but closes #12",pr=True),[(B+"#12","PR_CLOSURE_CLAIM")])
 def test_n5_abbreviations_with_uppercase_alias(self):
  self.assertEqual(self.refs("Blocked by e.g. CODEX #3"),[("GBOGEB/CODEX#3","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("Blocked by i.e. ABACUS #3"),[(A+"#3","DECLARED_BLOCKER_CANDIDATE")])
  self.assertEqual(self.refs("Blocked by old rollout, etc. See #3"),[(B+"#3","TEXT_ASSOCIATION")])
 def test_blockquote_continuation_is_one_criterion(self):
  c=m.checklist("## DoD\n> - [ ] Implement foo\n>   with native test")
  self.assertEqual(c["DoD"]["progress"]["total"],1)
  self.assertEqual(c["DoD"]["untracked"],0)
  self.assertIn("native test",c["DoD"]["items"][0]["text"])
if __name__=="__main__":unittest.main()
