import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))
class Phase02TaxonomyTests(unittest.TestCase):
    def test_six_kpis_qualified(self):
        d=doc("mission-control/federation-atlas/PHASE02_KPI_TAXONOMY_v1.json")
        self.assertEqual(len(d["kpis"]),6)
        self.assertEqual(len({x["id"] for x in d["kpis"]}),6)
        for k in d["kpis"]:
            for key in ("id","label","definition","unit","statistic","source_owner","denominator","required_fields","current_value","evidence_state"):
                self.assertIn(key,k)
            self.assertIsNone(k["current_value"])
            self.assertEqual(k["evidence_state"],"UNBOUND")
            self.assertGreater(len(k["required_fields"]),2)
        self.assertFalse(d["authority_transfer"])
    def test_nonstale_definitions_do_not_forge_live_measurements(self):
        glossary=doc("mission-control/v2/MC_GLOSSARY_TAXONOMY_v2.json")
        self.assertEqual(glossary["as_of"],"2026-09-27")
        ext=glossary["operational_extension"]
        self.assertEqual(ext["as_of"],"2026-10-12")
        self.assertFalse(ext["runtime_metrics_current"])
        self.assertEqual(ext["terms"]["BT"]["meaning"],"BRADLEY_TERRY_PAIRWISE_RANKING")
        self.assertEqual(ext["terms"]["MCP"]["meaning"],"MODEL_CONTEXT_PROTOCOL")
        self.assertEqual(glossary["reservations"]["MIP"]["canonical_meaning"],"MODERNIZE_INNOVATE_PERPETUATE_IN_MISSION_CONTROL")
    def test_bt_method_is_pairwise(self):
        d=doc("mission-control/federation-atlas/METHOD_OBSERVABILITY_v1.json")
        bt=next(x for x in d["methods"] if x["id"]=="BT")
        self.assertEqual(bt["role"],"ADVISORY_BRADLEY_TERRY_RANKING")
        self.assertEqual(bt["trigger"],"OBSERVED_WINNER_LOSER_COMPARISONS")
        self.assertEqual(bt["metric"],"pairwise_comparisons_observed")
if __name__=="__main__":
    unittest.main()
