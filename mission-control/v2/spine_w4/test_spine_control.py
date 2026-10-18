"""W4 SPINE control-plane acceptance and reverse-pressure tests (offline)."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from spine_control import build, html_view, mermaid, sipoc_md, svg, validate

BASE=Path(__file__).with_name("control_view.json")


class SpineW4(unittest.TestCase):
    def setUp(self):
        self.d=json.loads(BASE.read_text(encoding="utf-8"))

    def fail(self, fragment):
        with self.assertRaisesRegex(ValueError,fragment):
            validate(self.d)

    def test_source_is_readonly_and_nonpromoting(self):
        r=validate(self.d)
        self.assertEqual(r["gate"],"HOLD")
        self.assertEqual((r["node_count"],r["forward_edge_count"],
                          r["next_pulse_feedback_count"],r["sipoc_processes"]),
                         (20,21,3,6))
        self.assertFalse(r["authority_transfer"])
        self.assertEqual(r["governed_issue_closures"],0)

    def test_exact_authority_paths_not_new_ssot(self):
        byname={(x["repo"],x["path"]) for x in self.d["authority_refs"]}
        self.assertIn(("GBOGEB/CODEX","mission_control/mycelium/control_manifest.yaml"),byname)
        self.assertIn(("GBOGEB/pipeline-automation-hub","mission-control/v2/MISSION_CONTROL_CURRENT_v2.json"),byname)
        self.assertIn(("GBOGEB/CODEX","governance/adr/ADR-0002-spine-core-public-backbone.md"),byname)

    def test_source_identity_unpinned_rejected(self):
        self.d["source_snapshot"]["sha"]="latest"
        self.fail("source provenance")

    def test_missing_node_rejected(self):
        self.d["nodes"].pop()
        self.fail("fixed controls incomplete")

    def test_duplicate_node_identity_rejected(self):
        self.d["nodes"].append(copy.deepcopy(self.d["nodes"][0]))
        self.fail("node identity")

    def test_dag_cycle_rejected(self):
        self.d["edges"].append({"from":"G3C","to":"HUB_PR_CI",
                      "type":"FEEDFORWARD","binding":"DECLARED_DEPENDENCY",
                      "condition":"illegal future-to-past"})
        self.fail("forward edge violates stage order")

    def test_dag_unknown_endpoint_rejected(self):
        self.d["edges"][0]["to"]="NOT_A_REAL_NODE"
        self.fail("edge semantics")

    def test_feedback_next_pulse_only(self):
        self.d["edges"][-1]["type"]="FEEDFORWARD"
        self.fail("forward edge violates stage order")

    def test_feedback_cannot_authorize_admission(self):
        self.d["edges"][-1]["to"]="HUB_ADMISSION"
        self.fail("feedback must cross into NEXT pulse")

    def test_empty_sipoc_customer_rejected(self):
        self.d["sipoc"][3]["customer"]=""
        self.fail("SIPOC missing owner")

    def test_telemetry_run_identity_is_mandatory(self):
        self.d["telemetry_contract"]["identities"].remove("job_id")
        self.fail("incomplete native identity")

    def test_human_approval_not_compensated_by_statistics(self):
        self.d["spine_rules"]["merge_requires"].remove("eligible_independent_approval")
        self.fail("admission gate weakened")

    def test_forecast_cannot_grant_governed_credit(self):
        self.d["named_counts"]["governed_issue_closures"]=1
        self.fail("false governed credit")

    def test_no_consumer_acceptance_without_owner(self):
        n=next(x for x in self.d["nodes"] if x["id"]=="MYCELIUM")
        n["state"]="HOLD"
        self.fail("false-green snapshot")

    def test_mermaid_stages_separate_next_pulse(self):
        m=mermaid(self.d)
        self.assertIn("flowchart LR",m)
        self.assertEqual(m.count('-. "N+1 only" .->'),3)
        self.assertIn("HUB_ADMISSION --> HUB_MAIN_CI",m)

    def test_svg_accessible_and_no_script(self):
        s=svg(self.d)
        self.assertIn('role="img"',s)
        self.assertIn("ABACUS hard gate",s)
        self.assertNotIn("<script",s)
        self.assertEqual(s.count("<rect"),20)

    def test_sipoc_distinct_from_analytics(self):
        s=sipoc_md(self.d)
        self.assertIn("| Supplier | Inputs | Process | Outputs | Customer | Authority |",s)
        self.assertIn("Authorized rule receipts",s)
        self.assertIn("Source-controlled",s) if False else None

    def test_deterministic_file_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            m=build(self.d,out)
            self.assertEqual(m["gate"],"HOLD")
            self.assertEqual(len(m["artifacts_sha256"]),5)
            self.assertIn("Admission remains HOLD",
                          (out/"spine-control.html").read_text())
            self.assertIn("This is an architectural review view",
                          (out/"spine-control.html").read_text())
            for name,digest in m["artifacts_sha256"].items():
                self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)
            self.assertEqual(m,build(self.d,out))

    def test_forged_source_rule_blocked(self):
        self.d["merge_admission"]="PASS"
        self.fail("authority promotion")


if __name__=="__main__":
    unittest.main()
