#!/usr/bin/env python3
"""FOCUS5 evidence channels for the gates that were hard-coded UNKNOWN.

Owner of the H03, H09 and H12 evaluation used by tools/focus5_pulse.py. Every
check reads GitHub live on the exact head SHA of the pulse; nothing is read from
prose, a previous pulse or a receipt the agent wrote. UNKNOWN is never PASS and
each UNKNOWN names the one thing that is missing, so the owner can act on it.

  H03  owner scope: an annotated tag ``jade-scope/<name>`` on the head SHA whose
       signature GitHub reports as verified and whose message contains
       ``JADE-H03``, tagged by an owner identity (see OWNER_TAGGER_RX). Only the
       owner's signing key can produce it; an agent or collaborator with push
       access cannot.
  H09  independent human review: the head SHA is the merge commit of a merged
       pull request, and that PR has an APPROVED review on its final head by a
       ``User`` who is not the PR author and not a bot, with no later
       CHANGES_REQUESTED from an eligible reviewer.
  H12  owner release: an annotated, verified tag on the head SHA, a published
       (non-draft, non-prerelease) release for that tag with at least one asset,
       and a release body line ``Rollback: <tag>`` naming another existing tag
       that resolves to a different (older) commit than the release head.

Owner binding: GitHub's ``verification.verified`` only says the signature is
valid for the GitHub account owning the tagger email. It is bound to the owner
by requiring that email to be the GitHub noreply address of an owner login
(``<login>@users.noreply.github.com`` or ``<id>+<login>@...``); the owner logins
default to the repository owner. No personal email is stored in the repo.

H10 and H11 use the declared-workflow mechanism of focus5_pulse.py (see
DECLARED_ONLY_GATES there); H07 stays UNKNOWN (independent security acceptance).
"""
from __future__ import annotations

import re
import subprocess
from typing import Callable

Lookup = Callable[[str], object]
SCOPE_PREFIX = "jade-scope/"
SCOPE_TOKEN = "JADE-H03"
ROLLBACK_RX = re.compile(r"^\s*rollback:\s*(\S+)\s*$", re.I | re.M)
OWNER_TAGGER_RX = re.compile(r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$", re.I)


def owner_logins(repo: str, owners: tuple[str, ...] | None = None) -> frozenset[str]:
    return frozenset(o.casefold() for o in (owners or (repo.split("/", 1)[0],)))


def _owner_tagger(obj: dict, owners: frozenset[str]) -> str | None:
    """The owner login the verified tagger email binds to, or None."""
    m = OWNER_TAGGER_RX.match(((obj.get("tagger") or {}).get("email") or "").strip())
    return m.group(1) if m and m.group(1).casefold() in owners else None


def _pages(lookup: Lookup, path: str, limit: int = 10) -> list[dict]:
    sep = "&" if "?" in path else "?"
    out: list[dict] = []
    for page in range(1, limit + 1):
        batch = lookup(f"{path}{sep}per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError(f"{path}: expected a list")
        out.extend(batch)
        if len(batch) < 100:
            return out
    raise ValueError(f"{path}: more than {limit * 100} entries; refusing a partial read")


def _annotated(repo: str, tag: str, lookup: Lookup) -> dict | None:
    """The git tag object for ``tag`` (None for a lightweight tag)."""
    ref = lookup(f"repos/{repo}/git/ref/tags/{tag}")
    obj = ref.get("object") or {}
    if obj.get("type") != "tag":
        return None
    return lookup(f"repos/{repo}/git/tags/{obj['sha']}")


def _verified_tags_on(repo: str, sha: str, tags: list[dict], lookup: Lookup,
                      owners: tuple[str, ...] | None = None) -> tuple[list[dict], list[str]]:
    """Annotated tags on ``sha`` with a verified owner signature, plus why the others failed."""
    good, why = [], []
    trusted = owner_logins(repo, owners)
    for t in tags:
        if t["commit"]["sha"] != sha:
            continue
        obj = _annotated(repo, t["name"], lookup)
        if obj is None:
            why.append(f"{t['name']} is lightweight")
        elif (obj.get("object") or {}).get("sha") != sha:
            why.append(f"{t['name']} does not point at the head commit")
        elif not (obj.get("verification") or {}).get("verified"):
            why.append(f"{t['name']} signature not verified ({(obj.get('verification') or {}).get('reason', 'unsigned')})")
        elif not (login := _owner_tagger(obj, trusted)):
            why.append(f"{t['name']} tagger is not an owner identity ({', '.join(sorted(trusted))})")
        else:
            good.append({"name": t["name"], "message": obj.get("message") or "", "tagger": login})
    return good, why


def evaluate_h03(repo: str, sha: str, tags: list[dict], lookup: Lookup,
                 owners: tuple[str, ...] | None = None) -> tuple[str, str | None, str]:
    scoped = [t for t in tags if t["name"].startswith(SCOPE_PREFIX)]
    good, why = _verified_tags_on(repo, sha, scoped, lookup, owners)
    good = [t for t in good if SCOPE_TOKEN in t["message"]]
    if good:
        name = good[0]["name"]
        return "PASS", f"https://github.com/{repo}/releases/tag/{name}", f"Owner-signed scope tag {name} on this SHA"
    detail = "; ".join(why) if why else f"no {SCOPE_PREFIX}* tag on this SHA"
    return "UNKNOWN", None, (f"Owner scope not evidenced: needs a signed annotated {SCOPE_PREFIX}<name> tag on "
                             f"this SHA with {SCOPE_TOKEN} in its message ({detail})")


def _merged_pr(repo: str, sha: str, lookup: Lookup) -> dict | None:
    for pr in lookup(f"repos/{repo}/commits/{sha}/pulls"):
        if pr.get("merged_at") and pr.get("merge_commit_sha") == sha:
            return pr
    return None


def evaluate_h09(repo: str, sha: str, lookup: Lookup) -> tuple[str, str | None, str]:
    pr = _merged_pr(repo, sha, lookup)
    if pr is None:
        return "UNKNOWN", None, "Head SHA is not the merge commit of a merged pull request; no review to evaluate"
    n, author, head = pr["number"], pr["user"]["login"], pr["head"]["sha"]
    latest: dict[str, dict] = {}
    for r in _pages(lookup, f"repos/{repo}/pulls/{n}/reviews"):
        u = r.get("user") or {}
        if u.get("type") != "User" or u.get("login") == author or u.get("login", "").endswith("[bot]"):
            continue
        if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[u["login"]] = r  # reviews are returned oldest first
    blocking = sorted(k for k, r in latest.items() if r["state"] == "CHANGES_REQUESTED")
    approved = [r for r in latest.values() if r["state"] == "APPROVED" and r.get("commit_id") == head]
    base = f"https://github.com/{repo}/pull/{n}"
    if blocking:
        return "UNKNOWN", base, f"PR #{n}: changes requested by {', '.join(blocking)}"
    if approved:
        who = sorted(r["user"]["login"] for r in approved)
        return "PASS", approved[0].get("html_url") or base, f"PR #{n} approved on its final head by {', '.join(who)} (not the author)"
    stale = sorted(k for k, r in latest.items() if r["state"] == "APPROVED")
    reason = (f"PR #{n}: approval by {', '.join(stale)} is not on the final head {head[:10]}" if stale else
              f"PR #{n} by {author}: no APPROVED review from an eligible human other than the author")
    return "UNKNOWN", base, reason


def evaluate_h12(repo: str, sha: str, tags: list[dict], lookup: Lookup,
                 owners: tuple[str, ...] | None = None) -> tuple[str, str | None, str]:
    good, why = _verified_tags_on(repo, sha, [t for t in tags if not t["name"].startswith(SCOPE_PREFIX)],
                                  lookup, owners)
    if not good:
        detail = "; ".join(why) if why else "no tag on this SHA"
        return "UNKNOWN", None, f"Owner release not evidenced: needs a signed annotated tag on this SHA ({detail})"
    commit_of = {t["name"]: t["commit"]["sha"] for t in tags}
    problems = []
    for t in good:
        try:
            rel = lookup(f"repos/{repo}/releases/tags/{t['name']}")
        except subprocess.CalledProcessError:
            problems.append(f"{t['name']}: no release")
            continue
        url = rel.get("html_url")
        if rel.get("draft") or rel.get("prerelease"):
            problems.append(f"{t['name']}: release is draft or prerelease")
        elif not rel.get("assets"):
            problems.append(f"{t['name']}: release has no assets")
        else:
            m = ROLLBACK_RX.search(rel.get("body") or "")
            if not m:
                problems.append(f"{t['name']}: release body has no 'Rollback: <tag>' line")
            elif m.group(1) == t["name"] or m.group(1) not in commit_of:
                problems.append(f"{t['name']}: rollback target {m.group(1)} is not another existing tag")
            elif commit_of[m.group(1)] == sha:
                problems.append(f"{t['name']}: rollback target {m.group(1)} points at the release head, "
                                "not an older commit")
            else:
                return "PASS", url, (f"Signed tag {t['name']}, published release with {len(rel['assets'])} asset(s), "
                                     f"rollback to {m.group(1)}")
    return "UNKNOWN", None, "Owner release not evidenced: " + "; ".join(problems)


def list_tags(repo: str, lookup: Lookup) -> list[dict]:
    return _pages(lookup, f"repos/{repo}/tags")

