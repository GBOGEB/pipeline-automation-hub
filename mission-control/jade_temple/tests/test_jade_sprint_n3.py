"""JADE_CASTE N+3 negative controls: release gates, DAG, workers, cache and SHA."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SPRINT=ROOT/"mission-control"/"jade_temple"/"sprint"
sys.path.insert(0,str(SPRINT))
import model
import cli


class SprintDAGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master=json.loads((ROOT/"mission-control"/"jade_temple"/"data"/
                              "REPO_READINESS_NPLUS1.json").read_text(encoding='utf-8'))
    def setUp(self):
        self.data=copy.deepcopy(self.master)

    def test_fifteen_denominators_and_top21(self):
        p=model.build(self.data)
        self.assertEqual(len(p["dimensions"]),15)
        self.assertEqual(len(p["work_orders"]),21)
        self.assertTrue(all(x["numerator"] is None and x["denominator"] is None
                            for x in p["dimensions"]))
    def test_full_release_gate_dag(self):
        p=model.build(self.data)
        self.assertEqual((len(p["graph"]["nodes"]),len(p["graph"]["edges"])),(253,420))
        self.assertGreater(len(p["graph"]["layers"]),2)
        self.assertEqual(p["summary"]["inventory_observed"],{"numerator":21,"denominator":21})
    def test_no_release_authority(self):
        p=model.build(self.data)
        self.assertEqual(p["point_release"],"TARGET_NOT_ACHIEVED")
        self.assertEqual(p["admission"],"HOLD")
        self.assertFalse(p["authority_transfer"])
        releases=[n for n in p["graph"]["nodes"] if n.get("gate")=="J5"]
        self.assertEqual(len(releases),21)
        self.assertTrue(all(not n["executor_enabled"] and n["release_credit"]==0 for n in releases))
    def test_pressure_is_structural_only(self):
        x=model.build(self.data)["pressure"]["GBOGEB/ABACUS"]
        self.assertEqual(x["reachable_unique"],11)
        self.assertIsNone(x["verified_unlocks"])
    def test_source_roster_duplication_fail_closed(self):
        self.data["rows"][0]["repo"]=self.data["rows"][1]["repo"]
        with self.assertRaisesRegex(ValueError,"ROSTER_COLLISION"):model.build(self.data)
    def test_head_name_not_an_exact_sha(self):
        self.data["rows"][0]["head_readback"]="main"
        with self.assertRaisesRegex(ValueError,"UNPINNED_HEAD"):model.build(self.data)
    def test_false_release_readiness_rejected(self):
        self.data["rows"][0]["readiness"]["point_release"]="PASS"
        with self.assertRaisesRegex(ValueError,"FALSE_RELEASE_SUCCESS"):model.build(self.data)
    def test_forced_admission_rejected(self):
        self.data["admission"]="PASS"
        with self.assertRaisesRegex(ValueError,"AUTHORITY_TRANSFER"):model.build(self.data)
    def test_cohort_shrink_rejected(self):
        self.data["rows"].pop()
        with self.assertRaisesRegex(ValueError,"TOP21_DENOMINATOR"):model.build(self.data)
    def test_priority_population_bounded(self):
        self.assertEqual(model.build(self.data)["summary"]["priority_population"],
                         {"P0":5,"P1":9,"P2":7})
    def test_n2_readback_owner_promotion_denied(self):
        n2={"schema":"jade.temple.fleet_readback.v2","merge_admission":"HOLD",
            "authority_transfer":False,
            "rows":[{"repo":r["repo"],"current_head":r["head_readback"],
                     "owner_J5_point_release":None} for r in self.data["rows"]]}
        self.assertTrue(model.build(self.data,n2)["readback_included"])
        n2["rows"][0]["owner_J5_point_release"]=True
        with self.assertRaisesRegex(ValueError,"UNAUTHENTICATED_READINESS"):
            model.build(self.data,n2)
    def test_disconnected_dependency_fails(self):
        with self.assertRaisesRegex(ValueError,"DANGLING_EDGE"):
            model.topo([{"id":"A"}],[{"from":"A","to":"MISSING"}])
    def test_ordering_cycle_fails(self):
        with self.assertRaisesRegex(ValueError,"EXECUTABLE_DAG_CYCLE"):
            model.topo([{"id":"A"},{"id":"B"}],
                       [{"from":"A","to":"B"},{"from":"B","to":"A"}])
    def test_duplicate_edge_fails(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_EDGE"):
            model.topo([{"id":"A"},{"id":"B"}],
                       [{"from":"A","to":"B"},{"from":"A","to":"B"}])
    def test_sipoc_separate_provenance(self):
        p=model.build(self.data)
        self.assertEqual({x["axis"] for x in p["dimensions"]},
                         {x["axis"] for x in p["sipoc"]})
    def test_html_escapes_issue_text(self):
        self.data["rows"][0]["next_point_release_todo"]="<script>alert(9)</script>"
        page=model.render_html(model.build(self.data))
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>alert(9)</script>",page)
        self.assertNotIn("fetch(",page)
    def test_n4_svg_is_internal_and_stage_anchored(self):
        page=model.render_html(model.build(self.data))
        self.assertIn("<svg",page)
        self.assertIn("J5 POINT RELEASE",page)
        self.assertIn("id='dimensions'",page)
        self.assertIn("id='owners'",page)
        self.assertNotIn("fetch(",page)
    def test_worker_capacity_remains_unverified(self):
        p=model.build(self.data)
        self.assertIsNone(p["pools"]["native_runner_slots"])
        self.assertIsNone(p["pools"]["local_python_observed"])
        self.assertEqual(p["pools"]["dispatch_count"],0)


class SprintPreflightTests(unittest.TestCase):
    def test_local_jobs_are_allowlisted(self):
        jobs=cli.jobs(ROOT,sys.executable,False)
        self.assertIn("N1_CONTRACT_TESTS",{x["id"] for x in jobs})
        self.assertIn("N1_GREEN_CHECK",{x["id"] for x in jobs})
        self.assertTrue(all(j["pool"]=="LOCAL_PYTHON" for j in jobs))
        self.assertFalse(any("workflow" in " ".join(x["argv"]) for x in jobs))
    def test_cache_is_source_and_command_sensitive(self):
        job=cli.jobs(ROOT,sys.executable,False)[0]
        a=cli.cachekey(job,"a"*40,"b"*64)
        self.assertNotEqual(a,cli.cachekey(job,"a"*40,"c"*64))
        changed=copy.deepcopy(job)
        changed["argv"].append("--unsafe")
        self.assertNotEqual(a,cli.cachekey(changed,"a"*40,"b"*64))
    def test_local_cache_never_counts_native_or_release(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            job={"id":"TEST","pool":"LOCAL_PYTHON",
                 "argv":[sys.executable,"-c","print('pass')"],"timeout":10}
            x=cli.run_one(job,path,path,path/"cache","a"*40,"b"*64,12,False,0)
            y=cli.run_one(job,path,path,path/"cache","a"*40,"b"*64,12,False,0)
            self.assertEqual(x["status"],"LOCAL_TEST_PASS")
            self.assertEqual(y["status"],"LOCAL_CACHE_HIT")
            self.assertIsNone(y["native_proof"])
            self.assertEqual(y["release_credit"],0)
    def test_queue_wait_is_float_when_clock_does_not_tick(self):
        # A coarse monotonic clock (Windows) can give a zero or negative delta; the
        # clamp must still yield a float so local_queue_p95_seconds keeps its type.
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            job={"id":"TEST","pool":"LOCAL_PYTHON",
                 "argv":[sys.executable,"-c","print('pass')"],"timeout":10}
            x=cli.run_one(job,path,path,path/"cache","a"*40,"b"*64,12,True,float("inf"))
            self.assertIsInstance(x["queue_wait_seconds"],float)
            self.assertEqual(x["queue_wait_seconds"],0.0)
    def test_local_cache_stales_on_content_change(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            job={"id":"TEST","pool":"LOCAL_PYTHON",
                 "argv":[sys.executable,"-c","print('pass')"],"timeout":10}
            cli.run_one(job,path,path,path/"cache","a"*40,"b"*64,12,False,0)
            z=cli.run_one(job,path,path,path/"cache","a"*40,"d"*64,12,False,0)
            self.assertEqual(z["status"],"LOCAL_TEST_PASS")
    def test_hash_manifest_detects_drift(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            head,inputs=cli.write_bundle(ROOT,path)
            cli.seal(path,head,inputs)
            cli.verify(ROOT,path,head,inputs)
            (path/"SPRINT_QUEUE.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError,"HASH_DRIFT"):
                cli.verify(ROOT,path,head,inputs)
    def test_stale_local_report_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            head,inputs=cli.write_bundle(ROOT,path)
            (path/"LOCAL_RUN.json").write_bytes(cli.canonical({"head":"0"*40}))
            with self.assertRaisesRegex(ValueError,"STALE_OR_PROMOTED_LOCAL_RESULT"):
                cli.seal(path,head,inputs)
    def test_ps1_does_not_hide_network_work(self):
        script=(SPRINT/"Start-JadeSprint.ps1").read_text(encoding='utf-8')
        for token in ("$FreshClone","$InstallOptionalDependencies","$Offline",
                      "$ExpectedHead","$NoCache","git clone","python.exe"):
            self.assertIn(token,script)
    def test_pinned_optional_dependencies(self):
        # Exact pins, not exact versions: Dependabot (pip-jade-sprint-minor-patch) owns the bump.
        txt=(SPRINT/"requirements-optional.txt").read_text(encoding='utf-8')
        pins=dict(line.split("==",1) for line in txt.split())
        self.assertEqual(sorted(pins),["coverage","playwright"])
        for name,version in pins.items():
            self.assertRegex(version,r"^\d+\.\d+\.\d+$",name)
    def test_pool_max_enforced_before_exec(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            with self.assertRaisesRegex(ValueError,"WORKER_BOUND_1_TO_4"):
                cli.local_run(ROOT,path,path/"cache","a"*40,"b"*64,8,12,True,False)
    def test_no_second_pages_deployer(self):
        script=(ROOT/".github"/"workflows"/"jade-sprint-n3-qualification.yml")
        self.assertNotIn("deploy-pages",script.read_text(encoding='utf-8'))

if __name__=="__main__":
    unittest.main()
