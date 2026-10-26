"""Private boundary: a private repo appears in public JADE outputs as counts and statuses only.
Row-level identifiers (links, commit SHAs, private blob OIDs, run/issue ids) become MARK; every
committed JSON output is a fixed point of the projection, and no text output links into it."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jade_private_boundary", ROOT / "tools" / "private_boundary.py")
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)

PRIV, PUB = "GBOGEB/secret-repo", "GBOGEB/open-repo"
C1, C2, BLOB = "1" * 40, "2" * 40, "b" * 40
M = pb.MARK


class Projection(unittest.TestCase):
    def setUp(self):
        self.b = pb.Boundary([PRIV])

    def test_private_row_keeps_counts_and_statuses(self):
        row = {"repo": PRIV, "rank": 4, "percent": 33.3, "source_sha": C1,
               "gates": [{"id": "H01", "status": "PASS", "evidence": f"https://github.com/{PRIV}/commit/{C1}"}],
               "runs": [{"id": 39159008697, "conclusion": "failure", "name": "qps-canonicalization",
                         "url": f"https://github.com/{PRIV}/actions/runs/39159008697"}],
               "issue_links": [f"https://github.com/{PRIV}/issues/{n}" for n in (1, 2, 3)],
               "todo": f"Investigate run 39159008697; close #1959 at {C1[:9]}"}
        out = self.b.project({"rows": [row]})["rows"][0]
        self.assertEqual((out["rank"], out["percent"], out["gates"][0]["status"]), (4, 33.3, "PASS"))
        self.assertEqual((out["source_sha"], out["gates"][0]["evidence"]), (M, M))
        self.assertEqual(out["runs"][0]["id"], None)
        self.assertEqual(out["runs"][0]["name"], "qps-canonicalization")  # structure, not evidence
        self.assertEqual(out["issue_links"], [M, M, M])  # the count survives
        self.assertNotRegex(out["todo"], r"\d{8,}|#\d|" + C1[:9])

    def test_private_commit_is_redacted_wherever_it_occurs(self):
        doc = {"rows": [{"repo": PRIV, "head_sha": C1}],
               "alignment": {"mismatch": [{"label": "prior", "value": C1}], "note": f"seen {C1[:7]}"}}
        out = json.dumps(self.b.project(doc))
        self.assertNotIn(C1[:7], out)

    def test_public_rows_are_untouched(self):
        doc = {"rows": [{"repo": PUB, "head_sha": C2, "runs": [{"id": 12345678901, "conclusion": "success"}],
                         "url": f"https://github.com/{PUB}/actions/runs/12345678901", "note": "fix #12"}]}
        self.assertEqual(self.b.project(doc), doc)

    def test_shared_blob_oid_is_private_only_inside_the_private_row(self):
        # Blob OIDs hash content: the same workflow file in a public repo has the same OID there.
        doc = {"repos": {PRIV: {"workflows": [{"path": "a.yml", "blob_oid": BLOB}]},
                         PUB: {"workflows": [{"path": "a.yml", "blob_oid": BLOB}]}}}
        out = self.b.project(doc)
        self.assertEqual(out["repos"][PRIV]["workflows"][0]["blob_oid"], M)
        self.assertEqual(out["repos"][PUB]["workflows"][0]["blob_oid"], BLOB)

    def test_a_public_row_naming_the_private_repo_stays_public(self):
        doc = {"repo": PUB, "workflows": [{"name": "secret-repo Federation Check", "blob_oid": BLOB}]}
        self.assertEqual(self.b.project(doc), doc)

    def test_node_ids_scopes_and_private_paths_count(self):
        b = self.b
        self.assertTrue(b.row_is_private({"id": "S.secret-repo"}))
        self.assertTrue(b.row_is_private({"scope": "secret-repo"}))
        self.assertTrue(b.path_is_private({"path": "GBOGEB/secret-repo:controls/x.yaml"}))
        self.assertFalse(b.row_is_private({"name": "secret-repo-tools"}))

    def test_idempotent(self):
        doc = {"rows": [{"repo": PRIV, "head_sha": C1, "links": [f"https://github.com/{PRIV}/tree/{C1}"]}]}
        once = self.b.project(doc)
        self.assertEqual(self.b.project(once), once)


class Committed(unittest.TestCase):
    def test_private_list_has_one_owner(self):
        reg = json.loads(pb.REGISTRY.read_text(encoding="utf-8"))
        self.assertIn("GBOGEB/cryoplant-project", reg["private_repos"])
        self.assertEqual(pb.private_repos(), tuple(reg["private_repos"]))

    def test_every_committed_json_is_projected(self):
        for p in pb.committed_json():
            with self.subTest(path=p.name):
                doc = json.loads(p.read_text(encoding="utf-8"))
                self.assertEqual(pb.project(doc), doc)

    def test_no_text_output_links_into_a_private_repo(self):
        rx = re.compile("|".join(re.escape(f"github.com/{r}/") for r in pb.private_repos()), re.I)
        for p in sorted(ROOT.rglob("*")):
            if p.suffix in {".json", ".csv", ".js", ".html", ".md", ".mmd"} and p.is_file():
                with self.subTest(path=p.relative_to(ROOT).as_posix()):
                    self.assertIsNone(rx.search(p.read_text(encoding="utf-8", errors="replace")))


if __name__ == "__main__":
    unittest.main()
