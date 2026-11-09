"""Adversarial, offline acceptance tests for the JADE portfolio consumer.

Synthetic observations exercise evidence boundaries. Integration cases call the
real source owners against the checked-in, hash-bound JADE history.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import portfolio_readiness as portfolio


BASE_SHA = "897298dc3ed1a45607121b205617d4c103e7b226"
OTHER_SHA = "d" * 40
AS_OF = "2026-11-09T11:00:00Z"
AT = datetime(2026, 11, 9, 11, tzinfo=timezone.utc)


def observation(*rows, frontier=None):
    return {
        "schema": "jade.portfolio-observation.v1",
        "captured_at": "2026-11-09T10:00:00Z",
        "repos": list(rows),
        "frontier": frontier or [],
    }


def task(identity="A", repo="GBOGEB/ABACUS", cluster="source", **changes):
    value = {
        "id": identity,
        "cluster": cluster,
        "title": "Repair an observed defect",
        "intent": "Preserve evidence while fixing the source",
        "target_repo": repo,
        "state": "READY",
        "phase": "P0_CONTROL",
        "crew": "BUILDER",
        "source_sha": BASE_SHA,
        "t0_ref": f"https://github.com/{repo}/issues/12",
        "dov": ["Exact-source regression passes, including failure path"],
        "dod": ["Independent review and owner acceptance recorded"],
        "touch_paths": ["README.md"],
        "write_pr": True,
        "depends_on": [],
    }
    value.update(changes)
    return value


def plan(*tasks, **changes):
    value = {
        "schema": "jade.portfolio-plan.v1",
        "clusters": [{"id": c, "title": c} for c in sorted({t["cluster"] for t in tasks})],
        "tasks": list(tasks),
        "max_parallel": 2,
        "per_cluster": 1,
        "open_stack": 0,
    }
    value.update(changes)
    return value


def issue_snapshot():
    repo = "GBOGEB/ABACUS"
    return {
        "schema": "jade.issue-rank.snapshot.v2", "owner": "GBOGEB",
        "fetched_at": "2026-11-09T10:00:00Z",
        "repos": {repo: {
            "private": False, "default_branch": "main", "head_sha": OTHER_SHA,
            "prs": [], "issues": [{
                "repo": repo, "number": 1, "type": "Issue", "title": "[P0] Synthetic issue",
                "url": "https://github.com/GBOGEB/ABACUS/issues/1",
                "created_at": "2026-11-09T08:00:00Z", "updated_at": "2026-11-09T08:00:00Z",
                "labels": [], "assignees": [], "comments": [], "refs_in": [],
                "body": "## DOV\n- [ ] Exact-head tests\n## DOD\n- [ ] Owner acceptance",
            }],
        }},
    }


class ObservationBoundaryTests(unittest.TestCase):
    def test_no_observation_and_zero_checks_are_distinct(self):
        missing = portfolio.observations(None, AT, set())
        empty = portfolio.observations(observation({
            "repo": "GBOGEB/ABACUS", "head_sha": OTHER_SHA,
            "check_counts": {"success": 0, "failure": 0},
        }), AT, set())
        self.assertEqual("NOT_SUPPLIED", missing["status"])
        self.assertEqual([], missing["repos"])
        self.assertEqual(0, empty["repos"][0]["check_counts"]["success"])
        self.assertEqual("NOT_REQUALIFIED", empty["repos"][0]["current_qualification"])
        self.assertFalse(empty["full_census"])

    def test_omitted_check_counts_stay_null(self):
        result = portfolio.observations(observation({"repo": "GBOGEB/ABACUS"}), AT, set())
        self.assertIsNone(result["repos"][0]["check_counts"])
        self.assertFalse(result["repos"][0]["check_collection_complete"])

    def test_bad_counts_fail_instead_of_becoming_zero(self):
        for counts in ({"success": -1}, {"failure": True}, {"success": 0.5}, {"unknown_metric": 2}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                portfolio.observations(observation({"repo": "GBOGEB/ABACUS", "check_counts": counts}), AT, set())

    def test_duplicate_repositories_and_future_receipts_are_rejected(self):
        row = {"repo": "GBOGEB/ABACUS"}
        with self.assertRaises(ValueError):
            portfolio.observations(observation(row, row), AT, set())
        future = observation(row)
        future["captured_at"] = "2026-11-10T10:00:00Z"
        with self.assertRaises(ValueError):
            portfolio.observations(future, AT, set())
        with self.assertRaises(ValueError):
            portfolio.observations(observation({**row, "observed_at": "2026-11-09T10:00:01Z"}), AT, set())

    def test_unknown_frontier_repository_is_rejected(self):
        with self.assertRaises(ValueError):
            portfolio.observations(observation({"repo": "GBOGEB/ABACUS"}, frontier=[
                {"repository": "GBOGEB/CODEX", "head_sha": OTHER_SHA}
            ]), AT, set())

    def test_malformed_or_floating_head_is_rejected(self):
        for sha in ("main", "abcd123", "G" * 40, 12):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                portfolio.observations(observation({"repo": "GBOGEB/ABACUS", "head_sha": sha}), AT, set())

    def test_private_raw_evidence_does_not_escape_observation(self):
        marker = "PRIVATE_RAW_PAYLOAD_NEVER_PUBLISH"
        result = portfolio.observations(observation({
            "repo": "GBOGEB/synthetic-private", "private": True, "head_sha": OTHER_SHA,
            "raw_body": marker, "comments": [marker], "check_counts": {"failure": 4},
            "source_urls": [f"https://github.com/GBOGEB/synthetic-private/commit/{OTHER_SHA}"],
        }), AT, set())
        encoded = json.dumps(result)
        self.assertNotIn(marker, encoded)
        self.assertNotIn(OTHER_SHA, encoded)
        self.assertNotIn("/commit/", encoded)
        self.assertEqual("UNKNOWN_PRIVATE_OWNER", result["repos"][0]["current_qualification"])

    def test_public_raw_bodies_are_not_forwarded(self):
        result = portfolio.observations(observation({
            "repo": "GBOGEB/ABACUS", "body": "RAW_BODY_MARKER", "comments": ["RAW_COMMENT_MARKER"],
        }), AT, set())
        self.assertNotIn("RAW_BODY_MARKER", json.dumps(result))
        self.assertNotIn("RAW_COMMENT_MARKER", json.dumps(result))

    def test_release_metadata_does_not_smuggle_raw_bodies(self):
        result = portfolio.observations(observation({
            "repo": "GBOGEB/ABACUS", "latest_release": {
                "tag_name": "v0.1.0", "body": "RAW_RELEASE_BODY_MARKER",
                "comments": ["RAW_RELEASE_COMMENT_MARKER"],
            },
        }), AT, set())
        self.assertFalse("RAW_RELEASE_BODY_MARKER" in json.dumps(result), "raw release body leaked")
        self.assertFalse("RAW_RELEASE_COMMENT_MARKER" in json.dumps(result), "raw release comments leaked")

    def test_unsafe_or_malformed_links_are_removed_without_crashing(self):
        for url in ("javascript:alert(1)", "data:text/html,hello", "http://github.com/GBOGEB/ABACUS",
                    "https://github.com.evil.example/GBOGEB/ABACUS", "https://user@github.com/GBOGEB/ABACUS",
                    "https://github.com:bad/GBOGEB/ABACUS", "https://[broken", "https://github.com:999999/x"):
            with self.subTest(url=url):
                self.assertIsNone(portfolio.safe_url(url))
        self.assertEqual("https://github.com/GBOGEB/ABACUS/pull/12",
                         portfolio.safe_url("https://github.com/GBOGEB/ABACUS/pull/12"))


class ProposalSafetyTests(unittest.TestCase):
    def test_every_task_requires_explicit_dov_and_dod(self):
        for key in ("dov", "dod"):
            for value in (None, [], [""], "PASS"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    portfolio.proposal(plan(task(**{key: value})), BASE_SHA, set())

    def test_proposal_cannot_claim_done_or_running(self):
        for state in ("DONE", "RUNNING", "PASS"):
            with self.subTest(state=state), self.assertRaises(ValueError):
                portfolio.proposal(plan(task(state=state)), BASE_SHA, set())

    def test_cycles_and_unknown_dependencies_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            portfolio.proposal(plan(task("A", depends_on=["B"]), task("B", depends_on=["A"])), BASE_SHA, set())
        with self.assertRaisesRegex(ValueError, "unknown"):
            portfolio.proposal(plan(task(depends_on=["MISSING"])), BASE_SHA, set())

    def test_kahn_waves_keep_required_sequential_work_separate(self):
        result = portfolio.proposal(plan(task("A"), task("B", depends_on=["A"]),
                                         task("C", repo="GBOGEB/CODEX", cluster="other")), BASE_SHA, set())
        self.assertEqual([["A", "C"], ["B"]], result["waves"])
        self.assertIn({"id": "B", "reason": "DEPENDENCY_NOT_DONE"}, result["matrix"]["held"])
        self.assertFalse(result["matrix"]["authority"]["dispatch_performed"])

    def test_only_two_disjoint_candidates_can_enter_one_pulse(self):
        tasks = [task(str(i), repo=f"GBOGEB/repo-{i}", cluster=f"c{i}") for i in range(4)]
        result = portfolio.proposal(plan(*tasks), BASE_SHA, set())
        self.assertEqual(2, len(result["matrix"]["on"]))
        self.assertEqual(2, sum(row["reason"] == "PARALLEL_CAP" for row in result["matrix"]["held"]))
        self.assertTrue(all(row["dispatch"] == "CANDIDATE_NOT_LAUNCHED" for row in result["matrix"]["on"]))
        for cap in (0, 3, True):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                portfolio.proposal(plan(*tasks, max_parallel=cap), BASE_SHA, set())

    def test_same_filename_in_distinct_repositories_is_disjoint(self):
        result = portfolio.proposal(plan(task("A"), task("B", repo="GBOGEB/CODEX", cluster="other")), BASE_SHA, set())
        self.assertEqual({"A", "B"}, {row["id"] for row in result["matrix"]["on"]})

    def test_same_repository_path_collision_is_held(self):
        result = portfolio.proposal(plan(task("A"), task("B", cluster="other")), BASE_SHA, set())
        self.assertEqual(["A"], [row["id"] for row in result["matrix"]["on"]])
        self.assertIn({"id": "B", "reason": "OVERLAPPING_PATHS"}, result["matrix"]["held"])

    def test_path_aliases_cannot_dodge_overlap(self):
        for path in ("./README.md", "a/../README.md", "/README.md", "a//b", "a\\b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                portfolio.proposal(plan(task(touch_paths=[path])), BASE_SHA, set())

    def test_wrong_planning_source_holds_task_without_dispatch(self):
        result = portfolio.proposal(plan(task(source_sha=OTHER_SHA)), BASE_SHA, set())
        self.assertEqual([], result["matrix"]["on"])
        self.assertIn({"id": "A", "reason": "STALE_SOURCE_SHA"}, result["matrix"]["held"])

    def test_private_task_raw_fields_are_not_a_public_escape_hatch(self):
        private = "GBOGEB/synthetic-private"
        value = plan(task(repo=private, target_head_sha=OTHER_SHA, raw_body="PRIVATE_TASK_RAW_PAYLOAD"))
        result = portfolio.proposal(value, BASE_SHA, {private})
        rendered = json.dumps(result)
        self.assertFalse("PRIVATE_TASK_RAW_PAYLOAD" in rendered, "private task payload leaked")
        self.assertFalse(OTHER_SHA in rendered, "private target head leaked")
        self.assertFalse(f"https://github.com/{private}/" in rendered, "private source link leaked")


class CanonicalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA)

    def test_canonical_owner_projections_are_used_and_remain_historical(self):
        actual = self.baseline
        boundary = portfolio.owner("private_boundary")
        self.assertEqual(boundary.project(portfolio.owner("gate12").project(portfolio.JADE)), actual["gate12_frozen"])
        self.assertEqual(boundary.project(portfolio.owner("rolling5").project(portfolio.JADE)), actual["rolling5_historical"])
        self.assertEqual(["P0001", "P0002", "P0003", "P0004", "P0005"], [r["id"] for r in actual["history"]])
        self.assertEqual("2026-11-04", actual["history"][-1]["observed_date"])
        self.assertTrue(all(not row["current_native_qualification"] for row in actual["history"]))
        self.assertIsNone(actual["authority"]["live_weighted_closure_rate"])
        self.assertIsNone(actual["authority"]["current_point_release_readiness"])
        self.assertEqual("HOLD", actual["authority"]["merge_admission"])
        self.assertFalse(actual["watch"]["enabled"])

    def test_source_match_does_not_promote_historical_green_to_current_pass(self):
        historic = next(row for row in self.baseline["source_comparisons"] if row["historical_sha"])
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, observation=observation({
            "repo": historic["repository"], "head_sha": historic["historical_sha"],
            "check_counts": {"success": 58, "failure": 0}, "check_collection_complete": True,
        }))
        row = next(r for r in result["source_comparisons"] if r["repository"] == historic["repository"])
        self.assertEqual("SOURCE_MATCH_ONLY", row["source_comparison"])
        self.assertIsNone(row["current_gate_pass"])
        self.assertIsNone(result["authority"]["current_point_release_readiness"])

    def test_new_source_head_invalidates_historical_identity(self):
        historic = next(row for row in self.baseline["source_comparisons"] if row["historical_sha"])
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, observation=observation({
            "repo": historic["repository"], "head_sha": OTHER_SHA,
        }))
        row = next(r for r in result["source_comparisons"] if r["repository"] == historic["repository"])
        self.assertEqual("SOURCE_CHANGED", row["source_comparison"])
        self.assertIsNone(row["current_gate_pass"])

    def test_render_time_alone_is_no_update(self):
        first = copy.deepcopy(self.baseline)
        result = portfolio.project(as_of="2026-11-09T12:00:00Z", source_sha=BASE_SHA, previous=first)
        self.assertEqual("NO_UPDATE", result["delta"]["notification"])
        self.assertFalse(result["delta"]["material_change"])
        self.assertTrue(result["delta"]["basis_comparable"])

    def test_canonical_issue_snapshot_is_projected_without_inventing_population_credit(self):
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, issue_snapshot=issue_snapshot())
        self.assertEqual("SOURCE_OWNER_PROJECTION", result["issues"]["status"])
        self.assertEqual(1, result["issues"]["public_open_items"])
        self.assertFalse(result["issues"]["full_population_qualified"])
        self.assertEqual("GBOGEB/ABACUS#1", result["issues"]["model"]["items"][0]["key"])
        self.assertIsNone(result["authority"]["live_weighted_closure_rate"])

    def test_issue_and_repository_observations_cannot_form_a_mixed_source_pulse(self):
        snap = issue_snapshot()
        same = observation({"repo": "GBOGEB/ABACUS", "head_sha": OTHER_SHA})
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, issue_snapshot=snap, observation=same)
        self.assertEqual(1, result["issues"]["public_open_items"])
        wrong = observation({"repo": "GBOGEB/ABACUS", "head_sha": "e" * 40})
        with self.assertRaisesRegex(ValueError, "MIXED_PULSE"):
            portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, issue_snapshot=snap, observation=wrong)

    def test_unchanged_issue_snapshot_does_not_notify_for_derived_age_alone(self):
        snap = issue_snapshot()
        first = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, issue_snapshot=snap)
        later = portfolio.project(as_of="2026-11-09T12:00:00Z", source_sha=BASE_SHA,
                                  issue_snapshot=snap, previous=first)
        self.assertEqual("NO_UPDATE", later["delta"]["notification"])

    def test_changed_planning_sha_is_not_a_no_update(self):
        result = portfolio.project(as_of="2026-11-09T12:00:00Z", source_sha=OTHER_SHA,
                                   previous=copy.deepcopy(self.baseline))
        self.assertFalse(result["delta"]["basis_comparable"])
        self.assertNotEqual("NO_UPDATE", result["delta"]["notification"])

    def test_previous_snapshot_schema_and_time_must_be_compatible(self):
        for changes in ({"schema": "arbitrary"}, {"as_of": "2026-11-10T00:00:00Z"}):
            prior = copy.deepcopy(self.baseline)
            prior.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, previous=prior)

    def test_hash_bound_history_rejects_modified_snapshot_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            snapshot = {"source": {"observed_date": "2026-11-04"}, "rows": [], "metrics": {"unknown": 1}}
            data = json.dumps(snapshot).encode()
            (root / "data/pulse.json").write_bytes(data)
            (root / "data/ROLLING5_PULSES.json").write_text(json.dumps({"pulses": [{
                "id": "P1", "observed_date": "2026-11-04", "snapshot": "data/pulse.json",
                "snapshot_sha256": hashlib.sha256(data).hexdigest(),
            }]}), encoding="utf-8", newline="\n")
            self.assertEqual("P1", portfolio.history_view(root, AT)[0]["id"])
            (root / "data/pulse.json").write_bytes(data + b"\n")
            with self.assertRaisesRegex(ValueError, "snapshot drift"):
                portfolio.history_view(root, AT)

    def test_public_model_does_not_leak_newly_declared_private_repository_evidence(self):
        private = "GBOGEB/synthetic-private"
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA,
                                   observation=observation({"repo": private, "private": True, "head_sha": OTHER_SHA}),
                                   plan=plan(task(repo=private, target_head_sha=OTHER_SHA,
                                                  raw_body="PRIVATE_TASK_RAW_PAYLOAD")))
        text = json.dumps(result)
        self.assertFalse(OTHER_SHA in text, "private target head leaked into full model")
        self.assertFalse("PRIVATE_TASK_RAW_PAYLOAD" in text, "private payload leaked into full model")
        self.assertFalse(f"https://github.com/{private}/" in text, "private link leaked into full model")


class DashboardBoundaryTests(unittest.TestCase):
    def test_html_payloads_do_not_create_nodes_or_event_handlers(self):
        payload = '<img src=x onerror="window.PORTFOLIO_ATTACK=1">'
        value = plan(task(title=payload, intent='</script><script>window.PORTFOLIO_ATTACK=1</script>'))
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, plan=value,
                                   observation=observation({"repo": "GBOGEB/ABACUS"}, frontier=[{
                                       "repository": "GBOGEB/ABACUS", "id": "P1", "status": payload,
                                       "url": "javascript:alert(1)", "blocker": payload,
                                   }]))
        page = portfolio.artifacts(result)["index.html"].decode()

        class Inspector(HTMLParser):
            unsafe = []

            def handle_starttag(self, tag, attrs):
                for key, val in attrs:
                    if key.startswith("on") or (key in {"href", "src"} and val and val.startswith("javascript:")):
                        self.unsafe.append((tag, key, val))
                if tag == "img":
                    self.unsafe.append((tag, attrs))

        inspector = Inspector()
        inspector.feed(page)
        self.assertEqual([], inspector.unsafe)
        self.assertNotIn('<script>window.PORTFOLIO_ATTACK=1</script>', page)

    def test_csv_formula_and_mermaid_label_injection_are_neutralized(self):
        value = plan(task(title='=HYPERLINK("https://evil.example")', intent="@command"))
        result = portfolio.project(as_of=AS_OF, source_sha=BASE_SHA, plan=value)
        files = portfolio.artifacts(result)
        import csv
        import io
        row = next(csv.DictReader(io.StringIO(files["action_queue.csv"].decode())))
        self.assertTrue(row["title"].startswith("'="))
        self.assertTrue(row["intent"].startswith("'@"))
        self.assertNotIn('"https://evil.example"', files["execution_dag.mmd"].decode())


if __name__ == "__main__":
    unittest.main()
