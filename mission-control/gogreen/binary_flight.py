"""Read-only GoGREEN PPTX/HTML/SVG truth adapter (stdlib; no publication).

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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _NoDeclarations(ET.TreeBuilder):
    def doctype(self, name, public_id, system_id):
        raise ValueError("unsafe XML declaration")


def _xml(raw: bytes):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("unsafe XML declaration")
    try:
        # The parser-level callback also covers UTF-16 and other XML encodings;
        # an ASCII byte search alone cannot enforce declaration rejection.
        return ET.fromstring(raw, parser=ET.XMLParser(target=_NoDeclarations()))
    except ET.ParseError as exc:
        raise ValueError("malformed OOXML/XML") from exc


def _safe_members(z: ZipFile, *, max_total: int = Z_LIMIT, max_member: int = Z_LIMIT,
                  selected_names: set[str] | None = None) -> list:
    """Validate all members, or only an explicit selection without bulk admission.

    The archive entry-count bound always applies. A selection never authorizes
    reading or extracting the remaining members; callers must report that scope.
    """
    members = z.infolist()
    if len(members) > N_LIMIT:
        raise ValueError("package member count/duplicates invalid")
    if selected_names is not None:
        if not selected_names or selected_names - {x.filename for x in members}:
            raise ValueError("empty or missing selected member")
        members = [info for info in members if info.filename in selected_names]
    if len(set(x.filename for x in members)) != len(members):
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
            table_text = " ".join(_text(table) for table in slide.findall(".//" + A + "tbl"))
            table_norm = " ".join(table_text.casefold().split())
            all_norm = " ".join(_text(slide).casefold().split())
            slides.append({
                "order":order, "member_sha256":sha(z.read(path)),
                "member_path":path, "relationship_id":rid,
                "slide_id":slide_ref.get("id"),
                "text_sha256":sha(norm.encode()), "text_chars":len(norm),
                "text_scope":"p_sp_drawingml_text",
                "all_text_sha256":sha(all_norm.encode()), "all_text_chars":len(all_norm),
                "all_text_scope":"drawingml_a_t_in_slide_part",
                "table_text_sha256":sha(table_norm.encode()), "table_text_chars":len(table_norm),
                "text_shape_count":len(text_by_shape), "shape_count":len(shapes),
                "picture_count":len(pictures), "connector_count":len(connectors),
                "group_count":len(groups),
                "table_count":sum(bool(g.findall(".//" + A + "tbl")) for g in graphic),
                "off_canvas_candidates":out_of_bounds,
                "has_absolute_text_geometry":bool(bounds),
                "has_groups":bool(groups),
                "group_transform_qualification":"NOT_EVALUATED" if groups else "NOT_APPLICABLE",
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


def inspect_svg(raw: bytes) -> dict:
    """Validate an SVG XML root and count native objects, without rendering."""
    if len(raw) > S_LIMIT:
        raise ValueError("SVG input exceeds size budget")
    root = _xml(raw)
    if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
        raise ValueError("XML root is not SVG")
    nodes = list(root.iter())
    return {"family":"svg", "source_sha256":sha(raw), "size_bytes":len(raw),
            "elements":len(nodes), "native_ids":sum(bool(node.get("id")) for node in nodes),
            "render":"NOT_TESTED", "semantic_text_completeness":"UNKNOWN"}


def survey(archives: list[Path], *, member_allowlist: set[str] | None = None) -> dict:
    """Read supported direct members; package reads never extract or execute.

    By default the complete outer member listing must satisfy the budget. An
    explicit allowlist is available for one archive at a time and leaves every
    unselected member unvalidated and unread. It cannot confer container safety.
    """
    if member_allowlist is not None and len(archives) != 1:
        raise ValueError("member allowlist requires exactly one source archive")
    start=time.monotonic()
    runs=[];errors=[]; counts=Counter(); corpus_hasher=hashlib.sha256()
    archive_members = unselected_members = unhandled_members = 0
    for path in archives:
        datahash=_file_sha256(path)
        corpus_hasher.update(bytes.fromhex(datahash))
        with ZipFile(path) as outer:
            selected = _safe_members(outer, max_total=2_000_000_000, max_member=600_000_000,
                                     selected_names=member_allowlist)
            all_members = outer.infolist()
            archive_members += len(all_members)
            unselected_members += len(all_members) - len(selected)
            source_indices = {id(info): index for index, info in enumerate(all_members)}
            for info in selected:
                if info.is_dir(): continue
                ext=PurePosixPath(info.filename).suffix.lower()
                if ext not in (".pptx",".pptm",".html",".htm",".svg"):
                    unhandled_members += 1
                    continue
                item_id=sha((datahash+"\x00"+info.filename).encode())[:20]
                lineage = {"source_archive_sha256":datahash,
                           "source_member_index":source_indices[id(info)],
                           "source_member_name_sha256":sha(info.filename.encode("utf-8"))}
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
                        runs.append({"id":item_id,**lineage,"family":rec["family"],"state":"PARSED", "slides":rec["slides"],
                            "sha256":rec["source_sha256"],"render":"NOT_TESTED","content":"NOT_PUBLISHED",
                            "active_content":rec["has_active_content"],"embedded_objects":rec["has_embedded_objects"],"external_rels":rec["external_relationships"]})
                    elif ext in (".html",".htm"):
                        rec=inspect_html(raw);counts["html_parsed"]+=1
                        runs.append({"id":item_id,**lineage,"family":"html","state":"PARSED", "sha256":rec["source_sha256"],
                            "scripts":rec["scripts"],"render":"NOT_TESTED","content":"NOT_PUBLISHED"})
                    else:
                        rec=inspect_svg(raw);counts["svg_parsed"]+=1
                        runs.append({"id":item_id,**lineage,"family":"svg","state":"PARSED",
                                     "sha256":rec["source_sha256"],"elements":rec["elements"],
                                     "native_ids":rec["native_ids"],"render":"NOT_TESTED","content":"NOT_PUBLISHED"})
                except (ValueError,BadZipFile,ET.ParseError,KeyError,RuntimeError,OSError,OverflowError) as exc:
                    errors.append({"id":item_id,**lineage,"family":ext.lstrip("."),"state":"INPUT_REJECTED",
                                   "error_class":type(exc).__name__})
        # A concurrent replacement must not bind newly read members to an older
        # parent hash. No receipt is returned when the source bytes changed.
        if _file_sha256(path) != datahash:
            raise ValueError("SOURCE_ARCHIVE_CHANGED_DURING_INSPECTION")
    return {"schema":SCHEMA,"source_set_sha256":corpus_hasher.hexdigest(),
            "counts":dict(sorted(counts.items())),"errors":errors,"objects":runs,
            "runtime_seconds":round(time.monotonic()-start,3),
            "coverage":{"parse_success_denominator":counts[".pptx"]+counts[".pptm"],
                        "parse_success_numerator":counts["ppt_parsed"],
                        "legacy_parse_success_scope":"PPTX_PPTM_ONLY",
                        "selected_recognized_denominator":len(runs)+len(errors),
                        "selected_recognized_numerator":len(runs),
                        "scope":"EXPLICIT_MEMBER_ALLOWLIST" if member_allowlist is not None else "ALL_DIRECT_MEMBERS",
                        "archive_member_count":archive_members,
                        "unselected_archive_members":unselected_members,
                        "selected_unhandled_members":unhandled_members,
                        "whole_archive_validated":False,
                        "whole_archive_member_metadata_validated":member_allowlist is None,
                        "recursive_archive_traversal":False,
                        "visual_qa_completed":None,"binary_generation_verified":None},
            "admission":"HOLD","authority_transfer":False,
            "security_waiver":False,"merge_authorized":False}


def main():
    a=argparse.ArgumentParser()
    a.add_argument("archives",nargs="+",type=Path)
    a.add_argument("--out",required=True,type=Path)
    a.add_argument("--member",action="append",help="Exact member name; repeat for an explicit one-archive selection")
    opts=a.parse_args()
    result=survey(opts.archives,member_allowlist=set(opts.member) if opts.member is not None else None)
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"counts":result["counts"],"errors":len(result["errors"]),"runtime_seconds":result["runtime_seconds"]}))

if __name__=="__main__":main()

