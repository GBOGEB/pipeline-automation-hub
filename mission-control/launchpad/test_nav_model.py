"""Source-bound Mission Control graph/DAG/SIPOC and scheduler negative tests."""
from __future__ import annotations
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("nav_model",ROOT/"nav_model.py")
nav=importlib.util.module_from_spec(spec);spec.loader.exec_module(nav)
def sample():
    return json.loads((ROOT/"MISSIONCONTROL_NAV_SOURCES_v1.json").read_text(encoding="utf-8"))
class ModelTests(unittest.TestCase):
    def reject(self,fn,reason="MC_NAV_HOLD"):
        d=sample();fn(d)
        with self.assertRaisesRegex(ValueError,reason):nav.project(d)
    def test_source_bound_population(self):
        d=sample();v=nav.project(d)
        self.assertEqual(len(v["repositories"]),6)
        self.assertEqual(len(v["hierarchy"]),5)
        self.assertIsNone(v["observed_dispatch_count"])
        self.assertIsNone(v["native_run_qa"])
        self.assertEqual(v["admission"],"HOLD")
        self.assertTrue(v["counts"]["declared_edges"]>0)
        self.assertEqual(v["counts"]["repositories"],len(d["repositories"]))
    def test_no_remote_mutation(self):
        for key in nav.MUTATION_FIELDS:
            self.reject(lambda d:d["policy"].update({key:True}),"authority/mutation")
    def test_no_transport(self):self.reject(lambda d:d["policy"].update(enabled_mutation_transports=["REMOTE_APPLY"]),"enabled transport")
    def test_no_false_merge(self):self.reject(lambda d:d["policy"].update(merge_admission="PASS"),"admission")
    def test_no_false_capacity(self):self.reject(lambda d:d["scheduler"].update(measured_concurrency=20),"no fake runner")
    def test_no_false_source(self):self.reject(lambda d:d["repositories"][1].update(sha="not-a-sha"),"repo SHA")
    def test_qps_classification(self):
        self.assertEqual(next(r for r in sample()["repositories"] if r["id"]=="qps")["public_class"],"METADATA_ONLY_OWNER_PUBLICATION_REVIEW")
    def test_duplicate_node_rejected(self):self.reject(lambda d:d["nodes"].append(copy.deepcopy(d["nodes"][0])),"node inventory")
    def test_orphan_edge_rejected(self):self.reject(lambda d:d["edges"].append(dict(d["edges"][0],to="absent")),"dangling")
    def test_executable_cycle_fails(self):self.reject(lambda d:d["edges"].append(dict(d["edges"][0],**{"from":"admit","to":"intake"})),"cyclic executable")
    def test_feedback_separate_from_dag(self):
        d=sample();p=nav.project(d)
        self.assertIn("pages",p["executable_dag_topology"])
        self.assertLess(p["executable_dag_topology"].index("admit"),
                        p["executable_dag_topology"].index("pages"))
        self.assertIn("FEEDBACK",{x["relation"] for x in d["edges"]})
    def test_sipoc_complete_and_hierarchy(self):
        d=sample();text=nav.sipoc_md(d)
        for term in ("Suppliers","Inputs","Process","Outputs","Customers","Mission","Sprint","Wave","Pulse","Run"):self.assertIn(term,text)
    def test_mermaid_declared_dashed(self):
        t=nav.mermaid(sample())
        self.assertIn("-.->",t);self.assertIn("-->",t)
        self.assertIn("pages -.-> intake",t)
    def test_byte_stable_and_no_new_authority(self):
        with tempfile.TemporaryDirectory() as td:
            r=nav.generate(out=td);a=(Path(td)/"snapshot.json").read_bytes()
            nav.generate(out=td)
            self.assertEqual(a,(Path(td)/"snapshot.json").read_bytes())
            self.assertIs(r["policy"]["authority_transfer"],False)
    def test_source_bytes_untrusted_do_not_promote(self):
        self.reject(lambda d:d["snapshot"].update(hosted_url_verified=True),"snapshot")
        self.reject(lambda d:d["snapshot"].update(accepted_n=3),"unproved telemetry")
    def test_work_queue_exact_classes(self):
        self.reject(lambda d:d["queues"].pop(),"queue coverage")
    def test_no_claimed_worker_count(self):
        self.reject(lambda d:d["workers"][0].update(active_count=8),"worker capacity invented")
    def test_reports_projected_with_count(self):
        d=sample();v=nav.project(d)
        self.assertEqual(v["reports"],d["reports"])
        self.assertEqual(v["counts"]["reports"],len(d["reports"]))
        self.assertEqual({r["repo"] for r in d["reports"]},{"hub","abacus","codex","qps","math"})
    def test_reports_carry_no_values_or_run_state(self):
        for key,val in (("value",1),("conclusion","success"),("last_run","2026-10-31T00:00Z")):
            self.reject(lambda d:d["reports"][0].update({key:val}),"report fields")
        self.reject(lambda d:d["reports"][0].pop("metrics"),"report fields")
    def test_report_page_listed_once(self):
        self.reject(lambda d:d["reports"].append(dict(d["reports"][0],id="copy")),"report page")
        self.reject(lambda d:d["reports"].append(dict(d["reports"][1],path="x.html")),"report id")
    def test_one_owner_per_metric(self):
        def dup(d):
            src=next(r for r in d["reports"] if r["metrics"])
            other=next(r for r in d["reports"] if r is not src)
            other["metrics"]=[dict(src["metrics"][0],owner="scripts/copy.py")]
        self.reject(dup,"one owner per metric")
    def test_report_sources_bound(self):
        self.reject(lambda d:d["reports"][0].update(repo="absent"),"report repo")
        self.reject(lambda d:d["reports"][0].update(path="../escape.html"),"report page")
        self.reject(lambda d:d["reports"][0].update(generator="C:\\tool.py"),"report generator")
        self.reject(lambda d:d["reports"][0].update(workflow="scripts/run.yml"),"report workflow")
        self.reject(lambda d:d["reports"][0].update(workflow_role="DEPLOYED"),"report workflow role")
        self.reject(lambda d:d["reports"][0].update(schedule="hourly"),"report schedule")
        self.reject(lambda d:d["reports"][0].update(observed_sha="6fbda559"),"report observed SHA")
    def test_report_pages_url_stays_on_own_site(self):
        def wrong(d):
            r=next(x for x in d["reports"] if x["repo"]=="abacus");r["pages_url"]="https://gbogeb.github.io/CODEX/"
        self.reject(wrong,"report Pages URL")
        self.reject(lambda d:d["reports"][0].update(pages_url="https://example.com/"),"report Pages URL")
if __name__=="__main__":unittest.main()
