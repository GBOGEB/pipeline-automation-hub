"""Validate a read-only evidence snapshot against one TOP7/14/21 measurement contract."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "CROSS_REPO_COVERAGE_ROLLUP_20261013.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")

def validate(doc):
    if doc.get("schema") != "missioncontrol.cross_repo_coverage_rollup.v1":
        raise ValueError("unknown contract schema")
    if doc.get("authority_transfer") is not False or doc.get("formal_credit_delta") != 0 or doc.get("engineering_credit_delta") != 0:
        raise ValueError("receipt cannot confer authority or engineering credit")
    policy = doc.get("policy", {})
    if policy.get("cohort_promotion_by_coverage_alone") is not False or policy.get("minimum_percent") != 80:
        raise ValueError("unsupported promotion or coverage policy")
    rows = doc.get("observations")
    if not isinstance(rows, list):
        raise ValueError("missing observations")
    seen = set()
    for row in rows:
        repo = row["repository"]
        if repo in seen:
            raise ValueError("duplicate repository")
        seen.add(repo)
        if row.get("cohort") not in {"top7", "top14_extension", "top21_extension"}:
            raise ValueError("invalid cohort")
        if not SHA40.fullmatch(row.get("source_sha", "")) or not SHA40.fullmatch(row.get("base_sha", "")):
            raise ValueError("invalid source or base SHA")
        if not SHA64.fullmatch(row.get("artifact_sha256", "")):
            raise ValueError("invalid artifact hash")
        if row.get("security_clearance") is True and row.get("effective_main_protection") is not True:
            raise ValueError("security clearance cannot bypass branch protection")
        eligible, covered = row.get("eligible_lines"), row.get("covered_lines")
        if not isinstance(eligible, int) or isinstance(eligible, bool) or not isinstance(covered, int) or isinstance(covered, bool):
            raise ValueError("invalid line counts")
        if not (0 <= covered <= eligible):
            raise ValueError("invalid coverage numerator/denominator")
        missing = row.get("missing_source_files")
        if not isinstance(missing, list):
            raise ValueError("missing source file census")
        measured = row.get("status") == "MEASURED"
        if measured:
            if eligible == 0 or missing:
                raise ValueError("measured coverage must have complete positive denominator")
            if row.get("percent") != round(100 * covered / eligible, 2):
                raise ValueError("coverage percentage inconsistent with source counts")
        elif row.get("status") == "INCOMPLETE_INSTRUMENTATION":
            if row.get("percent") is not None or not missing:
                raise ValueError("incomplete instrumentation requires missing files and null percent")
        else:
            raise ValueError("unsupported observation state")
    return {"schema": "missioncontrol.cross_repo_coverage_validation.v1", "repositories": len(seen), "measured": sum(x["status"] == "MEASURED" for x in rows), "unknown": sum(x["percent"] is None for x in rows), "authority_transfer": False}

if __name__ == "__main__":
    print(json.dumps(validate(json.loads(SOURCE.read_text(encoding="utf-8"))), sort_keys=True))
