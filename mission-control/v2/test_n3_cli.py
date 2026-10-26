"""CLI positive/negative subprocess-free smoke and deterministic parity."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import n3_dashboard, n3_integrity, n3_metrics

LEDGER=HERE.parent/'federation-atlas'/'CBD_GOLDEN_GRAPH_N3_20261017.json'


class CLITests(unittest.TestCase):
    def test_integrity_cli_valid(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'audit.json'
            with patch.object(sys,'argv',['n3_integrity.py',str(LEDGER),'--out',str(out)]):
                self.assertEqual(n3_integrity.main(),0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))['unknown_count'],9)

    def test_integrity_cli_invalid(self):
        with tempfile.TemporaryDirectory() as t:
            obj=json.loads(LEDGER.read_text(encoding="utf-8"))
            obj['receipts'][2]['coverage_delta']=101
            obj['receipts'][2]['coverage_matched']=True
            raw=Path(t)/'bad.json';raw.write_text(json.dumps(obj), encoding="utf-8", newline="\n")
            with patch.object(sys,'argv',['n3_integrity.py',str(raw)]):
                self.assertEqual(n3_integrity.main(),1)

    def test_metrics_cli_deterministic_json(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'metrics.json'
            with patch.object(sys,'argv',['n3_metrics.py',str(LEDGER),'--out',str(p)]):
                self.assertIsNone(n3_metrics.main())
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))['metrics']['pulse_receipts'],3)

    def test_dashboard_cli_writes_two_outputs(self):
        with tempfile.TemporaryDirectory() as t:
            h=Path(t)/'html'/'index.html';j=Path(t)/'metrics.json'
            with patch.object(sys,'argv',['n3_dashboard.py',str(LEDGER),'--html',str(h),'--metrics',str(j)]):
                self.assertIsNone(n3_dashboard.main())
            data=json.loads(j.read_text(encoding="utf-8"))
            self.assertIn(data['source_ledger_digest'],h.read_text(encoding="utf-8"))

    def test_valid_coverage_denominators(self):
        from n3_continuation import digest
        obj=json.loads(LEDGER.read_text(encoding="utf-8"))
        r=obj['receipts'][0]
        r.update(coverage_delta=1.3,coverage_matched=True,
                 coverage_comparison={'baseline_eligible':100,'actual_eligible':100})
        for i in range(1,len(obj['receipts'])):
            obj['receipts'][i]['prev_receipt_digest']=digest(obj['receipts'][i-1])
        self.assertEqual(n3_integrity.inspect(obj)['issue_count'],0)

    def test_invalid_native_attempt(self):
        from n3_continuation import digest
        obj=json.loads(LEDGER.read_text(encoding="utf-8"))
        r=obj['receipts'][2]
        r['tests']['kind']='NATIVE_EXACT_HEAD'
        r['tests']['tested_sha']=r['output_source_sha']
        r['tests']['native_evidence']={'workflow_run_id':12,'run_attempt':True,'artifact_sha256':'b'*64}
        self.assertIn('UNBOUND_NATIVE_PROOF','|'.join(n3_integrity.inspect(obj)['issues']))

    def test_source_evidence_invalid_shape(self):
        from n3_continuation import digest
        obj=json.loads(LEDGER.read_text(encoding="utf-8"))
        obj['receipts'][2]['source_evidence']={'source_sha':obj['receipts'][2]['output_source_sha'],'class':'FAKE','locator':'x'}
        self.assertIn('CONTRADICTORY_SOURCE_PROOF','|'.join(n3_integrity.inspect(obj)['issues']))


if __name__=='__main__':unittest.main()
