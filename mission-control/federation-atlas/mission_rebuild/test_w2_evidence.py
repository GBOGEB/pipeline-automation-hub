"""W2 regression cohort: source/attempt joins, unknown preservation and native provider drift."""
import copy
import json
import unittest
from pathlib import Path
import w2_live_bridge as bridge
import w2_plotly as plots

BASE = Path(__file__).resolve().parents[1]

def run(identity, head, status, conclusion=None, attempt=1):
    return {"id": identity, "head_sha": head, "status": status,
            "conclusion": conclusion, "run_attempt": attempt,
            "created_at": "2026-10-17T18:00:00Z",
            "updated_at": "2026-10-17T18:10:00Z"}

def job(ids, status, conclusion=None):
    return {"total_count": len(ids),
            "jobs": [{"id": x, "status": status, "conclusion": conclusion} for x in ids]}

def data():
    k=lambda r,s:r+s
    w,gg=bridge.W1_REPO,bridge.GG_REPO
    a={
       k(w, "/actions/runs/"+str(bridge.W1_RUN)):
           run(bridge.W1_RUN,bridge.W1_HEAD,"queued"),
       k(w, "/actions/runs/"+str(bridge.W1_RUN)+"/jobs?per_page=100"):
           job([117477894170],"queued"),
       k(w, "/actions/runs/"+str(bridge.W1_RUN)+"/artifacts?per_page=100"):
           {"total_count":0,"artifacts":[]},
       k(w, "/pulls/669/reviews?per_page=100"):[],
       k(w, "/actions/runs?status=queued&per_page=1"):{"total_count":516},
       k(w, "/actions/runs?status=in_progress&per_page=1"):{"total_count":1},
    }
    for index,n in enumerate(bridge.GG_RUNS):
        sha=("37afe75d9911691698a849b21fcfad0df1844432" if index==0
             else "d073992785c68820c3c9aa44260314fb82bd8f34")
        a[k(gg, "/actions/runs/"+str(n))]=run(n,sha,"completed","success")
        a[k(gg, "/actions/runs/"+str(n)+"/jobs?per_page=100")]=job(
            list(range(100+index*3,103+index*2)),"completed","success")
        a[k(gg, "/actions/runs/"+str(n)+"/artifacts?per_page=100")]={
            "total_count":1,"artifacts":[{"id":100+index,"name":"sample",
            "size_in_bytes":2000,"digest":"sha256:"+"a"*64}]}
    return a

class TestW2NativeBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control=json.loads(bridge.BRIDGE.read_text(encoding="utf-8"))

    def make(self, values=None):
        rows=values if values is not None else data()
        def read(repo,suffix):
            return rows[repo+suffix]
        return bridge.make(read,"b"*40,self.control,"2026-10-17T19:40:00+00:00")

    def test_source_bound_native_counts_and_stale_consumer(self):
        s=self.make()
        self.assertEqual(s["w1"]["run"]["attempt"],1)
        self.assertEqual(s["w1"]["attempt_2"],"NOT_PRESENT")
        self.assertEqual(s["w1"]["jobs"]["queued"],1)
        self.assertEqual((s["fleet"]["queued_run_count"],s["fleet"]["in_progress_run_count"]),(516,1))
        self.assertEqual(s["gg_math"]["stale_bridge_classification"],
                         "CONSUMER_SNAPSHOT_STALE_PROVIDER_TERMINAL")
        self.assertFalse(s["w1"]["native_success_with_known_job_population"])
        self.assertIsNone(s["fleet"]["capacity_slots"])
        self.assertIsNone(s["unknown_burndown"]["coverage"]["covered_statements"])
        self.assertEqual(s["review"]["recorded_reviews"],0)

    def test_provider_native_not_capability(self):
        s=self.make()
        self.assertEqual(s["gg_math"]["native_live_pulse_receipts_ingested"],0)
        self.assertEqual(s["unknown_burndown"]["method"]["six_sigma"],"NOT_ATTESTED")
        self.assertFalse(s["gg_math"]["provider_plotly_artifact_bytes_verified_by_this_consumer"])
        self.assertEqual(s["governance"]["merge_admission"],"HOLD")

    def test_w1_attempt_two_is_not_fabricated(self):
        rows=data();key=bridge.W1_REPO+"/actions/runs/"+str(bridge.W1_RUN)
        rows[key]["run_attempt"]=2
        s=self.make(rows)
        self.assertEqual(s["w1"]["attempt_2"],"ATTEMPT_EXISTS_NEEDS_JOB_CHECK")
        self.assertNotEqual(s["w1"]["attempt_2"],"NOT_PRESENT")

    def test_invalid_run_identity_is_fatal(self):
        rows=data();key=bridge.W1_REPO+"/actions/runs/"+str(bridge.W1_RUN)
        rows[key]["head_sha"]="f"*40
        with self.assertRaisesRegex(ValueError,"native head SHA"):
            self.make(rows)

    def test_invalid_gg_math_authority_is_fatal(self):
        c=copy.deepcopy(self.control);c["controls"]["merge_admission"]="GO"
        with self.assertRaisesRegex(ValueError,"canonical gg_MATH bridge custody"):
            bridge.make(lambda r,s:data()[r+s],"b"*40,c,"2026-10-17T19:40:00Z")

    def test_job_population_not_overcredited(self):
        x=bridge.sample_jobs({"total_count":3,"jobs":[
            {"id":1,"status":"completed","conclusion":"success"}]},"test")
        self.assertFalse(x["complete"])
        self.assertIsNone(x["passing"])

    def test_renderer_inlays_keep_unknown(self):
        s=self.make();s["evidence_class"]="SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"
        page=plots.render(s)
        self.assertEqual(page.count('class="inlay"'),4)
        self.assertIn("Plotly.newPlot",page)
        self.assertIn("NOT_ASSESSABLE",page)
        self.assertIn("UNKNOWN",page)

    def test_offline_plotly_bundle_loads_before_synchronous_card_scripts(self):
        s=self.make();s["evidence_class"]="SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"
        page=plots.render(s)
        head=page.split("</head>",1)[0]
        self.assertIn("<script>",head)
        self.assertIn("Plotly",head)
        self.assertIn("js-plotly-plot",page)
        self.assertLess(page.index("<script>"),page.index('class="inlay"'),
                        "to_html scripts execute during parsing; Plotly must already exist")
        self.assertNotIn("<script src=",page,"offline bundle cannot fetch CDN scripts")

    def test_renderer_rejects_imputed_coverage(self):
        s=self.make();s["unknown_burndown"]["coverage"]["covered_statements"]=10
        with self.assertRaisesRegex(ValueError,"unknown counts may not be imputed"):
            plots.render(s)

if __name__=="__main__":
    unittest.main()
