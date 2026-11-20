"""Generic regression cases for source-bound partial binary inspection."""
import hashlib
import importlib.util
import io
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("binary_flight_receipts_owner", ROOT / "binary_flight.py")
bf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bf)
FIXTURE_SPEC = importlib.util.spec_from_file_location("binary_flight_fixture", Path(__file__).with_name("test_binary_flight.py"))
fixture = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(fixture)


def grouped_table_ppt():
    source = fixture.make_ppt()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as old, zipfile.ZipFile(out, "w") as new:
        for info in old.infolist():
            raw = old.read(info)
            if info.filename == "ppt/slides/slide1.xml":
                value = raw.decode("utf-8")
                value = value.replace("<p:sp>", "<p:grpSp><p:sp>").replace("</p:sp>", "</p:sp></p:grpSp>")
                value = value.replace("</p:spTree>", '<p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr><a:tc><a:txBody><a:p><a:r><a:t>Table only text</a:t></a:r></a:p></a:txBody></a:tc></a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame></p:spTree>')
                raw = value.encode("utf-8")
            new.writestr(info, raw)
    return out.getvalue()


class BinaryFlightReceiptTests(unittest.TestCase):
    def test_single_group_is_counted_and_member_locator_is_bound(self):
        result = bf.inspect_presentation(grouped_table_ppt())
        slide = result["slide_records"][1]
        self.assertEqual(slide["group_count"], 1)
        self.assertTrue(slide["has_groups"])
        self.assertEqual(result["grouped_slides"], 1)
        self.assertEqual(slide["member_path"], "ppt/slides/slide1.xml")
        self.assertEqual(slide["relationship_id"], "rId1")
        self.assertEqual(slide["slide_id"], "256")

    def test_table_text_has_separate_digest_without_changing_shape_digest(self):
        plain = bf.inspect_presentation(fixture.make_ppt())["slide_records"][1]
        added = bf.inspect_presentation(grouped_table_ppt())["slide_records"][1]
        self.assertEqual(added["text_sha256"], plain["text_sha256"])
        self.assertEqual(added["table_count"], 1)
        self.assertEqual(added["table_text_chars"], len("table only text"))
        self.assertNotEqual(added["all_text_sha256"], plain["all_text_sha256"])
        self.assertEqual(added["all_text_scope"], "drawingml_a_t_in_slide_part")

    def test_svg_has_individual_source_receipt_and_real_svg_root(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "objects.zip"
            svg = b'<svg xmlns="http://www.w3.org/2000/svg"><g id="one"><text>native</text></g></svg>'
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("diagram.svg", svg)
                archive.writestr("false.svg", b"<not_svg/>")
            result = bf.survey([path])
            self.assertEqual(result["counts"]["svg_parsed"], 1)
            self.assertEqual(len(result["objects"]), 1)
            obj = result["objects"][0]
            self.assertEqual(obj["sha256"], hashlib.sha256(svg).hexdigest())
            self.assertEqual(obj["source_member_index"], 0)
            self.assertEqual(obj["source_archive_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(obj["render"], "NOT_TESTED")
            self.assertEqual(result["coverage"]["selected_recognized_numerator"], 1)
            self.assertEqual(result["coverage"]["selected_recognized_denominator"], 2)
            self.assertEqual(len(result["errors"]), 1)

    def test_explicit_allowlist_can_skip_an_unread_held_member(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "objects.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("safe.html", b"<h1>Read only</h1>")
                archive.writestr("unselected.html", b"x" * 200000)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                bf.survey([path])
            with patch.object(Path, "read_bytes", side_effect=AssertionError("do not materialize outer archive")):
                result = bf.survey([path], member_allowlist={"safe.html"})
            self.assertEqual(result["counts"]["html_parsed"], 1)
            self.assertEqual(result["coverage"]["scope"], "EXPLICIT_MEMBER_ALLOWLIST")
            self.assertEqual(result["coverage"]["unselected_archive_members"], 1)
            self.assertFalse(result["coverage"]["whole_archive_validated"])
            self.assertEqual(result["admission"], "HOLD")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_allowlist_never_bypasses_selected_member_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "objects.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.html", "data")
            for names in ({"../escape.html"}, {"missing.html"}, set()):
                with self.subTest(names=names), self.assertRaises(ValueError):
                    bf.survey([path], member_allowlist=names)
            with self.assertRaises(ValueError):
                bf.survey([path, path], member_allowlist={"../escape.html"})

    def test_svg_declarations_and_wrong_namespace_are_rejected(self):
        for raw in (b'<!DOCTYPE svg><svg/>', b'<svg xmlns="urn:wrong"/>', b'<root/>'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                bf.inspect_svg(raw)

    def test_encoded_xml_declarations_never_bypass_the_gate(self):
        xml = '<!DOCTYPE svg [<!ENTITY value "injected">]><svg>&value;</svg>'
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                bf.inspect_svg(xml.encode(encoding))
        self.assertEqual(bf.inspect_svg('<svg/>'.encode('utf-16'))["family"], "svg")

    def test_archive_replacement_after_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changing.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("safe.html", "<h1>Original</h1>")
            original_parser = bf.inspect_html
            def mutate_during_inspection(raw):
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("safe.html", "<h1>Replacement</h1>")
                return original_parser(raw)
            with patch.object(bf, "inspect_html", side_effect=mutate_during_inspection):
                with self.assertRaisesRegex(ValueError, "SOURCE_ARCHIVE_CHANGED"):
                    bf.survey([path])

    def test_restored_archive_path_cannot_misbind_replacement_members(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changing.zip"
            original_html = b"<h1>Original</h1>"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("safe.html", original_html)
            original = path.read_bytes()
            replacement = io.BytesIO()
            with zipfile.ZipFile(replacement, "w") as archive:
                archive.writestr("safe.html", b"<h1>Replacement</h1>")
            open_zip = bf.ZipFile

            @contextmanager
            def replace_then_restore(source, *args, **kwargs):
                path.write_bytes(replacement.getvalue())
                try:
                    with open_zip(source, *args, **kwargs) as archive:
                        yield archive
                finally:
                    path.write_bytes(original)

            with patch.object(bf, "ZipFile", side_effect=replace_then_restore):
                result = bf.survey([path])
            self.assertEqual(result["objects"][0]["sha256"], hashlib.sha256(original_html).hexdigest())
            self.assertEqual(result["objects"][0]["source_archive_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(path.read_bytes(), original)

    def test_cli_rejects_duplicate_member_before_survey_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            args = ["binary_flight", "source.zip", "--out", str(output),
                    "--member", "safe.html", "--member", "safe.html"]
            result = {"counts": {}, "errors": [], "runtime_seconds": 0}
            with patch.object(sys, "argv", args), patch.object(bf, "survey", return_value=result) as survey:
                with patch.object(sys, "stderr", io.StringIO()) as errors:
                    with self.assertRaises(SystemExit) as raised:
                        bf.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("duplicate", errors.getvalue().lower())
            survey.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
