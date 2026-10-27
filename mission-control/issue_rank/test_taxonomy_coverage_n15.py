"""N15 whole-taxonomy module-roster, privacy and no-zero-file frontier."""
from __future__ import annotations

import importlib
import json
import unittest
import copy
import tempfile
import subprocess
import sys
from pathlib import Path

import taxonomy_dmaic_efficacy as dmaic
import taxonomy_slowburn_crew as crew

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
    def test_all_10_modules_import_and_have_named_authority(self):
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

    @staticmethod
    def _dmaic_wave():
        return {
            "wave":0, "cohort_id":"taxonomy-core-v1",
            "file_roster_sha256":"f"*64, "head_sha":"a"*40,
            "observed_at":"2026-10-26T12:00:00Z",
            "covered_lines":80, "total_lines":100,
            "zero_covered_files":2, "tests_passed":20,
            "tests_failed":0, "tests_skipped":1,
            "executed_jobs":2, "zero_step_jobs":0,
            "queue_depth":2, "in_progress":1
        }

    def test_dmaic_input_mutations_fail_without_scaling_credit(self):
        wave=self._dmaic_wave()
        base={"schema":dmaic.INPUT, "cohort_id":"taxonomy-core-v1",
              "waves":[wave]}
        trials=[
            ("wave", 4, "UNMATCHED_WAVE_INDEX"),
            ("cohort_id","cross-cohort","COHORT_CHANGED"),
            ("file_roster_sha256","short","FILE_ROSTER_NOT_PINNED"),
            ("head_sha","bad","HEAD_NOT_PINNED"),
            ("observed_at","2026-10-26T12:00:00","TIMEZONE_MISSING"),
            ("covered_lines",101,"COVERAGE_DENOMINATOR_INVALID"),
            ("total_lines",0,"COVERAGE_DENOMINATOR_INVALID"),
            ("queue_depth",-1,"INVALID_MEASURED_COUNTERS"),
            ("executed_jobs",0,"UNEXECUTED_TEST_PROOF"),
            ("zero_step_jobs",3,"ZERO_STEP_GT_JOBS"),
        ]
        for field,value,error in trials:
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,error):
                candidate=copy.deepcopy(base)
                candidate["waves"][0][field]=value
                dmaic.assess(candidate)
        empty=copy.deepcopy(base)
        empty["waves"][0]["tests_passed"]=0
        with self.assertRaisesRegex(ValueError,"ZERO_TEST_JOBS_NOT_CREDITABLE"):
            dmaic.assess(empty)

    def test_dmaic_cli_emits_no_credit_and_source_immutable(self):
        candidate={"schema":dmaic.INPUT,"cohort_id":"taxonomy-core-v1",
                   "waves":[self._dmaic_wave()]}
        with tempfile.TemporaryDirectory() as tmp:
            src,out=Path(tmp)/"in.json",Path(tmp)/"out.json"
            src.write_text(json.dumps(candidate),encoding="utf-8")
            original=src.read_bytes()
            self.assertEqual(dmaic.main(["--in",str(src),"--out",str(out)]),0)
            report=json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["formal_credit_delta"],0)
            self.assertEqual(report["next_action"],"PROVE_NEXT_SMALL_SLICE")
            self.assertEqual(src.read_bytes(),original)

    def test_slowburn_rex_invalid_schema_and_timeout_hard_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"bad.json"
            src.write_text(json.dumps({"schema":"unknown","entries":[]}))
            with self.assertRaisesRegex(ValueError,"REX_SCHEMA_NOT_CURRENT"):
                crew.rex_preflight(src)
        def timed_out(command,working,timeout):
            raise subprocess.TimeoutExpired(command,timeout)
        report=crew.run(
            lane="grammar",head="a"*40,waves=3,queue_depth=1,
            budget_seconds=120,gap_seconds=0,runner=timed_out,
            rex_check=lambda:["REX-001","REX-002","REX-005","REX-006"])
        self.assertEqual(report["status"],"FIRST_RED_STOP")
        self.assertEqual(report["waves_executed"],1)
        self.assertEqual(report["test_invocations"][0]["exit_code"],124)
        self.assertEqual(report["formal_credit_delta"],0)

    def test_slowburn_cli_actual_one_native_suite_has_receipt(self):
        # One bounded local Python test invocation, no GitHub dispatch.
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"crew.json"
            status=crew.main([
                "--lane","grammar","--head","a"*40,
                "--waves","1","--queue-depth","1",
                "--gap-seconds","0","--budget-seconds","90",
                "--out",str(out)])
            self.assertEqual(status,0)
            result=json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["status"],"PASS_ALL_BOUNDED_WAVES")
            self.assertEqual(result["waves_executed"],1)
            self.assertEqual(result["test_invocations"][0]["exit_code"],0)
            self.assertEqual(result["formal_credit_delta"],0)

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
