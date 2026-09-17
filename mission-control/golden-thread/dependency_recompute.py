#!/usr/bin/env python3
"""Execute a bounded real-file Golden Thread invalidation/recompute cone."""
from __future__ import annotations

import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ff = _load("federation_frontier", HERE / "federation_frontier.py")
adapter = _load("occurrence_connector_adapter", HERE / "occurrence_connector_adapter.py")


class DependencyRecomputeError(ValueError):
    pass


def _node_map(manifest):
    return {node["id"]: node for node in manifest["nodes"]}


def execute_cone(manifest, output_dir):
    """Invalidate a declared descendant cone and deterministically recompute it.

    SOURCE_FILE nodes are rebound to their actual repository file bytes. Derived
    nodes are recomputed from the source fixture rather than copied from prior
    receipts. Generated JSON renditions are review evidence only, never SSOT.
    """
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = _node_map(manifest)
    node_ids = sorted(nodes)
    edges = [tuple(edge) for edge in manifest["edges"]]

    receipt = ff.build_invalidation_receipt(
        node_ids,
        edges,
        manifest["root_nodes"],
        "DESCENDANT_CONE",
        renditions=manifest.get("renditions"),
        trigger=manifest.get("trigger"),
    )

    source = nodes["BOOTSTRAP_FIXTURE"]
    source_path = ROOT / source["path"]
    if not source_path.is_file():
        raise DependencyRecomputeError(f"source path missing: {source_path}")
    fixture = json.loads(source_path.read_text(encoding="utf-8"))
    source_digest = ff.digest(fixture)

    records = [
        adapter.normalize_connector_snapshot(
            item["repository"], item["object_type"], item["anchor_sha"], item["snapshot"]
        )
        for item in fixture["records"]
    ]
    projection = ff.import_occurrences(records)
    projection_path = output_dir / "normalized-occurrence-projection.json"
    projection_path.write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    repositories = sorted({r["repository"] for r in records})
    summary = {
        "schema": "missioncontrol.golden_thread.bootstrap_recompute_summary.v1",
        "cone_id": manifest["cone_id"],
        "source_digest": source_digest,
        "repository_count": len(repositories),
        "repositories": repositories,
        "occurrence_count": projection["occurrence_count"],
        "projection_digest": projection["projection_digest"],
        "lineage_coverage": len(repositories) / fixture["expected"]["repository_count"],
        "authority_transfer": False,
    }
    summary["summary_digest"] = ff.digest(summary)
    summary_path = output_dir / "bootstrap-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    recomputed_nodes = ["BOOTSTRAP_FIXTURE", "NORMALIZED_OCCURRENCE_PROJECTION", "BOOTSTRAP_SUMMARY"]
    regenerated_renditions = [projection_path.name, summary_path.name]
    closure = ff.close_invalidation(receipt, recomputed_nodes, regenerated_renditions)

    return {
        "receipt": receipt,
        "closure": closure,
        "source_digest": source_digest,
        "projection": projection,
        "summary": summary,
        "generated_files": sorted(regenerated_renditions),
        "authority_transfer": False,
    }
