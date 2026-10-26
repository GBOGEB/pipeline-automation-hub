"""Title taxonomy tests: parser, recursive associations, rollup and privacy."""
from __future__ import annotations

import copy
import unittest
import title_taxonomy as tax
import issue_rank as ir
import test_issue_rank as base

HUB = "GBOGEB/pipeline-automation-hub"
QPS = "GBOGEB/cryoplant-project"


class TitleParsing(unittest.TestCase):
    def test_conventional_metrics_and_nested_prefixes(self):
        m = tax.parse_title("metrics: refresh DMAIC commit metrics", "PullRequest")
        self.assertEqual((m["family"], m["path"]), ("metrics", "metrics"))
        f = tax.parse_title("feat(test W51-C0): zero-to-positive coverage", "PullRequest")
        self.assertEqual((f["family"], f["path"], f["codes"]), ("feat", "feat/test/W51/C0", ["W51", "C0"]))
        n = tax.parse_title("metrics: fix(test W51-C0): example")
        self.assertEqual(n["path"], "metrics/fix/test/W51/C0")
        r = tax.parse_title("feat(test(fix) W51-C0): nested")
        self.assertEqual(r["path"], "feat/test/fix/W51/C0")
        self.assertEqual(r["prefix_segments"][2]["depth"], 2)

    def test_markdown_heading_qualifier_chains(self):
        self.assertEqual(tax.parse_title("metrics: #### ###(fix) refresh metrics")["path"],
                         "metrics/fix")
        self.assertEqual(tax.parse_title("metrics: ###(fix(test W51-C0)) repair")["path"],
                         "metrics/fix/test/W51/C0")
        self.assertEqual(tax.parse_title("metrics: (draft) ordinary prose")["path"],
                         "metrics")
        self.assertEqual(tax.parse_title("metrics: #123 reference")["path"],
                         "metrics")
        self.assertEqual(tax.parse_title("feat(jade N+4 W51-C0): pulse")["path"],
                         "feat/JADE/N+4/W51/C0")
    def test_issue_brackets_waves_and_safety(self):
        i = tax.parse_title("[U14] Main red since 2026-10-18: import networkx")
        self.assertEqual(i["path"], "UNCLASSIFIED/U14")
        p = tax.parse_title("P0 CBS N+4: stacked-base 403")
        self.assertEqual(p["priority"], "P0")
        self.assertIn("N+4", p["codes"])
        c = tax.parse_title("W369b: LOOP boil-off")
        self.assertIn("W369B", c["codes"])
        hold = tax.parse_title("⛔ DO NOT MERGE — MACH-II red canary")
        self.assertEqual(hold["policy_flags"], ["DO_NOT_MERGE"])
        self.assertEqual(hold["path"], "UNCLASSIFIED/MACH-II")

    def test_programme_and_concatenated_scope(self):
        self.assertEqual(tax.parse_title("CODE PURPLE: evidence reuse")["path"],
                         "UNCLASSIFIED/CODE_PURPLE")
        self.assertEqual(tax.parse_title("MIP-STABILIZE — BD convergence")["path"],
                         "UNCLASSIFIED/MIP/stabilize")
        self.assertEqual(tax.parse_title("fix(jade devops): fail closed")["path"],
                         "fix/JADE/DEVOPS")
        self.assertEqual(tax.parse_title("chore(deps-pip): patch")["path"],
                         "chore/deps/pip")
        self.assertEqual(tax.parse_title("feat(mc G3A N13–N15): pulse")["path"],
                         "feat/MC/G3A/N13-N15")
        self.assertEqual(tax.parse_title("QPS BNB N+4 R01 — source binding")["path"],
                         "UNCLASSIFIED/QPS/BNB/N+4/R01")

    def test_no_body_inference_and_malformed(self):
        self.assertEqual(tax.parse_title("Repair e.g. fix failing tests")["family"],
                         "UNCLASSIFIED")
        self.assertIn("UNBALANCED_CONVENTIONAL_SCOPE",
                      tax.parse_title("feat(test(W51-C0): broken")["lint"])
        self.assertEqual(tax.parse_title("DO NOT MERGE — unsafe code")["policy_flags"],
                         ["DO_NOT_MERGE"])
        self.assertEqual(tax.parse_title("###(fix) something")["family"], "fix")

    def test_family_is_disjoint_hierarchy_is_not(self):
        titles = ["feat(test W51-C0): one", "feat(test W51-C1): two",
                  "metrics: third", "[U14] fourth"]
        items = [{"type": "Issue" if n == 3 else "PullRequest", "title": title}
                 for n, title in enumerate(titles)]
        out = tax.summary(items)
        self.assertEqual(out["total"], 4)
        self.assertEqual(sum(x["total"] for x in out["family"].values()), 4)
        self.assertEqual(out["hierarchy_nodes_nonadditive"]["feat/test"]["total"], 2)
        self.assertEqual(out["leaf_clusters"]["feat/test/W51/C0"]["total"], 1)
        self.assertGreater(sum(x["total"] for x in out["hierarchy_nodes_nonadditive"].values()), 4)


    def test_semantic_topic_cluster_and_word_boundaries(self):
        obj = tax.parse_title("fix(watch): signed payload and outbox integrity hard gates",
                              "PullRequest", ["CODE PURPLE"])
        self.assertEqual(obj["family"], "fix")
        self.assertIn("watch", obj["topic_families"])
        self.assertIn("code-purple", obj["topic_families"])
        self.assertIn("integrity", obj["technical_clusters"])
        failed = tax.parse_title("fix(jade devops): census fails closed when blobs are missing")
        self.assertIn("fail-closed", failed["technical_clusters"])
        self.assertIn("census", failed["technical_clusters"])
        false_positive = tax.parse_title("docs: specific requirements", "Issue")
        self.assertNotIn("ci", false_positive["technical_clusters"])
        self.assertEqual(false_positive["path"], "docs")

    def test_nonexclusive_semantic_counts_do_not_inflate_items(self):
        items = [{"type": "Issue", "title": "fix(watch): signed payload and outbox"},
                 {"type": "PullRequest", "title": "feat(jade devops): census with coverage"},
                 {"type": "Issue", "title": "[U14] CODE PURPLE: security checks"}]
        result = tax.summary(items)
        self.assertEqual(result["total"], 3)
        self.assertEqual(sum(c["total"] for c in result["family"].values()), 3)
        self.assertIn("integrity", result["technical_clusters_nonexclusive"])
        self.assertIn("code-purple", result["topic_families_nonexclusive"])
        self.assertFalse(result["hierarchy_nodes_additive"])

    def test_candidates_are_unverified_and_cycle_safe(self):
        items = [
            {"key": "a", "type": "Issue", "title": "[U1] task"},
            {"key": "b", "type": "PullRequest", "title": "fix(test W51-C0): repair"},
            {"key": "c", "type": "Issue", "title": "docs: finish"},
        ]
        edges = [{"source": "a", "target": "b", "kind": "CLOSES"},
                 {"source": "b", "target": "c", "kind": "MENTION"},
                 {"source": "c", "target": "a", "kind": "XREF"}]
        c = tax.associated_families(items, edges)
        self.assertEqual([x["family"] for x in c["a"]], ["docs", "fix"])
        self.assertTrue(all(x["grade"] == "UNVERIFIED_ASSOCIATION_ONLY" for x in c["a"]))
        self.assertEqual(tax.parse_title(items[0]["title"])["family"], "UNCLASSIFIED")
        with self.assertRaises(ValueError):
            tax.associated_families(items, edges, max_hops=8)


class Integration(unittest.TestCase):
    def changed(self):
        s = base.fixture()
        s["repos"][HUB]["prs"][0]["title"] = "feat(test W51-C0): replay"
        s["repos"][HUB]["issues"][0]["title"] = "[U14] parent"
        s["repos"][QPS]["issues"][0]["title"] = "metrics(secret-supplier): private"
        return s

    def test_rank_per_repo_ja_de_and_user(self):
        out = ir.rank(self.changed())
        self.assertEqual(out["rollups"]["USER"]["title_taxonomy"]["schema"], tax.SCHEMA)
        kinds = out["rollups"][HUB]["title_taxonomy"]
        self.assertEqual(sum(r["total"] for r in kinds["family"].values()), kinds["total"])
        self.assertIn("feat/test/W51/C0", kinds["leaf_clusters"])
        self.assertIn("title_taxonomy", out["items"][0])
        self.assertIn("related_families", out["items"][0]["title_taxonomy"])
        self.assertIn("family", ir.to_csv(out).splitlines()[0])
        self.assertIn("Title family census", ir.render_html(out))

    def test_private_redaction_excludes_facet_leak(self):
        out = ir.rank(self.changed())
        redacted = ir.redact(out)
        self.assertEqual(redacted["rollups"][QPS]["title_taxonomy"]["total"], 0)
        self.assertGreater(redacted["rollups"][QPS]["title_taxonomy"]["private_items_excluded"], 0)
        self.assertNotIn("secret-supplier", str(redacted["rollups"]))
        self.assertEqual(redacted["rollups"][QPS]["title_taxonomy"]["topic_families_nonexclusive"], {})
        self.assertEqual(redacted["rollups"][QPS]["title_taxonomy"]["technical_clusters_nonexclusive"], {})
        for i in redacted["items"]:
            if i.get("private"):
                self.assertEqual(i["title_taxonomy"]["family"], "REDACTED_PRIVATE")
            else:
                self.assertTrue(all(not item["source_item"].startswith(QPS + "#")
                                    for item in i["title_taxonomy"]["related_families"]))

    def test_taxonomy_delta_does_not_promote_credit(self):
        s = self.changed()
        old = ir.rank(s)
        newer = copy.deepcopy(s)
        newer["repos"][HUB]["prs"][0]["title"] = "fix(jade): explicit repair"
        current = ir.rank(newer)
        delta = ir.diff(old, current)
        self.assertTrue(delta["taxonomy_moves"])
        self.assertFalse(current["authority"]["closure_authorized"])


if __name__ == "__main__":
    unittest.main()
