"""Fail-closed read-only check for LDAB, Bandit and BD census crosswalk."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE / "LDAB_SECURITY_CENSUS_CROSSWALK_20261013.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


def validate(doc):
    if doc.get("schema") != "missioncontrol.ldab_security_crosswalk.v1":
        raise ValueError("unknown schema")
    if (doc.get("authority_transfer") is not False or
            doc.get("formal_credit_delta") != 0 or
            doc.get("engineering_credit_delta") != 0):
        raise ValueError("unauthorized credit")
    obs = doc["observation"]
    if not SHA.fullmatch(obs.get("source_sha", "")):
        raise ValueError("invalid exact source SHA")
    if not HASH.fullmatch(obs.get("artifact_sha256", "")):
        raise ValueError("invalid artifact hash")
    counted = obs["bandit_touched_counts"]
    if sum(counted.values()) != sum(int(v) for v in counted.values()):
        raise ValueError("invalid counts")
    if any(type(v) is not int or v < 0 for v in counted.values()):
        raise ValueError("negative or non-integer findings")
    if counted["B101"] - obs["baseline_B101"] != obs["new_B101_count_delta"]:
        raise ValueError("Bandit delta discrepancy")
    if obs.get("security_admission") != "HOLD" or obs.get("independent_disposition") is not None:
        raise ValueError("independent security admission not established")
    if not 0 <= obs["changed_covered"] <= obs["changed_eligible"]:
        raise ValueError("invalid coverage counts")
    if round(100 * obs["changed_covered"] / obs["changed_eligible"], 2) != obs["changed_percent"]:
        raise ValueError("invalid coverage percentage")
    ldab = doc["ldab"]
    if ldab.get("status") == "DECLARED_NOT_LIVE":
        if any(ldab.get(k) is not None for k in
               ("container_id", "image_digest", "observed_port", "lldb_session",
                "steps", "exact_sha", "receipt_sha256")):
            raise ValueError("declared runtime cannot claim execution proof")
    else:
        raise ValueError("live LDAB requires separately authenticated runtime producer")
    if len({f["fingerprint_family"] for f in doc["linked_findings"]}) != len(doc["linked_findings"]):
        raise ValueError("duplicate census finding family")
    return {"schema": "missioncontrol.ldab_crosswalk_validation.v1",
            "finding_families": len(doc["linked_findings"]),
            "bandit_findings": sum(counted.values()),
            "ldab_live_verified": False, "security_clearance": None}


if __name__ == "__main__":
    print(json.dumps(validate(json.loads(INPUT.read_text(encoding="utf-8"))), sort_keys=True))
