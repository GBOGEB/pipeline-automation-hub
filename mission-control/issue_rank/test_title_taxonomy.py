"""Pure contract tests: taxonomy labels, prefix lint, recursive joins, denominator safety."""
import unittest
import title_taxonomy as t

class TitleTaxonomy(unittest.TestCase):
    def test_canonical_pr_examples(self):
        f=t.classify_title("fix(jade devops): census fails closed when blobs are missing", item_type="PullRequest")
        self.assertEqual((f["action_type"],f["scope"]),("fix","jade-devops"))
        self.assertEqual(f["primary_family"],"jade-devops")
        self.assertIn("fail-closed",f["clusters"])
        self.assertIn("census",f["clusters"])
        self.assertEqual(f["composite"],"fix/jade-devops/jade-devops/census")

    def test_prefix_variants(self):
        self.assertEqual(t.classify_title("doc(handover): map")["action_type"],"docs")
        self.assertEqual(t.classify_title("ci(p-proces): proof")["scope"],"p-process")
        self.assertEqual(t.classify_title("feat(gogreen): native watch")["scope"],"gogreen")
        self.assertEqual(t.classify_title("fix(watch): payload")["scope"],"watch")
        self.assertEqual(t.classify_title("feat(jade devops): census")["scope"],"jade-devops")

    def test_legacy_preserves_identifier(self):
        f=t.classify_title("[U5] DevOps census N12: read all repos")
        self.assertEqual(f["action_type"],"unclassified")
        self.assertEqual(f["bracket_ids"],["U5"])
        self.assertIn("N12",f["waves"])
        self.assertIn("census",f["clusters"])

    def test_no_false_prefix_or_ci_fragment(self):
        f=t.classify_title("W305-A1: specific requirements")
        self.assertEqual(f["action_type"],"unclassified")
        self.assertNotIn("ci",f["clusters"])

    def test_security_and_multi_membership(self):
        f=t.classify_title("fix(watch): signed payload and outbox integrity hard gates")
        self.assertIn("integrity",f["clusters"])
        self.assertIn("watch",f["families"])

    def test_recursive_parent_chain_and_cycle(self):
        def item(k,title):
            return {"key":k,"type":"Issue","taxonomy":t.classify_title(title)}
        items=[item("r#1","feat(gogreen): root"),item("r#2","Uncategorized child"),
               item("r#3","Uncategorized grandchild")]
        edges=[{"source":"r#1","target":"r#2","kind":"CHILD"},
               {"source":"r#2","target":"r#3","kind":"CHILD"},
               {"source":"r#3","target":"r#1","kind":"CHILD"}]
        t.inherit_parent_families(items,edges)
        self.assertEqual(items[2]["taxonomy"]["primary_family"],"gogreen")
        self.assertEqual(items[2]["taxonomy"]["action_type"],"unclassified")

    def test_conflicting_parents_fail_closed(self):
        items=[{"key":str(i),"type":"Issue","taxonomy":t.classify_title(title)}
               for i,title in enumerate(["feat(watch): one","fix(gogreen): two","child"])]
        edges=[{"source":"0","target":"2","kind":"CHILD"},
               {"source":"1","target":"2","kind":"CHILD"}]
        t.inherit_parent_families(items,edges)
        self.assertEqual(items[2]["taxonomy"]["primary_family"],"unclassified")
        self.assertIn("ambiguous-parent-family",items[2]["taxonomy"]["lint"])

    def test_memberships_not_additive(self):
        items=[{"type":"Issue","taxonomy":t.classify_title("fix(gogreen): watch telemetry")},
               {"type":"PullRequest","taxonomy":t.classify_title("docs(handover): report")}]
        r=t.rollup(items)
        self.assertEqual(r["denominator"],2)
        self.assertEqual(sum(r["type_counts"].values()),2)
        self.assertTrue(r["multi_label_counts_are_not_additive"])
        self.assertEqual(r["typed_prefix_rate"],1.0)

    def test_no_parent_inference_across_mentions(self):
        items=[{"key":"a","type":"Issue","taxonomy":t.classify_title("feat(watch): root")},
               {"key":"b","type":"Issue","taxonomy":t.classify_title("unclassified")}]
        t.inherit_parent_families(items,[{"source":"a","target":"b","kind":"MENTION"}])
        self.assertEqual(items[1]["taxonomy"]["primary_family"],"unclassified")

if __name__=="__main__":
    unittest.main()
