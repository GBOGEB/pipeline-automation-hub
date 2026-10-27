"""Public ingress archive and declassification negative controls."""
import copy
import tempfile
import unittest
import json
from pathlib import Path

import taxonomy_public_ingress as ingress

BASE = "mission-control/issue_rank/title_census/"


class Ingress(unittest.TestCase):
    def test_raw_archive_without_approval_is_hard_hold(self):
        out = ingress.audit([{"filename": BASE + "data/raw.json.gz"}])
        self.assertEqual(out["assets_on_hold"], 1)
        self.assertEqual(out["items"][0]["reason"], "NO_OWNER_SOURCE_CLASSIFICATION")
        self.assertFalse(out["byte_verified"])
        self.assertFalse(out["declassification_authorized"])

    def test_manifest_hash_alone_is_not_declassification(self):
        path = BASE + "reference/title_taxonomy_src.zip"
        values = {path: {"visibility": "PUBLIC", "sha256": "a"*64}}
        r = ingress.audit([{"filename": path}], values)
        self.assertEqual(r["items"][0]["reason"], "OWNER_APPROVAL_ABSENT")
        values[path]["owner_approval_receipt"] = "owner-private-inbox-ref"
        r = ingress.audit([{"filename": path}], values)
        self.assertEqual(r["items"][0]["status"], "REVIEW_CANDIDATE")
        self.assertEqual(r["merge_admission"], "HOLD")
        self.assertFalse(r["declassification_authorized"])

    def test_private_claim_stays_hold_even_with_hash(self):
        path = BASE + "dashboard/index.html"
        receipt = {path: {"visibility": "PRIVATE", "sha256": "b"*64,
                          "owner_approval_receipt": "owner"}}
        out = ingress.audit([{"filename": path}], receipt)
        self.assertEqual(out["items"][0]["reason"], "SOURCE_NOT_PUBLIC")

    def test_root_paths_do_not_traverse_and_repeated_files_rejected(self):
        for name in ("../raw.json", "x/../raw.json", "/tmp/raw.json",
                     "x\\raw.json", "x//raw.json", "x/\x00.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ingress.audit([{"filename": name}])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PATH"):
            ingress.audit([{"filename": BASE + "data/a.gz"}]*2)

    def test_normal_unrelated_source_remains_out_of_scope(self):
        x = ingress.audit([{"filename": "mission-control/issue_rank/title_taxonomy.py"}])
        self.assertEqual(x["census_assets"], 0)
        self.assertEqual(x["admission"], "NO_CENSUS_INGRESS_OBSERVED")
        self.assertEqual(x["formal_credit_delta"], 0)

    def test_deterministic_receipt_and_cli_no_source_mutation(self):
        changes = [{"filename": BASE + "data/raw.json.gz"},
                   {"filename": BASE + "outputs/edges.csv.gz"},
                   {"filename": BASE + "README.md"}]
        r = ingress.audit(changes)
        self.assertEqual(r["census_assets"], 2)
        self.assertEqual(r["assets_on_hold"], 2)
        self.assertEqual(r["sha256"], ingress.audit(copy.deepcopy(changes))["sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/"changes.json", Path(tmp)/"out.json"
            source.write_text(json.dumps(changes))
            before = source.read_bytes()
            self.assertEqual(ingress.main(["--changed-files", str(source),
                                          "--out", str(output)]), 0)
            self.assertEqual(before, source.read_bytes())
            self.assertEqual(json.loads(output.read_text())["admission"], "HOLD")


if __name__ == "__main__":
    unittest.main()
