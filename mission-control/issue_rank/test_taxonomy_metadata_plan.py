"""Fail-closed metadata planner negative tests; no GitHub API needed."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import taxonomy_metadata_plan as planner
import title_taxonomy as tax

HUB = "GBOGEB/pipeline-automation-hub"
QPS = "GBOGEB/cryoplant-project"


def item(repo, n, title, private=False, labels=()):
    return {
        "key": f"{repo}#{n}", "number": n, "repo": repo, "type": "Issue",
        "private": private, "labels": list(labels), "title": title,
        "title_taxonomy": tax.parse_title(title, "Issue", labels),
    }


def source():
    return {"schema": planner.RANK_SCHEMA,
            "heads": {HUB: {"private": False, "head_sha": "a"*40},
                      QPS: {"private": True, "head_sha": "b"*40}},
            "items": [item(HUB, 1, "fix(watch): census fails closed", labels=["type:fix"]),
                      item(HUB, 2, "[U14] incomplete owner decision"),
                      item(QPS, 3, "fix(secret vendor): classified pricing", private=True)]}


class Metadata(unittest.TestCase):
    def test_safe_labels_keep_original_and_no_writes(self):
        m = source()
        original = copy.deepcopy(m)
        p = planner.propose(m, parser_sha="c"*40)
        self.assertEqual(m, original)
        self.assertEqual(len(p["proposals"]), 2)
        self.assertEqual(p["excluded_private"], 1)
        self.assertEqual(p["issue_title_rewrites"], 0)
        self.assertEqual(p["auto_label_writes"], 0)
        self.assertFalse(p["mutation_permitted"])
        self.assertNotIn(QPS, json.dumps(p))
        first = p["proposals"][0]
        self.assertIn("family:watch", first["labels_to_consider"])
        self.assertNotIn("type:fix", first["labels_to_consider"])
        self.assertEqual(p["proposals"][1]["status"], "NEEDS_EXPLICIT_TYPE_OWNER")
        self.assertNotIn("type:fix", p["proposals"][1]["labels_to_consider"])
        self.assertEqual(p["projection_sha256"], planner.propose(m, parser_sha="c"*40)["projection_sha256"])

    def test_v2_redacted_private_head_keeps_public_only_proposals(self):
        m = source()
        m["schema"] = "jade.issue-rank.v2"
        m["heads"][QPS]["head_sha"] = None
        m["items"] = [i for i in m["items"] if i["repo"] != QPS]
        proposal = planner.propose(m)
        self.assertEqual(len(proposal["proposals"]), 2)
        self.assertNotIn(QPS, json.dumps(proposal))
        m["heads"][HUB]["head_sha"] = None
        with self.assertRaisesRegex(ValueError, "SOURCE_SHA_UNVERIFIED"):
            planner.propose(m)

    def test_existing_type_conflict_is_human_review_only(self):
        s = source()
        s["items"][0]["labels"] = ["type:feat"]
        p = planner.propose(s)
        self.assertEqual(p["proposals"][0]["status"], "CONFLICT_OWNER_REVIEW")
        self.assertEqual(p["proposals"][0]["conflicting_existing_types"], ["type:feat"])
        self.assertFalse(p["proposals"][0]["authorized_write"])

    def test_private_requires_explicit_local_optin(self):
        pub = planner.propose(source())
        local = planner.propose(source(), allow_private=True)
        self.assertEqual(len(local["proposals"]), 3)
        self.assertIn(QPS, local["source_heads"])
        self.assertNotIn(QPS, pub["source_heads"])
        self.assertEqual(local["visibility"], "OWNER_PRIVATE_LOCAL")

    def test_reject_source_sha_schema_and_duplicate_identity(self):
        m = source()
        m["heads"][HUB]["head_sha"] = "not-sha"
        with self.assertRaisesRegex(ValueError, "SOURCE_SHA_UNVERIFIED"):
            planner.propose(m)
        m = source()
        m["items"][0]["title_taxonomy"]["schema"] = "foreign"
        with self.assertRaisesRegex(ValueError, "TAXONOMY_SCHEMA_MISMATCH"):
            planner.propose(m)
        m = source()
        m["items"].append(copy.deepcopy(m["items"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_IDENTITY"):
            planner.propose(m)

    def test_wrong_repo_privacy_labels_and_parser_pin_fail(self):
        m = source()
        m["items"][2]["private"] = False
        with self.assertRaisesRegex(ValueError, "PRIVACY_MISMATCH"):
            planner.propose(m)
        m = source()
        m["items"][0]["labels"] = [None]
        with self.assertRaisesRegex(ValueError, "LABEL_INVALID"):
            planner.propose(m)
        with self.assertRaisesRegex(ValueError, "PARSER_SHA_MISSING_OR_INVALID"):
            planner.propose(source(), parser_sha="too-short")

    def test_cli_never_changes_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp)/"source.json", Path(tmp)/"plan.json"
            src.write_text(json.dumps(source()), encoding="utf-8")
            before = src.read_bytes()
            self.assertEqual(planner.main(["--model", str(src), "--out", str(out)]), 0)
            self.assertEqual(src.read_bytes(), before)
            self.assertTrue(json.loads(out.read_text())["approval_required"])
            self.assertNotIn("classified pricing", out.read_text())


if __name__ == "__main__":
    unittest.main()
