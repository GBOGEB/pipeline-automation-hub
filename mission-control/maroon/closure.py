#!/usr/bin/env python3
"""Proof-bound, restartable review-thread closure; never a merge or alert dismissal.

The caller owns diagnosis, source tests and the durable worker lease. JSON is an
evidence envelope, not an authentication token. A trusted provider adapter checks
current GitHub facts; a successful ledger checkpoint precedes every side effect.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("maroon_closure_review", HERE / "review_threads.py")
RT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RT)
OPS_SPEC = importlib.util.spec_from_file_location("maroon_closure_operations", HERE / "operations.py")
OPS = importlib.util.module_from_spec(OPS_SPEC)
OPS_SPEC.loader.exec_module(OPS)
OID = re.compile(r"[0-9a-f]{40}\Z")
CLASSIFICATIONS = {"fixed", "already_fixed", "false_positive"}


class Hold(ValueError):
    """Current evidence does not authorize the next operation."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def discussion_hash(comments):
    """Use the same contextual fields and ordering as review_threads.threads_of."""
    return digest(sorted(comments, key=lambda c: (c.get("created_at") or "", c["id"])))


def rest_author_login(actor):
    """Preserve the REST intake identity for a positively typed GraphQL Bot.

    GraphQL Bot logins omit the REST bot suffix. Do not strip suffixes, infer bot identity from
    an account name, or rewrite User/unknown actors:
    their exact identity remains part of the discussion hash and any change must fail validation.
    """
    actor = actor or {}
    login = actor.get("login")
    if actor.get("__typename") == "Bot" and isinstance(login, str) and login and not login.endswith("[bot]"):
        return login + "[bot]"
    return login


def is_negative_canary(title, body):
    """Reuse the intake owner's conservative intent classifier."""
    return RT.is_negative_canary(title, body)


def validate(proof, live, *, ignored_reply_ids=()):
    """Check positive source identity, current discussion and bounded proof facts.

    The agent must have actually executed/read the cited proof. This validator
    detects drift and malformed envelopes; it does not infer semantic correctness
    or independent review from a prose assertion or from a reviewer login.
    """
    if proof.get("schema") != "code_maroon.closure-proof.v1":
        raise Hold("unknown proof schema")
    if proof.get("item_id") != OPS.observation_id(proof.get("repo"), proof.get("pr"), proof.get("comment_id")):
        raise Hold("item identity does not match this repository, PR and root comment")
    if proof.get("classification") not in CLASSIFICATIONS:
        raise Hold("classification needs a fix or a substantiated disposition")
    for key in ("repo", "pr", "thread_id", "head_sha", "base_sha"):
        if not proof.get(key) or proof[key] != live.get(key):
            raise Hold(f"current {key} differs from proof")
    if not all(OID.fullmatch(proof.get(k, "")) for k in ("head_sha", "base_sha")):
        raise Hold("full commit OIDs required")
    if live.get("pr_state") != "open" or live.get("negative_canary") is not False:
        raise Hold("only a positively identified active, non-canary PR is eligible")
    if live.get("complete") is not True:
        raise Hold("incomplete provider read")
    comments = [c for c in live.get("comments", []) if c["id"] not in ignored_reply_ids]
    if not comments or discussion_hash(comments) != proof.get("discussion_hash"):
        raise Hold("discussion changed; diagnose again")
    if comments[0]["id"] != proof.get("comment_id"):
        raise Hold("root comment mismatch")
    blobs = proof.get("blob_oids")
    if not isinstance(blobs, dict) or not blobs:
        raise Hold("source blob OIDs required, including for false positives")
    for path, oid in blobs.items():
        parts = PurePosixPath(path).parts
        if not path or path.startswith("/") or ".." in parts or "\\" in path or not OID.fullmatch(oid):
            raise Hold("invalid source path/OID")
        if live.get("blob_oids", {}).get(path) != oid:
            raise Hold(f"source blob changed: {path}")
    if not isinstance(proof.get("method"), str) or len(proof["method"].strip()) < 20:
        raise Hold("explain the method and why it settles this finding")
    evidence = proof.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise Hold("positive proof references required")
    for item in evidence:
        if (not isinstance(item, dict) or item.get("source_sha") != proof["head_sha"]
                or item.get("conclusion") != "PASS" or not item.get("ref")
                or item.get("kind") not in {"local_test", "native_test", "source_analysis", "independent_review"}):
            raise Hold("proof must identify an executed test or source analysis at this head")
    if proof["classification"] == "fixed" and not any(e["kind"] in {"local_test", "native_test"} for e in evidence):
        raise Hold("a code fix needs relevant tests")
    return True


def evidence_reply(proof, marker):
    evidence = "\n".join(f"- {e['kind']}: {e['ref']} (PASS on `{e['source_sha']}`)" for e in proof["evidence"])
    return (f"{marker}\n**MAROON disposition: {proof['classification']}**\n\n"
            f"Verified against head `{proof['head_sha']}`.\n\n{proof['method']}\n\n{evidence}\n\n"
            "This disposition addresses this review finding. Native scanner-alert state and PR merge gates are separate.")


def validate_claim(proof, packet):
    """Bind a fresh provider proof to the exact source admitted by the worker lease."""
    if proof.get("repo") != packet.get("repo") or proof.get("item_id") not in packet.get("member_ids", []):
        raise Hold("proof item is outside this worker's claim")
    members = [row for row in packet.get("members", []) if row.get("id") == proof["item_id"]]
    if len(members) != 1:
        raise Hold("claim member is not uniquely identified")
    member = members[0]
    for field in ("pr", "comment_id", "thread_id", "head_sha", "base_sha", "discussion_hash", "blob_oids"):
        if proof.get(field) != member.get(field):
            raise Hold("proof differs from claimed source: " + field)
    if member.get("core_oids") != packet.get("core_oids") or packet.get("core_oids") != OPS.runtime_core_oids():
        raise Hold("claimed executor core differs from current code")
    return packet


def apply_close(proof, provider, journal, checkpoint, close_item, check_lease):
    """Reply -> resolve -> provider readback -> ledger close, with restart healing.

    checkpoint(journal) MUST durably save (with CAS when shared); check_lease()
    MUST reject expiry/fencing/head drift before mutations. close_item(receipt)
    MUST durably close only this manifestation. A failed checkpoint stops work.
    Reply timeouts are ambiguous: never blindly post again. Reread on the next
    pulse and hold if the previous operation still cannot be located.
    """
    operation_id = digest(proof)
    marker = f"<!-- MAROON_CLOSURE_V1 {operation_id} -->"
    body = evidence_reply(proof, marker)
    if journal and journal.get("operation_id") != operation_id:
        raise Hold("journal belongs to different evidence")
    if not journal:
        journal.update(operation_id=operation_id, phase="prepared", proof=copy.deepcopy(proof))
        checkpoint(copy.deepcopy(journal))
    if journal.get("phase") != "closed":
        check_lease()
    live = provider.read(proof)
    replies = provider.own_replies(live, body)
    if len(replies) > 1:
        raise Hold("duplicate evidence replies require reconciliation")
    ignored = [r["id"] for r in replies]
    validate(proof, live, ignored_reply_ids=ignored)
    if journal.get("phase") == "closed":
        if not live.get("provider_resolved") or not journal.get("receipt"):
            raise Hold("terminal journal differs from current provider state")
        return copy.deepcopy(journal["receipt"])
    if not replies:
        if journal.get("phase") in {"reply_intent", "reply_uncertain", "replied", "resolve_intent", "resolved", "closed"}:
            raise Hold("previous reply outcome unknown or reply removed; do not repost")
        if live.get("provider_resolved"):
            raise Hold("pre-existing resolution is not a MAROON proof receipt")
        check_lease()
        journal["phase"] = "reply_intent"
        checkpoint(copy.deepcopy(journal))
        try:
            provider.reply(proof, body)
        except Exception:
            journal["phase"] = "reply_uncertain"
            checkpoint(copy.deepcopy(journal))
            raise
        live = provider.read(proof)
        replies = provider.own_replies(live, body)
        if len(replies) != 1:
            raise Hold("reply not uniquely confirmed by provider")
        ignored = [replies[0]["id"]]
    journal.update(phase="replied", reply_id=replies[0]["id"], reply_url=replies[0].get("url"))
    checkpoint(copy.deepcopy(journal))
    validate(proof, live, ignored_reply_ids=ignored)
    if live.get("provider_resolved") is not True:
        if live.get("viewer_can_resolve") is not True:
            raise Hold("provider does not grant thread resolution")
        check_lease()
        journal["phase"] = "resolve_intent"
        checkpoint(copy.deepcopy(journal))
        provider.resolve(proof["thread_id"])
    live = provider.read(proof)
    validate(proof, live, ignored_reply_ids=ignored)
    if live.get("provider_resolved") is not True:
        raise Hold("provider resolution not confirmed")
    check_lease()
    receipt = journal.get("receipt") or {
        "schema": "code_maroon.closure-receipt.v1", "operation_id": operation_id,
        "item_id": proof["item_id"], "head_sha": proof["head_sha"],
        "discussion_hash": proof["discussion_hash"], "disposition": proof["classification"],
        "thread_id": proof["thread_id"], "method": proof["method"], "base_sha": proof["base_sha"],
        "provider_resolved": True, "provider_readback_at": datetime.now(timezone.utc).isoformat(),
        "provider_readback_ref": live["url"], "proof_refs": [e["ref"] for e in proof["evidence"]],
        "reply_id": replies[0]["id"], "blob_oids": proof["blob_oids"],
        "reply_body_hash": hashlib.sha256(body.encode()).hexdigest(),
    }
    receipt["provider_readback"] = {
        "resolved": True, "observed_at": receipt["provider_readback_at"],
        "reference": live["url"], "head_sha": proof["head_sha"],
        "discussion_hash": proof["discussion_hash"], "thread_id": proof["thread_id"],
    }
    journal.update(phase="resolved", receipt=receipt)
    checkpoint(copy.deepcopy(journal))
    close_item(copy.deepcopy(receipt))
    journal["phase"] = "closed"
    checkpoint(copy.deepcopy(journal))
    return receipt


class GitHub:
    """Native authenticated gh adapter; uses official REST + GraphQL APIs only."""

    def __init__(self, gh=RT.run_gh):
        self.gh = gh
        self.login = RT.gh_json(gh, "user")["login"]

    def graphql(self, query, **variables):
        args = ["api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            if value is not None:
                args += ["-f", f"{key}={value}"]
        code, out, _err = self.gh(args)
        if code:
            raise Hold("GitHub GraphQL request failed")
        data = json.loads(out)
        if data.get("errors") or not data.get("data"):
            raise Hold("GitHub GraphQL returned incomplete evidence")
        return data["data"]

    def read(self, proof):
        repo, number = proof["repo"], proof["pr"]
        pr = RT.gh_json(self.gh, f"repos/{repo}/pulls/{number}")
        comments, cursor, seen = [], None, set()
        query = '''query($id:ID!,$after:String){node(id:$id){... on PullRequestReviewThread{
          id isResolved viewerCanResolve pullRequest{number repository{nameWithOwner}}
          comments(first:100,after:$after){nodes{databaseId body createdAt updatedAt url
            author{__typename login} originalCommit{oid} commit{oid}}
            pageInfo{hasNextPage endCursor}}}}}'''
        for _ in range(100):
            thread = self.graphql(query, id=proof["thread_id"], after=cursor).get("node")
            if not thread or thread.get("id") != proof["thread_id"]:
                raise Hold("thread unavailable")
            if (thread["pullRequest"]["number"] != number
                    or thread["pullRequest"]["repository"]["nameWithOwner"] != repo):
                raise Hold("thread belongs to another PR")
            for c in thread["comments"]["nodes"]:
                comments.append({"id": c["databaseId"], "body": c.get("body") or "",
                                 "author": rest_author_login(c.get("author")),
                                 "created_at": c.get("createdAt"), "updated_at": c.get("updatedAt"),
                                 "commit_id": (c.get("commit") or c.get("originalCommit") or {}).get("oid")})
            page = thread["comments"]["pageInfo"]
            if not page["hasNextPage"]:
                break
            cursor = page.get("endCursor")
            if not cursor or cursor in seen:
                raise Hold("comment pagination incomplete")
            seen.add(cursor)
        else:
            raise Hold("comment page budget exhausted")
        if len({c["id"] for c in comments}) != len(comments):
            raise Hold("duplicate provider comment IDs")
        blobs = {}
        for path in proof["blob_oids"]:
            value = RT.gh_json(self.gh, f"repos/{repo}/contents/{quote(path, safe='/')}?ref={pr['head']['sha']}")
            if not isinstance(value, dict) or value.get("type") != "file":
                raise Hold("source is not a readable regular file")
            blobs[path] = value["sha"]
        current = RT.gh_json(self.gh, f"repos/{repo}/pulls/{number}")
        if any(current.get(key) != pr.get(key) for key in ("state", "title", "body")) or any(
                current.get(side, {}).get("sha") != pr.get(side, {}).get("sha") for side in ("head", "base")):
            raise Hold("PR changed during provider read; recollect before mutation")
        canary = is_negative_canary(pr.get("title"), pr.get("body"))
        return {"repo": repo, "pr": number, "thread_id": proof["thread_id"],
                "head_sha": pr["head"]["sha"], "base_sha": pr["base"]["sha"], "pr_state": pr["state"],
                "negative_canary": canary, "complete": True, "comments": comments, "blob_oids": blobs,
                "provider_resolved": thread["isResolved"], "viewer_can_resolve": thread["viewerCanResolve"],
                "url": f"https://github.com/{repo}/pull/{number}#discussion_r{proof['comment_id']}"}

    def own_replies(self, live, exact_body):
        return [c for c in live["comments"] if c.get("author") == self.login and c.get("body") == exact_body]

    def reply(self, proof, body):
        code, out, _err = self.gh(["api", "--method", "POST",
                                  f"repos/{proof['repo']}/pulls/{proof['pr']}/comments/{proof['comment_id']}/replies",
                                  "-f", f"body={body}"])
        if code:
            raise Hold("reply outcome unconfirmed")
        return json.loads(out)

    def resolve(self, thread_id):
        data = self.graphql('''mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{id isResolved}}}''', id=thread_id)
        thread = data.get("resolveReviewThread", {}).get("thread", {})
        if thread.get("id") != thread_id or thread.get("isResolved") is not True:
            raise Hold("resolve response unconfirmed")
