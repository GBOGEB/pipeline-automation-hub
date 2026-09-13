#!/usr/bin/env python3
"""QPS triage J1-J6 static publication validator."""
from __future__ import annotations

import json
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parents[1]
TRIAGE = SITE.parent
WEB = TRIAGE / "web"
REPO = TRIAGE.parents[1]
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
require((WEB / "QPS_BROWSER_SUPPORT_v1.2.md").exists(), "browser support contract missing")

# Shared Next/Jekyll token vocabulary
next_adapter = REPO / "app" / "lib" / "qps-ui-tokens.ts"
next_contract_page = REPO / "app" / "app" / "qps-ui-contract" / "page.tsx"
require(next_adapter.exists(), "Next token adapter missing")
require(next_contract_page.exists(), "Next token contract route missing")
if next_adapter.exists():
    adapter = next_adapter.read_text(encoding="utf-8")
    require("QPS_UI_TOKENS_v1.2.json" in adapter, "Next adapter does not consume governed token JSON")

# Browser target consistency
package_path = REPO / "app" / "package.json"
with package_path.open(encoding="utf-8") as fh:
    package = json.load(fh)
browser_rules = [str(x).lower() for x in package.get("browserslist", [])]
require(not any(rule.strip() == "ie >= 11" for rule in browser_rules), "operational app still claims IE11 support")
require(any("not ie 11" in rule for rule in browser_rules), "IE11 exclusion is not explicit")

# J3/J4: structure and CSS contract
css = (SITE / "assets" / "css" / "qps-ui-1.2.css").read_text(encoding="utf-8")
for marker in ["qps-state-pass", "qps-state-partial", "qps-state-blocked", "qps-state-held", "qps-state-control", "prefers-reduced-motion", "@media print"]:
    require(marker in css, f"CSS contract missing {marker}")

source_index = (SITE / "index.md").read_text(encoding="utf-8")
for heading in ["Fleet", "Topology", "Crew", "Execution", "REX", "Historian", "Evidence economics", "PCA / BT"]:
    require(f"## {heading}" in source_index, f"atlas missing {heading} view")

mmd = SITE / "assets" / "diagrams" / "qps-web-architecture.mmd"
svg = SITE / "assets" / "diagrams" / "qps-web-architecture.svg"
require(mmd.exists(), "canonical Mermaid source missing")
require(svg.exists(), "durable SVG rendering missing")
require("qps-web-architecture.svg" in source_index, "durable SVG is not published in atlas")

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
