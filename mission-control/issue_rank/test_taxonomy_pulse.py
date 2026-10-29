"""Adversarial contracts for the additive, privacy-aware taxonomy pulse."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import taxonomy_pulse as pulse
import title_taxonomy as tax

HUB = "GBOGEB/pipeline-automation-hub"
QPS = "GBOGEB/cryoplant-project"
ABACUS = "GBOGEB/ABACUS"
HEADS = {
    HUB: {"head_sha": "a" * 40, "default_branch": "master", "private": False},
    QPS: {"head_sha": "b" * 40, "default_branch": "main", "private": True},
}
TIME = "2026-10-26T13:56:00+01:00"


def item(repo, number, title, kind="Issue", private=None):
    if private is None:
        private = repo == QPS
    return {
        "key": repo + "#" + str(number), "repo": repo, "number": number,
        "type": kind, "title": title, "private": private,
        "title_taxonomy": tax.parse_title(title, kind),
    }


def model(items=None, at=TIME, heads=None):
    return {
        "schema": "jade.issue-rank.v1", "fetched_at": at,
        "heads": copy.deepcopy(HEADS if heads is None else heads),
        "items": copy.deepcopy(items if items is not None else [
            item(HUB, 1, "fix(jade devops): census fails closed when blobs are missing", "PullRequest"),
            item(HUB, 2, "feat(watch): code-purple and gogreen telemetry", "Issue"),
            item(QPS, 3, "fix(secret supplier): restricted pricing", "Issue"),
        ]),
    }


class PulseIdentity(unittest.TestCase):
    def test_v2_source_model_schema_is_accepted_without_v1_alias(self):
        m = model()
        m["schema"] = "jade.issue-rank.v2"
        result = pulse.build(m, parser_sha="a" * 40)
        self.assertEqual(result["taxonomy_schema"], tax.SCHEMA)
        self.assertEqual(result["formal_credit_delta"], 0)

    def test_public_denominators_composites_and_overlap(self):
        r = pulse.build(model(), parser_sha="c" * 40)
        self.assertEqual(r["population"], {"total": 2, "issues": 1, "prs": 1})
        self.assertEqual(r["visibility"], "PUBLIC_PROJECTION")
        self.assertEqual(r["private_items_excluded"], 1)
        self.assertEqual(r["parser_pin_state"], "PINNED")
        self.assertNotIn(QPS, r["source_heads"])
        self.assertNotIn(QPS, r["rollups"])
        h = r["rollups"][HUB]
        self.assertEqual(sum(h["primary_family"].values()), 2)
        self.assertEqual(sum(h["single_composite"].values()), 2)
        self.assertEqual(h["single_composite"]["fix/jade-devops/census/fail-closed"], 1)
        self.assertGreater(sum(h["topic_memberships_nonadditive"].values()), h["total"])
        self.assertFalse(h["memberships_additive"])
        self.assertEqual(r["formal_credit_delta"], 0)
        serialized = json.dumps(r)
        for secret in (QPS, "secret supplier", "restricted pricing"):
            self.assertNotIn(secret, serialized)

    def test_private_local_opt_in_and_empty_population(self):
        r = pulse.build(model(), public=False)
        self.assertEqual(r["population"]["total"], 3)
        self.assertIn(QPS, r["source_heads"])
        self.assertEqual(r["visibility"], "PRIVATE_LOCAL_ONLY")
        empty = model([])
        self.assertEqual(pulse.build(empty)["population"]["total"], 0)
        self.assertIsNone(pulse.build(empty)["rollups"]["USER"]["typed_prefix_rate"])

    def test_no_double_count_from_nested_programme_code_or_lint(self):
        m = model([item(HUB, 1, "metrics: fix(test W51-C0): census failed closed")])
        report = pulse.build(m)
        s = report["rollups"]["USER"]
        self.assertEqual(s["total"], 1)
        self.assertEqual(sum(s["primary_family"].values()), 1)
        self.assertEqual(sum(s["single_composite"].values()), 1)
        self.assertTrue(s["code_memberships_nonadditive"])
        self.assertEqual(s["typed_prefix_rate"], 1.0)

    def test_source_population_preserves_zero_item_repository(self):
        m = model([item(HUB, 1, "fix: one")])
        r = pulse.build(m, public=False)
        self.assertEqual(r["rollups"][QPS]["total"], 0)
        self.assertEqual(r["rollups"][QPS]["issues"], 0)
        self.assertEqual(sum(r["rollups"]["USER"]["primary_family"].values()), 1)

    def test_history_has_two_source_pinned_points_and_long_form_csv(self):
        older = model([item(HUB, 1, "fix(watch): old")])
        current = model([item(HUB, 1, "fix(watch): new"), item(HUB, 2, "docs: new")],
                        at="2026-10-26T15:00:00+01:00")
        r = pulse.build(current, older, parser_sha="c"*40, previous_parser_sha="c"*40)
        self.assertEqual([x["wave"] for x in r["history_points"]], ["N", "N+1"])
        self.assertEqual([x["rollups"]["USER"]["total"] for x in r["history_points"]], [1, 2])
        self.assertTrue(r["delta"]["parser_identity_comparable"])
        csv = pulse.csv_view(r)
        self.assertIn(",N,", csv)
        self.assertIn(",N+1,", csv)
        self.assertIn("scope_denominator,additive", csv.splitlines()[0])
        r2 = pulse.build(current, older, parser_sha="d"*40, previous_parser_sha="c"*40)
        self.assertFalse(r2["delta"]["parser_identity_comparable"])
        self.assertEqual(r2["delta"]["classification_attribution"],
                         "WITHHELD_PARSER_VERSION_NOT_MATCHED")

    def test_empty_cluster_first_red_is_safe_and_additive(self):
        # Native first red 40329143161, Python 3.11/3.12:
        # taxonomy_pulse.py:125 IndexError when family==scope but clusters=[].
        x = item(HUB, 1, "fix(watch): status")
        projected = pulse.visible(model([x]), public=True)["items"][0]
        self.assertEqual(projected["technical_clusters"], [])
        facet = pulse.facets(projected)
        self.assertEqual(facet["scope"], "watch")
        self.assertEqual(facet["family"], "watch")
        self.assertEqual(facet["cluster"], "general")
        report = pulse.build(model([x]))
        self.assertEqual(report["rollups"]["USER"]["total"], 1)
        self.assertEqual(sum(report["rollups"]["USER"]["single_composite"].values()), 1)

    def test_empty_cluster_and_unscoped_title_stays_general(self):
        x = item(HUB, 1, "[U14] plain status note")
        projected = pulse.visible(model([x]), public=True)["items"][0]
        facet = pulse.facets(projected)
        self.assertEqual(facet["scope"], "unscoped")
        self.assertEqual(facet["family"], "general")
        self.assertEqual(facet["cluster"], "general")
        self.assertEqual(facet["action"], "unclassified")

    def test_reject_duplicates_unknown_ids_and_inconsistent_privacy(self):
        source = model()
        source["items"].append(copy.deepcopy(source["items"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ITEM_IDENTITY"):
            pulse.build(source)
        source = model()
        source["items"][0]["key"] = "other#1"
        with self.assertRaisesRegex(ValueError, "IDENTITY_REPO_MISMATCH"):
            pulse.build(source)
        source = model()
        source["items"][0]["private"] = True
        with self.assertRaisesRegex(ValueError, "ITEM_PRIVACY_HEAD_MISMATCH"):
            pulse.build(source)

    def test_reject_unpinned_or_unknown_taxonomy(self):
        source = model()
        source["heads"][HUB]["head_sha"] = "not-a-sha"
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_HEAD"):
            pulse.build(source)
        source = model()
        source["items"][0]["title_taxonomy"]["schema"] = "jade.unknown.v999"
        with self.assertRaisesRegex(ValueError, "TAXONOMY_SCHEMA_MISMATCH"):
            pulse.build(source)
        with self.assertRaisesRegex(ValueError, "INVALID_PARSER_SHA"):
            pulse.build(model(), parser_sha="deadbeef")


class PulseDelta(unittest.TestCase):
    def test_new_absent_and_reclassified_not_root_closed(self):
        before = model([item(HUB, 1, "fix(watch): census"), item(HUB, 2, "docs: older")])
        after = model([item(HUB, 1, "feat(watch): census fails closed"),
                       item(HUB, 3, "test(watch): integrity")],
                      at="2026-10-26T14:00:00+01:00")
        r = pulse.build(after, before)
        d = r["delta"]
        self.assertTrue(d["comparable"])
        self.assertEqual((d["newly_open_observed"], d["absent_from_open_not_verified_closed"],
                          d["persisting_open"], d["reclassified"]), (1, 1, 1, 1))
        self.assertEqual(d["new_by_primary_family"], {"test": 1})
        self.assertEqual(d["absent_by_primary_family"], {"docs": 1})
        self.assertIsNone(d["verified_closed"])
        self.assertEqual(d["classification_moves"][0]["evidence"],
                         "CLASSIFICATION_CHANGE_NOT_ROOT_CLOSURE")

    def test_scope_drift_withholds_comparison_not_fake_reductions(self):
        before = model([item(HUB, 1, "fix: first")])
        later = model([item(HUB, 1, "fix: first")], heads={HUB: HEADS[HUB]},
                      at="2026-10-26T15:00:00+01:00")
        d = pulse.build(later, before, public=False)["delta"]
        self.assertFalse(d["comparable"])
        self.assertEqual(d["reason"], "REPOSITORY_POPULATION_CHANGED")
        self.assertNotIn("absent_from_open_not_verified_closed", d)

    def test_reversed_time_and_type_rewrite_fail_closed(self):
        old = model([item(HUB, 1, "fix: first")], at="2026-10-27T10:00:00+01:00")
        with self.assertRaisesRegex(ValueError, "PULSE_TIMESTAMP_NOT_STRICTLY_LATER"):
            pulse.build(model([item(HUB, 1, "fix: newer")]), old)
        old = model([item(HUB, 1, "fix: first")])
        now = model([item(HUB, 1, "fix: first", "PullRequest")],
                    at="2026-10-26T16:00:00+01:00")
        with self.assertRaisesRegex(ValueError, "IDENTITY_ITEM_TYPE_MUTATED"):
            pulse.build(now, old)

    def test_csv_semantics_and_local_cli_roundtrip(self):
        r = pulse.build(model())
        view = pulse.csv_view(r)
        self.assertIn("scope_denominator,additive", view.splitlines()[0])
        self.assertIn("topic_memberships_nonadditive", view)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src, json_out, csv_out = base / "in.json", base / "out.json", base / "out.csv"
            src.write_text(json.dumps(model()), encoding="utf-8")
            self.assertEqual(pulse.main(["--current", str(src), "--json-out", str(json_out),
                                         "--csv-out", str(csv_out)]), 0)
            self.assertEqual(json.loads(json_out.read_text())["population"]["total"], 2)
            self.assertEqual(csv_out.read_text().splitlines()[0].split(",")[0], "observed_at")


if __name__ == "__main__":
    unittest.main()
