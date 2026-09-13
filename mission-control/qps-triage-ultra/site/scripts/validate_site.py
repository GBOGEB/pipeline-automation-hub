#!/usr/bin/env python3
"""QPS triage J1-J6 static publication validator."""
from __future__ import annotations

import json
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parents[1]
ROOT = SITE.parents[2]
WEB = ROOT / "qps-triage-ultra" / "web"
BUILT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else SITE / "_site"

errors: list[str] = []

def require(ok: bool, message: str) -> None:
    if not ok:
        errors.append(message)

# J1: contracts
with (WEB / "QPS_UI_TOKENS_v1.2.json").open(encoding="utf-8") as fh:
    tokens = json.load(fh)
require(tokens.get("schema") == "qps.ui.tokens.v1.2", "token schema mismatch")
require(tokens.get("principles", {}).get("meaning_not_color_alone") is True, "color-only semantics forbidden")

with (WEB / "QPS_WEB_GATE_REGISTRY_v1.json").open(encoding="utf-8") as fh:
    gates = json.load(fh)
expected_gates = {f"J{i}_{name}" for i, name in enumerate(["SOURCE", "GENERATE", "STRUCTURE", "VISUAL", "IDENTITY", "REPEAT"], 1)}
actual_gates = {g["id"] for g in gates.get("gates", [])}
require(actual_gates == expected_gates, f"J1-J6 gate mismatch: {actual_gates}")

# J3/J4: structure and CSS contract
css = (SITE / "assets" / "css" / "qps-ui-1.2.css").read_text(encoding="utf-8")
for marker in ["qps-state-pass", "qps-state-partial", "qps-state-blocked", "qps-state-held", "qps-state-control", "prefers-reduced-motion", "@media print"]:
    require(marker in css, f"CSS contract missing {marker}")

source_index = (SITE / "index.md").read_text(encoding="utf-8")
for heading in ["Fleet", "Topology", "Crew", "Execution", "REX", "Historian", "Evidence economics", "PCA / BT"]:
    require(f"## {heading}" in source_index, f"atlas missing {heading} view")

# J5: built identity
index_html = BUILT / "index.html"
require(index_html.exists(), f"built index missing: {index_html}")
if index_html.exists():
    html = index_html.read_text(encoding="utf-8")
    for attr in ["data-qps-ui=\"1.2\"", "data-release-id=", "data-source-sha=", "data-schema-version=", "data-evidence-state="]:
        require(attr in html, f"built HTML missing {attr}")
    require("UNBOUND" not in html, "built HTML contains UNBOUND provenance")
    sha = re.search(r'data-source-sha="([0-9a-f]{40})"', html)
    require(bool(sha), "source_sha is not an exact 40-character Git SHA")
    require("mermaid.min.js" not in html and "cdn.jsdelivr.net/npm/mermaid" not in html, "CDN Mermaid is forbidden for governed evidence")

if errors:
    print("QPS WEB VALIDATION: FAIL")
    for item in errors:
        print(f"- {item}")
    raise SystemExit(1)
print("QPS WEB VALIDATION: PASS")
print(f"validated={BUILT}")
