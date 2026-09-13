#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decision_for(score, candidate):
    independent = len(candidate.get("independent_need_signals", [])) >= 2
    trial_ready = bool(candidate.get("trial_ready", False))
    collision = bool(candidate.get("authority_collision", False))
    if score >= 0.65 and independent and trial_ready and not collision:
        return "TRIAL_CANDIDATE"
    if score >= 0.45:
        return "WATCH_OR_SECOND"
    return "REUSE_TRAIN_TOOL_OR_PRUNE"


def score_candidate(policy, candidate):
    signals = candidate.get("signals", {})
    penalties = candidate.get("penalties", {})
    positive = 0.0
    negative = 0.0
    missing = []

    for name, spec in policy["signals"].items():
        if name not in signals:
            missing.append(f"signal:{name}")
            continue
        value = float(signals[name])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{candidate['candidate_role_id']} {name} outside 0..1")
        positive += value * float(spec["weight"])

    for name, spec in policy["penalties"].items():
        if name not in penalties:
            missing.append(f"penalty:{name}")
            continue
        value = float(penalties[name])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{candidate['candidate_role_id']} {name} outside 0..1")
        negative += value * float(spec["weight"])

    if missing:
        raise ValueError(f"{candidate['candidate_role_id']} missing {', '.join(missing)}")

    score = max(0.0, min(1.0, positive - negative))
    return {
        "candidate_role_id": candidate["candidate_role_id"],
        "name": candidate.get("name"),
        "score": round(score, 4),
        "positive": round(positive, 4),
        "penalty": round(negative, 4),
        "decision": decision_for(score, candidate),
        "evidence_class": candidate.get("evidence_class"),
        "trial_ready": bool(candidate.get("trial_ready", False)),
        "authority_collision": bool(candidate.get("authority_collision", False)),
        "independent_need_signal_count": len(candidate.get("independent_need_signals", [])),
        "warning": candidate.get("warning")
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    policy = load_json(args.policy)
    signal_doc = load_json(args.signals)
    evidence_class = signal_doc.get("evidence_class", "UNPROVEN")

    results = []
    for candidate in signal_doc.get("candidates", []):
        c = dict(candidate)
        c["evidence_class"] = evidence_class
        results.append(score_candidate(policy, c))

    payload = {
        "schema": "missioncontrol.crew.role_gap_score_receipt.v1",
        "source_evidence_class": evidence_class,
        "authority_transfer": False,
        "permanent_role_promotion_allowed": evidence_class in {"MEASURED", "ACCEPTED"},
        "results": results
    }

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
