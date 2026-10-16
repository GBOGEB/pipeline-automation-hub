"""GOGREEN GoGREEN binary positive/negative controls - synthetic only."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import zipfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("binary_flight", ROOT / "binary_flight.py")
bf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bf)

PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def make_ppt(*, ordered=(2, 1), traversal=False, duplicate=False, broken=False,
             external=False, malformed=False, doctype=False, outside=False,
             valid_other_rel=False, duplicate_id=False, size=None, active=False):
    sx,sy=size or (12192000,6858000)
    ids = "".join(f'<p:sldId id="{255+i}" r:id="rId{n}"/>' for i,n in enumerate(ordered))
    present = f'<p:presentation xmlns:p="{PNS}" xmlns:r="{RNS}"><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="{sx}" cy="{sy}"/></p:presentation>'
    target = "../../secret.xml" if traversal else ("../customXml/item1.xml" if valid_other_rel else "slides/slide2.xml")
    links = [f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="{target if traversal else "slides/slide2.xml"}"/>',
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>']
    if external: links[0] = links[0].replace('Target="slides/slide2.xml"','Target="https://example.com/x" TargetMode="External"')
    if duplicate_id: links.append(links[0])
    if valid_other_rel:links.append(f'<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml" Target="../customXml/item1.xml"/>')
    rels=f'<Relationships xmlns="{PKG}">'+"".join(links)+'</Relationships>'
    def slide(s):
        tx=f'<a:t>Section {s} complete</a:t>'
        return f'<p:sld xmlns:p="{PNS}" xmlns:a="{ANS}"><p:cSld><p:spTree><p:sp><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="11000000" cy="300000"/></a:xfrm></p:spPr><p:txBody><a:p><a:r>{tx}</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    data = {'[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            'ppt/presentation.xml': present,
            'ppt/_rels/presentation.xml.rels': rels,
            'ppt/slides/slide1.xml': slide(1),
            'ppt/slides/slide2.xml': slide(2)}
    if traversal:data['ppt/_rels/presentation.xml.rels'] = data['ppt/_rels/presentation.xml.rels'].replace('Target="slides/slide2.xml"','Target="../../secret.xml"')
    if malformed:data['ppt/slides/slide1.xml'] = '<broken>'
    if doctype:data['ppt/slides/slide1.xml'] = '<!DOCTYPE foo [<!ENTITY x "unsafe">]>'+data['ppt/slides/slide1.xml']
    if broken:del data['ppt/slides/slide1.xml']
    if active:data['ppt/vbaProject.bin'] = 'fake, never executed'
    if outside:data['ppt/slides/slide1.xml'] = data['ppt/slides/slide1.xml'].replace('y="0"','y="8900000"')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for n,v in data.items():z.writestr(n,v)
        if duplicate:z.writestr('ppt/slides/slide1.xml',data['ppt/slides/slide1.xml'])
    return buf.getvalue()



class BinaryFlightUnittest(unittest.TestCase):
    def test_real_slide_order_and_source_bytes(self):
        raw = make_ppt()
        r = bf.inspect_presentation(raw)
        self.assertEqual(r["slides"], 2)
        self.assertEqual(r["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(r["slide_records"][0]["text_sha256"], bf.sha(b"section 2 complete"))
        self.assertTrue(r["unverified_render"])
        self.assertFalse(r["has_active_content"])

    def test_safe_package_relationship_resolution(self):
        self.assertEqual(bf.inspect_presentation(make_ppt(valid_other_rel=True))["slides"], 2)

    def test_active_macro_is_not_executed(self):
        r = bf.inspect_presentation(make_ppt(active=True),ext=".pptm")
        self.assertTrue(r["has_active_content"])
        self.assertEqual(r["family"], "pptm")

    def test_embedded_object_not_confused_with_macro(self):
        source = make_ppt(); out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(source)) as src,zipfile.ZipFile(out,"w") as z:
            for n in src.namelist(): z.writestr(n,src.read(n))
            z.writestr("ppt/embeddings/object1.bin", "test")
        r=bf.inspect_presentation(out.getvalue())
        self.assertTrue(r["has_embedded_objects"])
        self.assertFalse(r["has_active_content"])

    def test_negative_presentation_variants(self):
        for name, opts in (
            ("archive traversal",{"traversal": True}),
            ("duplicate members",{"duplicate": True}),
            ("missing slide",{"broken": True}),
            ("external slide",{"external":True}),
            ("malformed xml",{"malformed":True}),
            ("doctype",{"doctype":True}),
            ("duplicate rel",{"duplicate_id":True}),
            ("bad geometry",{"size":(0,0)}),
        ):
            with self.subTest(name=name):
                with self.assertRaises((ValueError,zipfile.BadZipFile)):
                    bf.inspect_presentation(make_ppt(**opts))

    def test_offcanvas_is_not_render_proof(self):
        r=bf.inspect_presentation(make_ppt(outside=True))
        self.assertEqual(r["off_canvas_candidates"],1)
        self.assertTrue(r["unverified_render"])

    def test_non_zip_false_green_rejected(self):
        with self.assertRaises(zipfile.BadZipFile):
            bf.inspect_presentation(b"not pptx content")

    def test_member_path_negatives(self):
        for name in ("../escape","ppt\\evil","/abs"):
            with self.subTest(name=name):
                out=io.BytesIO()
                with zipfile.ZipFile(out,"w") as z:z.writestr(name,"x")
                with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
                    with self.assertRaises(ValueError):bf._safe_members(z)

    def test_link_and_layout_not_fabricated_for_html(self):
        r=bf.inspect_html(b'<html><h1>Example</h1><script>x</script><a href="test">go</a></html>')
        self.assertEqual(r["links"],1)
        self.assertEqual(r["browser_qa"],"DEFER")
        with self.assertRaises(ValueError):bf.inspect_html(b"\xff\xfe")

    def test_svg_doctype_is_not_accepted_as_validated(self):
        with self.assertRaises(ValueError):bf._xml(b"<!DOCTYPE svg><svg/>")

    def test_scoped_corpus_returns_unknown_visual_and_gate_hold(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            outer=Path(d)/"sample.zip"
            with zipfile.ZipFile(outer,"w") as z:
                z.writestr("first.pptx",make_ppt())
                z.writestr("bad.pptx",b"not zip")
                z.writestr("site.html",b"<h1>hello</h1>")
                z.writestr("diagram.svg",b"<svg/>")
            a=bf.survey([outer]);b=bf.survey([outer]);c=a["counts"]
            self.assertEqual((c["ppt_parsed"],c["slides"],c["html_parsed"],c["svg_parsed"]),(1,2,1,1))
            self.assertEqual(len(a["errors"]),1)
            self.assertEqual(a["coverage"]["parse_success_denominator"],2)
            self.assertIsNone(a["coverage"]["visual_qa_completed"])
            self.assertEqual(a["admission"],"HOLD")
            self.assertFalse(a["authority_transfer"])
            self.assertEqual(a["source_set_sha256"],b["source_set_sha256"])
            self.assertEqual(a["objects"][0]["id"],b["objects"][0]["id"])

if __name__ == "__main__":
    unittest.main()
