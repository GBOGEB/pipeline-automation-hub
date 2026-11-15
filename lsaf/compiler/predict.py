"""N->N+1 prediction receipts with append-only outcomes."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def make_prediction(
    prediction_id: str,
    source_state: dict[str, Any],
    *,
    next_state: str,
    confidence: float,
    next_blocker: str | None = None,
    next_repo: str | None = None,
    runs_to_boundary: int | None = None,
    commits_to_boundary: int | None = None,
) -> dict[str, Any]:
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0, 1]")
    return {
        "schema": "lsaf/prediction/v0.1",
        "prediction_id": prediction_id,
        "source_state": deepcopy(source_state),
        "predicted": {
            "next_state": next_state,
            "next_blocker": next_blocker,
            "next_repo": next_repo,
            "runs_to_boundary": runs_to_boundary,
            "commits_to_boundary": commits_to_boundary,
        },
        "confidence": float(confidence),
        "outcome": None,
        "score": None,
        "evidence_class": "PREDICTED",
    }


def append_outcome(receipt: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("outcome") is not None:
        raise ValueError("prediction outcome already recorded; original receipt is immutable")
    result = deepcopy(receipt)
    result["outcome"] = deepcopy(outcome)
    predicted_state = (receipt.get("predicted") or {}).get("next_state")
    actual_state = outcome.get("next_state")
    result["score"] = {
        "top1_correct": predicted_state == actual_state,
        "false_ready": bool(predicted_state == "EXECUTABLE" and actual_state in {"BLOCKED", "UNKNOWN"}),
        "false_blocked": bool(predicted_state == "BLOCKED" and actual_state == "EXECUTABLE"),
    }
    result["evidence_class"] = "DERIVED"
    return result
