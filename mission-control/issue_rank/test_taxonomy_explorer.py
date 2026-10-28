"""Negative and positive contract tests for offline taxonomy explorer."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import taxonomy_explorer as explorer
import title_taxonomy as tax

HUB = "GBOGEB/pipeline-automation-hub"
QPS = "GBOGEB/cryoplant-project"


def item(repo, number, title, kind="Issue", private=False, labels=()):
    return {
        "repo": repo, "number": number, "key": repo + "#" + str(number),
        "type": kind, "title": title, "private": private,
        "url": "javascript:alert('xss')",  # generator MUST ignore untrusted source URL
        "title_taxonomy": tax.parse_title(title, kind, labels),
    }


def model():
    return {
        "schema": explorer.RANK_SCHEMA,
        "fetched_at": "2026-10-26T13:56:00+01:00",
        "heads": {
            HUB: {"head_sha": "a" * 40, "private": False},
            QPS: {"head_sha": "b" * 40, "private": True},
        },
        "items": [
            item(HUB, 11, "fix(jade devops): census fails closed", "PullRequest"),
            item(HUB, 12, "feat(watch): GoGREEN integrity; [U14]", labels=["everred"]),
            item(QPS, 7, "fix(secret supplier): CLASSIFIED-PRIVATE-778", private=True),
        ],
    }


class WorkItemParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = 0
        self.selects = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and "data-repo" in attrs:
            self.rows += 1
        if tag == "select":
            self.selects.add(attrs.get("id"))


class Explorer(unittest.TestCase):
    def test_public_default_hides_private_titles_repos_and_unsafe_urls(self):
        page = explorer.render(model())
        self.assertIn("PUBLIC_PROJECTION", page)
        self.assertIn("Private items excluded: 1", page)
        self.assertNotIn(QPS, page)
        self.assertNotIn("CLASSIFIED-PRIVATE-778", page)
        self.assertNotIn("secret supplier", page)
        self.assertNotIn("javascript:alert", page)
        self.assertIn("fix/JADE/DEVOPS", page)
        self.assertIn("data-cluster=\"census|fail-closed\"", page)
        self.assertIn("/pull/11", page)
        self.assertIn("/issues/12", page)
        self.assertIn("No merge / release / engineering credit", page)

    def test_v2_redacted_private_head_is_allowed_but_public_head_is_required(self):
        m = model()
        m["schema"] = "jade.issue-rank.v2"
        m["heads"][QPS]["head_sha"] = None
        m["items"] = [i for i in m["items"] if i["repo"] != QPS]
        page = explorer.render(m)
        self.assertIn("PUBLIC_PROJECTION", page)
        self.assertNotIn(QPS, page)
        m["heads"][HUB]["head_sha"] = None
        with self.assertRaisesRegex(ValueError, "INVALID_REPO_OR_HEAD"):
            explorer.render(m)

    def test_filters_and_peer_counts_have_real_targets(self):
        page = explorer.render(model())
        parser = WorkItemParser()
        parser.feed(page)
        self.assertEqual(parser.rows, 2)
        self.assertEqual(parser.selects, {
            "f-repo", "f-type", "f-family", "f-topic", "f-cluster",
            "f-cohort", "f-classification",
        })
        self.assertIn('data-repo-count="' + HUB + '"', page)
        self.assertIn('id="visible-count">2</strong>', page)
        self.assertIn("row.hidden = !visible", page)
        self.assertIn("row.textContent.toLocaleLowerCase()", page)

    def test_untrusted_title_escapes_attribute_html_and_script(self):
        raw = '<img src=x onerror="alert(1)"> & "</script><script>alert(5)</script>'
        m = model()
        m["items"][0] = item(HUB, 11, "fix(watch): " + raw, "PullRequest")
        page = explorer.render(m)
        self.assertNotIn("<img src=x", page)
        self.assertNotIn('onerror="alert(1)"', page)
        self.assertNotIn("</script><script>alert(5)</script>", page)
        self.assertIn("&lt;img src=x", page)
        self.assertIn("&lt;/script&gt;", page)

    def test_private_local_is_explicit(self):
        page = explorer.render(model(), include_private=True)
        self.assertIn("PRIVATE_LOCAL_ONLY", page)
        self.assertIn("CLASSIFIED-PRIVATE-778", page)
        self.assertIn(QPS, page)
        self.assertIn("Never publish PRIVATE_LOCAL_ONLY", page)

    def test_reject_duplicate_and_cross_repo_identity(self):
        m = model()
        m["items"].append(copy.deepcopy(m["items"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_WORK_ITEM"):
            explorer.render(m)
        m = model()
        m["items"][0]["key"] = QPS + "#11"
        with self.assertRaisesRegex(ValueError, "ITEM_IDENTITY_INVALID"):
            explorer.render(m)

    def test_reject_source_privacy_confusion_and_schema_drift(self):
        m = model()
        m["items"][0]["private"] = True
        with self.assertRaisesRegex(ValueError, "PRIVATE_REPO_INCONSISTENT"):
            explorer.render(m)
        m = model()
        m["items"][0]["title_taxonomy"]["schema"] = "unverified-taxonomy"
        with self.assertRaisesRegex(ValueError, "TAXONOMY_SCHEMA_MISMATCH"):
            explorer.render(m)
        m = model()
        m["heads"][HUB]["head_sha"] = "short"
        with self.assertRaisesRegex(ValueError, "INVALID_REPO_OR_HEAD"):
            explorer.render(m)

    def test_cli_writes_static_offline_page_with_private_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "rank.json", root / "explorer.html"
            source.write_text(json.dumps(model()), encoding="utf-8")
            self.assertEqual(explorer.main(["--model", str(source),
                                            "--out", str(output)]), 0)
            body = output.read_text(encoding="utf-8")
            self.assertIn("PUBLIC_PROJECTION", body)
            self.assertNotIn(QPS, body)
            self.assertNotIn("<script src=", body)
            self.assertIn("<script>", body)


if __name__ == "__main__":
    unittest.main()
