"""N15 whole-taxonomy module-roster, privacy and no-zero-file frontier."""
from __future__ import annotations

import importlib
import json
import unittest

import title_taxonomy as title
import taxonomy_pulse as pulse
import taxonomy_peer_confidence as peer

HUB="GBOGEB/pipeline-automation-hub"
QPS="GBOGEB/cryoplant-project"
EXPECTED=(
    "title_taxonomy", "taxonomy_pulse", "taxonomy_explorer",
    "taxonomy_metadata_plan",
    "taxonomy_public_ingress", "taxonomy_root_occurrence",
    "taxonomy_dmaic_efficacy", "taxonomy_slowburn_crew",
    "taxonomy_peer_confidence", "taxonomy_successor_audit",
)


class Cohort(unittest.TestCase):
    def test_all_11_modules_import_and_have_named_authority(self):
        for name in EXPECTED:
            with self.subTest(name=name):
                module=importlib.import_module(name)
                self.assertTrue(module.__file__.endswith(name+".py"))
        self.assertEqual(len(set(EXPECTED)),10)

    def test_private_population_remains_noncomparable_after_projection(self):
        def item(repo,n,t,private):
            return {"key":f"{repo}#{n}", "repo":repo,"number":n,
                    "type":"Issue","title":t,"private":private,
                    "title_taxonomy":title.parse_title(t,"Issue")}
        def snap(at,include_qps):
            heads={HUB:{"private":False,"head_sha":"a"*40}}
            if include_qps:
                heads[QPS]={"private":True,"head_sha":"b"*40}
            return {"schema":pulse.RANK_SCHEMA,"fetched_at":at,"heads":heads,
                    "items":[item(HUB,1,"fix(watch): status",False)]}
        old=snap("2026-10-26T11:00:00Z",True)
        new=snap("2026-10-26T11:30:00Z",False)
        report=peer.analyze(new,old)
        self.assertFalse(report["previous_population_comparable"])
        self.assertEqual(report["peer_delta"],{})
        self.assertNotIn(QPS,json.dumps(report))
        self.assertEqual(report["formal_credit_delta"],0)

    def test_all_sources_remain_auditory_not_acceptance_authority(self):
        specs=[
            ("taxonomy_pulse","SCHEMA"),
            ("taxonomy_explorer","SCHEMA"),
            ("taxonomy_metadata_plan","SCHEMA"),
            ("taxonomy_public_ingress","SCHEMA"),
            ("taxonomy_root_occurrence","SCHEMA"),
            ("taxonomy_dmaic_efficacy","SCHEMA"),
            ("taxonomy_slowburn_crew","SCHEMA"),
            ("taxonomy_peer_confidence","SCHEMA"),
            ("taxonomy_successor_audit","SCHEMA"),
        ]
        for mod,schema in specs:
            with self.subTest(mod=mod):
                value=getattr(importlib.import_module(mod),schema)
                self.assertTrue(isinstance(value,str) and len(value)>10)
        self.assertEqual(title.SCHEMA,pulse.tax.SCHEMA)


if __name__=="__main__":
    unittest.main()
