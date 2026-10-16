"""Read-only GoGREEN PPTX/HTML binary truth adapter (stdlib; no document publication).

Provides the missing *executed bytes* observation between ABACUS's semantic
bridge, CODEX visual golden, and hub GoGREEN evidence producers. This does not
execute macros, claim rendered QA, authorize merges or authenticate workers.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from html.parser import HTMLParser
import io
import json
import posixpath
import re
import stat
import time
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

SCHEMA = "gogreen.binary-testflight.v1"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
S_LIMIT = 90_000_000
Z_LIMIT = 250_000_000
N_LIMIT = 12000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _xml(raw: bytes):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("unsafe XML declaration")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("malformed OOXML/XML") from exc


def _safe_members(z: ZipFile, *, max_total: int = Z_LIMIT, max_member: int = Z_LIMIT) -> list:
    members = z.infolist()
    if len(members) > N_LIMIT or len(set(x.filename for x in members)) != len(members):
        raise ValueError("package member count/duplicates invalid")
    total = 0
    for f in members:
        name = f.filename
        p = PurePosixPath(name)
        mode = f.external_attr >> 16
        if (p.is_absolute() or ".." in p.parts or "\\" in name or
            stat.S_ISLNK(mode) or f.flag_bits & 1):
            raise ValueError("unsafe package member")
        if f.file_size > max_member or (f.compress_size and f.file_size > max(1000, f.compress_size*300)):
            raise ValueError("package member expansion budget exceeded")
        total += f.file_size
        if total > max_total:
            raise ValueError("package expansion budget exceeded")
    return members


def _rel_map(z: ZipFile, member: str, origin: str) -> dict:
    out = {}
    root = _xml(z.read(member))
    for e in root.findall(PKG + "Relationship"):
        rid = e.get("Id")
        target = e.get("Target", "")
        external = e.get("TargetMode") == "External"
        if not rid or rid in out:
            raise ValueError("invalid or duplicate relationship id")
        if not external:
            target = posixpath.normpath(posixpath.join(origin, target.lstrip("/"))) if not target.startswith("/") else target.lstrip("/")
            if target.startswith("../") or target == "..":
                raise ValueError("relationship escapes archive root")
        out[rid] = {"path": target, "external": external, "type": e.get("Type", "")}
    return out


def _text(elem):
    return " ".join(" ".join((x.text or "") for x in elem.iter(A + "t")).split())


def inspect_presentation(raw: bytes, *, ext: str = ".pptx") -> dict:
    """Inspect genuine PPTX/PPTM package bytes, never filenames as a substitute."""
    if len(raw) > S_LIMIT:
        raise ValueError("PPT input size budget exceeded")
    with ZipFile(io.BytesIO(raw)) as z:
        members = _safe_members(z)
        names = {x.filename for x in members}
        required = {"[Content_Types].xml", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"}
        if not required.issubset(names):
            raise ValueError("missing mandatory PowerPoint package members")
        root = _xml(z.read("ppt/presentation.xml"))
        rel = _rel_map(z, "ppt/_rels/presentation.xml.rels", "ppt")
        slides_order = root.find(P + "sldIdLst")
        if slides_order is None:
            raise ValueError("no slide identity list")
        size = root.find(P + "sldSz")
        if size is None or not size.get("cx") or not size.get("cy"):
            raise ValueError("slide geometry not provided")
        width, height = int(size.get("cx")), int(size.get("cy"))
        if width < 10000 or height < 10000:
            raise ValueError("invalid slide geometry")
        has_active = ext == ".pptm" or any("vbaProject" in n or "activeX" in n for n in names)
        has_embedded = any("embeddings/" in n for n in names)
        ext_rels = sum(1 for r in rel.values() if r["external"])
        for n in names:
            if n.endswith(".rels") and n != "ppt/_rels/presentation.xml.rels":
                try:
                    e = _xml(z.read(n))
                except ET.ParseError as exc:
                    raise ValueError("broken OOXML relationship XML") from exc
                ext_rels += sum(x.get("TargetMode") == "External" for x in e.findall(PKG + "Relationship"))
        slides = []
        seen = set()
        for order, slide_ref in enumerate(slides_order.findall(P + "sldId"), 1):
            rid = slide_ref.get(R + "id")
            link = rel.get(rid)
            if not link or link["external"] or "slide" not in link["type"]:
                raise ValueError("slide relationship absent/invalid")
            path = link["path"]
            if path in seen or path not in names or not re.fullmatch(r"ppt/slides/slide\d+\.xml", path):
                raise ValueError("slide identity missing/duplicated")
            seen.add(path)
            slide = _xml(z.read(path))
            shapes = list(slide.findall(".//" + P + "sp"))
            pictures = list(slide.findall(".//" + P + "pic"))
            connectors = list(slide.findall(".//" + P + "cxnSp"))
            groups = list(slide.findall(".//" + P + "grpSp"))
            graphic = list(slide.findall(".//" + P + "graphicFrame"))
            text_by_shape, bounds = [], []
            out_of_bounds = 0
            for sh in shapes:
                t = _text(sh)
                if t:
                    text_by_shape.append(t)
                xfm = sh.find("./" + P + "spPr/" + A + "xfrm")
                if xfm is not None:
                    o = xfm.find(A + "off")
                    e = xfm.find(A + "ext")
                    if o is not None and e is not None:
                        try:
                            x,y,w,h = map(int,[o.get("x"),o.get("y"),e.get("cx"),e.get("cy")])
                            if min(w,h)<0 or x<0 or y<0 or x+w>width+1000 or y+h>height+1000:
                                out_of_bounds += 1
                            if t and w>0 and h>0: bounds.append((x,y,w,h))
                        except (TypeError,ValueError) as exc:
                            raise ValueError("invalid geometry") from exc
            norm = " ".join(" ".join(text_by_shape).casefold().split())
            slides.append({
                "order":order, "member_sha256":sha(z.read(path)),
                "text_sha256":sha(norm.encode()), "text_chars":len(norm),
                "text_shape_count":len(text_by_shape), "shape_count":len(shapes),
                "picture_count":len(pictures), "connector_count":len(connectors),
                "group_count":max(0,len(groups)-1),
                "table_count":sum(bool(g.findall(".//" + A + "tbl")) for g in graphic),
                "off_canvas_candidates":out_of_bounds,
                "has_absolute_text_geometry":bool(bounds),
                "has_groups":len(groups)>1,
            })
        if not slides:
            raise ValueError("no valid presentation slides")
        sigs = Counter(s["text_sha256"] for s in slides if s["text_chars"]>=20)
        return {"family":ext.lstrip("."),"source_sha256":sha(raw),
                "size_bytes":len(raw),"slides":len(slides),"has_active_content":has_active,
                "external_relationships":ext_rels,"has_embedded_objects":has_embedded,"unverified_render":True,
                "slide_records":slides,
                "exact_text_duplicate_groups":sum(n>1 for n in sigs.values()),
                "grouped_slides":sum(s["has_groups"] for s in slides),
                "off_canvas_candidates":sum(s["off_canvas_candidates"] for s in slides)}


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags=Counter();self.links=[];self.ids=set()
    def handle_starttag(self, tag, attrs):
        self.tags[tag]+=1
        a=dict(attrs)
        if a.get("id"):self.ids.add(a["id"])
        if tag in ("a","img","script","link"):
            target=a.get("href") or a.get("src")
            if target:self.links.append(target)


def inspect_html(raw: bytes) -> dict:
    if len(raw)>S_LIMIT: raise ValueError("HTML input exceeds size budget")
    try: value=raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise ValueError("HTML encoding unsupported") from exc
    h=_HTML();h.feed(value)
    return {"family":"html","source_sha256":sha(raw),"size_bytes":len(raw),
            "links":len(h.links),"scripts":h.tags["script"],"svgs":h.tags["svg"],
            "headings":sum(h.tags[t] for t in ("h1","h2","h3","h4")),
            "semantic_text_completeness":"UNKNOWN","browser_qa":"DEFER"}


def survey(archives: list[Path]) -> dict:
    """Read-only nested archive census, redacted (hash IDs only)."""
    start=time.monotonic()
    runs=[];errors=[]; counts=Counter(); corpus_hasher=hashlib.sha256()
    for path in archives:
        datahash=sha(path.read_bytes())
        corpus_hasher.update(bytes.fromhex(datahash))
        with ZipFile(path) as outer:
            _safe_members(outer, max_total=2_000_000_000, max_member=600_000_000)
            for info in outer.infolist():
                if info.is_dir(): continue
                ext=PurePosixPath(info.filename).suffix.lower()
                if ext not in (".pptx",".pptm",".html",".htm",".svg"): continue
                item_id=sha((datahash+"\x00"+info.filename).encode())[:20]
                counts[ext]+=1
                try:
                    raw=outer.read(info)
                    if ext in (".pptx",".pptm"):
                        rec=inspect_presentation(raw,ext=ext)
                        counts["ppt_parsed"]+=1;counts["slides"]+=rec["slides"]
                        counts["macro_presentation"]+=rec["has_active_content"]
                        counts["off_canvas_candidates"]+=rec["off_canvas_candidates"]
                        counts["grouped_slides"]+=rec["grouped_slides"]
                        # Public-facing receipt contains counts, not private slide text/digests.
                        runs.append({"id":item_id,"family":rec["family"],"state":"PARSED", "slides":rec["slides"],
                            "sha256":rec["source_sha256"],"render":"NOT_TESTED","content":"NOT_PUBLISHED",
                            "active_content":rec["has_active_content"],"embedded_objects":rec["has_embedded_objects"],"external_rels":rec["external_relationships"]})
                    elif ext in (".html",".htm"):
                        rec=inspect_html(raw);counts["html_parsed"]+=1
                        runs.append({"id":item_id,"family":"html","state":"PARSED", "sha256":rec["source_sha256"],
                            "scripts":rec["scripts"],"render":"NOT_TESTED","content":"NOT_PUBLISHED"})
                    else:
                        _xml(raw);counts["svg_parsed"]+=1
                except (ValueError,BadZipFile,ET.ParseError,KeyError,RuntimeError,OSError,OverflowError) as exc:
                    errors.append({"id":item_id,"family":ext.lstrip("."),"state":"INPUT_REJECTED",
                                   "error_class":type(exc).__name__})
    return {"schema":SCHEMA,"source_set_sha256":corpus_hasher.hexdigest(),
            "counts":dict(sorted(counts.items())),"errors":errors,"objects":runs,
            "runtime_seconds":round(time.monotonic()-start,3),
            "coverage":{"parse_success_denominator":counts[".pptx"]+counts[".pptm"],
                        "parse_success_numerator":counts["ppt_parsed"],
                        "visual_qa_completed":None,"binary_generation_verified":None},
            "admission":"HOLD","authority_transfer":False,
            "security_waiver":False,"merge_authorized":False}


def main():
    a=argparse.ArgumentParser()
    a.add_argument("archives",nargs="+",type=Path)
    a.add_argument("--out",required=True,type=Path)
    opts=a.parse_args()
    result=survey(opts.archives)
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"counts":result["counts"],"errors":len(result["errors"]),"runtime_seconds":result["runtime_seconds"]}))

if __name__=="__main__":main()
