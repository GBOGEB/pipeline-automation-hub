"""P-process -> MYCELIUM non-authoritative graph contract tests."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p_mycelium_bridge",P/"mycelium_bridge.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SITE=P/"site"
load=lambda path:json.loads((SITE/path).read_text(encoding="utf-8"))
SHA="a"*40

class MyceliumCandidate(unittest.TestCase):
    def setUp(self):
        self.state=load("data/p_state.json")
        self.census=load("code-purple/kit/census.json")
        self.ev=load("everred/data/everred.json")
        self.drift=load("rulesets/drift.json")
    def call(self,sha=SHA):
        return m.project(self.state,self.census,self.ev,self.drift,
                         source_sha=sha,source_digests={"state":"b"*64})
    def test_no_promotion_or_mutation(self):
        r=self.call()
        self.assertFalse(r["authority_transfer"])
        self.assertFalse(r["mutation_enabled"])
        self.assertFalse(r["dispatch_authorized"])
        self.assertEqual(r["merge_admission"],"HOLD")
        self.assertEqual(r["consumer_acceptance"],"WITHHELD")
        self.assertEqual(len(r["nodes"]),6+len(self.ev["roots"]))
        self.assertEqual(len(r["edges"]),len(self.ev["roots"]))
        # Counted from the published census, not pinned: a pulse can flip a criterion (30 Oct: L4).
        met=sum(x["ok"] is True for x in self.census["lift"])
        self.assertEqual(r["incident"]["criteria_met"],met)
        self.assertLess(met,len(self.census["lift"]),"an unlifted incident cannot meet every criterion")
    def test_root_provenance_unique(self):
        r=self.call()
        ids=[n["id"] for n in r["nodes"]]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(e["to"].startswith("repo:GBOGEB/") for e in r["edges"]))
    def test_stale_head_and_missing_repo_rejected(self):
        for head in ("short","Z"*40,None):
            with self.subTest(head=head),self.assertRaises(ValueError):
                self.call(head)
        self.state["repos"].pop("GBOGEB/CODEX")
        with self.assertRaises(ValueError):
            self.call()
    def test_forged_green_rejected(self):
        self.state["repos"]["GBOGEB/ABACUS"]["ruleset"]="GREEN"
        with self.assertRaises(ValueError):
            self.call()
    def test_duplicate_roots_rejected(self):
        self.ev["roots"].append(copy.deepcopy(self.ev["roots"][0]))
        with self.assertRaises(ValueError):
            self.call()
    def test_false_lift_rejected(self):
        self.census["lifted"]=True
        with self.assertRaises(ValueError):
            self.call()

if __name__=="__main__":unittest.main()
