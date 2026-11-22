import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

import test_report

report = test_report.report
development = report.development


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.fx = test_report.ReportTests()
        self.fx.setUp()
        self.fx.write("README.md", "# Repository purpose\nEntry: main.py\n")
        self.fx.write("docs/ADR-001.md", "# ADR-001 — source decision\n\n## Status\nPROPOSED\n\n**Owner:** Source owner\n")
        self.fx.commit()
        self.snap = self.fx.read()
        self.now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
        self.profile = dict(purpose="Fixture purpose", lane="Fixture lane", visibility="private",
            purpose_source="README.md", pipelines=[dict(id="pipeline", label="Fixture pipeline",
            entries=["main.py"], workflow=".github/workflows/ci.yml", scope_source="README.md",
            supplier="owner", input="source", process="validate", output="receipt", customer="reviewer")],
            decisions=[dict(path="docs/ADR-001.md", informs=["pipeline"], relation="REVIEW_CROSSWALK")])
        wf = self.snap["workflows"][0]
        self.obs = dict(repository="owner/repo", workflow=wf["path"], job_key="build",
            source_sha=self.snap["source_sha"], workflow_blob_oid=wf["blob_oid"],
            observed_at="2026-11-18T11:00:00Z", completed_at="2026-11-18T10:00:00Z",
            status="completed", conclusion="failure", run_id=100, job_id=200, run_attempt=1,
            run_url="https://github.com/owner/repo/actions/runs/100",
            job_url="https://github.com/owner/repo/actions/runs/100/job/200")

    def tearDown(self):
        self.fx.tearDown()

    def extend(self, records=()):
        return development.extend(copy.deepcopy(self.snap), self.profile, self.fx.root,
            report.git, report.source_link, report.workflows, records, self.now)["development"]

    def test_profile_scope_and_sipoc(self):
        doc = self.extend()
        p = doc["pipelines"][0]
        self.assertEqual(p["entry_loc"], 3)
        self.assertEqual(p["sipoc"]["input"], "source")
        self.assertEqual(p["layers"], [["build"], ["verify"]])

    def test_explicit_status_is_source_declaration_not_acceptance(self):
        adr = self.extend()["decision_records"][0]
        self.assertEqual(adr["acceptance"], "NOT_EVALUATED")
        self.assertIn("PROPOSED", [d["value"] for d in adr["declarations"]])
        self.assertEqual(adr["relation"], "REVIEW_CROSSWALK_NOT_HARD_DEPENDENCY")

    def test_accepted_word_does_not_authorize(self):
        fields = development.decision_fields("# Decision\nStatus: ACCEPTED\n")
        self.assertEqual(fields["acceptance"], "NOT_EVALUATED")

    def test_reported_failure_maps_to_consumer(self):
        nodes = self.extend([self.obs])["pipelines"][0]["nodes"]
        self.assertEqual(nodes[0]["evidence"]["state"], "REPORTED_FAILURE")
        self.assertEqual(nodes[1]["reported_failed_prerequisites"], ["build"])
        self.assertTrue(all(n["execution_readiness"] == "NOT_EVALUATED" for n in nodes))

    def test_reported_success_does_not_imply_readiness(self):
        self.obs["conclusion"] = "success"
        node = self.extend([self.obs])["pipelines"][0]["nodes"][0]
        self.assertEqual(node["evidence"]["state"], "REPORTED_SUCCESS")
        self.assertEqual(node["execution_readiness"], "NOT_EVALUATED")

    def test_unobserved_prerequisite_stays_unknown(self):
        node = self.extend()["pipelines"][0]["nodes"][1]
        self.assertEqual(node["unobserved_prerequisites"], ["build"])

    def test_source_drift_rejected(self):
        self.obs["source_sha"] = "0" * 40
        node = self.extend([self.obs])["pipelines"][0]["nodes"][0]
        self.assertEqual(node["evidence"]["reason"], "SOURCE_DRIFT")

    def test_workflow_drift_rejected(self):
        self.obs["workflow_blob_oid"] = "0" * 40
        self.assertEqual(self.extend([self.obs])["pipelines"][0]["nodes"][0]["evidence"]["reason"], "SOURCE_DRIFT")

    def test_fresh_collection_cannot_refresh_old_job(self):
        self.obs["completed_at"] = "2020-01-01T00:00:00Z"
        node = self.extend([self.obs])["pipelines"][0]["nodes"][0]
        self.assertEqual(node["evidence"]["state"], "UNKNOWN")
        self.assertEqual(node["evidence"]["reason"], "FUTURE_OR_STALE_OBSERVATION")

    def test_missing_completion_rejected(self):
        del self.obs["completed_at"]
        self.assertEqual(self.extend([self.obs])["pipelines"][0]["nodes"][0]["evidence"]["state"], "UNKNOWN")

    def test_future_collection_rejected(self):
        self.obs["observed_at"] = "2099-01-01T00:00:00Z"
        self.assertEqual(self.extend([self.obs])["pipelines"][0]["nodes"][0]["evidence"]["state"], "UNKNOWN")

    def test_missing_run_identity_rejected(self):
        self.obs["run_id"] = None
        self.assertEqual(self.extend([self.obs])["pipelines"][0]["nodes"][0]["evidence"]["state"], "UNKNOWN")

    def test_wrong_repository_job_url_rejected(self):
        self.obs["job_url"] = "https://github.com/someone/else/actions/runs/100/job/200"
        self.assertEqual(self.extend([self.obs])["pipelines"][0]["nodes"][0]["evidence"]["state"], "UNKNOWN")

    def test_latest_failure_not_overridden_by_old_green(self):
        older = dict(self.obs, conclusion="success", observed_at="2026-11-18T10:30:00Z")
        self.assertEqual(self.extend([older, self.obs])["pipelines"][0]["nodes"][0]["evidence"]["state"], "REPORTED_FAILURE")

    def test_duplicate_pipeline_ids_rejected(self):
        self.profile["pipelines"] *= 2
        with self.assertRaises(ValueError):
            self.extend()

    def test_missing_workflow_rejected(self):
        self.profile["pipelines"][0]["workflow"] = ".github/workflows/missing.yml"
        with self.assertRaises(ValueError):
            self.extend()

    def test_no_crosswalk_to_missing_pipeline(self):
        self.profile["decisions"][0]["informs"] = ["missing"]
        with self.assertRaises(ValueError):
            self.extend()

    def test_profile_symlink_refused(self):
        (self.fx.root / "linked.py").symlink_to("main.py")
        self.fx.commit()
        self.snap = self.fx.read()
        self.profile["pipelines"][0]["entries"] = ["linked.py"]
        with self.assertRaises(ValueError):
            self.extend()

    def test_crosswalk_cannot_add_hard_edges(self):
        self.profile["decisions"][0]["relation"] = "HARD_DAG"
        with self.assertRaises(ValueError):
            self.extend()

    def test_cli_profile_and_html_integration(self):
        registry = Path(self.fx.temp.name) / "profiles.json"
        registry.write_text(json.dumps(dict(schema="jade.repo-bios.profiles.v1", repositories={"owner/repo": self.profile})))
        out = Path(self.fx.temp.name) / "development"
        report.main(["--repo", f"owner/repo={self.fx.root}", "--profiles", str(registry), "--out", str(out)])
        data = json.loads((out / "report.json").read_text())
        self.assertEqual(data["repositories"][0]["selected_pipeline_entry_loc"], 3)
        page = (out / "index.html").read_text()
        self.assertIn("function drawPipeline", page)
        self.assertIn("renderDevelopment(r,s)", page)


if __name__ == "__main__":
    unittest.main()
