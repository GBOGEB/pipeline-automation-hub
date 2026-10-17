#!/usr/bin/env python3
"""Reusable fail-closed HTML static contract for Mission Control review pages.

Does not confer hosted publication, underlying metric proof, security or merge admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ALLOWED_PROTOCOLS = {"http", "https", "mailto"}
LOCAL_ASSET_ATTRS = {"href", "src"}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.anchors = []
        self.assets = []
        self.buttons = []
        self.selects = []
        self.label_refs = []
        self.metas = []
        self.headings = []
        self.images = []
        self.scripts = []
        self.labels = []
        self.title = ""
        self._in_title = False
        self._in_h1 = False
        self._label_depth = 0
        self._button_stack = []

    def handle_starttag(self, tag, raw_attrs):
        attrs = dict(raw_attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
            self.headings.append("")
        elif tag == "label":
            self._label_depth += 1
            if attrs.get("for"):
                self.label_refs.append(attrs["for"])
        elif tag == "button":
            self._button_stack.append({"attrs": attrs, "text": ""})
        elif tag == "select":
            self.selects.append({"attrs": attrs, "wrapped_in_label": self._label_depth > 0})
        elif tag == "a":
            self.anchors.append(attrs)
        elif tag == "img":
            self.images.append(attrs)
        elif tag == "script":
            self.scripts.append(attrs)
        elif tag == "meta":
            self.metas.append(attrs)
        if tag in {"link", "img", "script", "source"}:
            for key in LOCAL_ASSET_ATTRS:
                if attrs.get(key):
                    self.assets.append({"tag": tag, "attr": key, "value": attrs[key]})

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h1:
            self.headings[-1] += data
        if self._button_stack:
            self._button_stack[-1]["text"] += data

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        elif tag == "button" and self._button_stack:
            self.buttons.append(self._button_stack.pop())


def resolve_reference(value: str, base_dir: Path, ids: set[str], *, require_exists: bool) -> list[str]:
    problems = []
    if not value or value.isspace():
        return ["EMPTY_REFERENCE"]
    p = urlparse(value)
    if p.scheme and p.scheme not in ALLOWED_PROTOCOLS:
        return ["UNSAFE_SCHEME"]
    if p.scheme in ALLOWED_PROTOCOLS:
        if not p.netloc and p.scheme != "mailto":
            problems.append("INVALID_REMOTE_REFERENCE")
        return problems
    if value.startswith("//"):
        return ["PROTOCOL_RELATIVE_URL_FORBIDDEN"]
    if p.path.startswith("/"):
        return ["ABSOLUTE_SITE_PATH_NOT_PORTABLE"]
    if p.fragment and not p.path and p.fragment not in ids:
        return ["BROKEN_INTERNAL_ANCHOR"]
    if p.path:
        local = (base_dir / unquote(p.path)).resolve()
        root = base_dir.resolve()
        if not local.is_relative_to(root):
            return ["LOCAL_PATH_ESCAPE"]
        if require_exists and not local.is_file():
            problems.append("MISSING_LOCAL_FILE")
    return problems


def inspect(source: str, *, base_dir: Path, strict_local: bool = True) -> dict:
    tree = PageParser()
    tree.feed(source)
    errors = []
    def add(message: str):
        if message not in errors:
            errors.append(message)
    if not tree.title.strip():
        add("MISSING_TITLE")
    if len(tree.headings) != 1 or not tree.headings[0].strip():
        add("MISSING_OR_MULTIPLE_H1")
    if not any(m.get("name") == "viewport" and m.get("content") for m in tree.metas):
        add("MISSING_VIEWPORT_META")
    dup = [k for k, n in Counter(tree.ids).items() if n > 1]
    if dup:
        add("DUPLICATE_DOM_IDS:" + ",".join(sorted(dup)))
    ids = set(tree.ids)
    refs = []
    for anchor in tree.anchors:
        target = anchor.get("href")
        refs.append(target)
        for problem in resolve_reference(target or "", base_dir, ids, require_exists=strict_local):
            add("ANCHOR_" + problem)
        if anchor.get("target") == "_blank":
            rel = set((anchor.get("rel") or "").split())
            if not {"noopener", "noreferrer"} <= rel:
                add("UNSAFE_NEW_TAB")
        if not anchor.get("aria-label") and not target:
            add("UNLABELED_ANCHOR")
    for asset in tree.assets:
        value = asset["value"]
        # Whitelisted asset references, but never infer an image's on-screen quality.
        for problem in resolve_reference(value, base_dir, ids, require_exists=strict_local):
            add("ASSET_" + problem)
    for button in tree.buttons:
        if not button["text"].strip() and not button["attrs"].get("aria-label"):
            add("BUTTON_WITHOUT_ACCESSIBLE_NAME")
    for select in tree.selects:
        control_id = select["attrs"].get("id")
        if not select["wrapped_in_label"] and control_id not in tree.label_refs and not select["attrs"].get("aria-label"):
            add("UNLABELED_SELECT")
    for image in tree.images:
        if image.get("alt") is None:
            add("IMAGE_WITHOUT_ALT")
    for script in tree.scripts:
        if script.get("src", "").lower().startswith("http:"):
            add("INSECURE_SCRIPT_DEPENDENCY")
    return {
        "schema": "missioncontrol.html_quality.static.v1",
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "title": tree.title.strip(),
        "h1": tree.headings[0].strip() if len(tree.headings) == 1 else None,
        "dom_id_count": len(tree.ids),
        "anchor_count": len(tree.anchors),
        "button_count": len(tree.buttons),
        "select_count": len(tree.selects),
        "image_count": len(tree.images),
        "external_link_count": sum(urlparse(x or "").scheme in ALLOWED_PROTOCOLS for x in refs),
        "errors": sorted(errors),
        "status": "FAIL" if errors else "PASS",
        "evidence_level": "STATIC_LOCAL_CHECK_ONLY",
        "merge_admission": "HOLD",
        "authority_transfer": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--allow-unmaterialized-local", action="store_true")
    args = ap.parse_args()
    result = inspect(args.html.read_text(encoding="utf-8"),
                     base_dir=args.html.parent,
                     strict_local=not args.allow_unmaterialized_local)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "errors": result["errors"], "source_sha256": result["source_sha256"]}, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
