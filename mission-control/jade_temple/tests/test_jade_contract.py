import csv
import importlib.util
import io
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PORT=json.loads((ROOT/'data/TOP21_PORTFOLIO.json').read_text(encoding='utf-8'))
REG=json.loads((ROOT/'data/SOURCE_REGISTRY.json').read_text(encoding='utf-8'))
STATE=json.loads((ROOT/'data/JADE_STATE.json').read_text(encoding='utf-8'))

class JadeContractTest(unittest.TestCase):
    def test_01_name_and_roster(self):
        self.assertEqual(PORT['mission'],'JADE_TEMPLE');self.assertEqual(PORT['method'],'JADE_CASTE');self.assertEqual(PORT['cohort'],'MISSION_SELECTED_TOP21')
    def test_02_roster_count_unique(self):
        self.assertEqual(len(PORT['repositories']),21);self.assertEqual(len({x['repo'] for x in PORT['repositories']}),21)
    def test_03_historical_file_count(self):
        self.assertEqual(sum(x['n11_historical']['files'] for x in PORT['repositories']),26836)
    def test_04_root_counts(self):
        self.assertEqual(sum(x['n11_historical']['root_files'] for x in PORT['repositories']),880);self.assertEqual(sum(x['n11_historical']['root_review_candidates'] for x in PORT['repositories']),706)
    def test_05_candidates_not_defects(self):
        self.assertFalse(PORT['historical_totals']['review_is_defect_count'])
    def test_06_no_authority_or_waiver(self):
        self.assertFalse(PORT['authority_transfer']);self.assertEqual(PORT['merge_admission'],'HOLD');self.assertFalse(STATE['security_waiver']);self.assertFalse(STATE['authority_transfer'])
    def test_07_exact_head_syntax(self):
        for row in PORT['repositories']:
            self.assertRegex(row['commit_sha_observed'],r'^(?:[0-9a-f]{40}|PRIVATE_AGGREGATE_ONLY)$');self.assertTrue(row['branch'])  # private head: counts only
    def test_08_unknown_release_and_pages(self):
        for row in PORT['repositories']:
            self.assertEqual(row['site']['proof_status'],'UNKNOWN');self.assertIsNone(row['site']['verified_http_status']);self.assertEqual(row['release']['readiness_level'],'UNASSESSED')
    def test_09_readme_case_sensitive(self):
        s=[x['entrypoint']['path'] for x in PORT['repositories']];self.assertEqual(s.count('README.md'),20);self.assertEqual(s.count('ReadMe.md'),1)
    def test_10_5_plus_7_plus_9(self):
        from collections import Counter
        self.assertEqual(Counter(x['cohort_lane'] for x in PORT['repositories']),{'CORE':5,'EXPAND':7,'SUPPORT':9})
    def test_11_provenance_sources(self):
        for k in ['missioncontrol_top21','missioncontrol_n11_rollup','abacus_five_nominees','handover_v2','cp_protocol']:
            self.assertIn(k,REG);self.assertRegex(REG[k]['git_blob_sha1'],r'^[0-9a-f]{40}$')
    def test_12_predecessor_digest(self):
        self.assertEqual(REG['nplus2_prior_zip']['sha256'],STATE['historical_nplus2_sha256']);self.assertTrue(REG['nplus2_prior_zip']['verified_crc'])
    def test_13_burndown_queue_ids(self):
        with (ROOT/'data/BD_QUEUE.csv').open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),15);self.assertEqual(len({r['id'] for r in rows}),15);self.assertIn('P0',{r['priority'] for r in rows})
    def test_14_spine_non_authority(self):
        x=(ROOT/'diagrams/JADE_SPINE.mmd').read_text(encoding='utf-8');self.assertIn('flowchart',x);self.assertIn('reference-only',x);self.assertIn('HOLD',x)
    def test_15_html_determinism(self):
        spec=importlib.util.spec_from_file_location('jade_builder', ROOT/'site/build_dashboard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        data=m.generate();self.assertEqual(data,(ROOT/'site/index.html').read_bytes());self.assertEqual(data,m.generate())
    def test_16_no_external_script_or_image(self):
        h=(ROOT/'site/index.html').read_text(encoding='utf-8');self.assertNotIn('http://',h);self.assertNotIn('<script src=',h);self.assertIn('connect-src \'none\'',h)
    def test_17_html_21_cases(self):
        h=(ROOT/'site/index.html').read_text(encoding='utf-8');self.assertIn('JADE_TEMPLE',h);self.assertIn('Root stewardship',h);self.assertIn('Release gates',h)
    def test_18_anti_false_promotion_negative(self):
        spec=importlib.util.spec_from_file_location('jade_builder', ROOT/'site/build_dashboard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        old=m.DATA
        try:
            tmp=ROOT/'data/__negative__.json'
            b=json.loads(json.dumps(PORT));b['merge_admission']='PASS';tmp.write_text(json.dumps(b),encoding='utf-8',newline="\n");m.DATA=tmp
            with self.assertRaises(AssertionError):m.generate()
            b['merge_admission']='HOLD';b['repositories'][0]['release']['readiness_level']='J5';tmp.write_text(json.dumps(b),encoding='utf-8',newline="\n")
            with self.assertRaises(AssertionError):m.generate()
        finally:
            m.DATA=old;tmp.unlink(missing_ok=True)
    def test_19_sha_comparison(self):
        x=json.loads((ROOT/'data/HEAD_CROSSWALK.json').read_text(encoding='utf-8'))
        codex=next(r for r in x['repositories'] if r['repo']=='GBOGEB/CODEX')
        self.assertTrue(codex['changed']);self.assertNotEqual(codex['prior_sha'],codex['observed_sha'])
    def test_20_no_false_stability(self):
        h=(ROOT/'03_JADE_CASTE_METHOD.md').read_text(encoding='utf-8');self.assertIn('Six Sigma',h);self.assertIn('three comparable eligible pulses',h)

if __name__=='__main__':unittest.main()
