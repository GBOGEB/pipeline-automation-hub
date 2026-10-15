"""Exact-byte W169 telemetry replay; no invented global proof rates or QPS ACCEPT."""
import copy
import json
import hashlib
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sideload_telemetry as m

class SideloadTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pin=json.loads(m.PIN.read_text())
        cls.raw=m.SOURCE.read_bytes()
        cls.taxonomy=json.loads(m.TAXONOMY.read_text())
    def sample(self):
        return copy.deepcopy(self.pin),self.raw,copy.deepcopy(self.taxonomy)
    def test_native_single_run_proof_and_nulls(self):
        row=m.evaluate(*self.sample())
        self.assertEqual(row["w169_scoped_native_proof_yield"],{"numerator":1,"denominator":1,"scope":"ONLY_THIS_PINNED_W169_RUN"})
        self.assertEqual(row["metrics"]["restart_count"],0)
        self.assertAlmostEqual(row["metrics"]["request_p95_ms"],7.257121999998617)
        self.assertIsNone(row["unbound"]["queue_p95_seconds"])
        self.assertIsNone(row["unbound"]["cpu_peak_millicores"])
        self.assertIsNone(row["unbound"]["sideload_rejection_count"])
        self.assertIsNone(row["unbound"]["first_red_propagation_count"])
        self.assertEqual((row["qps_disposition"],row["release"]),("DEFER","HOLD"))
    def test_raw_bytes_tamper_rejected(self):
        p,b,t=self.sample()
        with self.assertRaisesRegex(ValueError,"raw receipt mismatch"):
            m.evaluate(p,b+b" ",t)
    def test_fake_proof_metadata_rejected(self):
        for key,v in (("run_id",9),("attempt",2),("artifact_id",42),("source_sha","a"*40)):
            p,b,t=self.sample();p[key]=v
            with self.assertRaises(ValueError):m.evaluate(p,b,t)
    def test_fake_authority_or_time_promotion_rejected(self):
        for key,v in (("release","PASS"),("child_disposition","ACCEPT"),("engineering_credit_delta",1),("authority_transfer",True),("evidence_class","LIVE_NOW")):
            p,b,t=self.sample();p[key]=v
            with self.assertRaises(ValueError):m.evaluate(p,b,t)
    def test_kpi_taxonomy_cannot_drift(self):
        p,b,t=self.sample();t["kpis"][0]["id"]="QUEUE_AVG"
        with self.assertRaisesRegex(ValueError,"KPI identity drift"):m.evaluate(p,b,t)
    def test_no_unsupported_metric_imputation(self):
        p,b,t=self.sample()
        rec=json.loads(b)
        rec["feature_row"]["cpu_peak_millicores"]=75
        forged=json.dumps(rec,sort_keys=True,indent=2).encode()+b"\n"
        p["source_receipt_sha256"]=hashlib.sha256(forged).hexdigest()
        p["source_receipt_size_bytes"]=len(forged)
        with self.assertRaisesRegex(ValueError,"unsupported metric imputation"):m.evaluate(p,forged,t)
    def test_historical_proof_not_false_green(self):
        p,b,t=self.sample()
        rec=json.loads(b);rec["real_kubernetes_api"]="failure"
        forged=json.dumps(rec,sort_keys=True,indent=2).encode()+b"\n"
        p["source_receipt_sha256"]=hashlib.sha256(forged).hexdigest()
        p["source_receipt_size_bytes"]=len(forged)
        with self.assertRaisesRegex(ValueError,"not successful"):m.evaluate(p,forged,t)
    def test_deterministic_json_and_digest(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            x=m.build(Path(a));y=m.build(Path(b))
            self.assertEqual(x,y)
            a1=(Path(a)/"sideload-telemetry.json").read_bytes()
            self.assertEqual(a1,(Path(b)/"sideload-telemetry.json").read_bytes())
            manifest=json.loads((Path(a)/"sideload-telemetry.sha256.json").read_text())
            self.assertEqual(hashlib.sha256(a1).hexdigest(),manifest["projection_sha256"])

if __name__=="__main__":
    unittest.main()
