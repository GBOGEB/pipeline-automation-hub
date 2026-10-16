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
    """Accessible review of canonical truth; embedded payload remains authoritative.

    Cards, labels and event samples are projections of the same canonical JSON.
    This adds visual comprehension, not new data or a separate HTML SSOT.
    """
    value_digest = canonical_truth_digest(truth)
    payload = _json_payload(truth)
    safe_payload = (
        payload.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    esc = lambda value: html.escape(str(value), quote=True)
    metrics = truth.get("metrics") if isinstance(truth.get("metrics"), dict) else {}
    selection = (
        truth.get("temporal_selection")
        if isinstance(truth.get("temporal_selection"), dict)
        else {}
    )
    names = (
        ("Events", "event_count"),
        ("Occurrences", "occurrence_count"),
        ("Root objects", "root_count"),
        ("Lineage edges", "lineage_edge_count"),
        ("Unknown-reader items", "unknown_needs_reader_count"),
    )
    cards = "".join(
        '<div class="card"><small>' + esc(label) + '</small><strong>'
        + esc(metrics.get(key, "UNKNOWN")) + "</strong></div>"
        for label, key in names
    )
    timeline = (
        '<p><b>Known at:</b> ' + esc(selection.get("known_at_utc", "UNKNOWN"))
        + ' · <b>Occurred by:</b> '
        + esc(selection.get("occurred_by_utc") or "unbounded")
        + ' · <b>Complete source chain verified:</b> '
        + esc(selection.get("full_ledger_verified", "UNKNOWN"))
        + ' · <b>Selected chain prefix:</b> '
        + esc(selection.get("chain_prefix", "UNKNOWN"))
        + "</p>"
        if selection else
        "<p>Current or historical event-boundary projection. "
        "No separate recorded-knowledge cutoff is asserted.</p>"
    )
    selected = selection.get("selected_event_ids") if selection else None
    events = selected if isinstance(selected, list) else truth.get("events_applied")
    events = events if isinstance(events, list) else []
    chips = "".join('<li><code>' + esc(x) + '</code></li>' for x in events[:32])
    if len(events) > 32:
        chips += '<li>… ' + str(len(events) - 32) + " more in source payload</li>"
    stylesheet = """<style>
:root{color-scheme:light;--ink:#192c42;--muted:#566b7d;--edge:#d7e1e9;--mint:#087d73}
*{box-sizing:border-box}body{font:15px/1.55 system-ui,-apple-system,sans-serif;color:var(--ink);background:#f5f8fb;margin:0}
main{max-width:1140px;margin:auto;padding:28px}h1{font-size:clamp(26px,4vw,42px);line-height:1.15}
small{color:var(--muted)}.eyebrow{font-size:12px;letter-spacing:.14em;font-weight:750;color:var(--mint)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card,section{background:white;border:1px solid var(--edge);border-radius:13px;padding:18px}
.card strong{font-size:30px;display:block;line-height:1.3}.card small{display:block}
section{margin:15px 0}code{overflow-wrap:anywhere;font:12px ui-monospace,SFMono-Regular,Consolas,monospace}
ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:6px;list-style:none;padding:0}
li{padding:7px;border-radius:7px;background:#e9f2f5}p{overflow-wrap:anywhere}
.warning{color:#8a541f}details{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
@media(max-width:500px){main{padding:12px}.card{padding:10px}.card strong{font-size:24px}}
</style>"""
    title = "Golden Thread Canonical Truth Rendition"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        '<meta name="golden-thread-truth-digest" content="'
        + esc(value_digest) + '"><title>Golden Thread Truth</title>'
        + stylesheet + "</head><body><main>"
        '<p class="eyebrow">MISSION CONTROL / GOLDEN THREAD / EVIDENCE REVIEW</p>'
        "<h1>" + title + "</h1>"
        '<p><b>Immutable semantic identity:</b> <code>'
        + esc(value_digest) + "</code></p>"
        '<p class="warning">Read-only rendition. Projection is not root '
        'closure, child acceptance, release admission or a new SSOT.</p>'
        '<div class="grid">' + cards + "</div>"
        '<section><h2>Historical perspective</h2>' + timeline
        + '<p><b>Boundary:</b> ' + esc(truth.get("boundary", "UNKNOWN"))
        + ' · <b>Authority transfer:</b> '
        + esc(truth.get("authority_transfer", "UNKNOWN")) + "</p></section>"
        '<section><h2>Applied event identities</h2>'
        '<p>Sample of the first 32 events. Full source identity remains embedded below.</p>'
        "<ul>" + chips + "</ul></section>"
        '<details><summary>Machine-readable canonical payload</summary><pre>'
        + esc(json.dumps(truth, indent=2, sort_keys=True, ensure_ascii=False))
        + "</pre></details>"
        '<script id="golden-thread-canonical-truth" type="application/json">'
        + safe_payload + "</script></main></body></html>\n"
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
