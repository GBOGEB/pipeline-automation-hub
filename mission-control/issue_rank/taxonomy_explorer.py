#!/usr/bin/env python3
"""Offline filterable issue/PR taxonomy explorer; PUBLIC by default.

Consumes the existing issue_rank.json only. Never rewrites source titles,
publishes private rows or grants engineering, merge, review or closure credit.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

import title_taxonomy as tax

RANK_SCHEMA = "jade.issue-rank.v1"
RANK_SCHEMAS = frozenset((RANK_SCHEMA, "jade.issue-rank.v2"))
SCHEMA = "jade.taxonomy-explorer.v1"
SHA = re.compile(r"^[0-9a-f]{40}$", re.I)
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
CSS = """
:root {--bg:#fbf9f5;--surface:#fff;--ink:#30243c;--muted:#6d6170;--line:#ddd0de;
  --accent:#682a80;--accent-soft:#f1e5ee;--warn:#934d63}
@media(prefers-color-scheme:dark){:root{--bg:#201b25;--surface:#302638;
  --ink:#faf4f9;--muted:#d8c8d7;--line:#59415f;--accent:#e7addc;
  --accent-soft:#432d45;--warn:#ffc9d4}}
body{font:14px/1.5 system-ui,sans-serif;color:var(--ink);background:var(--bg);
 margin:0 auto;max-width:1500px;padding:20px}
h1{font-size:24px;margin:0 0 6px}h2{font-size:17px;margin:20px 0 8px}
small,.muted{color:var(--muted)} .surface{background:var(--surface);
 padding:16px;border:1px solid var(--line);border-radius:10px;margin:12px 0}
.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
label{display:block;font-size:12px;font-weight:600}
input,select{display:block;width:100%;min-width:0;box-sizing:border-box;
 background:var(--surface);color:var(--ink);border:1px solid var(--line);
 border-radius:6px;padding:8px;margin-top:4px}
.table-wrap{overflow-x:auto;max-width:100%}table{border-collapse:collapse;
 width:100%;font-size:12px}
td,th{padding:7px 8px;text-align:left;border-bottom:1px solid var(--line);
 vertical-align:top}th{white-space:nowrap;color:var(--muted)}
.num{font-variant-numeric:tabular-nums;text-align:right}
a{color:var(--accent)}tr[hidden]{display:none}
.badge{padding:1px 7px;border-radius:12px;background:var(--accent-soft);
 white-space:nowrap}
.notice{border-left:3px solid var(--warn);padding-left:10px}
footer{margin-top:24px;color:var(--muted)}
"""
SCRIPT = """
(function () {
  "use strict";
  const fields = ["repo","type","family","topic","cluster","cohort","classification"];
  const elements = Object.fromEntries(fields.map(k => [k,document.getElementById("f-"+k)]));
  const text = document.getElementById("f-text");
  const rows = [...document.querySelectorAll("#taxonomy-rows tr")];
  function tokens(raw) {return raw ? raw.split("|") : [];}
  function update() {
    const counts = Object.create(null);
    let shown = 0;
    for (const row of rows) {
      const search = (text.value || "").toLocaleLowerCase();
      const visible = fields.every(k => {
        const wanted = elements[k].value;
        return !wanted || (k === "topic" || k === "cluster" || k === "cohort"
          ? tokens(row.dataset[k]).includes(wanted)
          : row.dataset[k] === wanted);
      }) && (!search || row.textContent.toLocaleLowerCase().includes(search));
      row.hidden = !visible;
      if (visible) {shown++; counts[row.dataset.repo] = (counts[row.dataset.repo] || 0) + 1;}
    }
    document.getElementById("visible-count").textContent = String(shown);
    for (const cell of document.querySelectorAll("[data-repo-count]")) {
      cell.textContent = String(counts[cell.dataset.repoCount] || 0);
    }
  }
  for (const el of Object.values(elements)) el.addEventListener("change", update);
  text.addEventListener("input", update);
  update();
})();
"""


def _escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _options(values: set[str], first: str) -> str:
    return '<option value="">' + _escape(first) + "</option>" + "".join(
        '<option value="' + _escape(v) + '">' + _escape(v) + "</option>"
        for v in sorted(values))


def collect(model: dict, *, include_private: bool = False) -> dict:
    if model.get("schema") not in RANK_SCHEMAS:
        raise ValueError("UNSUPPORTED_RANK_MODEL")
    heads = model.get("heads")
    if not isinstance(heads, dict) or not heads:
        raise ValueError("MISSING_SOURCE_HEADS")
    for repo, h in heads.items():
        if not REPO.fullmatch(repo) or not (SHA.fullmatch(str(h.get("head_sha") or ""))
                                         or model["schema"] == "jade.issue-rank.v2"
                                         and h.get("private") is True and h.get("head_sha") is None):
            raise ValueError("INVALID_REPO_OR_HEAD")
    seen, rows, excluded = set(), [], 0
    for item in model.get("items", []):
        repo, ident, kind = item.get("repo"), item.get("key"), item.get("type")
        if repo not in heads or kind not in ("Issue", "PullRequest"):
            raise ValueError("ITEM_REPO_OR_TYPE_INVALID")
        number = item.get("number")
        if not isinstance(number, int) or number <= 0 or ident != repo + "#" + str(number):
            raise ValueError("ITEM_IDENTITY_INVALID")
        if ident in seen:
            raise ValueError("DUPLICATE_WORK_ITEM")
        seen.add(ident)
        if bool(item.get("private")) != bool(heads[repo].get("private")):
            raise ValueError("PRIVATE_REPO_INCONSISTENT")
        taxonomy = item.get("title_taxonomy")
        if not isinstance(taxonomy, dict) or taxonomy.get("schema") != tax.SCHEMA:
            raise ValueError("TAXONOMY_SCHEMA_MISMATCH")
        if item.get("private") and not include_private:
            excluded += 1
            continue
        rows.append({
            "repo": repo, "number": number, "key": ident, "type": kind,
            "family": taxonomy.get("family") or "UNCLASSIFIED",
            "path": taxonomy.get("path") or "UNCLASSIFIED",
            "topic": sorted(set(taxonomy.get("topic_families") or [])),
            "cluster": sorted(set(taxonomy.get("technical_clusters") or [])),
            "cohort": sorted(set(taxonomy.get("codes") or [])),
            "classification": taxonomy.get("classification") or "UNCLASSIFIED",
            "lint": sorted(set(taxonomy.get("lint") or [])),
            "title": item.get("title") or "",
        })
    rows.sort(key=lambda x: (x["repo"], x["type"], x["number"]))
    return {"rows": rows, "excluded_private": excluded,
            "heads": {repo: h["head_sha"] for repo, h in sorted(heads.items())
                      if include_private or not h.get("private")},
            "timestamp": model.get("fetched_at") or "UNKNOWN",
            "visibility": "PRIVATE_LOCAL_ONLY" if include_private else "PUBLIC_PROJECTION"}


def render(model: dict, *, include_private: bool = False) -> str:
    obj = collect(model, include_private=include_private)
    rows = obj["rows"]
    repos = {r["repo"] for r in rows}
    kinds = {r["type"] for r in rows}
    families = {r["family"] for r in rows}
    topics = {x for r in rows for x in r["topic"]}
    clusters = {x for r in rows for x in r["cluster"]}
    cohorts = {x for r in rows for x in r["cohort"]}
    classifications = {r["classification"] for r in rows}
    counts = Counter(r["repo"] for r in rows)
    table_rows = []
    for r in rows:
        url = ("https://github.com/" + r["repo"] +
               ("/issues/" if r["type"] == "Issue" else "/pull/") + str(r["number"]))
        data = {
            "repo": r["repo"], "type": r["type"], "family": r["family"],
            "topic": "|".join(r["topic"]), "cluster": "|".join(r["cluster"]),
            "cohort": "|".join(r["cohort"]), "classification": r["classification"],
        }
        attrs = " ".join('data-' + k + '="' + _escape(v) + '"' for k, v in data.items())
        cells = [
            _escape(r["repo"]), _escape(r["type"]),
            '<a href="' + _escape(url) + '">#' + str(r["number"]) + "</a>",
            '<span class="badge">' + _escape(r["family"]) + "</span>",
            _escape(r["path"]), _escape(", ".join(r["topic"])),
            _escape(", ".join(r["cluster"])), _escape(", ".join(r["cohort"])),
            _escape(r["classification"]), _escape(", ".join(r["lint"])),
            _escape(r["title"]),
        ]
        table_rows.append("<tr " + attrs + ">" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>")
    filters = [
        ("repo", "Repository", repos), ("type", "Item type", kinds),
        ("family", "Action type", families), ("topic", "Programme / topic", topics),
        ("cluster", "Technical cluster", clusters), ("cohort", "Wave / cohort code", cohorts),
        ("classification", "Classification", classifications),
    ]
    controls = "".join('<label for="f-' + key + '">' + _escape(label)
                       + '<select id="f-' + key + '">' + _options(vals, "All")
                       + "</select></label>"
                       for key, label, vals in filters)
    head_rows = "".join("<tr><td>" + _escape(repo) + "</td><td class=\"num\">"
                        + str(counts[repo]) + "</td><td class=\"num\" data-repo-count=\""
                        + _escape(repo) + "\">" + str(counts[repo]) + "</td></tr>"
                        for repo in sorted(repos))
    head_pins = " · ".join(_escape(repo) + "@" + _escape(sha[:12])
                           for repo, sha in obj["heads"].items())
    table_head = "".join("<th>" + x + "</th>" for x in
                         ("Repository", "Type", "Work item", "Action", "Prefix path",
                          "Programme/topics", "Technical clusters", "Cohort",
                          "Classification", "Lint", "Original title"))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>JADE taxonomy explorer</title><style>{CSS}</style></head><body>'
            f'<h1>Portfolio PR + issue taxonomy</h1>'
            f'<p class="muted">Schema {_escape(SCHEMA)} / {_escape(tax.SCHEMA)}'
            f' · snapshot {_escape(obj["timestamp"])} · {_escape(obj["visibility"])}'
            f' · NON_ATOMIC_SOURCE_HEADS</p>'
            f'<p class="muted">Source heads: {head_pins}</p>'
            f'<div class="surface notice">Read-only classification, not an owner decision.'
            f' Related-family graph candidates and overlapping memberships are not'
            f' additive or evidence of closure. No merge / release / engineering credit.'
            f' Private items excluded: {obj["excluded_private"]}.</div>'
            f'<div class="surface"><h2>Filter work items</h2><div class="filters">'
            f'{controls}<label for="f-text">Title / text search'
            f'<input id="f-text" type="search" placeholder="Filter visible rows"></label>'
            f'</div><p aria-live="polite"><strong id="visible-count">{len(rows)}</strong>'
            f' of {len(rows)} visible source items</p></div>'
            f'<div class="surface"><h2>Repository peer counts</h2><div class="table-wrap">'
            f'<table><thead><tr><th>Repository</th><th>Baseline</th>'
            f'<th>Matching filters</th></tr></thead><tbody>{head_rows}</tbody></table>'
            f'</div></div><div class="surface"><h2>Facet-linked items</h2>'
            f'<div class="table-wrap"><table><thead><tr>{table_head}</tr></thead>'
            f'<tbody id="taxonomy-rows">{"".join(table_rows)}</tbody></table></div></div>'
            f'<footer>Local static view; no network calls, no write actions.'
            f' Never publish PRIVATE_LOCAL_ONLY output on GitHub Pages.</footer>'
            f'<script>{SCRIPT}</script></body></html>\n')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--private-local", action="store_true")
    args = ap.parse_args(argv)
    model = json.loads(args.model.read_text(encoding="utf-8"))
    page = render(model, include_private=args.private_local)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8", newline="\n")
    print("TAXONOMY_EXPLORER:", "PRIVATE_LOCAL_ONLY" if args.private_local else "PUBLIC_PROJECTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
