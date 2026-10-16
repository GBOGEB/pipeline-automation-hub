"""Fail-closed read-only CBQ/CH-BD source census projection."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "code-purple.cbq_ch_bd.pulse.v1"
PRIORITY = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate(data):
    require(isinstance(data, dict) and data.get("schema") == SCHEMA,
            "invalid pulse schema")
    authority = data.get("authority", {})
    require(authority.get("engineering") == "QPS_OWNER_ONLY"
            and authority.get("qps_decision") == "DEFER"
            and authority.get("native_four_hop") == "UNKNOWN"
            and authority.get("synthetic_promotion") is False
            and authority.get("root_closure_credit") == 0
            and authority.get("security") == "INDEPENDENT_A10_AND_SAFETY",
            "authority inversion")
    labels = data.get("semantic_names", {})
    require(set(labels) == {"CBQ", "CH-BD"}
            and all(v == "USER_LABEL_PENDING_CANONICAL_GLOSSARY"
                    for v in labels.values()), "invented taxonomy")
    entries = data.get("snapshots")
    require(isinstance(entries, list) and entries, "missing snapshots")
    seen = set()
    for entry in entries:
        identity = (entry.get("repository"), entry.get("pr"))
        require(identity not in seen, "duplicate PR")
        seen.add(identity)
        require(isinstance(entry.get("head_sha"), str)
                and re.fullmatch(r"[0-9a-f]{40}", entry["head_sha"]),
                "missing exact head")
        for key in ("success", "failed", "cancelled", "nonterminal"):
            require(type(entry.get(key)) is int and entry[key] >= 0,
                    "invalid workflow count")
        require(sum(entry[k] for k in (
            "success", "failed", "cancelled", "nonterminal")) > 0,
            "zero-workflow denominator")
        require(entry.get("evidence") == "LIVE_GITHUB_WORKFLOW_METADATA",
                "unsupported evidence")
    roots = data.get("families")
    require(isinstance(roots, list) and roots, "missing causal queue")
    root_ids = set()
    for item in roots:
        require(item.get("id") not in root_ids, "duplicate root")
        root_ids.add(item.get("id"))
        require(item.get("priority") in PRIORITY
                and item.get("verified_closed") is False
                and isinstance(item.get("proof"), str) and bool(item["proof"])
                and isinstance(item.get("owner"), str) and bool(item["owner"]),
                "unqualified root closure")
    chain = data.get("chain")
    require(isinstance(chain, list) and len(chain) == 4
            and all(e.get("status") in ("UNKNOWN", "DEFER")
                    for e in chain), "unqualified federation")
    base = data.get("baseline", {})
    require(base.get("historical_QPS_product_closure")
            == {"numerator": 70, "denominator": 90}
            and base.get("historical_GOGREEN_cells")
            == {"numerator": 6, "denominator": 42, "unknown": 36}
            and base.get("independent_verified_closures") == 0,
            "historical population or closure promoted")
    s = data.get("scale", {})
    require(s.get("candidate_disjoint_source_workers") == 2
            and s.get("scale_to") == 4
            and s.get("actual_live_worker_count") is None
            and s.get("queue_p95_seconds") is None
            and s.get("worked_hours") is None,
            "worker deployment inferred")


def produce(source, out):
    source = Path(source)
    out = Path(out)
    raw = source.read_bytes()
    data = json.loads(raw)
    validate(data)
    out.mkdir(parents=True, exist_ok=True)
    queue = sorted(data["families"], key=lambda r: (
        PRIORITY[r["priority"]], r["id"]))
    counts = {
        key: sum(x[key] for x in data["snapshots"])
        for key in ("success", "failed", "cancelled", "nonterminal")
    }
    projection = {
        "schema": "code-purple.cbq_ch_bd.projection.v1",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "pulse": data["pulse"],
        "cbq": queue,
        "ch_bd": data["chain"],
        "snapshots": data["snapshots"],
        "workflow_totals": counts,
        "historical_baseline": data["baseline"],
        "scale": data["scale"],
        "authority": data["authority"],
        "verified_root_closures": 0,
        "grade": "SUPPORTING_READ_ONLY_PROJECTION",
    }
    (out / "projection.json").write_text(
        json.dumps(projection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    with (out / "cbq.csv").open("w", encoding="utf-8", newline="") as fp:
        fields = ["priority", "id", "owner", "state",
                  "proof", "proposed_workers"]
        writer = csv.DictWriter(fp, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(queue)
    lines = [
        "# CODE PURPLE — CBQ / CH-BD pulse",
        "",
        "Read-only dated GitHub status, not merge or QPS engineering authority.",
        "",
        "| PR | SHA | PASS | FAIL | CANCEL | PENDING |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for x in data["snapshots"]:
        lines.append(
            f'| {x["repository"]} #{x["pr"]} | {x["head_sha"][:12]} | '
            f'{x["success"]} | {x["failed"]} | {x["cancelled"]} | '
            f'{x["nonterminal"]} |'
        )
    lines.extend(["", "## CBQ causal work order", "",
                  "| Priority | Root | Owner | Disposition | Required DoV |",
                  "|---|---|---|---|---|"])
    for x in queue:
        lines.append(
            f'| {x["priority"]} | {x["id"]} | {x["owner"]} | '
            f'{x["state"]} | {x["proof"]} |'
        )
    lines.extend(["", "## CH-BD evidence handoffs", "",
                  "| From | To | Proof | Status |",
                  "|---|---|---|---|"])
    for x in data["chain"]:
        lines.append(
            f'| {x["from"]} | {x["to"]} | '
            f'{x["obligation"]} | {x["status"]} |'
        )
    lines.extend([
        "", "## Scaling gate", "",
        "2 disjoint candidate workers; 4 only after comparable p95,"
        " zero path conflicts, exact-head proof and no security waiver.",
        "",
        "**QPS DEFER | NATIVE FOUR-HOP UNKNOWN | CLOSED ROOTS 0**",
        "",
    ])
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {
        "source_sha256": projection["source_sha256"],
        "artifacts": {
            name: hashlib.sha256((out / name).read_bytes()).hexdigest()
            for name in ("projection.json", "cbq.csv", "report.md")
        },
        "evidence_level": "LOCAL_REPRODUCIBILITY",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(produce(a.source, a.out), sort_keys=True))


if __name__ == "__main__":
    main()
