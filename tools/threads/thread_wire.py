"""Thread wireframe: one record per Claude thread (repo, branch, OID -> intent, TODO, current, next). Read-only.

    python tools/threads/thread_wire.py DIR/wire

Inputs in ``DIR/wire`` (a local, private folder, never this repository):

* ``sessions.json``: the raw ``list_sessions {include_archived: true, limit: 200}`` array.
* ``wire_*.json``: per-family records, one object per thread::

      {id, title, parent, state, repo, pr, pr_state, branch, head_oid, merge_oid, base,
       worktree?, key_files, intent, done, todo, current, next,
       waiting_on_user {value, what}, unexecuted_user_turn, verdict}

Outputs in ``DIR``: ``THREAD_WIRE.json`` (wireframed records plus bare rows for the rest)
and ``THREAD_MAP.md`` (action list, then the tree by ``startedBy``). Optional inputs in
``DIR``: ``parked_intents.json`` + ``parked_intents_filed.tsv`` (section 0) and
``PROGRESS_LOG.md`` (section 4).

Verdicts: RESUME, CHECK, KEEP, PARKED (an issue owns it), DONE. To refresh, re-pull
``sessions.json``, re-read the tails of non-DONE threads, update their records and re-run.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ORDER = {"RESUME": 0, "CHECK": 1, "KEEP": 2, "PARKED": 3, "DONE": 4, "-": 5}
ACT = ("RESUME", "CHECK", "KEEP", "PARKED")
NUMBERED = re.compile(r"^(L\d|Lane [A-Z]|U\d+|MR |M\d|W\d{3}|Next wave|P\d|GM-|J\d)")


def short(oid):
    return oid[:10] if oid else "-"


def merge(sessions: list[dict], wire: dict[str, dict]) -> list[dict]:
    kids = collections.defaultdict(list)
    for s in sessions:
        if s.get("startedBy"):
            kids[s["startedBy"]].append(s["sessionId"])
    merged = []
    for s in sessions:
        r = dict(wire.get(s["sessionId"], {}))
        r.setdefault("id", s["sessionId"])
        r.setdefault("title", s["title"])
        r.setdefault("parent", (s.get("startedBy") or "")[6:14] or None)
        r["archived"] = s["isArchived"]
        r["running"] = s["isRunning"]
        r["lastActivityAt"] = s["lastActivityAt"]
        r.setdefault("pr", s.get("prNumber"))
        r.setdefault("pr_state", s.get("prState"))
        r.setdefault("verdict", "-")
        r["startedBy"] = s.get("startedBy")
        r["children"] = kids.get(s["sessionId"], [])
        merged.append(r)
    return merged


def flag(r):
    return "R" if r["running"] else ("L" if not r["archived"] else "A")


def line(r, depth):
    pr = (f"#{r['pr']} " + (r.get("pr_state") or "")).strip() if r.get("pr") else "no PR"
    oid = short(r.get("merge_oid") or r.get("head_oid"))
    return ("  " * depth + f"- [{flag(r)}] **{r['verdict']}** {r['title']} `{r['id'][6:14]}` · "
            + (r.get("repo") or "?") + f" · {pr} · `{oid}`")


def action_block(r) -> list[str]:
    w = r.get("waiting_on_user") or {}
    where = (f"- **Where:** {r.get('repo')} · branch `{r.get('branch') or '-'}` · PR {r.get('pr') or '-'} "
             + (r.get("pr_state") or "") + f" · head `{short(r.get('head_oid'))}` · merge `{short(r.get('merge_oid'))}`")
    if r.get("worktree"):
        where += " · worktree " + r["worktree"]
    out = [f"### {r['verdict']} · {r['title']} `{r['id']}` [{flag(r)}]", where]
    if r.get("key_files"):
        out.append("- **Files:** " + ", ".join("`" + k + "`" for k in r["key_files"][:6]))
    out += [f"- **Intent:** {r.get('intent')}", f"- **Current:** {r.get('current')}"]
    out += ["  - [ ] " + t for t in r.get("todo") or []]
    out.append(f"- **Next:** {r.get('next')}")
    if w.get("value"):
        out.append(f"- **Waiting on you:** {w.get('what')}")
    if r.get("unexecuted_user_turn"):
        out.append(f"- **Unexecuted turn:** {r['unexecuted_user_turn']}")
    return out + [""]


def render(merged: list[dict], n_wire: int, title_date: str, extra_dir: Path | None = None) -> list[str]:
    rec = {r["id"]: r for r in merged}
    out = [f"# Thread wireframe, {title_date} (map mode: nothing archived, moved or deleted)", "",
           "Built by `tools/threads/thread_wire.py` from `wire/` (list_sessions + transcript tails + `gh pr view`).",
           "`[A]` archived, `[L]` live idle, `[R]` running. OID = merge commit, else PR head. Full records: `THREAD_WIRE.json`.", ""]
    cnt = collections.Counter(r["verdict"] for r in merged)
    live = sum(not r["archived"] for r in merged)
    out += [f"{len(merged)} threads: {live} live, {len(merged) - live} archived; {n_wire} wireframed. Verdicts: "
            + ", ".join(f"{v} {cnt.get(v, 0)}" for v in ORDER if v != "-"), ""]
    if extra_dir is not None:
        out += parked_section(extra_dir)
    out += ["## 1 · Act on these (RESUME / CHECK / KEEP / PARKED)", ""]
    for r in sorted((r for r in merged if r["verdict"] in ACT), key=lambda r: (ORDER[r["verdict"]], r["title"])):
        out += action_block(r)
    out += ["## 2 · Tree by parent (families first)", ""]
    roots = [r for r in merged if not r.get("startedBy") or r["startedBy"] not in rec]

    def walk(r, depth):
        out.append(line(r, depth))
        for k in sorted(r["children"], key=lambda k: rec[k]["title"] if k in rec else k):
            if k in rec:
                walk(rec[k], depth + 1)

    for r in sorted((r for r in roots if r["children"]), key=lambda r: (-len(r["children"]), r["title"])):
        walk(r, 0)
    out += ["", "## 3 · Standalone threads", ""]
    for r in sorted((r for r in roots if not r["children"]), key=lambda r: r["lastActivityAt"], reverse=True):
        out.append(line(r, 0) + (" · numbered" if NUMBERED.match(r["title"]) else ""))
    out.append("")
    if extra_dir is not None and (extra_dir / "PROGRESS_LOG.md").exists():
        out += ["## 4 · Progress log", "", (extra_dir / "PROGRESS_LOG.md").read_text(encoding="utf-8").strip(), ""]
    return out


def parked_section(d: Path) -> list[str]:
    filed, spec_f = d / "parked_intents_filed.tsv", d / "parked_intents.json"
    if not (filed.exists() and spec_f.exists()):
        return []
    spec = json.loads(spec_f.read_text(encoding="utf-8"))
    srcs = {i["id"]: i["sessions"][0][1][6:14] for i in spec.get("items", [])}
    for cm in spec.get("comment_only", []):
        m = re.search(r"local_([0-9a-f]{8})", cm["body"])
        srcs[cm["id"]] = m.group(1) if m else "?"
    out = ["## 0 · Parked intents filed", "", "| Id | Where | How | Source thread |", "|---|---|---|---|"]
    for ln in filed.read_text(encoding="utf-8").splitlines():
        pid, repo, num, how = ln.split("\t")
        out.append(f"| {pid} | GBOGEB/{repo}#{num} | {how} | `{srcs.get(pid, '?')}` |")
    return out + [""]


def main(argv=None) -> int:
    src = Path((argv or sys.argv[1:])[0])
    sessions = json.loads((src / "sessions.json").read_text(encoding="utf-8"))
    wire = {}
    for f in sorted(src.glob("wire_*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            wire[r["id"]] = r
    merged = merge(sessions, wire)
    (src.parent / "THREAD_WIRE.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    date = src.parent.name if re.fullmatch(r"\d{4}-\d{2}-\d{2}", src.parent.name) else "undated"
    (src.parent / "THREAD_MAP.md").write_text("\n".join(render(merged, len(wire), date, src.parent)), encoding="utf-8")
    print(f"wrote {src.parent / 'THREAD_MAP.md'} ({len(merged)} threads, {len(wire)} wireframed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
