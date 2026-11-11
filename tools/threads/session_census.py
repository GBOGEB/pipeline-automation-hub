"""Session census: the archive wireframe of every Claude Code desktop session. Read-only.

    python -I tools/threads/session_census.py --sessions-dir SESSIONS --pulse PULSE --out OUT \
        [--projects PROJECTS] [--memory MEMORY ...] [--notes NOTES] [--git-root DIR ...] \
        [--task-title TITLE ...]

SESSIONS is the desktop app's per-session JSON folder (`claude-code-sessions/<account>/<org>`),
which also holds sessions past the 200-row `list_sessions` cap. PROJECTS is the transcript root
(default `~/.claude/projects`), PULSE the handover folder searched for rescues, maps and mining
cards, MEMORY the memory folder(s) searched for index entries, NOTES the side-session notes root
(default `%APPDATA%/Claude/side-session-notes`). A `--git-root` folder holds git clones or
worktrees: a file there that is gone now was most likely committed; `--git-home-re` does the
same with a regex on the backslash path. `--task-title` marks a title
as a scheduled-task run when its session JSON carries no `scheduledTaskId`.

Reads the app's per-session JSON (title, archive state, parent, PRs, wrap-up) and each
session's transcript JSONL(s), and writes, for every session:

  SESSION_CENSUS.json   one record per session (machine-readable, for data and method mining)
  ARCHIVE_WIREFRAME.md  human tree: reserved-number families first, then parents with children,
                        each with state, capture verdict, risk flags and its wake line
  REENTRY_CARDS.md      one re-entry card per archived thread: keywords, wake triggers, outcome

All three hold session titles and transcript excerpts: keep OUT local and private and never
commit it (README "Rules").

Capture verdict for a thread (how losslessly it is recorded outside its transcript):
  CAPTURED  every output it wrote still exists or was rescued, and a PR, a rescue or an index
            entry records the outcome
  PARTIAL   recorded somewhere, but some outputs or pasted inputs exist only in the transcript
  AT_RISK   outputs or pasted inputs exist only in the transcript and nothing records the
            outcome (no merged PR, no rescue, no index or map entry)
  TASK_RUN  a scheduled-task run (pulse refresh, wake check): its output is the task's own record

Nothing is unarchived, sent, or changed.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import sys
from pathlib import Path

# Titles of scheduled-task runs whose session JSON lacks a scheduledTaskId (--task-title adds more).
TASK_TITLES = frozenset({"Parked intents: daily wake check"})

# Reserved-number families. A number, once given to a use case, keeps it: a renamed or
# re-ordered thread keeps its number, and a new use case takes the next free number.
FAMILIES = [
    ("GROUP", re.compile(r"^(?P<n>[0-9]) · ")),
    ("M", re.compile(r"^M(?P<n>\d+)\b")),
    ("C", re.compile(r"^C(?P<n>\d+) [a-z]+ane\b")),
    ("L", re.compile(r"^L(?P<n>\d(?:\+L\d)?(?:-R\d|-fix)?)\b")),
    ("LANE", re.compile(r"^Lane (?P<n>[A-Z]\w*(?:-main)?)\b")),
    ("U", re.compile(r"^\[?U(?P<n>\d+)\b")),
    ("W", re.compile(r"\bW(?P<n>\d{3}[a-z]?)\b")),
    ("S", re.compile(r"^S(?P<n>\d F\d)\b")),
    ("K", re.compile(r"^K(?P<n>\d+)\b|K-series")),
    ("GM", re.compile(r"^GM-(?P<n>[IVX]+(?:-[A-Z])?)")),
    ("J", re.compile(r"\bJ(?P<n>\d{2})\b")),
    ("MR", re.compile(r"^MR (?P<n>[A-Z0-9]+)\b")),
    ("G", re.compile(r"\(G-(?P<n>[A-Z]+)\)")),
    ("P", re.compile(r"^P(?P<n>\d[a-z]?)\b")),
    ("NEXT", re.compile(r"^Next wave: (?P<n>.+)$")),
]

OUT_EXT = r"xlsx|xlsm|xls|pptx|docx|pdf|html?|svg|png|csv|zip|mmd|ipynb"
PATH_RE = re.compile(
    r"(?<![A-Za-z0-9/:\\])(?:[A-Za-z]:(?:\\{1,4}|/)|/[a-z]/)(?!/)[^\s\"'<>|*?\r\n`]*?\.(?:" + OUT_EXT + r")\b", re.I
)
# Placeholders, temp caches and pasted-image caches are never deliverables.
SKIP_RE = re.compile(
    r"\\path\\to\\|\\\.\.\.\\|[<{]|\\Temp\\tmp|\\Temp\\claude\\[^\\]+\\[^\\]+\\images\\", re.I
)
# App-made worktrees are always git homes; --git-root adds the user's clone and worktree folders.
# A file there that is gone now was most likely committed (check the PR) rather than lost.
GIT_HOME_RE = re.compile(r"\\\.claude\\worktrees\\", re.I)


def under(path: str, roots) -> bool:
    """True when the normalised `path` lies inside one of `roots`: a normalised folder (str) or
    a compiled regex searched against the path."""
    pl = path.lower()
    for r in roots:
        if isinstance(r, str):
            if pl.startswith(r.lower().rstrip("\\") + "\\"):
                return True
        elif r.search(path):
            return True
    return False


def where(path: str, git_roots: tuple = ()) -> str:
    """Where a referenced file lived: skip, temp, scratchpad, scratch-ws, git-home, user-docs, other.

    `git_roots` holds normalised (norm()) folders, or compiled regexes, for git clones or worktrees.
    """
    if SKIP_RE.search(path):
        return "skip"
    pl = path.lower()
    if "\\appdata\\local\\temp\\" in pl:
        return "scratchpad" if "\\scratchpad\\" in pl else "temp"
    if "scratch-workspaces" in pl:
        return "scratch-ws"
    if GIT_HOME_RE.search(path) or under(path, git_roots):
        return "git-home"
    if any(k in pl for k in ("onedrive", "\\documents\\", "\\downloads\\", "\\desktop\\")):
        return "user-docs"
    return "other"


ARTIFACT_RE = re.compile(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]+")
PR_RE = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)")
LOCAL_RE = re.compile(r"local_([0-9a-f]{8})")
PASTE_RE = re.compile(r"<pasted_content[^>]*>(.*?)</pasted_content", re.S)
FOLDBACK_RE = re.compile(r"Method fold-back", re.I)


def ts(ms):
    if not ms:
        return "?"
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def family(title: str):
    for name, rx in FAMILIES:
        m = rx.search(title or "")
        if m:
            n = m.groupdict().get("n") or ""
            return name, f"{name}{n}" if name not in ("LANE", "NEXT", "GROUP") else f"{name}:{n}"
    return None, None


def norm(p: str) -> str:
    p = p.strip().rstrip(".,;:)]}")
    if re.match(r"^/[a-z]/", p):
        p = p[1].upper() + ":" + p[2:]
    return re.sub(r"\\{2,}", lambda _m: "\\", p.replace("/", "\\"))


_git_cache: dict[str, bool] = {}


def in_git(path: str) -> bool:
    d = os.path.dirname(path)
    seen = []
    while d and d not in _git_cache:
        seen.append(d)
        if os.path.isdir(os.path.join(d, ".git")) or os.path.isfile(os.path.join(d, ".git")):
            _git_cache[d] = True
            break
        nd = os.path.dirname(d)
        if nd == d:
            _git_cache[d] = False
            break
        d = nd
    val = _git_cache.get(d, False)
    for s in seen:
        _git_cache[s] = val
    return val


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    out = []
    for p in content or []:
        if isinstance(p, dict):
            if p.get("type") == "text":
                out.append(p.get("text", ""))
            elif p.get("type") == "tool_result":
                c = p.get("content")
                out.append(text_of(c)[:20000] if not isinstance(c, str) else c[:20000])
    return "\n".join(out)


def scan_transcript(paths: list[str]) -> dict:
    r = dict(bytes=0, user_turns=0, first_intent="", last_user="", last_outcome="",
             writes={}, edits=set(), outputs=set(), artifacts=set(), prs=set(),
             pasted=0, pasted_bytes=0, foldback=False, mentions=set(), compactions=0)
    for path in paths:
        r["bytes"] += os.path.getsize(path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                t = o.get("type")
                msg = o.get("message") or {}
                c = msg.get("content")
                if t == "user":
                    is_tool = isinstance(c, list) and any(
                        isinstance(p, dict) and p.get("type") == "tool_result" for p in c)
                    txt = text_of(c)
                    if is_tool:
                        for m in PATH_RE.findall(txt):
                            r["outputs"].add(norm(m))
                        continue
                    if "This session is being continued from a previous conversation" in txt:
                        r["compactions"] += 1
                        continue
                    clean = re.sub(r"<system-reminder>.*?</system-reminder>", "", txt, flags=re.S).strip()
                    if not clean or clean.startswith((
                            "Another Claude session", "<task-notification", "Base directory for this skill",
                            "<side-sessions-event", "<ci-monitor", "<cross-session")):
                        continue
                    r["user_turns"] += 1
                    if not r["first_intent"]:
                        r["first_intent"] = clean[:600]
                    r["last_user"] = clean[:400]
                    for pc in PASTE_RE.findall(clean):
                        r["pasted"] += 1
                        r["pasted_bytes"] += len(pc.encode("utf-8"))
                    for m in PATH_RE.findall(clean):
                        r["outputs"].add(norm(m))
                elif t == "assistant":
                    for p in c or []:
                        if not isinstance(p, dict):
                            continue
                        if p.get("type") == "text":
                            tx = p.get("text", "")
                            if tx.strip():
                                r["last_outcome"] = tx[:900]
                            if FOLDBACK_RE.search(tx):
                                r["foldback"] = True
                            for m in PATH_RE.findall(tx):
                                r["outputs"].add(norm(m))
                            r["artifacts"].update(ARTIFACT_RE.findall(tx))
                            r["prs"].update(f"{a}#{b}" for a, b in PR_RE.findall(tx))
                            r["mentions"].update(LOCAL_RE.findall(tx))
                        elif p.get("type") == "tool_use":
                            inp = p.get("input") or {}
                            name = p.get("name", "")
                            fp = inp.get("file_path")
                            if name == "Write" and fp:
                                r["writes"][norm(fp)] = len(inp.get("content") or "")
                            elif name in ("Edit", "NotebookEdit") and fp:
                                r["edits"].add(norm(fp))
                            blob = json.dumps(inp, ensure_ascii=False)[:20000]
                            for m in PATH_RE.findall(blob):
                                r["outputs"].add(norm(m))
                            r["artifacts"].update(ARTIFACT_RE.findall(blob))
    return r


def mention_index(roots: list[Path]) -> dict[str, set[str]]:
    """id8 -> set of files (under _pulse / memory) that name it."""
    idx: dict[str, set[str]] = collections.defaultdict(set)
    for root in roots:
        if not root.exists():
            continue
        for dp, dns, fns in os.walk(root):
            for fn in fns:
                fpth = os.path.join(dp, fn)
                for m in LOCAL_RE.findall(fpth):
                    idx[m].add(fpth)
                if not fn.lower().endswith((".md", ".json", ".txt", ".csv", ".yaml", ".yml")):
                    continue
                try:
                    if os.path.getsize(fpth) > 4_000_000:
                        continue
                    with open(fpth, encoding="utf-8", errors="replace") as fh:
                        data = fh.read()
                except OSError:
                    continue
                for m in set(LOCAL_RE.findall(data)):
                    idx[m].add(fpth)
    return idx


SOLE_EXT = (".md", ".py", ".ps1", ".json", ".yaml", ".yml", ".html", ".csv", ".txt", ".mmd", ".js", ".ts")


def verdict(rec) -> tuple[str, list[str]]:
    """Capture verdict plus risk flags. A thread's outputs count as lost only when they lived
    outside git and outside temp (deliverables in scratch workspaces or user folders)."""
    if rec["task_run"]:
        return "TASK_RUN", []
    flags = []
    gone_deliv = [o for o in rec["outputs"] if not o["exists"] and o["where"] in ("scratch-ws", "user-docs", "other")]
    sole_writes = [w for w in rec["writes"] if not w["exists"] and not w["in_git"]
                   and w["where"] not in ("git-home", "skip") and w["chars"] >= 1500
                   and w["path"].lower().endswith(SOLE_EXT)]
    live_scratch = rec["scratch"] and rec["scratch"].get("files", 0)
    if gone_deliv:
        flags.append(f"deliverables-gone:{len(gone_deliv)}")
    if sole_writes:
        flags.append(f"sole-copy-writes:{len(sole_writes)}")
    if rec["pasted"]:
        flags.append(f"pasted:{rec['pasted']}")
    if live_scratch:
        flags.append(f"scratch-files:{rec['scratch']['files']}")
    if rec["artifacts"]:
        flags.append(f"artifacts:{len(rec['artifacts'])}")
    merged = any(p.endswith(":MERGED") for p in rec["prs_app"])
    if rec.get("mined_in"):
        # A mining card (thread-rollup 1c) records outcome, outputs, methods and the wake decision.
        return "CAPTURED", flags + ["mined"]
    rescued = bool(rec["rescue_dirs"])
    recorded = merged or rescued or bool(rec["mapped_in"]) or bool(rec["indexed_in"])
    if not recorded:
        flags.append("no-record")
    if rec["user_turns"] >= 8 and not rec["foldback"]:
        flags.append("no-foldback")
    exposed = bool(gone_deliv or len(sole_writes) >= 3 or (rec["pasted"] and not rescued))
    if exposed and not rescued and not merged:
        return "AT_RISK", flags
    if not recorded and rec["user_turns"] >= 5:
        return "AT_RISK", flags
    if exposed or not recorded:
        return "PARTIAL", flags
    return "CAPTURED", flags


def default_notes() -> str:
    base = os.environ.get("APPDATA")
    return os.path.join(base, "Claude", "side-session-notes") if base else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--sessions-dir", required=True, help="the app's per-session JSON folder")
    ap.add_argument("--projects", default=os.path.join(os.path.expanduser("~"), ".claude", "projects"),
                    help="transcript root (<project>/<cliSessionId>.jsonl)")
    ap.add_argument("--pulse", required=True, help="handover folder searched for rescues, maps and mining cards")
    ap.add_argument("--memory", action="append", default=[], help="memory folder searched for index entries")
    ap.add_argument("--notes", default=default_notes(), help="side-session notes root")
    ap.add_argument("--git-root", action="append", default=[], help="folder holding git clones or worktrees")
    ap.add_argument("--git-home-re", action="append", default=[],
                    help="case-insensitive regex on the backslash path that marks a git home")
    ap.add_argument("--task-title", action="append", default=[], help="title that marks a scheduled-task run")
    ap.add_argument("--out", required=True, help="output folder (local and private)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    task_titles = TASK_TITLES | set(a.task_title)
    git_roots = tuple(norm(g) for g in a.git_root) + tuple(re.compile(x, re.I) for x in a.git_home_re)

    jsonl = {Path(f).stem: f for f in glob.glob(os.path.join(a.projects, "*", "*.jsonl"))}
    rescue_roots = [Path(a.pulse)]
    rescued = mention_index(rescue_roots)
    indexed = mention_index([Path(m) for m in a.memory])

    recs = []
    for f in sorted(glob.glob(os.path.join(a.sessions_dir, "local_*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except ValueError:
            continue
        if not isinstance(d, dict) or not str(d.get("sessionId", "")).startswith("local_"):
            continue
        sid = d["sessionId"]
        id8 = sid[6:14]
        title = (d.get("title") or "").replace("\n", " ")
        task_run = title in task_titles or bool(d.get("scheduledTaskId"))
        fam, num = family(title)
        clis = [c for c in dict.fromkeys([d.get("cliSessionId"), d.get("lastAssistantCliSessionId")]) if c]
        paths = [jsonl[c] for c in clis if c in jsonl]
        tr = scan_transcript(paths) if (paths and not task_run) else None
        cwd = d.get("cwd") or ""
        scratch = None
        if "scratch-workspaces" in cwd:
            n = 0
            if os.path.isdir(cwd):
                for _dp, _dn, fns in os.walk(cwd):
                    n += len(fns)
            scratch = {"path": cwd, "exists": os.path.isdir(cwd), "files": n}
        notes_dir = os.path.join(a.notes, sid) if a.notes else ""
        pts = d.get("postTurnSummary") if isinstance(d.get("postTurnSummary"), dict) else {}
        rec = {
            "id": sid,
            "id8": id8,
            "cli": clis,
            "title": title,
            "family": fam,
            "number": num,
            "archived": bool(d.get("isArchived")),
            "task_run": task_run,
            "created": ts(d.get("createdAt")),
            "last": ts(d.get("lastActivityAt")),
            "cwd": cwd,
            "parent": (d.get("spawnedFrom") or {}).get("sessionId"),
            "root": (d.get("startChain") or {}).get("firstSessionId"),
            "turns": d.get("completedTurns"),
            "model": d.get("model"),
            "effort": d.get("effort"),
            "permission": d.get("permissionMode"),
            "prs_app": [f"{p.get('repo')}#{p.get('prNumber')}:{p.get('state')}"
                        for p in (d.get("prs") or []) if isinstance(p, dict)],
            "branches": sorted({p.get("branch") for p in (d.get("prs") or [])
                                if isinstance(p, dict) and p.get("branch")}),
            "wrap_up": (d.get("turnWrapUp") or {}).get("description") if isinstance(d.get("turnWrapUp"), dict) else None,
            "status": pts.get("status_category"),
            "status_detail": pts.get("status_detail"),
            "needs_action": pts.get("needs_action"),
            "scratch": scratch,
            "notes_dir_exists": bool(notes_dir) and os.path.isdir(notes_dir),
            "rescue_dirs": sorted(p for p in rescued.get(id8, set()) if "\\rescue\\" in p.replace("/", "\\"))[:12],
            "mapped_in": sorted(p for p in rescued.get(id8, set()) if "\\rescue\\" not in p.replace("/", "\\"))[:12],
            "indexed_in": sorted(indexed.get(id8, set()))[:6],
            "mined_in": sorted(p for p in rescued.get(id8, set())
                               if "\\mining\\" in p.replace("/", "\\")
                               and os.path.basename(p).startswith(id8) and p.endswith(".md"))[:3],
            "transcripts": paths,
        }
        if tr:
            rec.update({
                "transcript_bytes": tr["bytes"],
                "user_turns": tr["user_turns"],
                "compactions": tr["compactions"],
                "first_intent": tr["first_intent"],
                "last_user": tr["last_user"],
                "last_outcome": tr["last_outcome"],
                "writes": [{"path": p, "chars": n, "exists": os.path.exists(p), "in_git": in_git(p),
                            "where": where(p, git_roots)} for p, n in sorted(tr["writes"].items())],
                "edits": len(tr["edits"]),
                "outputs": [{"path": p, "exists": os.path.exists(p), "where": where(p, git_roots)}
                            for p in sorted(tr["outputs"]) if where(p, git_roots) != "skip"],
                "artifacts": sorted(tr["artifacts"]),
                "prs_text": sorted(tr["prs"])[:40],
                "pasted": tr["pasted"],
                "pasted_bytes": tr["pasted_bytes"],
                "foldback": tr["foldback"],
                "mentions": sorted(tr["mentions"] - {id8})[:40],
            })
        else:
            rec.update({"transcript_bytes": 0, "user_turns": 0, "compactions": 0, "first_intent": "",
                        "last_user": "", "last_outcome": "", "writes": [], "edits": 0, "outputs": [],
                        "artifacts": [], "prs_text": [], "pasted": 0, "pasted_bytes": 0,
                        "foldback": False, "mentions": []})
        rec["verdict"], rec["flags"] = verdict(rec)
        rec["wake"] = (f"unarchive_session {sid}, then SendMessage to:{sid} \"resume: <goal>\""
                       if rec["archived"] else f"SendMessage to:{sid} \"resume: <goal>\"")
        recs.append(rec)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "SESSION_CENSUS.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
    write_md(recs, out / "ARCHIVE_WIREFRAME.md")
    write_cards(recs, out / "REENTRY_CARDS.md")
    c = collections.Counter((r["archived"], r["verdict"]) for r in recs)
    for k, v in sorted(c.items(), key=str):
        print(("ARCHIVED" if k[0] else "LIVE"), k[1], v)
    return 0


def write_md(recs, path: Path) -> None:
    by = {r["id"]: r for r in recs}
    kids = collections.defaultdict(list)
    for r in recs:
        if r["parent"] in by:
            kids[r["parent"]].append(r["id"])
    real = [r for r in recs if not r["task_run"]]
    tasks = [r for r in recs if r["task_run"]]
    L = ["# Archive wireframe", "",
         f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M}Z by `session_census.py` (read-only).",
         f"{len(recs)} sessions: {len(real)} threads ({sum(r['archived'] for r in real)} archived), "
         f"{len(tasks)} scheduled-task runs ({sum(not r['archived'] for r in tasks)} not archived).", "",
         "Verdicts: CAPTURED · PARTIAL · AT_RISK · TASK_RUN. The machine record is `SESSION_CENSUS.json`.", "",
         "## Reserved-number families", "",
         "| Number | State | Verdict | Thread | Id | Last |", "|---|---|---|---|---|---|"]
    fam = sorted([r for r in real if r["number"]], key=lambda r: (r["family"], r["number"], r["last"]))
    for r in fam:
        L.append(f"| {r['number']} | {'ARC' if r['archived'] else 'LIVE'} | {r['verdict']} | "
                 f"{r['title'][:70]} | `{r['id8']}` | {r['last'][:10]} |")
    L += ["", "## Threads by parent (newest first)", ""]

    def line(r, dep):
        fl = " ".join(r["flags"])
        prs = " ".join(r["prs_app"][:4])
        L.append(f"{'  ' * dep}- **{r['verdict']}** {'ARC' if r['archived'] else 'LIVE'} `{r['id8']}` "
                 f"{r['last'][:10]} {r['title'][:90]}" + (f" — {prs}" if prs else "") + (f" — _{fl}_" if fl else ""))
        for k in sorted(kids[r["id"]], key=lambda k: by[k]["last"]):
            if not by[k]["task_run"]:
                line(by[k], dep + 1)

    roots = [r for r in real if r["parent"] not in by]
    for r in sorted(roots, key=lambda r: r["last"], reverse=True):
        line(r, 0)
    L += ["", "## At-risk threads (wake or mine first)", ""]
    for r in sorted([r for r in real if r["verdict"] == "AT_RISK"], key=lambda r: -(r["user_turns"] or 0)):
        L.append(f"- `{r['id8']}` {r['title'][:80]} — {r['user_turns']} user turns, flags {' '.join(r['flags'])}. "
                 f"Wake: `{r['wake']}`")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


STOP = set("the and for with from into that this then when what main fix add run new all its are not via per one two "
           "next wave lane threads thread session review check update".split())


def keywords(r) -> list[str]:
    """3-6 distinctive search terms: the reserved number, PR refs, then rare title words."""
    kw = []
    if r["number"]:
        kw.append(r["number"])
    kw += [p.split(":")[0].replace("GBOGEB/", "") for p in r["prs_app"][:2]]
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_.+-]{3,}", r["title"]):
        if w.lower() not in STOP and w not in kw:
            kw.append(w)
        if len(kw) >= 6:
            break
    return kw[:6]


def write_cards(recs, path: Path) -> None:
    """Re-entry card per archived thread: keywords, wake triggers, outcome, re-entry line."""
    rows = [r for r in recs if r["archived"] and not r["task_run"]]
    L = ["# Re-entry cards for archived threads", "",
         f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M}Z by `session_census.py` from the app's session files.",
         f"{len(rows)} archived threads, newest first. Search this file for a number (`L5`, `U16`, `W372`), a PR",
         "(`cryoplant-project#2269`), a branch or a keyword. Re-entry: unarchive, then send `resume: <goal>`;",
         "mine the transcript first (`/thread-rollup` 1c) if the card's verdict is AT_RISK or PARTIAL.", "",
         "| Number | Thread | Id | Last | Verdict | Outcome | Keywords | Wake triggers |",
         "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["last"], reverse=True):
        outcome = (r.get("wrap_up") or r.get("status_detail") or "").replace("|", "/").replace("\n", " ")[:140]
        trig = [p.split(":")[0].replace("GBOGEB/", "") for p in r["prs_app"][:4]] + r.get("branches", [])[:2]
        L.append(f"| {r['number'] or ''} | {r['title'][:70].replace('|', '/')} | `{r['id']}` | {r['last'][:10]} | "
                 f"{r['verdict']} | {outcome} | {', '.join(keywords(r))} | {', '.join(trig)} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
