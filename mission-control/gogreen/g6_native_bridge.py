"""G6 read-only intake adapter for #531's canonical six-repo census.

Caller must authenticate repository heads and GitHub run/job metadata separately.
No network, dispatch, mutation, ZIP byte verification, or admission authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from spine import INPUT_SCHEMA, build

G5_SCHEMA = "codepurple.g5.discovery-gap-crosswalk.v1"


def bridge(crosswalk: dict, authenticated_heads: dict, observations: list) -> dict:
    if not isinstance(crosswalk, dict) or crosswalk.get("schema") != G5_SCHEMA:
        raise ValueError("invalid G5 crosswalk")
    if crosswalk.get("controls", {}).get("authority_transfer") is not False:
        raise ValueError("authority transfer forbidden")
    cohort = crosswalk["current_cohort"]
    if cohort.get("validated_observed_cells") is not None:
        raise ValueError("G5 planning observations unexpectedly promoted")
    repos = cohort["repos"]
    heads = {r["repository"]: r["source_sha"] for r in repos}
    if len(repos) != 6 or len(heads) != 6 or not isinstance(authenticated_heads, dict):
        raise ValueError("six exact repository heads required")
    if heads != authenticated_heads:
        raise ValueError("repository head drift; refresh cohort before ingestion")
    if not isinstance(observations, list):
        raise ValueError("native observation list required")
    catalog = [
        {"repository": r["repository"], "head_sha": r["source_sha"],
         "ref_kind": "MAIN", "target_families": r["families"],
         "authority_transfer": False}
        for r in repos
    ]
    if sum(len(r["target_families"]) for r in catalog) != 42:
        raise ValueError("eligible denominator drift")
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("invalid observation")
        if row.get("workflow_status") != "completed" or row.get("job_status") != "completed":
            raise ValueError("nonterminal evidence rejected")
        artifact = row.get("artifact")
        if artifact is not None and artifact.get("bytes_verified") is not False:
            raise ValueError("independent #530 ZIP/member verification required")
    evidence, scouts, hooks = build({
        "schema": INPUT_SCHEMA, "repositories": catalog, "observations": observations
    })
    return {
        "schema": "codepurple.g6.native-intake-bridge.v1",
        "classification": "OBSERVATIONAL_METADATA_ONLY",
        "cohort_heads": heads, "evidence": evidence,
        "scout_plan": scouts, "federation_hooks": hooks,
        "independent_530_verification": None,
        "verified_zip_members": None,
        "worker_hours": None, "accepted_root_closures": None,
        "m1": "METADATA_ONLY", "m2": "HOLD", "m3": "HOLD",
        "pca_bt": "NOT_ASSESSABLE",
        "merge_authorized": False, "security_waiver": False,
        "qps_owner_acceptance": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crosswalk", type=Path, required=True)
    p.add_argument("--heads", type=Path, required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = bridge(json.loads(a.crosswalk.read_text(encoding="utf-8")),
                    json.loads(a.heads.read_text(encoding="utf-8")),
                    json.loads(a.observations.read_text(encoding="utf-8")))
    a.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
