"""W5 source-bound lossless handover invariants; strictly read-only."""
import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CENSUS = json.loads((HERE/"W5_CENSUS_TELEMETRY_20261018.json").read_text(encoding="utf-8"))
GRAPH = json.loads((HERE/"W5_FEDERATION_DAG_20261018.json").read_text(encoding="utf-8"))
SHA = re.compile(r"^[a-f0-9]{40}$")

class W5HandoverTests(unittest.TestCase):
    def test_uses_existing_owner_authority(self):
        self.assertEqual(CENSUS["canonical"]["bd_register"],"mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json")
        self.assertEqual(GRAPH["role"],"READ_ONLY_PROJECTION_NOT_MASTER_DAGS")
        self.assertEqual(CENSUS["privacy_and_controls"]["merge_admission"],"HOLD")
        self.assertFalse(CENSUS["privacy_and_controls"]["authority_transfer"])

    def test_exact_public_shas_not_private(self):
        rows=CENSUS["public_repositories"]
        self.assertEqual(len(rows),4)
        self.assertEqual(len({r["repo"] for r in rows}),4)
        self.assertTrue(all(SHA.fullmatch(r["sha"]) and r["collection_complete"] for r in rows))
        self.assertNotIn("cryoplant-project",(HERE/"W5_CENSUS_TELEMETRY_20261018.json").read_text(encoding="utf-8"))
        self.assertIsNone(CENSUS["restricted_qps"]["private_sha"])
        self.assertIsNone(CENSUS["restricted_qps"]["private_issue_count"])

    def test_no_issue_pr_or_bd_denominator_mix(self):
        rows=CENSUS["public_repositories"]
        self.assertEqual(sum(r["issues"] for r in rows),83)
        self.assertEqual(sum(r["prs"] for r in rows),17)
        self.assertEqual((CENSUS["change_vs_W4"]["issues"],CENSUS["change_vs_W4"]["prs"]),(1,-6))
        cpq=CENSUS["canonical_CPQ"]
        self.assertEqual(cpq["item_count"],19)
        self.assertEqual(sum(cpq["states"].values()),19)
        self.assertEqual(cpq["states"]["DONE"],10)
        self.assertIsNone(cpq["current_engineering_root_closures_accepted"])

    def test_runs_terminal_vs_censored(self):
        rows=CENSUS["public_repositories"]
        for r in rows:
            self.assertEqual(sum(r["statuses"].values()),r["run_count"])
        d=CENSUS["public_total"]
        self.assertEqual(d["run_count"],90)
        self.assertEqual(d["terminal"],d["success"]+d["failure"]+d["skipped"])
        self.assertEqual(d["run_count"],d["terminal"]+d["nonterminal"])
        self.assertEqual((d["success"],d["failure"],d["skipped"],d["nonterminal"]),(35,4,4,47))
        self.assertAlmostEqual(d["terminality_pct"],100*d["terminal"]/d["run_count"],places=2)

    def test_abacus_current_b0_is_not_qualified(self):
        a=CENSUS["abacus_exact_current_head_jobs"]
        self.assertEqual(a["b0"]["head"],CENSUS["public_repositories"][0]["sha"])
        self.assertIsNone(a["b0"]["run_conclusion"])
        self.assertEqual(a["b0"]["job_statuses"]["success"],12)
        self.assertEqual(a["b0"]["job_statuses"]["queued"],1)
        self.assertEqual(sum(a["matrix"]["job_statuses"].values()),6)

    def test_queue_conservation_and_no_fake_eta(self):
        v=CENSUS["queue_pressure"]
        self.assertEqual(v["arrival_delta"]-v["terminal_delta"],v["nonterminal_delta"])
        self.assertEqual(v["nonterminal_delta"],16)
        self.assertTrue(v["ABACUS_later_same_head"]["nonterminal"]>v["ABACUS_early_same_head"]["nonterminal"])

    def test_source_first_reds_not_root_ids(self):
        reds=CENSUS["first_red_occurrences"]
        self.assertEqual(len(reds),4)
        self.assertEqual(len({(x["owner"],x["run"]) for x in reds}),4)
        self.assertTrue(all(x["job"]>0 and x["step"] for x in reds))

    def test_absent_coverage_stays_null(self):
        cov=CENSUS["coverage"]
        for name in ("current_main_statement","current_main_branch","current_pr_broad","current_pr_diff"):
            self.assertIsNone(cov[name])
        self.assertIsNone(CENSUS["evidence_penetration"]["accepted_rex"])
        self.assertIsNone(CENSUS["evidence_penetration"]["authenticated_remote_crew_runs"])

    def test_governance_not_inferred(self):
        a=CENSUS["governance"]["ABACUS"]
        self.assertEqual(a["required_approvals"],0)
        self.assertFalse(a["last_push_approval"])
        self.assertFalse(a["review_threads"])
        self.assertEqual(GRAPH["merge_admission"],"HOLD")
        self.assertFalse(GRAPH["security_waiver"])
        self.assertFalse(GRAPH["authority_transfer"])

    def test_graph_nodes_edges_distinct_and_sipoc(self):
        nodes=GRAPH["nodes"]
        edges=GRAPH["edges"]
        ids={n["id"] for n in nodes}
        self.assertEqual((len(nodes),len(ids),len(edges)),(25,25,33))
        self.assertEqual(GRAPH["metrics"]["required_dependency_edges"],22)
        self.assertEqual(len(GRAPH["sipoc"]),5)
        self.assertTrue(all(e["from"] in ids and e["to"] in ids for e in edges))
        self.assertTrue(all(n["url"].startswith("https://github.com/GBOGEB/") for n in nodes))

    def test_dependency_topological_sort_and_no_worker_simulation(self):
        graph={x["id"]:[] for x in GRAPH["nodes"]}
        indeg={n:0 for n in graph}
        for e in GRAPH["edges"]:
            if e["edge_type"]=="requires":
                graph[e["from"]].append(e["to"])
                indeg[e["to"]]+=1
                self.assertEqual(e["binding"],"REQUIRED_NOT_EXECUTED")
        unseen=set(graph)
        layers=[]
        while unseen:
            ready=sorted(n for n in unseen if indeg[n]==0)
            self.assertTrue(ready,"cycle in required edges")
            layers.append(ready)
            for node in ready:
                unseen.remove(node)
                for other in graph[node]:
                    indeg[other]-=1
        self.assertEqual(layers,GRAPH["scheduler_projection"]["topological_layers"])
        self.assertEqual(len(layers),4)
        self.assertIsNone(GRAPH["metrics"]["observed_authenticated_remote_dispatches"])
        self.assertIsNone(GRAPH["metrics"]["accepted_rex"])

    def test_task_checklists_are_unpromoted(self):
        issues={q["repo"]:q for q in CENSUS["current_issues"]}
        self.assertEqual((issues["GBOGEB/ABACUS"]["checked"],issues["GBOGEB/ABACUS"]["total"]),(1,12))
        self.assertEqual((issues["GBOGEB/CODEX"]["checked"],issues["GBOGEB/CODEX"]["total"]),(0,7))

if __name__=="__main__":
    unittest.main()
