"""N2 adversarial regressions against source-owned LDAB and canonical DAG."""
import unittest
import ldab_guard as lg
import ldab_dag_sipoc as dag
from test_ldab_guard import row, jobs, RUN_ID
from test_ldab_dag_sipoc import samples


class NewAdversarialTests(unittest.TestCase):
    def test_successful_job_with_failed_step_is_not_green(self):
        j = row(conclusion="success")
        j["steps"][1]["conclusion"] = "failure"
        r = lg.assess_jobs(jobs([j]), "LDAB", RUN_ID)
        self.assertFalse(r["terminal_success_with_steps"],
                         "masked step failure must not count as clean native proof")
        self.assertEqual(len(r["ldab_step_manifestations"]), 1)

    def test_graph_repo_to_stage_edge_is_rejected(self):
        graph, evidence = samples()
        graph["edges"][0]["source"] = "REPO_0"
        with self.assertRaisesRegex(ValueError, "typed edge endpoint"):
            dag.build(graph, evidence)

    def test_graph_cross_kind_beam_edge_is_rejected(self):
        graph, evidence = samples()
        graph["edges"][39]["target"] = "STAGE_0"
        with self.assertRaisesRegex(ValueError, "typed edge endpoint"):
            dag.build(graph, evidence)

    def test_duplicate_typed_edge_rejected(self):
        graph, evidence = samples()
        graph["edges"][1] = dict(graph["edges"][0])
        with self.assertRaisesRegex(ValueError, "duplicate typed edge"):
            dag.build(graph, evidence)

    def test_edge_type_census_rejected(self):
        graph, evidence = samples()
        graph["edges"][38]["kind"] = "FEEDBACK"
        graph["edges"][38]["temporal"] = "NEXT_PULSE"
        with self.assertRaisesRegex(ValueError, "edge-type census"):
            dag.build(graph, evidence)

    def test_disconnected_stage_chain_rejected(self):
        graph, evidence = samples()
        graph["edges"][20]["source"] = "STAGE_19"
        with self.assertRaisesRegex(ValueError, "process chain degree"):
            dag.build(graph, evidence)


if __name__ == "__main__":
    unittest.main()
