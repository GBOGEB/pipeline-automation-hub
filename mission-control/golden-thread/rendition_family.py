#!/usr/bin/env python3
"""Deterministic rendition-family generator and zero-delta verifier."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

import golden_thread as gt

RENDITION_SCHEMA = "missioncontrol.golden_thread_rendition_family.v1"
MD_RE = re.compile(r"```json\n(?P<payload>\{.*\})\n```", re.DOTALL)
HTML_RE = re.compile(
    r'<script id="golden-thread-canonical-truth" type="application/json">(?P<payload>.*?)</script>',
    re.DOTALL,
)


def canonical_truth_digest(truth):
    return gt.digest(truth)


def _json_payload(truth):
    return gt.cjson(truth)


def render_json(truth):
    return _json_payload(truth) + "\n"


def render_yaml(truth):
    # JSON is a valid YAML 1.2 subset. Keeping the canonical JSON payload removes
    # a second serializer authority while still yielding a real .yaml artifact.
    return _json_payload(truth) + "\n"


def render_markdown(truth):
    digest = canonical_truth_digest(truth)
    return (
        "# Golden Thread Canonical Truth Rendition\n\n"
        f"Canonical truth digest: `{digest}`\n\n"
        "```json\n"
        f"{_json_payload(truth)}\n"
        "```\n"
    )


def render_html(truth):
    digest = canonical_truth_digest(truth)
    payload = _json_payload(truth)
    safe_payload = (
        payload.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8">'
        f'<meta name="golden-thread-truth-digest" content="{html.escape(digest)}">'
        "<title>Golden Thread Truth</title></head><body>"
        "<h1>Golden Thread Canonical Truth Rendition</h1>"
        f"<p>Canonical truth digest: <code>{html.escape(digest)}</code></p>"
        '<script id="golden-thread-canonical-truth" type="application/json">'
        f"{safe_payload}</script>"
        "</body></html>\n"
    )


def render_family(truth):
    digest = canonical_truth_digest(truth)
    return {
        "schema": RENDITION_SCHEMA,
        "canonical_truth_digest": digest,
        "authority_transfer": False,
        "renditions": {
            "json": {
                "extension": ".json",
                "mime": "application/json",
                "content": render_json(truth),
                "truth_digest": digest,
            },
            "yaml": {
                "extension": ".yaml",
                "mime": "application/yaml",
                "content": render_yaml(truth),
                "truth_digest": digest,
            },
            "markdown": {
                "extension": ".md",
                "mime": "text/markdown",
                "content": render_markdown(truth),
                "truth_digest": digest,
            },
            "html": {
                "extension": ".html",
                "mime": "text/html",
                "content": render_html(truth),
                "truth_digest": digest,
            },
        },
    }


def extract_rendition(kind, content):
    if kind in {"json", "yaml"}:
        return json.loads(content)
    if kind == "markdown":
        match = MD_RE.search(content)
        if not match:
            raise gt.GoldenThreadError("markdown rendition lacks canonical JSON payload")
        return json.loads(match.group("payload"))
    if kind == "html":
        match = HTML_RE.search(content)
        if not match:
            raise gt.GoldenThreadError("HTML rendition lacks canonical truth script")
        return json.loads(match.group("payload"))
    raise gt.GoldenThreadError(f"unsupported rendition kind: {kind}")


def verify_family(truth, family):
    expected = canonical_truth_digest(truth)
    results = {}
    all_pass = (
        family.get("schema") == RENDITION_SCHEMA
        and family.get("canonical_truth_digest") == expected
        and family.get("authority_transfer") is False
    )
    for kind in ("json", "yaml", "markdown", "html"):
        item = (family.get("renditions") or {}).get(kind)
        if not isinstance(item, dict):
            results[kind] = {"status": "FAIL", "reason": "missing rendition"}
            all_pass = False
            continue
        try:
            extracted = extract_rendition(kind, item.get("content", ""))
            observed = canonical_truth_digest(extracted)
            status = "PASS" if observed == expected == item.get("truth_digest") else "FAIL"
            results[kind] = {
                "status": status,
                "expected_truth_digest": expected,
                "observed_truth_digest": observed,
                "declared_truth_digest": item.get("truth_digest"),
            }
            if status != "PASS":
                all_pass = False
        except (ValueError, TypeError, gt.GoldenThreadError) as exc:
            results[kind] = {"status": "FAIL", "reason": str(exc)}
            all_pass = False
    return {
        "schema": "missioncontrol.golden_thread_rendition_verification.v1",
        "status": "PASS" if all_pass else "FAIL",
        "canonical_truth_digest": expected,
        "rendition_count": len(results),
        "results": results,
        "authority_transfer": False,
    }


def write_family(truth, outdir, stem="GOLDEN_THREAD_TRUTH"):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    family = render_family(truth)
    manifest = {
        "schema": RENDITION_SCHEMA,
        "canonical_truth_digest": family["canonical_truth_digest"],
        "authority_transfer": False,
        "files": {},
    }
    for kind, item in family["renditions"].items():
        path = out / f"{stem}{item['extension']}"
        path.write_text(item["content"], encoding="utf-8")
        manifest["files"][kind] = {
            "path": path.name,
            "truth_digest": item["truth_digest"],
            "content_sha256": gt.digest(item["content"]),
        }
    manifest_path = out / f"{stem}_RENDITION_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return family, manifest


def verify_directory(truth, directory, manifest_name="GOLDEN_THREAD_TRUTH_RENDITION_MANIFEST.json"):
    root = Path(directory)
    manifest = json.loads((root / manifest_name).read_text(encoding="utf-8"))
    family = {
        "schema": manifest.get("schema"),
        "canonical_truth_digest": manifest.get("canonical_truth_digest"),
        "authority_transfer": manifest.get("authority_transfer"),
        "renditions": {},
    }
    for kind, meta in manifest.get("files", {}).items():
        content = (root / meta["path"]).read_text(encoding="utf-8")
        if gt.digest(content) != meta.get("content_sha256"):
            raise gt.GoldenThreadError(f"rendition content digest mismatch: {kind}")
        family["renditions"][kind] = {
            "content": content,
            "truth_digest": meta.get("truth_digest"),
        }
    return verify_family(truth, family)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render")
    p.add_argument("truth")
    p.add_argument("outdir")
    p.add_argument("--stem", default="GOLDEN_THREAD_TRUTH")
    p = sub.add_parser("verify")
    p.add_argument("truth")
    p.add_argument("directory")
    p.add_argument("--manifest", default="GOLDEN_THREAD_TRUTH_RENDITION_MANIFEST.json")
    args = parser.parse_args(argv)
    try:
        truth = _load(args.truth)
        if args.cmd == "render":
            family, manifest = write_family(truth, args.outdir, args.stem)
            result = verify_family(truth, family)
            result["manifest"] = manifest
        else:
            result = verify_directory(truth, args.directory, args.manifest)
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["status"] == "PASS" else 2
    except (OSError, ValueError, gt.GoldenThreadError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
