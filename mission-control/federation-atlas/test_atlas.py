import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_atlas

class AtlasTests(unittest.TestCase):
    def test_doctor_guard(self):
        sha="a"*40
        self.assertEqual(build_atlas.event_receipt("DMAIC","ANALYZE",{"source_sha":sha,"executed_steps":2,"observed_application_red":True})["recommended_route"],"DOCTOR_REX_LOOKUP")
        self.assertEqual(build_atlas.event_receipt("DMAIC","ANALYZE",{"source_sha":sha,"executed_steps":0,"observed_application_red":True})["recommended_route"],"DOCKMASTER")
        self.assertEqual(build_atlas.event_receipt("DMAIC","ANALYZE",{"source_sha":sha,"executed_steps":2,"observed_application_red":False})["recommended_route"],"EVIDENCE_PENDING_OR_3PR")
        self.assertEqual(build_atlas.event_receipt("DMAIC","ANALYZE",{"source_sha":sha,"executed_steps":2,"observed_application_red":True,"owner_external":True})["recommended_route"],"RETURN_OWNER")
    def test_invalid_steps(self):
        with self.assertRaises(ValueError):
            build_atlas.event_receipt("DMAIC","MEASURE",{"executed_steps":-1})
    def test_source_projection(self):
        with tempfile.TemporaryDirectory() as d:
            m=build_atlas.build(d)
            self.assertEqual(m["evidence_state"],"HISTORICAL_SOURCE_SNAPSHOT_NOT_LIVE")
            self.assertEqual(len(m["phase02_kpis"]),6)
            self.assertTrue(all(x["current_value"] is None and x["evidence_state"]=="UNBOUND" for x in m["phase02_kpis"]))
            self.assertEqual([m["top7_repositories"],m["top14_repositories"],m["top21_repositories"]],[7,14,21])
            self.assertIsNone(m["active_method"])
            p=Path(d)/"index.html"
            self.assertTrue(p.exists())
            s=p.read_text()
            self.assertIn("Hosted candidate",s)
            self.assertIn("Doctor",s)
            self.assertIn("Mission",s)
            self.assertNotIn("Automatically merged",s)
            svg=(Path(d)/"federation.svg").read_text()
            self.assertEqual(svg.count('marker-end="url(#arrow)"'),11)
            self.assertEqual(svg.count('data-binding="DECLARED"'),7)
            self.assertEqual(svg.count('stroke-dasharray="6 5"'),7)
    def test_invalid_phase(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build_atlas.build(d,"MIP","APPROVE")
if __name__=="__main__":
    unittest.main()
