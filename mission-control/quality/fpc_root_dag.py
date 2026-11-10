"""First-Pass Closure root-red DAG: trace every red gate evaluation back to its source.

    python mission-control/quality/fpc_root_dag.py fetch   --days 30 --cache DIR
    python mission-control/quality/fpc_root_dag.py project --cache DIR --out DIR [--now ISO]

``fetch`` (network, read only, resumable): every completed run of the First-Pass Closure Gate
workflow in the window, with its receipt artifact (the gate's own ``reason``), plus, per PR, whether
the Codex connector said it hit its usage limit. Results land in ``DIR/evaluations.jsonl`` and
``DIR/prs.json``.

``project`` (offline): builds the cause model, attributes every red evaluation to one
**source** (a root node with no causes), layers the DAG with Kahn's method (the canonical
``lifecycle.topo_layers``), and writes:

* ``fpc_root_dag.json``: the model, its Kahn waves, per-node counts, per-window and
  per-iteration metrics, and the known-failure ledger;
* ``fpc_root_dag.md``: a reading of the DAG, the ledger and the windows;
* ``fpc_windows.svg``, ``fpc_iterations.svg``, ``fpc_dag.svg``: plots, written with no third-party libraries.

Every source has a class:

* ``INHERITED``: upstream of the PR, such as a Codex quota or the gate's own policy on controller paths.
  A PR cannot fix it by changing its code.
* ``TRANSIENT``: timing. The gate ran before the review or proof finished, and a later evaluation of the same
  head got past that step.
* ``PR_CAUSED``: the PR's own content, such as material Codex findings or a proof that failed on its head and was
  not passed later.
* ``PROCESS``: the PR's paperwork, such as a stale receipt. The author can fix it without code changes.
* ``UNKNOWN``: not classified. It is reported, never counted as quiet.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import importlib.util
import io
import json
import re
import subprocess
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

REPO = "GBOGEB/pipeline-automation-hub"
WORKFLOW = "first-pass-closure-gate.yml"
ARTIFACT = "first-pass-closure-gate"
CODEX_LOGIN = "chatgpt-codex-connector"
QUOTA_RE = re.compile(r"reached your Codex usage limits", re.I)
HERE = Path(__file__).resolve().parent
LIFECYCLE = HERE.parent / "jade_temple" / "devops" / "lifecycle.py"
SCHEMA = "missioncontrol.fpc_root_dag.v1"

# Windows in hours; None = total.
WINDOWS = [("4h", 4), ("6h", 6), ("8h", 8), ("12h", 12), ("24h", 24), ("2d", 48), ("3d", 72), ("5d", 120),
           ("7d", 168), ("14d", 336), ("21d", 504), ("30d", 720), ("total", None)]
ITER_BLOCK = 10

# ------------------------------------------------------------------ cause model
# node -> (kind, class, description). kind: SOURCE (root), REASON (gate reason code), OUTCOME.
NODES = {
    "SRC_CODEX_QUOTA": ("SOURCE", "INHERITED", "Codex connector hit its review usage limit"),
    "SRC_CODEX_REVIEW_PENDING": ("SOURCE", "TRANSIENT", "gate ran before the Codex review finished on this head"),
    "SRC_CODEX_REVIEW_ABSENT": ("SOURCE", "UNKNOWN", "no completed Codex review on the head and no quota notice"),
    "SRC_CONTROLLER_PATH": ("SOURCE", "INHERITED", "PR touches a protected FPC controller path (bootstrap policy)"),
    "SRC_PROOF_PENDING": ("SOURCE", "TRANSIENT", "proof workflow not finished on this head yet"),
    "SRC_PROOF_FAILED": ("SOURCE", "PR_CAUSED", "proof workflow failed on this head and never passed later"),
    "SRC_HEAD_MOVED": ("SOURCE", "PROCESS", "receipt or run bound to an older head"),
    "SRC_RECEIPT_ABSENT": ("SOURCE", "PROCESS", "PR body had no FPC receipt and the gate did not derive one"),
    "SRC_CODE_FINDINGS": ("SOURCE", "PR_CAUSED", "material Codex findings on the exact head"),
    "SRC_GATE_INFRA": ("SOURCE", "INHERITED", "GitHub API or gate infrastructure error"),
    "SRC_UNCLASSIFIED": ("SOURCE", "UNKNOWN", "reason code not in the cause model"),
    "R_CODEX_REVIEW_NOT_COMPLETED": ("REASON", None, "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD"),
    "R_CONTROL_PLANE_BOOTSTRAP": ("REASON", None, "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP"),
    "R_MISSING_PROOF": ("REASON", None, "MISSING_REQUIRED_PROOF_PURPOSE / RUN_NOT_SUCCESS"),
    "R_STALE_HEAD": ("REASON", None, "STALE_HEAD / RUN_HEAD_MISMATCH / INVALID_RECEIPT_HEAD_SHA"),
    "R_RECEIPT_MISSING": ("REASON", None, "MISSING_RECEIPT"),
    "R_CODEX_FINDINGS": ("REASON", None, "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD"),
    "R_GATE_ERROR": ("REASON", None, "PR_HEAD_UNAVAILABLE / POLICY_* / other gate errors"),
    "R_OTHER": ("REASON", None, "any other reason code"),
    "FPC_RED": ("OUTCOME", None, "First-Pass Closure status red on the PR head"),
    "MERGE_BLOCKED": ("OUTCOME", None, "required check red: the ruleset refuses the merge"),
}
EDGES = [
    ("SRC_CODEX_QUOTA", "R_CODEX_REVIEW_NOT_COMPLETED", "CAUSES"),
    ("SRC_CODEX_REVIEW_PENDING", "R_CODEX_REVIEW_NOT_COMPLETED", "CAUSES"),
    ("SRC_CODEX_REVIEW_ABSENT", "R_CODEX_REVIEW_NOT_COMPLETED", "CAUSES"),
    ("SRC_CONTROLLER_PATH", "R_CONTROL_PLANE_BOOTSTRAP", "CAUSES"),
    ("SRC_PROOF_PENDING", "R_MISSING_PROOF", "CAUSES"),
    ("SRC_PROOF_FAILED", "R_MISSING_PROOF", "CAUSES"),
    ("SRC_HEAD_MOVED", "R_STALE_HEAD", "CAUSES"),
    ("SRC_RECEIPT_ABSENT", "R_RECEIPT_MISSING", "CAUSES"),
    ("SRC_CODE_FINDINGS", "R_CODEX_FINDINGS", "CAUSES"),
    ("SRC_GATE_INFRA", "R_GATE_ERROR", "CAUSES"),
    ("SRC_UNCLASSIFIED", "R_OTHER", "CAUSES"),
] + [(r, "FPC_RED", "CAUSES") for r, v in NODES.items() if v[0] == "REASON"] + [("FPC_RED", "MERGE_BLOCKED", "CAUSES")]

REASON_NODE = [
    (re.compile(r"^CODEX_REVIEW_NOT_COMPLETED"), "R_CODEX_REVIEW_NOT_COMPLETED"),
    (re.compile(r"^CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP"), "R_CONTROL_PLANE_BOOTSTRAP"),
    (re.compile(r"^MISSING_RECEIPT"), "R_RECEIPT_MISSING"),
    (re.compile(r"^(MISSING_REQUIRED_PROOF_PURPOSE|RUN_NOT_SUCCESS|NO_PROOF_RUN|NO_ALLOWLISTED_PROOF_RUN)"), "R_MISSING_PROOF"),
    (re.compile(r"^(STALE_HEAD|RUN_HEAD_MISMATCH|TRIGGER_HEAD_MISMATCH|INVALID_RECEIPT_HEAD_SHA)"), "R_STALE_HEAD"),
    (re.compile(r"^CODEX_MATERIAL_FINDINGS"), "R_CODEX_FINDINGS"),
    (re.compile(r"^(PR_HEAD_UNAVAILABLE|PR_BASE_UNAVAILABLE|POLICY_|ADMISSION_ARGUMENTS|API_|HTTP|GATE_ERROR|"
                r"UNTRUSTED_PROOF|PROOF_WORKFLOW_MUTATED|CODEX_SUMMARY_AUTHOR|NO_RECEIPT_ARTIFACT|"
                r"PRE_EVALUATOR_FAILURE|GitHub API \d+)"), "R_GATE_ERROR"),
]


def is_codex(login: str | None) -> bool:
    """The Codex connector, as the REST API (``…[bot]``) or GraphQL (bare) names it."""
    return (login or "").removesuffix("[bot]") == CODEX_LOGIN


def quota_notice(comments: list[dict]) -> bool:
    """True if the Codex connector told this PR it hit its review usage limit."""
    return any(is_codex((c.get("user") or c.get("author") or {}).get("login")) and QUOTA_RE.search(c.get("body") or "")
               for c in comments)


def _lifecycle():
    spec = importlib.util.spec_from_file_location("jade_lifecycle", LIFECYCLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def kahn_waves() -> list[list[str]]:
    """Kahn layering of the cause model through the canonical owner (AGENTS.md: topological layering)."""
    return _lifecycle().topo_layers(list(NODES), EDGES)


def reason_node(reason: str | None) -> str:
    for pat, node in REASON_NODE:
        if reason and pat.search(reason):
            return node
    return "R_OTHER"


def attribute(ev: dict, later_on_head: list[dict], pr: dict) -> str:
    """The source node of one red evaluation. ``later_on_head``: later evaluations of the same PR head."""
    node = reason_node(ev.get("reason"))
    got_past = [e for e in later_on_head if e["status"] == "PASS" or reason_node(e.get("reason")) != node]
    if node == "R_CODEX_REVIEW_NOT_COMPLETED":
        if pr.get("codex_quota"):
            return "SRC_CODEX_QUOTA"
        return "SRC_CODEX_REVIEW_PENDING" if got_past else "SRC_CODEX_REVIEW_ABSENT"
    if node == "R_MISSING_PROOF":
        return "SRC_PROOF_PENDING" if got_past else "SRC_PROOF_FAILED"
    return {"R_CONTROL_PLANE_BOOTSTRAP": "SRC_CONTROLLER_PATH", "R_STALE_HEAD": "SRC_HEAD_MOVED",
            "R_RECEIPT_MISSING": "SRC_RECEIPT_ABSENT",
            "R_CODEX_FINDINGS": "SRC_CODE_FINDINGS", "R_GATE_ERROR": "SRC_GATE_INFRA"}.get(node, "SRC_UNCLASSIFIED")


def ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def attribute_all(evals: list[dict], prs: dict, heads: dict | None = None) -> list[dict]:
    """Each evaluation plus ``reason_node``, ``source``, ``klass``; chronological.

    ``heads`` maps a head SHA to its PR number. The gate's runs mostly carry no PR, so the head
    decides; a PR the run did name wins. Later evaluations are matched by head SHA.
    """
    heads = heads or {}
    evals = sorted(({**e, "pr": e.get("pr") or heads.get(e["head_sha"])} for e in evals), key=lambda e: e["created_at"])
    by_head = defaultdict(list)
    for e in evals:
        by_head[e["head_sha"]].append(e)
    out = []
    for e in evals:
        row = dict(e)
        if e["status"] == "PASS":
            row.update(reason_node=None, source=None, klass="PASS")
        else:
            seq = by_head[e["head_sha"]]
            later = seq[seq.index(e) + 1:]
            src = attribute(e, later, prs.get(str(e.get("pr")), {}))
            row.update(reason_node=reason_node(e.get("reason")), source=src, klass=NODES[src][1])
        out.append(row)
    return out


def summarize(rows: list[dict]) -> dict:
    n, red = len(rows), [r for r in rows if r["klass"] != "PASS"]
    klass = Counter(r["klass"] for r in red)
    heads = defaultdict(list)
    for r in rows:
        heads[(r.get("pr"), r["head_sha"])].append(r)
    first_pass = sum(1 for seq in heads.values() if seq[0]["status"] == "PASS")
    closed = sum(1 for seq in heads.values() if seq[-1]["status"] == "PASS")
    return {
        "evaluations": n, "pass": n - len(red), "red": len(red),
        "red_rate": round(len(red) / n, 4) if n else None,
        "inherited_share_of_red": round(klass["INHERITED"] / len(red), 4) if red else None,
        "pr_caused_share_of_red": round(klass["PR_CAUSED"] / len(red), 4) if red else None,
        "by_class": dict(sorted(klass.items())),
        "by_source": dict(Counter(r["source"] for r in red).most_common()),
        "prs": len({r.get("pr") for r in rows}), "heads": len(heads),
        "first_pass_rate": round(first_pass / len(heads), 4) if heads else None,
        "head_closure_rate": round(closed / len(heads), 4) if heads else None,
    }


def windows(rows: list[dict], now: dt.datetime) -> list[dict]:
    out = []
    for name, hours in WINDOWS:
        sel = rows if hours is None else [r for r in rows if ts(r["created_at"]) >= now - dt.timedelta(hours=hours)]
        out.append({"window": name, "hours": hours, **summarize(sel)})
    return out


def iterations(rows: list[dict], block: int = ITER_BLOCK) -> list[dict]:
    """Blocks of ``block`` consecutive evaluations; N is the newest block, labelled N, N-10, N-20 ..."""
    out = []
    total = len(rows)
    for end in range(total, 0, -block):
        chunk = rows[max(0, end - block):end]
        label = "N" if end == total else f"N-{total - end}"
        out.append({"label": label, "first": chunk[0]["created_at"], "last": chunk[-1]["created_at"], **summarize(chunk)})
    return list(reversed(out))


def ledger(rows: list[dict]) -> list[dict]:
    """Known failures by source: count, PRs, first and last seen. INHERITED rows are the merge-route candidates."""
    by = defaultdict(list)
    for r in rows:
        if r["klass"] != "PASS":
            by[r["source"]].append(r)
    out = []
    for src, rs in by.items():
        out.append({"id": "FPC-" + src[4:], "source": src, "class": NODES[src][1], "what": NODES[src][2],
                    "evaluations": len(rs), "prs": sorted({r.get("pr") for r in rs if r.get("pr")}),
                    "first_seen": rs[0]["created_at"], "last_seen": rs[-1]["created_at"],
                    "pr_can_fix": NODES[src][1] in ("PR_CAUSED", "PROCESS")})
    return sorted(out, key=lambda x: (-x["evaluations"], x["id"]))


def node_counts(rows: list[dict]) -> dict:
    c = Counter()
    for r in rows:
        if r["klass"] != "PASS":
            c[r["source"]] += 1
            c[r["reason_node"]] += 1
            c["FPC_RED"] += 1
            c["MERGE_BLOCKED"] += 1
    return dict(c)


# ------------------------------------------------------------------ plots (plain SVG)
COLORS = {"INHERITED": "#c2410c", "TRANSIENT": "#a3a3a3", "PR_CAUSED": "#2563eb", "PROCESS": "#7c3aed",
          "UNKNOWN": "#111827", "PASS": "#16a34a"}
ORDER = ["PASS", "TRANSIENT", "PROCESS", "PR_CAUSED", "INHERITED", "UNKNOWN"]


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def stacked_svg(series: list[dict], title: str, xkey: str) -> str:
    """100%-stacked bars of evaluations by class, one bar per series row, with red rate labels."""
    w, h, left, top, bottom = 920, 360, 60, 40, 70
    n = max(1, len(series))
    bw = (w - left - 20) / n
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Segoe UI, Arial, sans-serif" font-size="11">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>', f'<text x="{left}" y="22" font-size="14" font-weight="600">{_esc(title)}</text>']
    ph = h - top - bottom
    for i, s in enumerate(series):
        x = left + i * bw
        total = s["evaluations"] or 0
        counts = {"PASS": s["pass"], **s["by_class"]}
        y = top + ph
        for k in ORDER:
            v = counts.get(k, 0)
            if not total or not v:
                continue
            hh = ph * v / total
            y -= hh
            out.append(f'<rect x="{x + 2:.1f}" y="{y:.1f}" width="{bw - 4:.1f}" height="{hh:.1f}" fill="{COLORS[k]}"><title>{k}: {v}</title></rect>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{top + ph + 14}" text-anchor="middle">{_esc(s[xkey])}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{top + ph + 27}" text-anchor="middle" fill="#555">n={total}</text>')
        if total:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{top - 4}" text-anchor="middle" fill="#555">{round(100 * s["red"] / total)}%</text>')
    lx = left
    for k in ORDER:
        out.append(f'<rect x="{lx}" y="{h - 22}" width="10" height="10" fill="{COLORS[k]}"/><text x="{lx + 14}" y="{h - 13}">{k}</text>')
        lx += 110
    out.append(f'<text x="{w - 20}" y="22" text-anchor="end" fill="#555">label above bar = red rate</text></svg>')
    return "\n".join(out)


def dag_svg(waves: list[list[str]], counts: dict) -> str:
    colw, rowh = 230, 34
    h = 50 + rowh * max(len(wv) for wv in waves)
    w = 30 + colw * len(waves)
    pos = {}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Segoe UI, Arial, sans-serif" font-size="11">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
    for i, wave in enumerate(waves):
        out.append(f'<text x="{20 + i * colw}" y="18" font-weight="600">Kahn wave {i}</text>')
        for j, nd in enumerate(wave):
            pos[nd] = (20 + i * colw, 30 + j * rowh)
    for a, b, _ in EDGES:
        if counts.get(a) and counts.get(b):
            (x1, y1), (x2, y2) = pos[a], pos[b]
            out.append(f'<line x1="{x1 + 200}" y1="{y1 + 12}" x2="{x2}" y2="{y2 + 12}" stroke="#999"/>')
    for nd, (x, y) in pos.items():
        kind, klass, _ = NODES[nd]
        fill = COLORS.get(klass, "#e5e7eb") if kind == "SOURCE" else "#e5e7eb"
        txt = "#fff" if kind == "SOURCE" else "#111"
        c = counts.get(nd, 0)
        op = "1" if c else "0.35"
        out.append(f'<g opacity="{op}"><rect x="{x}" y="{y}" width="200" height="24" rx="4" fill="{fill}"/>'
                   f'<text x="{x + 6}" y="{y + 16}" fill="{txt}">{_esc(nd)} · {c}</text></g>')
    out.append("</svg>")
    return "\n".join(out)


# ------------------------------------------------------------------ report
def pct(v):
    return "-" if v is None else f"{100 * v:.0f}%"


def markdown(doc: dict) -> str:
    L = [f"# FPC root-red DAG, {doc['generated_at']}", "",
         f"Source: `{REPO}` First-Pass Closure Gate runs since {doc['since']} ({doc['totals']['evaluations']} evaluations, "
         f"{doc['totals']['prs']} PRs). Each red evaluation is traced to one source node; Kahn waves come from "
         "`lifecycle.topo_layers`.", "", "## Kahn waves (source → reason → outcome)", ""]
    for i, wave in enumerate(doc["kahn_waves"]):
        L.append(f"- wave {i}: " + ", ".join(f"`{n}` ({doc['node_counts'].get(n, 0)})" for n in wave))
    L += ["", "## Known-failure ledger", "", "| Id | Class | PR can fix | Evaluations | PRs | First seen | Last seen | What |",
          "|---|---|---|---|---|---|---|---|"]
    for x in doc["ledger"]:
        L.append(f"| {x['id']} | {x['class']} | {'yes' if x['pr_can_fix'] else 'no'} | {x['evaluations']} | {len(x['prs'])} | "
                 f"{x['first_seen'][:16]} | {x['last_seen'][:16]} | {x['what']} |")
    L += ["", "## Windows (back from now)", "", "| Window | Evals | Red | Red rate | Inherited share | PR-caused share | First-pass rate | Heads closed |",
          "|---|---|---|---|---|---|---|---|"]
    for wv in doc["windows"]:
        L.append(f"| {wv['window']} | {wv['evaluations']} | {wv['red']} | {pct(wv['red_rate'])} | {pct(wv['inherited_share_of_red'])} | "
                 f"{pct(wv['pr_caused_share_of_red'])} | {pct(wv['first_pass_rate'])} | {pct(wv['head_closure_rate'])} |")
    L += ["", f"## Iterations (blocks of {ITER_BLOCK} evaluations; N = newest)", "",
          "| Block | From | To | Red rate | Inherited share | Top source |", "|---|---|---|---|---|---|"]
    for it in doc["iterations"][-12:]:
        top = next(iter(it["by_source"]), "-")
        L.append(f"| {it['label']} | {it['first'][:16]} | {it['last'][:16]} | {pct(it['red_rate'])} | {pct(it['inherited_share_of_red'])} | {top} |")
    L += ["", "Plots: `fpc_windows.svg`, `fpc_iterations.svg`, `fpc_dag.svg`.", ""]
    return "\n".join(L)


def project(cache: Path, out: Path, now: dt.datetime) -> dict:
    evals = [json.loads(x) for x in (cache / "evaluations.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = attribute_all(evals, _load(cache / "prs.json"), _load(cache / "heads.json"))
    waves = kahn_waves()
    counts = node_counts(rows)
    doc = {"schema": SCHEMA, "repository": REPO, "generated_at": now.isoformat().replace("+00:00", "Z"),
           "since": rows[0]["created_at"] if rows else None, "nodes": {k: list(v) for k, v in NODES.items()},
           "edges": EDGES, "kahn_waves": waves, "node_counts": counts, "totals": summarize(rows),
           "windows": windows(rows, now), "iterations": iterations(rows), "ledger": ledger(rows)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "fpc_root_dag.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    (out / "fpc_root_dag.md").write_text(markdown(doc), encoding="utf-8", newline="\n")
    (out / "fpc_windows.svg").write_text(stacked_svg(doc["windows"], "FPC evaluations by root class, per window back from now", "window"),
                                         encoding="utf-8", newline="\n")
    (out / "fpc_iterations.svg").write_text(stacked_svg(doc["iterations"][-24:], f"FPC evaluations by root class, blocks of {ITER_BLOCK} (N = newest)", "label"),
                                            encoding="utf-8", newline="\n")
    (out / "fpc_dag.svg").write_text(dag_svg(waves, counts), encoding="utf-8", newline="\n")
    return doc


# ------------------------------------------------------------------ fetch (network)
def _token() -> str:
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, env=env, check=True).stdout.strip()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_API = urllib.request.build_opener(_NoRedirect)


def _get(url: str, token: str, raw: bool = False):
    """GET from the GitHub API. A redirect (artifact downloads go to blob storage) is followed
    without the Authorization header, so the token never leaves api.github.com."""
    req = urllib.request.Request(url if url.startswith("http") else "https://api.github.com" + url,
                                 headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with _API.open(req, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        with urllib.request.urlopen(e.headers["Location"], timeout=60) as r:
            data = r.read()
    return data if raw else json.loads(data)


def _runs_for_day(day: str, token: str) -> list[dict]:
    out, page = [], 1
    while True:
        d = _get(f"/repos/{REPO}/actions/workflows/{WORKFLOW}/runs?per_page=100&page={page}&created={day}", token)
        out += d["workflow_runs"]
        if len(d["workflow_runs"]) < 100:
            return out
        page += 1


def _reason(run: dict, token: str) -> dict:
    arts = _get(f"/repos/{REPO}/actions/runs/{run['id']}/artifacts", token)["artifacts"]
    art = next((a for a in arts if a["name"] == ARTIFACT and not a["expired"]), None)
    rec = {}
    if art:
        z = zipfile.ZipFile(io.BytesIO(_get(art["archive_download_url"], token, raw=True)))
        rec = json.loads(z.read(z.namelist()[0]))
    prs = [p["number"] for p in run.get("pull_requests") or []]
    status = "PASS" if rec.get("merge_allowed") is True else ("FAIL" if rec else ("PASS" if run["conclusion"] == "success" else "FAIL"))
    return {"run_id": run["id"], "created_at": run["created_at"], "event": run["event"], "conclusion": run["conclusion"],
            "head_sha": run["head_sha"], "pr": prs[0] if prs else None, "title": run.get("display_title"),
            "status": status, "reason": rec.get("reason") or (None if status == "PASS" else "NO_RECEIPT_ARTIFACT")}


def _reason_or_none(run: dict, token: str) -> dict | None:
    """``_reason`` that returns None on a network or API error, so the run is retried on the next fetch."""
    try:
        return _reason(run, token)
    except (urllib.error.URLError, OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print(f"  skip run {run['id']}: {type(e).__name__}", flush=True)
        return None


def fetch(days: int, cache: Path, lookups_only: bool = False) -> None:
    """Fetch evaluations (unless ``lookups_only``), then the head -> PR map and the per-PR quota notice.

    The artifact pass costs about two API calls per evaluation (30 days ~ 3,500 calls), so a
    second pass with ``--lookups-only`` reuses the cached evaluations after a rate-limit reset."""
    token = _token()
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / "evaluations.jsonl"
    if lookups_only:
        return _lookups(path, cache, token)
    done = {json.loads(x)["run_id"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()} if path.exists() else set()
    today = dt.datetime.now(dt.timezone.utc).date()
    runs = []
    for i in range(days + 1):
        runs += _runs_for_day((today - dt.timedelta(days=i)).isoformat(), token)
    todo = [r for r in runs if r["status"] == "completed" and r["conclusion"] in ("success", "failure") and r["id"] not in done]
    print(f"runs={len(runs)} evaluations_to_fetch={len(todo)} cached={len(done)}", flush=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh, cf.ThreadPoolExecutor(8) as ex:
        for k, row in enumerate(ex.map(lambda r: _reason_or_none(r, token), todo), 1):
            if row is None:
                continue
            fh.write(json.dumps(row) + "\n")
            if k % 100 == 0:
                print(f"  {k}/{len(todo)}", flush=True)
    _lookups(path, cache, token)


def _lookups(path: Path, cache: Path, token: str) -> None:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    heads = _load(cache / "heads.json")
    for sha in sorted({r["head_sha"] for r in rows} - set(heads)):
        pulls = _get_patient(f"/repos/{REPO}/commits/{sha}/pulls", token)
        if pulls is not None:
            heads[sha] = pulls[0]["number"] if pulls else None
            _save(cache / "heads.json", heads)
    prs = _load(cache / "prs.json")
    for n in sorted({r["pr"] or heads.get(r["head_sha"]) for r in rows} - {None} - {int(k) for k in prs}):
        comments = _get_patient(f"/repos/{REPO}/issues/{n}/comments?per_page=100", token)
        if comments is not None:
            prs[str(n)] = {"codex_quota": quota_notice(comments)}
            _save(cache / "prs.json", prs)
    print(f"evaluations={len(rows)} heads={len(heads)} prs={len(prs)} quota_prs={sum(v['codex_quota'] for v in prs.values())}")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(p: Path, d: dict) -> None:
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8", newline="\n")


def _get_patient(url: str, token: str, tries: int = 5):
    """``_get`` that backs off on 403/429/5xx (secondary rate limits); None after the last try."""
    import time
    for n in range(tries):
        try:
            return _get(url, token)
        except urllib.error.HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503) or n + 1 == tries:
                print(f"  give up {url}: HTTP {e.code}", flush=True)
                return None
            time.sleep(int(e.headers.get("Retry-After") or 30 * (n + 1)))
        except (urllib.error.URLError, OSError):
            time.sleep(10 * (n + 1))
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--days", type=int, default=30)
    f.add_argument("--cache", type=Path, required=True)
    f.add_argument("--lookups-only", action="store_true", help="skip the run/artifact pass; reuse cached evaluations")
    p = sub.add_parser("project")
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--now", help="ISO UTC; default now")
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        fetch(a.days, a.cache, a.lookups_only)
    else:
        now = ts(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
        doc = project(a.cache, a.out, now)
        print(f"FPC_ROOT_DAG evaluations={doc['totals']['evaluations']} red={doc['totals']['red']} "
              f"inherited_share={pct(doc['totals']['inherited_share_of_red'])} waves={len(doc['kahn_waves'])} out={a.out.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
