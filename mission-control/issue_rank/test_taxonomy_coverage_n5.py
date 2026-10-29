"""N+5 independent coverage frontier for existing canonical taxonomy modules.

No production changes, no implicit reclassification, no private source bytes.
Tests target boundary classes in parser, N/N+1 pulse and HTML projection.
"""
from __future__ import annotations

import copy
import json
import unittest

import title_taxonomy as t
import taxonomy_explorer as e
import taxonomy_pulse as p

HUB = "GBOGEB/pipeline-automation-hub"
QPS = "GBOGEB/cryoplant-project"
T0 = "2026-10-26T12:00:00+00:00"
T1 = "2026-10-26T12:01:00+00:00"


def item(repo, num, title, private=False, kind="Issue"):
    return {"key": f"{repo}#{num}", "repo": repo, "number": num,
            "type": kind, "private": private, "title": title,
            "labels": [], "title_taxonomy": t.parse_title(title, kind)}


def model(rows, at=T0):
    return {"schema": p.RANK_SCHEMA, "fetched_at": at,
            "heads": {
                HUB: {"head_sha": "a"*40, "private": False, "default_branch": "master"},
                QPS: {"head_sha": "b"*40, "private": True, "default_branch": "main"}},
            "items": rows}


class BoundaryFrontier(unittest.TestCase):
    def test_aliases_never_rewrite_title_and_legacy_not_assumed_approved(self):
        for source in ("doc(watch): test", "docs(watch): test",
                       "fix(jade devops): census fails closed",
                       "fix(p-proces): first-red", "fix(p-process): first-red",
                       "metrics: CI(Watch): negative test"):
            with self.subTest(source=source):
                parsed = t.parse_title(source, "Issue")
                self.assertEqual(parsed["schema"], t.SCHEMA)
                self.assertTrue(parsed["family"])
                self.assertTrue(parsed["path"])
                self.assertTrue(isinstance(parsed["lint"], list))
        self.assertEqual(t.parse_title("doc(watch): notes", "Issue")["family"], "docs")

    def test_title_and_kind_metamorphism_preserves_explicit_action(self):
        for action in ("fix", "feat", "test", "docs", "ci"):
            with self.subTest(action=action):
                title = f"{action}(watch): census integrity"
                a = t.parse_title(title, "Issue")
                b = t.parse_title(title, "PullRequest")
                self.assertEqual(a["family"], action)
                self.assertEqual(b["family"], action)
                self.assertEqual(a["classification"], "EXPLICIT_ACTION")

    def test_full_privacy_boundary_across_two_renderers(self):
        data = model([item(HUB, 11, "fix(watch): census fails closed"),
                      item(QPS, 12, "fix(secret OEM): BID-SENSITIVE-STRING", True)])
        before = copy.deepcopy(data)
        projected = p.build(data, public=True, parser_sha="c"*40)
        rendered = e.render(data)
        self.assertEqual(data, before)
        self.assertEqual(projected["population"]["total"], 1)
        self.assertEqual(projected["private_items_excluded"], 1)
        self.assertNotIn(QPS, json.dumps(projected))
        self.assertNotIn(QPS, rendered)
        self.assertNotIn("BID-SENSITIVE-STRING", rendered)
        self.assertEqual(sum(projected["rollups"]["USER"]["single_composite"].values()), 1)

    def test_unclustered_title_zero_division_and_additive_invariants(self):
        data = model([item(HUB, 3, "[U14] proof"),
                      item(HUB, 4, "feat(watch): document text")])
        r = p.build(data)
        self.assertEqual(r["rollups"]["USER"]["total"], 2)
        self.assertEqual(sum(r["rollups"]["USER"]["primary_family"].values()), 2)
        self.assertEqual(sum(r["rollups"]["USER"]["single_composite"].values()), 2)
        self.assertEqual(r["rollups"][QPS]["total"] if QPS in r["rollups"] else 0, 0)
        self.assertEqual(r["formal_credit_delta"], 0)

    def test_matched_parser_proof_and_unmatched_version_withholds_attribution(self):
        old = model([item(HUB, 1, "fix(watch): census")])
        new = model([item(HUB, 1, "fix(watch): census integrity"),
                     item(HUB, 2, "docs: new")], at=T1)
        matched = p.build(new, old, parser_sha="a"*40, previous_parser_sha="a"*40)
        self.assertTrue(matched["delta"]["parser_identity_comparable"])
        self.assertEqual(matched["delta"]["newly_open_observed"], 1)
        self.assertIsNone(matched["delta"]["verified_closed"])
        unmatched = p.build(new, old, parser_sha="b"*40, previous_parser_sha="a"*40)
        self.assertFalse(unmatched["delta"]["parser_identity_comparable"])
        self.assertEqual(unmatched["delta"]["classification_attribution"],
                         "WITHHELD_PARSER_VERSION_NOT_MATCHED")

    def test_refuse_wrong_head_private_mismatch_unknown_schema(self):
        data = model([item(HUB, 11, "fix: title")])
        data["heads"][HUB]["head_sha"] = "bad"
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_HEAD"):
            p.build(data)
        data = model([item(QPS, 3, "fix(secret): note", False)])
        with self.assertRaisesRegex(ValueError, "PRIVACY"):
            p.build(data)
        with self.assertRaisesRegex(ValueError, "PRIVATE_REPO_INCONSISTENT"):
            e.render(data)
        data = model([item(HUB, 1, "fix: ok")])
        data["items"][0]["title_taxonomy"]["schema"] = "unknown"
        with self.assertRaisesRegex(ValueError, "TAXONOMY_SCHEMA_MISMATCH"):
            p.build(data)

    def test_markup_escaping_and_source_url_not_trusted(self):
        source = "<img src=x onerror=alert(1)>"
        d = model([item(HUB, 4, "fix(watch): " + source)])
        d["items"][0]["url"] = "javascript:alert(99)"
        html = e.render(d)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("javascript:alert(99)", html)
        self.assertIn("&lt;img", html)
        self.assertIn("https://github.com/" + HUB + "/issues/4", html)

    def test_repeated_run_determinism_and_source_not_mutated(self):
        d = model([item(HUB, 1, "fix(watch): census")])
        a = p.build(d, parser_sha="f"*40)
        b = p.build(copy.deepcopy(d), parser_sha="f"*40)
        self.assertEqual(p.canonical(a), p.canonical(b))
        self.assertEqual(a["visible_projection_sha256"], b["visible_projection_sha256"])
        self.assertFalse(a["closure_authority"])


if __name__ == "__main__":
    unittest.main()
