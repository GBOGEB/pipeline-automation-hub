import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import office_semantic_carrier as osc


CONTENT_TYPES_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/{main_part}" ContentType="application/xml"/>
</Types>
'''

ROOT_RELS_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{main_part}"/>
</Relationships>
'''

MAIN_XML = {
    ".docx": ('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'),
    ".xlsx": ('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'),
    ".pptx": ('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>'),
}


class OfficeSemanticCarrierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.truth = {
            "schema": "missioncontrol.golden_thread_projection.v1",
            "authority_transfer": False,
            "boundary": "CURRENT",
            "metrics": {"occurrence_count": 4, "lineage_retention_coverage": 1.0},
            "head_event_digest": "sha256:" + "a" * 64,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def make_stub(self, ext, name, metadata="meta-a"):
        path = self.root / f"{name}{ext}"
        main_part, main_xml = MAIN_XML[ext]
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(osc.CONTENT_TYPES, CONTENT_TYPES_TEMPLATE.format(main_part=main_part))
            zf.writestr(osc.ROOT_RELS, ROOT_RELS_TEMPLATE.format(main_part=main_part))
            zf.writestr(main_part, main_xml)
            zf.writestr("docProps/core.xml", f"<core>{metadata}</core>")
        return path

    def rewrite_part(self, source, destination, part_name, replacement):
        with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == part_name:
                    data = replacement
                dst.writestr(info.filename, data)

    def test_docx_xlsx_pptx_extract_same_canonical_truth(self):
        digests = set()
        for ext in (".docx", ".xlsx", ".pptx"):
            with self.subTest(ext=ext):
                src = self.make_stub(ext, "src" + ext[1:])
                dst = self.root / f"out{ext}"
                receipt = osc.inject(src, dst, self.truth)
                self.assertEqual(receipt["status"], "WRITTEN")
                extracted = osc.extract(dst)
                self.assertEqual(extracted["truth"], self.truth)
                self.assertFalse(extracted["authority_transfer"])
                self.assertFalse(extracted["manifest"]["visual_fidelity_credit"])
                self.assertEqual(osc.verify(dst, self.truth)["status"], "PASS")
                digests.add(extracted["truth_digest"])
        self.assertEqual(len(digests), 1)
        self.assertEqual(digests.pop(), osc.truth_digest(self.truth))

    def test_unrelated_office_metadata_does_not_change_semantic_identity(self):
        a_src = self.make_stub(".docx", "a", metadata="office-build-a")
        b_src = self.make_stub(".docx", "b", metadata="office-build-b")
        a = self.root / "a-carried.docx"
        b = self.root / "b-carried.docx"
        ra = osc.inject(a_src, a, self.truth)
        rb = osc.inject(b_src, b, self.truth)
        self.assertNotEqual(ra["package_sha256"], rb["package_sha256"])
        self.assertEqual(osc.extract(a)["truth_digest"], osc.extract(b)["truth_digest"])
        self.assertEqual(osc.extract(a)["truth"], osc.extract(b)["truth"])

    def test_identical_reinjection_is_byte_preserving_replay(self):
        src = self.make_stub(".xlsx", "source")
        first = self.root / "first.xlsx"
        second = self.root / "second.xlsx"
        osc.inject(src, first, self.truth)
        replay = osc.inject(first, second, self.truth)
        self.assertEqual(replay["status"], "UNCHANGED_REPLAY")
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_changed_truth_creates_successor_manifest(self):
        src = self.make_stub(".pptx", "source")
        first = self.root / "first.pptx"
        second = self.root / "second.pptx"
        osc.inject(src, first, self.truth)
        changed = dict(self.truth)
        changed["boundary"] = "NEXT"
        receipt = osc.inject(first, second, changed)
        extracted = osc.extract(second)
        self.assertEqual(receipt["parent_truth_digest"], osc.truth_digest(self.truth))
        self.assertEqual(extracted["manifest"]["parent_truth_digest"], osc.truth_digest(self.truth))
        self.assertEqual(extracted["truth_digest"], osc.truth_digest(changed))
        self.assertNotEqual(extracted["truth_digest"], osc.truth_digest(self.truth))

    def test_truth_tamper_fails_closed(self):
        src = self.make_stub(".docx", "source")
        carried = self.root / "carried.docx"
        tampered = self.root / "tampered.docx"
        osc.inject(src, carried, self.truth)
        bad_truth = dict(self.truth)
        bad_truth["boundary"] = "TAMPERED"
        self.rewrite_part(
            carried,
            tampered,
            osc.TRUTH_PART,
            osc.canonical_json(bad_truth).encode("utf-8"),
        )
        with self.assertRaises(osc.OfficeSemanticError):
            osc.extract(tampered)

    def test_wrong_expected_truth_detects_semantic_delta(self):
        src = self.make_stub(".xlsx", "source")
        carried = self.root / "carried.xlsx"
        osc.inject(src, carried, self.truth)
        wrong = dict(self.truth)
        wrong["boundary"] = "WRONG"
        with self.assertRaises(osc.OfficeSemanticError):
            osc.verify(carried, wrong)


if __name__ == "__main__":
    unittest.main()
