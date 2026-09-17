#!/usr/bin/env python3
"""Normalize connector-captured GitHub issue/PR snapshots into Golden Thread occurrences."""
from __future__ import annotations

import copy


class ConnectorOccurrenceError(ValueError):
    pass


def _required(mapping, key):
    if key not in mapping or mapping[key] is None:
        raise ConnectorOccurrenceError(f"missing required connector field: {key}")
    return mapping[key]


def normalize_connector_snapshot(repository, object_type, anchor_sha, snapshot):
    """Convert a bounded GitHub connector snapshot to the occurrence-import contract.

    The caller supplies the exact observation anchor SHA. The adapter preserves only
    fields required for deterministic replay and intentionally does not infer authority.
    """
    if object_type not in {"issue", "pull_request"}:
        raise ConnectorOccurrenceError(f"unsupported object_type: {object_type}")
    number = int(_required(snapshot, "number"))
    payload = {
        "title": _required(snapshot, "title"),
        "state": _required(snapshot, "state"),
    }
    if object_type == "issue":
        if snapshot.get("updated_at") is not None:
            payload["updated_at"] = snapshot["updated_at"]
    else:
        head = snapshot.get("head") or {}
        base = snapshot.get("base") or {}
        payload.update(
            {
                "merged": bool(snapshot.get("merged", False)),
                "base_sha": _required(base, "sha"),
                "head_sha": _required(head, "sha"),
            }
        )
        if snapshot.get("merge_commit_sha") is not None:
            payload["merge_commit_sha"] = snapshot["merge_commit_sha"]

    return {
        "repository": repository,
        "object_type": object_type,
        "object_number": number,
        "anchor_sha": anchor_sha,
        "source_ref": f"{repository}#{number}",
        "payload": copy.deepcopy(payload),
    }
