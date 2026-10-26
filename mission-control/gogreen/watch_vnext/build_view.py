#!/usr/bin/env python3
"""CODE PURPLE N2 watch flightdeck: read-only canonical source projection.

No alternate census producer, private QPS data, GitHub token, runner dispatch,
watch scheduler, engineering release credit or automatic Pages deployment.
The source read is pinned by a full git commit SHA and object (blob) identity.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = "mission-control/gogreen/scale-dock/real/receipt/scale-dock.json"
REPO_URL = "https://github.com/GBOGEB/pipeline-automation-hub"
SCHEMA = "codepurple.watch.flightdeck/n2"
OWNER_SCHEMA = "codepurple.scale-dock.receipt.v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

# Each scalar is copied from the existing canonical scale-dock receipt, never
# remeasured. Unknown is represented by None, not zero or false.
FIELDS = (
    ("window_pulses", "Native observation pulses", "red_metrics.window_pulses",
     "Historical replay window, not freshly authenticated fleet breadth"),
    ("ever_red", "Ever-RED manifestations", "red_metrics.ever_red_in_window",
     "Occurrences in bounded historical pulse window; not causal roots"),
    ("red_burndown", "Manifestation burndown", "red_metrics.red_burndown",
     "Signed historical manifestation difference; not verified repairs"),
    ("recovery_rate", "Manifestation recovery fraction", "red_metrics.recovery_rate",
     "Source-defined fraction; not a global closure rate"),
    ("regression_rate", "Manifestation regression fraction", "red_metrics.regression_rate",
     "Source-defined fraction; not a fleet quality guarantee"),
    ("observed", "Observed source-bound cells", "source_bound_breadth.observed",
     "Historical three-public-repository cohort; not canonical six-repo #531"),
    ("eligible", "Eligible source-bound cells", "source_bound_breadth.eligible",
     "Historical source-defined denominator; not 42-cell authenticated census"),
    ("dock_consistency", "Observed dock consistency", "dock_consistency.state",
     "Agreements where sampled; no missing-source success"),
    ("shadow_regime", "Shadow workload regime", "shadow_proposals.regime",
     "Read-only proposal, no runner dispatch"),
)
MIP = (
    ("01", "Journal and last-qualified cursor", "SOURCE ADAPTER", "#881 / #882"),
    ("02", "Five distinct source identities", "CURRENT-HEAD PROOF", "#881"),
    ("03", "ZIP bytes + semantic acceptance", "POST-MERGE VALIDATION", "#878"),
    ("04", "Noncompensating required gates", "INDEPENDENT REVIEW", "#881"),
    ("05", "Producer/consumer authority", "SOURCE READBACK", "#530 / #531 / #533"),
    ("06", "One owned watch / no overlap", "OWNER DISPOSITION", "Scheduler"),
    ("07", "JUnit test accounting", "NATIVE COHORT", "ABACUS"),
    ("08", "Coverage population contract", "MATCHED BLOBS", "ABACUS / CODEX"),
    ("09", "Root / fingerprint / occurrence", "OWNER CLOSURE", "EVERRED"),
    ("10", "Runner capacity telemetry", "ACTUAL WORKER HOURS", "GoGREEN"),
    ("11", "Stability and notification", "QUALIFIED REPLAY", "#881 / #882"),
    ("12", "Navigable dashboard", "BROWSER + HOSTED QA", "This view"),
    ("13", "PCA and BT eligibility", "STATISTICAL VALIDATION", "gg_MATH"),
    ("14", "Mutation / reverse testing", "EXACT-HEAD RECEIPTS", "GoGREEN"),
    ("15", "Session-to-repo handover", "REPLAYABLE CHECKPOINT", "#876"),
)


def require(value, message):
    if not value:
        raise ValueError("WATCH_VIEW_HOLD:" + message)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()


def at(sha, path):
    require(isinstance(sha, str) and SHA40.fullmatch(sha) is not None,
            "full source commit SHA needed")
    require(path == SOURCE, "noncanonical source path")
    blob = git("rev-parse", f"{sha}:{path}")
    require(SHA40.fullmatch(blob) is not None, "source blob cannot be pinned")
    value = json.loads(git("cat-file", "blob", blob))
    return blob, value


def pick(obj, path):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def project(doc, source_sha, blob_oid):
    require(isinstance(doc, dict) and doc.get("schema") == OWNER_SCHEMA,
            "unexpected owner producer schema")
    require(doc.get("merge_admission") == "HOLD"
            and doc.get("authority_transfer") is False
            and doc.get("dispatch_authorized") is False,
            "source authority mismatch")
    require(doc.get("cohort_id") == "REAL-DEFAULT-HEADS-THREE-PUBLIC-REPOS",
            "unapproved source population")
    require(isinstance(source_sha, str) and SHA40.fullmatch(source_sha) is not None,
            "source SHA")
    require(isinstance(blob_oid, str) and SHA40.fullmatch(blob_oid) is not None,
            "source blob")
    require(isinstance(doc.get("red_metrics"), dict)
            and isinstance(doc.get("source_bound_breadth"), dict),
            "required owner projection absent")
    entries = []
    for ident, label, source_path, qualifier in FIELDS:
        value = pick(doc, source_path)
        if value is not None:
            require(type(value) in (int, float, str), "non-scalar owner field " + ident)
        entries.append({"id": ident, "label": label,
                        "value": value, "state": "OBSERVED" if value is not None else "UNKNOWN",
                        "source_path": source_path, "qualifier": qualifier})
    observed = pick(doc, "source_bound_breadth.observed")
    eligible = pick(doc, "source_bound_breadth.eligible")
    if observed is not None or eligible is not None:
        require(type(observed) is int and type(eligible) is int
                and 0 <= observed <= eligible and eligible > 0,
                "inconsistent observed population")
    return {
        "schema": SCHEMA,
        "source": {"repository": "GBOGEB/pipeline-automation-hub",
                   "commit_sha": source_sha, "path": SOURCE, "blob_oid": blob_oid,
                   "owner": "mission-control/gogreen/scale_dock.py"},
        "classification": "HISTORICAL_SOURCE_BOUND_READONLY_VIEW",
        "fresh_authenticated_42_cell_breadth": None,
        "current_head_coverage": None,
        "independent_root_closures": None,
        "eligible_independent_review": None,
        "required_status_enforcement": None,
        "qps_owner_readback": "RESTRICTED_OWNER_RETURN",
        "merge_admission": "HOLD", "formal_engineering_credit_delta": 0,
        "security_waiver": "NONE", "authority_transfer": False,
        "dispatch_authorized": False, "published_pages_verified": False,
        "fields": entries,
        "planning": [{"id": "MIP-" + n, "action": action, "next_proof": proof,
                      "navigation": nav, "status": "PROPOSED_NOT_QUALIFIED"}
                     for n, action, proof, nav in MIP],
    }


def _safe(value):
    if value is None:
        return "UNKNOWN"
    if type(value) is float:
        return format(value, ".4g")
    return str(value)


def render(snapshot):
    require(snapshot["schema"] == SCHEMA and snapshot["merge_admission"] == "HOLD",
            "false readiness")
    source = snapshot["source"]
    source_url = f"{REPO_URL}/blob/{source['commit_sha']}/{source['path']}"
    cards = "".join(
        '<article class="metric"><span class="label">' + html.escape(f["label"]) +
        '</span><strong>' + html.escape(_safe(f["value"])) +
        '</strong><small>' + html.escape(f["qualifier"]) +
        '</small><code>' + html.escape(f["source_path"]) + '</code></article>'
        for f in snapshot["fields"]
    )
    actions = "".join(
        "<tr><th scope='row'>" + html.escape(x["id"]) + "</th><td>" +
        html.escape(x["action"]) + "</td><td>" +
        html.escape(x["next_proof"]) + "</td><td>" +
        html.escape(x["status"]) + "</td></tr>"
        for x in snapshot["planning"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>CODE PURPLE Watch vNext | Mission Control evidence flightdeck</title>
<style>
:root{{--paper:#fbf7ed;--card:#fffdf8;--ink:#2d2132;--muted:#716674;--purple:#4f236d;--violet:#80509d;--border:#ddd1df;--pink:#f6dce8;--warn:#844126}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Aptos","Segoe UI",system-ui,sans-serif;overflow-x:hidden}}
a{{color:var(--purple);overflow-wrap:anywhere}}
a:focus-visible,summary:focus-visible{{outline:3px solid var(--violet);outline-offset:3px}}
header{{background:var(--purple);color:#fff;padding:25px max(20px,calc((100vw - 1180px)/2)) 20px}}
header a{{color:#fff}}
h1{{font-size:clamp(1.55rem,3.2vw,2.4rem);margin:4px 0}}
header p{{max-width:770px;color:#eee5f2;margin:0}}
nav{{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}}
nav a{{padding:9px 14px;border:1px solid #ad91bb;border-radius:8px;text-decoration:none;min-height:44px}}
main{{max-width:1200px;margin:auto;padding:24px 18px 60px}}
h2{{font-size:1.24rem;margin:12px 0}}
.meta{{color:var(--muted);font-size:.91rem}}
.label{{font-weight:700;color:var(--purple)}}
.hold{{font-weight:800;color:var(--warn)}}
.notice{{padding:16px;border-left:5px solid var(--purple);background:#f3e7f3;border-radius:5px;margin-bottom:22px}}
.metricgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:14px}}
.metric{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;display:flex;flex-direction:column;min-width:0;gap:7px}}
.metric strong{{font-size:clamp(22px,3vw,29px);overflow-wrap:anywhere}}
.metric code{{font:11px Consolas,monospace;color:var(--muted);overflow-wrap:anywhere}}
.metric small{{color:var(--muted)}}
.unknown{{font-weight:750;color:var(--warn)}}
.panel{{background:var(--card);border:1px solid var(--border);padding:18px;border-radius:10px;margin-top:20px}}
.tablewrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:690px}}
th,td{{text-align:left;border-bottom:1px solid var(--border);padding:10px;vertical-align:top}}
thead th{{background:var(--pink);color:var(--purple);position:sticky;top:0}}
tbody th{{font:600 12px Consolas,monospace}}
details{{padding:12px 0}}summary{{cursor:pointer;font-weight:700}}
code{{overflow-wrap:anywhere}}
footer{{border-top:1px solid var(--border);color:var(--muted);font-size:.88rem;padding-top:20px}}
@media(max-width:550px){{main{{padding:18px 12px}}header{{padding:18px 14px}}nav a{{flex:1 1 130px}}.panel{{padding:12px}}.metric{{padding:13px}}}}
</style></head>
<body><header><div class="meta" style="color:#e2cfe8">MISSION CONTROL / CODE PURPLE / N2 CANDIDATE</div>
<h1>Watch vNext · Evidence flightdeck</h1>
<p>Canonical source-bound historical measurements, governed dependencies and missing proof. This is a read-only projection, not a replacement for the authenticated census or Method Atlas.</p>
<nav aria-label="Flightdeck sections"><a href="#metrics">Source metrics</a><a href="#gates">Admission gates</a><a href="#mip">MIP queue</a><a href="#sources">Source identity</a></nav>
</header><main>
<section class="notice" aria-label="Readiness notice"><b class="hold">MERGE ADMISSION: HOLD</b> · No release, engineering acceptance or security waiver. The canonical six-repository 42-cell authenticated breadth remains <b>UNKNOWN</b> in this view. <b>Private QPS evidence is excluded.</b></section>
<section id="metrics"><h2>Canonical historical measurements</h2>
<p class="meta">Verbatim values from the pinned scale-dock owner receipt. These are a three-public-repository historical replay, not the fresh authenticated #531 cohort.</p>
<div class="metricgrid">{cards}</div></section>
<section id="gates" class="panel"><h2>Noncompensating admission gates</h2>
<p><b class="hold">HOLD</b> remains effective regardless of historical metric improvements. Independent review: <span class="unknown">UNKNOWN</span>; required-status enforcement: <span class="unknown">UNKNOWN</span>; exact-current-main coverage: <span class="unknown">UNKNOWN</span>; accepted causal-root closures: <span class="unknown">UNKNOWN</span>.</p>
<p>Fresh source authentication and publication proof require separate canonical producer receipts. This page neither dispatches workers nor sends notifications.</p></section>
<section id="mip" class="panel"><h2>MIP-01–15 · Next governed work</h2>
<p class="meta">Planning registry only. These 15 actions are <b>not qualified completions</b>; refer to the source-owned handover for actual dispositions.</p>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Scope</th><th>Required next proof</th><th>Status in this view</th></tr></thead><tbody>{actions}</tbody></table></div></section>
<section id="sources" class="panel"><h2>Golden thread / provenance</h2>
<details id="provenance"><summary>Show exact source identity and interpretation limits</summary>
<p>Repository: <code>{html.escape(source["repository"])}</code></p>
<p>Read-at commit: <code id="source-sha">{source["commit_sha"]}</code></p>
<p>Source blob: <code id="source-blob">{source["blob_oid"]}</code></p>
<p>Source file: <a href="{html.escape(source_url, quote=True)}">{html.escape(source["path"])}</a></p>
<p>Owner: <code>{html.escape(source["owner"])}</code></p>
<p>Authority: <code>HISTORICAL_SOURCE_BOUND_READONLY_VIEW</code>; QPS: <code>RESTRICTED_OWNER_RETURN</code>; current hosted deployment: <code>NOT_VERIFIED</code>.</p>
</details>
<p><a href="{REPO_URL}/pull/876">Lossless N0/N1 handover</a> · <a href="{REPO_URL}/pull/881">Transition consumer</a> · <a href="{REPO_URL}/pull/882">Native feed</a> · <a href="{REPO_URL}/pull/890">QPS owner-edge candidate</a> · <a href="{REPO_URL}/pull/891">Signed proof hardening</a></p></section>
<footer>Snapshot read at source git SHA <code>{source["commit_sha"]}</code>. Structural or browser QA does not confer engineering acceptance. No HTML Pages deployment is claimed.</footer>
</main></body></html>
"""


def build(revision, out):
    sha = git("rev-parse", f"{revision}^{{commit}}")
    require(SHA40.fullmatch(sha) is not None, "unresolved source commit")
    oid, owner = at(sha, SOURCE)
    view = project(owner, sha, oid)
    page = render(view).encode("utf-8")
    snapshot = (json.dumps(view, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    manifest = {
        "schema": "codepurple.watch.flightdeck-manifest/n2",
        "source_sha": sha, "source_blob_oid": oid,
        "owner_file": SOURCE,
        "sha256": {"index.html": hashlib.sha256(page).hexdigest(),
                   "snapshot.json": hashlib.sha256(snapshot).hexdigest()},
        "structural_qa": "PENDING_SEPARATE_RUN",
        "browser_qa": "PENDING_SEPARATE_RUN",
        "hosted_qa": "DEFER",
        "merge_admission": "HOLD",
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(page)
    (out / "snapshot.json").write_bytes(snapshot)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                       encoding="utf-8")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description="Build nonauthoritative CODE PURPLE watch view")
    p.add_argument("--rev", default="HEAD")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    print(json.dumps(build(args.rev, args.out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
