"""W380 process-family matrix: canonical stage parity and safe graph projections."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from metric_atlas import lane_process_graph as m
from metric_atlas import lane_lifecycle as lc


def snapshot():
    return {"schema":lc.SCHEMA,"cohort":"w380.process","observed_at":"2026-10-28T14:00:00Z",
            "mode":"READ_ONLY_SOURCE_DECLARED","source_heads":{},
            "observations":[],"authority_transfer":False,"merge_admission":"HOLD"}


class ProcessGraphTests(unittest.TestCase):
    def test_canonical_identity_and_no_maturity_transfer(self):
        r=m.project(snapshot())
        self.assertEqual(len(r["nodes"]),70)
        self.assertEqual(len({x["id"] for x in r["nodes"]}),70)
        self.assertEqual(len(r["edges"]),77)
        self.assertEqual(r["graph_metrics"]["cross_lane_edges"],13)
        self.assertEqual(r["graph_metrics"]["next_pulse_edges"],1)
        self.assertEqual(r["graph_metrics"]["within_pulse_edges"],76)
        self.assertEqual(r["merge_admission"],"HOLD")
        self.assertFalse(r["authority_transfer"])
        self.assertTrue(all(c["status"]=="UNKNOWN" for c in r["nodes"]))
        self.assertTrue(all(c["maturity_level"] is None for c in r["nodes"]))

    def test_stage_owner_and_sipoc_are_reused_not_duplicated(self):
        r=m.project(snapshot())
        for n in r["nodes"]:
            self.assertEqual(n["sipoc"],lc.OWNER.SIPOC[n["stage"]])
            self.assertEqual(n["canonical_probe_ids"],[
                p[0] for p in lc.OWNER.PROBES if p[1]==n["stage"]])
            self.assertEqual(len(n["canonical_probe_ids"]),5)
            self.assertEqual(n["owner"],lc.LANES[n["lane"]][1])

    def test_same_pulse_topological_layers_are_complete(self):
        r=m.project(snapshot())
        ids={n["id"] for n in r["nodes"]}
        self.assertEqual({n for layer in r["topological_layers"] for n in layer},ids)
        positions={n:i for i,layer in enumerate(r["topological_layers"]) for n in layer}
        for e in r["edges"]:
            if e["relation"]=="FEEDBACK_NEXT_PULSE":
                self.assertEqual((e["from"],e["to"]),("G.S9_CONTROL","A.S0_PLAN"))
            else:
                self.assertLess(positions[e["from"]],positions[e["to"]])

    def test_mermaid_all_views_same_node_and_edge_population(self):
        r=m.project(snapshot())
        for view in ("DAG","SIPOC","SPINE"):
            g=m.mermaid(r,view)
            self.assertEqual(sum('["' in line for line in g.splitlines()),70)
            self.assertEqual(sum("-->" in line for line in g.splitlines()),76)
            self.assertEqual(sum("-.->" in line for line in g.splitlines()),1)
        with self.assertRaisesRegex(ValueError,"UNKNOWN_GRAPH_VIEW"):
            m.mermaid(r,"MUTATE")

    def test_read_only_html_uses_text_nodes_and_responds_to_selection(self):
        h=m.html_view(m.project(snapshot()))
        self.assertIn('id="lane"',h)
        self.assertIn('id="stage"',h)
        self.assertIn('id="detail"',h)
        self.assertIn("textContent",h)
        self.assertIn("replaceChildren",h)
        self.assertNotIn("innerHTML",h)
        self.assertNotIn("fetch(",h)

    def test_untrusted_url_cannot_close_embedded_script(self):
        s=snapshot()
        s["source_heads"]={"GBOGEB/pipeline-automation-hub":"a"*40}
        s["observations"]=[{
            "lane":"A","stage":"S0_PLAN","repo":"GBOGEB/pipeline-automation-hub",
            "head_sha":"a"*40,"receipt_sha256":"b"*64,
            "observed_at":"2026-10-28T13:00:00Z","result":"PASS",
            "evidence_url":"https://github.com/GBOGEB/pipeline-automation-hub/issues/1/</script><svg onload=alert(1)>"}]
        h=m.html_view(m.project(s))
        self.assertEqual(h.count("</script>"),1)
        self.assertIn("<\\/script>",h)
        self.assertIn("OBSERVED_PASS_UNVERIFIED",h)
        self.assertNotIn("innerHTML",h)

    def test_output_manifest_reproducible_and_member_bound(self):
        a=m.project(snapshot())
        self.assertEqual(a,m.project(snapshot()))
        with tempfile.TemporaryDirectory() as directory:
            r=m.emit(snapshot(),directory)
            root=Path(directory)
            man=json.loads((root/"manifest.json").read_text())
            self.assertEqual(r,a)
            self.assertEqual(len(man["files_sha256"]),5)
            for name,digest in man["files_sha256"].items():
                self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
            self.assertEqual(json.loads((root/"lane-process.json").read_text())["sha256"],r["sha256"])

    def test_invalid_lane_or_stage_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_LANE_STAGE"):
            m.identifier("Z","S0_PLAN")
        with self.assertRaisesRegex(ValueError,"INVALID_LANE_STAGE"):
            m.identifier("A","S10_LEAK")

    def test_future_or_same_stage_cross_lane_edge_denied(self):
        bad=[("A","S2_BUILD","G","S2_BUILD","LEAP")]
        with self.assertRaisesRegex(ValueError,"BACK_EDGE_OR_SELF_INTERFACE"):
            m.project(snapshot(),bad)
        bad=[("A","S8_MONITOR","B","S3_TEST","BACK")]
        with self.assertRaisesRegex(ValueError,"BACK_EDGE_OR_SELF_INTERFACE"):
            m.project(snapshot(),bad)
        bad=[("A","S2_BUILD","A","S3_TEST","SELF")]
        with self.assertRaisesRegex(ValueError,"BACK_EDGE_OR_SELF_INTERFACE"):
            m.project(snapshot(),bad)

    def test_bad_interface_shape_and_duplicate_denied(self):
        with self.assertRaisesRegex(ValueError,"BAD_INTERFACE_SHAPE"):
            m.project(snapshot(),[("A","S2_BUILD")])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_INTERFACE"):
            m.project(snapshot(),[m.INTERFACES[0],m.INTERFACES[0]])
        with self.assertRaisesRegex(ValueError,"UNBOUNDED_INTERFACES"):
            m.project(snapshot(),list(m.INTERFACES)*3)

    def test_malformed_label_denied(self):
        with self.assertRaisesRegex(ValueError,"BAD_INTERFACE_LABEL"):
            m.project(snapshot(),[("A","S0_PLAN","B","S1_CODE","x/unsafe")])

    def test_stage_census_rejects_undocumented_authority(self):
        s=snapshot()
        s["merge_admission"]="PASS"
        with self.assertRaisesRegex(ValueError,"AUTHORITY_ESCALATION"):
            m.project(s)

    def test_graph_does_not_infer_queue_p95_or_worker_counts(self):
        r=m.project(snapshot())
        self.assertIsNone(r["graph_metrics"]["actual_queue_p95_seconds"])
        self.assertIsNone(r["graph_metrics"]["actual_worker_runs"])
        self.assertEqual(r["source_crosswalk_sha256"],lc.project(snapshot())["digest_sha256"])

    def test_graph_reacts_to_evidence_without_making_green_maturity(self):
        s=snapshot();s["source_heads"]={"GBOGEB/pipeline-automation-hub":"a"*40}
        s["observations"]=[{
            "lane":"G","stage":"S3_TEST","repo":"GBOGEB/pipeline-automation-hub",
            "head_sha":"a"*40,"receipt_sha256":"b"*64,"result":"PASS",
            "observed_at":"2026-10-28T13:00:00Z",
            "evidence_url":"https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/123"}]
        r=m.project(s)
        cell=next(n for n in r["nodes"] if n["id"]=="G.S3_TEST")
        self.assertEqual(cell["status"],"OBSERVED_PASS_UNVERIFIED")
        self.assertIsNone(cell["maturity_level"])
        self.assertEqual(r["merge_admission"],"HOLD")

if __name__=="__main__":
    unittest.main()
