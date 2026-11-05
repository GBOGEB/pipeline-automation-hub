import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_catalog as ec


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.cat = ec.load()

    def errors(self, cat=None, text=""):
        return ec.validate(cat or self.cat, raw_text=text)

    def check(self, cid, cat=None):
        return next(c for c in (cat or self.cat)["checks"] if c["id"] == cid)

    def test_real_catalogue_passes_and_is_not_empty(self):
        self.assertEqual(ec.validate(self.cat), [])
        self.assertGreater(len(self.cat["checks"]), 20)

    def test_every_binary_type_has_checks(self):
        for t in ("PPTX", "DOCX", "XLSX", "PDF", "HTML", "SVG"):
            self.assertTrue(any(c["id"].startswith(f"K-{t}-") for c in self.cat["checks"]), t)

    def test_duplicate_id_fails(self):
        cat = copy.deepcopy(self.cat)
        cat["checks"].append(copy.deepcopy(cat["checks"][0]))
        self.assertTrue(any("duplicate id" in e for e in self.errors(cat)))

    def test_reserved_series_style_id_fails(self):
        cat = copy.deepcopy(self.cat)
        cat["checks"][0]["id"] = "LEDGER.K13"
        self.assertTrue(any("id must be" in e for e in self.errors(cat)))

    def test_unknown_engine_and_tier_fail(self):
        cat = copy.deepcopy(self.cat)
        cat["checks"][0]["engines"] = ["nope"]
        cat["checks"][0]["tier"] = "G9"
        found = self.errors(cat)
        self.assertTrue(any("unknown engine" in e for e in found))
        self.assertTrue(any("unknown tier" in e for e in found))

    def test_implemented_claim_without_evidence_fails(self):
        cat = copy.deepcopy(self.cat)
        chk = self.check("K-DOCX-01", cat)
        chk["status"] = "implemented"
        self.assertTrue(any("without evidence" in e for e in self.errors(cat)))

    def test_implemented_claim_with_false_symbol_or_test_fails(self):
        cat = copy.deepcopy(self.cat)
        chk = self.check("K-PPTX-01", cat)
        chk["evidence"]["symbol"] = "no_such_function"
        chk["evidence"]["test"] = "test_no_such_case"
        found = self.errors(cat)
        self.assertTrue(any("symbol no_such_function" in e for e in found))
        self.assertTrue(any("test test_no_such_case" in e for e in found))

    def test_dropping_a_required_pillar_fails(self):
        cat = copy.deepcopy(self.cat)
        cat["checks"] = [c for c in cat["checks"] if c["id"] != "K-DOCX-06"]
        self.assertTrue(any("required pillar native" in e for e in self.errors(cat)))

    def test_individual_binary_name_or_hash_fails(self):
        for name in ("board.pptx", "board.pptm", "note.docx", "note.docm", "plan.xlsx", "plan.xlsm", "spec.pdf", "dash.html", "dash.htm", "flow.svg"):
            self.assertTrue(any("project data" in e for e in self.errors(text=f"source: {name}")), name)
        self.assertTrue(any("project data" in e for e in self.errors(text="sha: " + "a" * 64)))
        self.assertFalse(any("project data" in e for e in self.errors(text="type PPTX, Excel recalculation, PDF/A")))

    def test_stray_or_missing_check_field_fails(self):
        cat = copy.deepcopy(self.cat)
        cat["checks"][0]["laptop and mobile views"] = None
        del cat["checks"][1]["rule"]
        self.assertEqual(sum("check fields must be" in e for e in self.errors(cat)), 2)

    def test_matrix_says_planned_is_not_a_pass(self):
        text = ec.matrix(self.cat)
        self.assertIn("K-XLSX-04", text)
        self.assertIn("A planned check is not a pass", text)


class ProbeTest(unittest.TestCase):
    def test_absent_command_is_reported_not_raised(self):
        with mock.patch.object(ec.shutil, "which", return_value=None):
            self.assertEqual(ec.probe_command(["soffice"], ["--version"]), {"present": False, "version": None})

    def test_present_command_reads_real_output(self):
        with mock.patch.object(ec.shutil, "which", return_value=sys.executable):
            got = ec.probe_command(["python"], ["--version"])
        self.assertTrue(got["present"])
        self.assertIn("Python", got["version"])

    def test_missing_python_package_is_absent(self):
        self.assertFalse(ec.probe_engine({"python": "no-such-package-xyz"})["present"])

    def test_unprobeable_engine_is_null_not_false(self):
        self.assertIsNone(ec.probe_engine({"none": "runs inside a page"})["present"])

    def test_require_absent_engine_exits_one(self):
        fake = {"qpdf": {"present": False, "version": None}}
        with mock.patch.object(ec, "probe", return_value=fake), mock.patch("builtins.print"):
            self.assertEqual(ec.main(["probe", "--require", "qpdf"]), 1)
            self.assertEqual(ec.main(["probe"]), 0)

    def test_probe_output_is_json(self):
        fake = {"qpdf": {"present": False, "version": None}}
        with mock.patch.object(ec, "probe", return_value=fake), mock.patch("builtins.print") as p:
            ec.main(["probe"])
        self.assertEqual(json.loads(p.call_args[0][0])["engines"], fake)


if __name__ == "__main__":
    unittest.main()
