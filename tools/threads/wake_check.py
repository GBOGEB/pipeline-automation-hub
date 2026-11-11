"""Daily wake check: list parked intents whose triggers matched new GitHub activity. Read-only.

    python tools/threads/wake_check.py --pulse-dir DIR [--since 2026-10-25T00:00:00Z] [--no-state]

1. Finds every open ``parked-intent`` issue in GBOGEB and reads its marker through
   ``triway_burndown.parked_intent_meta`` (written by parked_intents.py).
2. Reads activity since the last run (state file ``DIR/wake_state.json``; first run: 24 h):
   PRs updated in each repo the triggers point at (title, changed files), the referenced
   issues and PRs, and comments on the parked issue itself.
3. Strong hit: a PR changed a file under a wake path, a referenced issue or PR was updated, or
   someone commented on the parked issue. Weak hit: a wake keyword in a PR title.
4. Writes ``DIR/<UTC date>/WAKE_CANDIDATES.md`` and ``.json`` and prints a one-line summary.
   A repo that could not be read is listed as unread, never treated as quiet, and the state
   window stays open until every repo was read.

It never unarchives, messages or comments: waking a thread stays the user's call.
DIR is a local, private working folder, never this repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    from . import _common as c
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _common as c


def parked() -> list[dict]:
    items = []
    for i in c.gh_json("search", "issues", "--owner", c.OWNER, "--label", c.LABEL, "--state", "open",
                       "--limit", "200", "--json", "repository,number,title,body,url"):
        meta = c.triway.parked_intent_meta(i.get("body"))
        if not meta or "wake" not in meta:
            continue
        items.append({"repo": i["repository"]["name"], "number": i["number"], "title": i["title"],
                      "url": i["url"], **meta})
    return items


def split_ref(ref: str, home: str) -> tuple[str, int]:
    m = re.fullmatch(r"(?:([\w.-]+))?#(\d+)", ref.strip())
    if not m:
        raise ValueError(ref)
    return (m.group(1) or home), int(m.group(2))


def prs_since(repo: str, since: str) -> list[dict]:
    return c.gh_json("pr", "list", "-R", f"{c.OWNER}/{repo}", "--state", "all", "--limit", "100",
                     "--search", f"updated:>={since[:10]}", "--json", "number,title,files,url,updatedAt,state")


def updated_since(repo: str, number: int, since: str) -> str | None:
    try:
        d = c.gh_json("api", f"repos/{c.OWNER}/{repo}/issues/{number}")
    except RuntimeError:
        return None
    return d["html_url"] if d.get("updated_at", "") >= since else None


def comments_since(repo: str, number: int, since: str) -> int:
    return len(c.gh_json("api", f"repos/{c.OWNER}/{repo}/issues/{number}/comments?since={since}"))


def match(item: dict, prs: dict[str, list[dict]], since: str, updated=updated_since, comments=comments_since) -> list[dict]:
    """Hits as {"strength": "strong"|"weak", "text": ...}; one line per PR with all its reasons."""
    w, hits = item["wake"], []
    refs = {split_ref(r, item["repo"]) for r in w.get("refs", [])}
    for pr in prs.get(item["repo"], []):
        if pr["number"] == item["number"] or (pr.get("updatedAt") or "") < since:
            continue
        files = [f["path"] for f in pr.get("files") or []]
        why = []
        for p in w.get("paths", []):
            n = sum(f.startswith(p) for f in files)
            if n:
                why.append(f"changes {n} file(s) under `{p}`")
        if (item["repo"], pr["number"]) in refs:
            why.append("is a referenced PR")
            refs.discard((item["repo"], pr["number"]))
        title = (pr.get("title") or "").lower()
        kw = [k for k in w.get("keywords", []) if k.lower() in title]
        if why or kw:
            reasons = why + (["title mentions " + ", ".join(repr(k) for k in kw)] if kw else [])
            hits.append({"strength": "strong" if why else "weak",
                         "text": f"PR #{pr['number']} ({pr['state'].lower()}) " + "; ".join(reasons) + f": {pr['url']}"})
    for repo, n in sorted(refs):
        url = updated(repo, n, since)
        if url:
            ref = f"#{n}" if repo == item["repo"] else f"{repo}#{n}"
            hits.append({"strength": "strong", "text": f"{ref} was updated: {url}"})
    k = comments(item["repo"], item["number"], since)
    if k:
        hits.append({"strength": "strong", "text": f"{k} new comment(s) on the parked issue itself"})
    return sorted(hits, key=lambda h: (h["strength"] != "strong", h["text"]))


def report(items: list[dict], rows: list[dict], unread: list[str], since: str, now: str) -> list[str]:
    cands = sorted((r for r in rows if r["hits"]), key=lambda r: (-r["strong"], -len(r["hits"])))
    out = [f"# Wake candidates, {now}", "",
           f"Activity since {since}. {len(items)} open parked intents, {len(cands)} with matching activity. "
           "Nothing was unarchived or posted.", ""]
    for r in cands:
        out += [f"## {r['title']} ({r['repo']}#{r['number']})", r["url"], "",
                "Source threads: " + ", ".join("`" + s + "`" for s in r.get("sessions", [])), ""]
        out += ["- **" + h["strength"] + "** " + h["text"] for h in r["hits"]] + [""]
        if r.get("sessions"):
            out += ["Wake: `unarchive_session " + r["sessions"][0] + "`, then SendMessage \"resume: " + r["title"] + "\"", ""]
    if not cands:
        out.append("No parked intent matched new activity.")
    if unread:
        out += ["", "## Not read (network or API error): re-run before concluding these are quiet", ""]
        out += ["- " + u for u in unread]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pulse-dir", type=Path, required=True, help="local folder for state and reports")
    ap.add_argument("--since", help="ISO UTC; default: last run, else 24 h ago")
    ap.add_argument("--no-state", action="store_true", help="do not record this run")
    a = ap.parse_args(argv)
    state_file = a.pulse_dir / "wake_state.json"
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    now_s = now.isoformat().replace("+00:00", "Z")
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    since = a.since or state.get("last_run") or (now - dt.timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    items = parked()
    prs, unread = {}, []
    for r in sorted({i["repo"] for i in items}):
        try:
            prs[r] = prs_since(r, since)
        except RuntimeError as e:
            unread.append(f"{r}: {e}")
    rows = []
    for i in items:
        try:
            rows.append({**i, "hits": match(i, prs, since)})
        except RuntimeError as e:
            unread.append(f"{i['repo']}#{i['number']}: {e}")
            rows.append({**i, "hits": [], "unread": True})
    for r in rows:
        r["strong"] = sum(h["strength"] == "strong" for h in r["hits"])
    out = a.pulse_dir / now.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    md = out / "WAKE_CANDIDATES.md"
    md.write_text("\n".join(report(items, rows, unread, since, now_s)) + "\n", encoding="utf-8", newline="\n")
    (out / "WAKE_CANDIDATES.json").write_text(json.dumps({"since": since, "run": now_s, "rows": rows}, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
    if not a.no_state and not unread:
        state_file.write_text(json.dumps({"last_run": now_s}) + "\n", encoding="utf-8", newline="\n")
    cands = [r for r in rows if r["hits"]]
    print(f"WAKE_CHECK parked={len(items)} candidates={len(cands)} unread={len(unread)} since={since} report={md.as_posix()}")
    for r in sorted(cands, key=lambda r: (-r["strong"], -len(r["hits"]))):
        print(f"  {r['repo']}#{r['number']} [{r.get('id')}] strong={r['strong']} weak={len(r['hits']) - r['strong']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
