"""N10 typed Golden Thread successor/remaining-obligation negative contracts."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import taxonomy_successor_audit as s

HEAD="a"*40
KEY=lambda n:"GBOGEB/pipeline-automation-hub#"+str(n)


def node(n,state="OPEN",preds=("P1",),accepted=False):
    return {"key":KEY(n),"state":state,
            "predicates":[{"id":p,"owner_accepted":accepted,
                           "evidence_sha":HEAD if accepted else None} for p in preds]}


def edge(a,b,relation="SUCCESSOR_OF"):
    return {"from":KEY(a),"to":KEY(b),"relation":relation}


def cohort(items,links):
    return {"schema":s.INPUT,"repo":s.REPO,"source_head":HEAD,
            "items":items,"edges":links}


class RootSuccessor(unittest.TestCase):
    def test_closed_issue_with_unowned_predicate_is_orphan_hold(self):
        r=s.audit(cohort([node(100,"CLOSED")],[]))
        self.assertEqual(r["closed_items"],1)
        self.assertEqual(r["residual_predicates"],1)
        self.assertEqual(r["orphaned_or_ambiguous"],1)
        self.assertEqual(r["candidate_migrations"][0]["status"],"ORPHANED_ROOT_RESIDUAL")
        self.assertEqual(r["root_closure_credit"],0)

    def test_typed_open_successor_is_candidate_not_verified_acceptance(self):
        r=s.audit(cohort([node(100,"CLOSED"),node(101)], [edge(100,101)]))
        m=r["candidate_migrations"][0]
        self.assertEqual(m["status"],"OPEN_SUCCESSOR_CANDIDATE_NOT_ACCEPTED")
        self.assertEqual(m["candidate_open_successors"],[KEY(101)])
        self.assertEqual(r["orphaned_or_ambiguous"],0)
        self.assertEqual(r["formal_credit_delta"],0)

    def test_mentions_not_parent_child_or_successor_proof(self):
        for typ in ("MENTION","PARENT","RELATED"):
            with self.subTest(typ=typ):
                r=s.audit(cohort([node(100,"CLOSED"),node(101)],[edge(100,101,typ)]))
                self.assertEqual(r["candidate_migrations"][0]["status"],
                                 "ORPHANED_ROOT_RESIDUAL")

    def test_recursive_two_hop_succession_tracks_original_predicate(self):
        r=s.audit(cohort([node(100,"CLOSED"),node(101,"CLOSED"),node(102)],
                         [edge(100,101),edge(101,102)]))
        owners=r["candidate_migrations"][0]["candidate_open_successors"]
        self.assertEqual(owners,[KEY(102)])
        self.assertEqual(r["root_closure_credit"],0)

    def test_two_open_successors_ambiguous_and_not_auto_selected(self):
        r=s.audit(cohort([node(100,"CLOSED"),node(101),node(102)],
                         [edge(100,101),edge(100,102)]))
        self.assertEqual(r["candidate_migrations"][0]["status"],"AMBIGUOUS_SUCCESSOR")
        self.assertEqual(r["orphaned_or_ambiguous"],1)

    def test_closed_successor_graph_cycle_fails_hard(self):
        with self.assertRaisesRegex(ValueError,"SUCCESSOR_GRAPH_CYCLE"):
            s.audit(cohort([node(100,"CLOSED"),node(101)],[
                 edge(100,101),edge(101,100)]))
        with self.assertRaisesRegex(ValueError,"SELF_SUCCESSOR_CYCLE"):
            s.audit(cohort([node(100,"CLOSED")],[edge(100,100)]))

    def test_accepted_predicate_needs_original_source_sha(self):
        x=node(100,"CLOSED",accepted=True)
        x["predicates"][0]["evidence_sha"]=None
        with self.assertRaisesRegex(ValueError,"ACCEPTANCE_WITHOUT_SOURCE_PROOF"):
            s.audit(cohort([x],[]))
        x=node(100,"CLOSED",accepted=True)
        r=s.audit(cohort([x],[]))
        self.assertEqual(r["residual_predicates"],0)
        self.assertEqual(r["root_closure_credit"],0)

    def test_duplicate_predicate_item_and_missing_node_fail(self):
        x=node(100,"CLOSED")
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_BAD_ITEM"):
            s.audit(cohort([x,copy.deepcopy(x)],[]))
        x=node(100,"CLOSED",preds=("P1","P1"))
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_BAD_PREDICATE"):
            s.audit(cohort([x],[]))
        with self.assertRaisesRegex(ValueError,"EDGE_NOT_BOUND"):
            s.audit(cohort([node(100)],[edge(100,999)]))

    def test_no_private_repo_or_unknown_source(self):
        x=cohort([node(100)],[])
        x["repo"]="GBOGEB/cryoplant-project"
        with self.assertRaisesRegex(ValueError,"PUBLIC_SOURCE_HEAD"):
            s.audit(x)
        x=cohort([node(100)],[])
        x["source_head"]="bad"
        with self.assertRaisesRegex(ValueError,"PUBLIC_SOURCE_HEAD"):
            s.audit(x)

    def test_deterministic_no_write_cli(self):
        x=cohort([node(100,"CLOSED"),node(101)],[edge(100,101)])
        a=s.audit(x);b=s.audit(copy.deepcopy(x))
        self.assertEqual(a["receipt_sha256"],b["receipt_sha256"])
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"in.json";out=Path(d)/"out.json"
            source.write_text(json.dumps(x))
            old=source.read_bytes()
            self.assertEqual(s.main(["--in",str(source),"--out",str(out)]),0)
            self.assertEqual(source.read_bytes(),old)
            self.assertEqual(json.loads(out.read_text())["merge_admission"],"HOLD")


if __name__=="__main__":
    unittest.main()
