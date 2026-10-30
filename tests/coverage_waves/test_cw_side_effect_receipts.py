"""Coverage-wave behavioural tests for mission-control/golden-thread/side_effect_receipts.py.

Targets branches the existing golden-thread tests leave uncovered: input
validation errors, registry corruption detection, receipt binding errors,
verification failure modes and the CLI entry point.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GT_DIR = REPO_ROOT / "mission-control" / "golden-thread"
if str(GT_DIR) not in sys.path:
    sys.path.insert(0, str(GT_DIR))

_spec = importlib.util.spec_from_file_location("cw_side_effect_receipts", GT_DIR / "side_effect_receipts.py")
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)


def _intent(**overrides):
    value = {
        "authority_domain": "GBOGEB/cw-example",
        "action": "GITHUB_ISSUE_COMMENT_CREATE",
        "target": "GBOGEB/cw-example#7",
        "mechanism": "REG",
        "source_state_digest": sr.digest({"state": 1}),
        "payload_digest": sr.digest({"payload": 1}),
        "schema_version": "github.issue_comment.v1",
        "expected_semantic_delta": "NONE",
    }
    value.update(overrides)
    return value


def _result_digest():
    return sr.digest({"result": "ok"})


# ---------------------------------------------------------------- load / canonical


def test_load_json_reads_object(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert sr.load_json(p) == {"a": 1}


def test_load_json_rejects_non_object(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(sr.SideEffectError, match="top-level JSON must be an object"):
        sr.load_json(p)


def test_canonical_intent_strips_strings_and_lowercases_digests():
    upper = "sha256:" + "A" * 64
    c = sr.canonical_intent(_intent(action="  ACT  ", source_state_digest=upper))
    assert c["action"] == "ACT"
    assert c["source_state_digest"] == "sha256:" + "a" * 64


def test_canonical_intent_without_semantic_delta_omits_key():
    intent = _intent()
    del intent["expected_semantic_delta"]
    c = sr.canonical_intent(intent)
    assert "expected_semantic_delta" not in c
    # And the identity differs from the variant carrying the delta.
    assert sr.transaction_id(intent) != sr.transaction_id(_intent())


def test_canonical_intent_rejects_non_object():
    with pytest.raises(sr.SideEffectError, match="^intent must be an object$"):
        sr.canonical_intent(["not", "a", "dict"])


@pytest.mark.parametrize("value", [None, "", "   ", 5])
def test_canonical_intent_rejects_missing_or_blank_string(value):
    with pytest.raises(sr.SideEffectError, match="^missing/invalid target$"):
        sr.canonical_intent(_intent(target=value))


def test_canonical_intent_rejects_malformed_digest():
    with pytest.raises(sr.SideEffectError, match="^payload_digest must be sha256:<64 hex>$"):
        sr.canonical_intent(_intent(payload_digest="sha256:xyz"))


def test_obligation_ignores_payload_and_source_state():
    a = _intent()
    b = _intent(payload_digest=sr.digest({"payload": 2}), source_state_digest=sr.digest({"state": 2}))
    assert sr.obligation_id(a) == sr.obligation_id(b)
    assert sr.transaction_id(a) != sr.transaction_id(b)


# ---------------------------------------------------------------- registry validation


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda r: r.__setitem__("schema", "other"), "registry schema mismatch"),
        (lambda r: r.__setitem__("authority_transfer", True), "registry authority_transfer must remain false"),
        (lambda r: r.__setitem__("transactions", []), "transactions must be an object"),
        (lambda r: r.__setitem__("obligation_heads", None), "obligation_heads must be an object"),
    ],
)
def test_plan_rejects_invalid_registry(mutate, message):
    registry = sr.empty_registry()
    mutate(registry)
    with pytest.raises(sr.SideEffectError, match="^" + message + "$"):
        sr.plan(registry, _intent())


def test_plan_detects_registry_corruption_on_hash_collision():
    registry = sr.register_planned(sr.empty_registry(), _intent())
    tx_id = sr.transaction_id(_intent())
    registry["transactions"][tx_id]["intent"]["target"] = "tampered"
    with pytest.raises(sr.SideEffectError, match="transaction hash collision or registry corruption"):
        sr.plan(registry, _intent())


def test_register_planned_replay_returns_equal_independent_copy():
    registry = sr.register_planned(sr.empty_registry(), _intent())
    again = sr.register_planned(registry, _intent())
    assert again == registry
    assert again is not registry
    again["transactions"].clear()
    assert registry["transactions"]


def test_register_successor_links_parent_and_moves_head():
    first = sr.register_planned(sr.empty_registry(), _intent())
    second_intent = _intent(payload_digest=sr.digest({"payload": 2}))
    decision = sr.plan(first, second_intent)
    assert decision["changed_from_parent"] is True
    second = sr.register_planned(first, second_intent)
    tx2 = sr.transaction_id(second_intent)
    assert second["transactions"][tx2]["parent_transaction_id"] == sr.transaction_id(_intent())
    assert second["obligation_heads"][sr.obligation_id(_intent())] == tx2


# ---------------------------------------------------------------- bind_receipt


def test_bind_receipt_unknown_transaction():
    with pytest.raises(sr.SideEffectError, match="^unknown transaction_id sha256:nope$"):
        sr.bind_receipt(
            sr.empty_registry(), "sha256:nope", provider="p", external_ref="r", observed_result_digest=_result_digest()
        )


def test_bind_receipt_unsupported_status():
    registry = sr.register_planned(sr.empty_registry(), _intent())
    tx_id = sr.transaction_id(_intent())
    with pytest.raises(sr.SideEffectError, match="^unsupported status DONE$"):
        sr.bind_receipt(
            registry, tx_id, provider="p", external_ref="r", observed_result_digest=_result_digest(), status="DONE"
        )


def test_bind_receipt_bad_result_digest():
    registry = sr.register_planned(sr.empty_registry(), _intent())
    tx_id = sr.transaction_id(_intent())
    with pytest.raises(sr.SideEffectError, match="observed_result_digest must be sha256:<64 hex>"):
        sr.bind_receipt(registry, tx_id, provider="p", external_ref="r", observed_result_digest="md5:abc")


def test_bind_receipt_with_metadata_and_failed_status_is_idempotent():
    registry = sr.register_planned(sr.empty_registry(), _intent())
    tx_id = sr.transaction_id(_intent())
    upper = "sha256:" + "B" * 64
    bound = sr.bind_receipt(
        registry,
        tx_id,
        provider="github",
        external_ref="comment/1",
        observed_result_digest=upper,
        status="FAILED",
        metadata={"http": 500},
    )
    tx = bound["transactions"][tx_id]
    assert tx["status"] == "FAILED"
    assert tx["receipt"]["metadata"] == {"http": 500}
    assert tx["receipt"]["observed_result_digest"] == "sha256:" + "b" * 64
    assert tx["receipt"]["intent_digest"] == sr.digest(tx["intent"])
    # The original registry is untouched.
    assert registry["transactions"][tx_id]["receipt"] is None
    # Re-binding the identical receipt is accepted.
    again = sr.bind_receipt(
        bound,
        tx_id,
        provider="github",
        external_ref="comment/1",
        observed_result_digest=upper,
        status="FAILED",
        metadata={"http": 500},
    )
    assert again == bound
    assert sr.verify_registry(bound)["completed_receipt_count"] == 1


# ---------------------------------------------------------------- verify_registry


def _two_obligation_registry():
    r = sr.register_planned(sr.empty_registry(), _intent())
    r = sr.register_planned(r, _intent(target="GBOGEB/cw-example#8"))
    return r


def _bound_registry():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    return sr.bind_receipt(r, tx, provider="p", external_ref="r", observed_result_digest=_result_digest()), tx


def test_verify_registry_counts_lineage_and_receipts():
    r = sr.register_planned(sr.empty_registry(), _intent())
    r = sr.register_planned(r, _intent(payload_digest=sr.digest({"payload": 2})))
    tx1 = sr.transaction_id(_intent())
    r = sr.bind_receipt(r, tx1, provider="p", external_ref="x", observed_result_digest=_result_digest())
    result = sr.verify_registry(r)
    assert result["status"] == "PASS"
    assert result["transaction_count"] == 2
    assert result["lineage_edge_count"] == 1
    assert result["completed_receipt_count"] == 1
    assert result["registry_digest"] == sr.digest(r)


def test_verify_detects_transaction_key_mismatch():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    r["transactions"][tx]["transaction_id"] = "sha256:other"
    with pytest.raises(sr.SideEffectError, match="^transaction key mismatch " + tx + "$"):
        sr.verify_registry(r)


def test_verify_detects_identity_mismatch():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    r["transactions"][tx]["intent"]["action"] = "OTHER"
    with pytest.raises(sr.SideEffectError, match="^transaction identity mismatch " + tx + "$"):
        sr.verify_registry(r)


def test_verify_treats_missing_intent_as_identity_mismatch():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    r["transactions"][tx]["intent"] = None
    with pytest.raises(sr.SideEffectError, match="missing/invalid authority_domain"):
        sr.verify_registry(r)


def test_verify_detects_obligation_mismatch():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    r["transactions"][tx]["obligation_id"] = "sha256:wrong"
    with pytest.raises(sr.SideEffectError, match="^obligation identity mismatch " + tx + "$"):
        sr.verify_registry(r)


def test_verify_detects_missing_parent():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    r["transactions"][tx]["parent_transaction_id"] = "sha256:ghost"
    with pytest.raises(sr.SideEffectError, match="^missing parent transaction sha256:ghost$"):
        sr.verify_registry(r)


def test_verify_detects_cross_obligation_parent_edge():
    r = _two_obligation_registry()
    tx_a = sr.transaction_id(_intent())
    tx_b = sr.transaction_id(_intent(target="GBOGEB/cw-example#8"))
    r["transactions"][tx_b]["parent_transaction_id"] = tx_a
    with pytest.raises(sr.SideEffectError, match="^cross-obligation parent edge " + tx_b + "$"):
        sr.verify_registry(r)


def test_verify_detects_bad_status():
    r = sr.register_planned(sr.empty_registry(), _intent())
    tx = sr.transaction_id(_intent())
    r["transactions"][tx]["status"] = "WEIRD"
    with pytest.raises(sr.SideEffectError, match="^bad transaction status " + tx + "$"):
        sr.verify_registry(r)


def test_verify_detects_receipt_transaction_mismatch():
    r, tx = _bound_registry()
    r["transactions"][tx]["receipt"]["transaction_id"] = "sha256:else"
    with pytest.raises(sr.SideEffectError, match="^receipt transaction mismatch " + tx + "$"):
        sr.verify_registry(r)


def test_verify_detects_receipt_digest_mismatch():
    r, tx = _bound_registry()
    r["transactions"][tx]["receipt"]["external_ref"] = "edited"
    with pytest.raises(sr.SideEffectError, match="^receipt digest mismatch " + tx + "$"):
        sr.verify_registry(r)


def test_verify_detects_receipt_authority_transfer_even_with_valid_digest():
    r, tx = _bound_registry()
    receipt = r["transactions"][tx]["receipt"]
    receipt.pop("receipt_digest")
    receipt["authority_transfer"] = True
    receipt["receipt_digest"] = sr.digest(receipt)
    with pytest.raises(sr.SideEffectError, match="^receipt authority transfer " + tx + "$"):
        sr.verify_registry(r)


def test_verify_detects_obligation_head_missing_transaction():
    r = sr.register_planned(sr.empty_registry(), _intent())
    obl = sr.obligation_id(_intent())
    r["obligation_heads"][obl] = "sha256:ghost"
    with pytest.raises(sr.SideEffectError, match="^obligation head missing transaction " + obl + "$"):
        sr.verify_registry(r)


def test_verify_detects_obligation_head_pointing_to_other_obligation():
    r = _two_obligation_registry()
    obl_a = sr.obligation_id(_intent())
    tx_b = sr.transaction_id(_intent(target="GBOGEB/cw-example#8"))
    r["obligation_heads"][obl_a] = tx_b
    with pytest.raises(sr.SideEffectError, match="^obligation head mismatch " + obl_a + "$"):
        sr.verify_registry(r)


# ---------------------------------------------------------------- dump / CLI


def test_dump_json_creates_parent_dirs(tmp_path):
    out = tmp_path / "nested" / "deeper" / "r.json"
    sr.dump_json({"b": 1, "a": 2}, out)
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')


def test_dump_json_stdout(capsys):
    sr.dump_json({"k": "v"}, None)
    assert json.loads(capsys.readouterr().out) == {"k": "v"}


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_main_plan_register_verify_round_trip(tmp_path, capsys):
    reg = _write(tmp_path / "reg.json", sr.empty_registry())
    intent = _write(tmp_path / "intent.json", _intent())

    assert sr.main(["plan", str(reg), str(intent)]) == 0
    plan_out = json.loads(capsys.readouterr().out)
    assert plan_out["decision"] == "NEW_TRANSACTION"
    assert plan_out["transaction_id"] == sr.transaction_id(_intent())

    out = tmp_path / "out" / "reg2.json"
    assert sr.main(["register", str(reg), str(intent), "--out", str(out)]) == 0
    registered = json.loads(out.read_text(encoding="utf-8"))
    assert list(registered["transactions"]) == [sr.transaction_id(_intent())]

    assert sr.main(["verify", str(out)]) == 0
    verify_out = json.loads(capsys.readouterr().out)
    assert verify_out["status"] == "PASS"
    assert verify_out["transaction_count"] == 1

    assert sr.main(["plan", str(out), str(intent)]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "REPLAY_EXISTING"


def test_main_reports_failure_and_returns_2(tmp_path, capsys):
    bad = _write(tmp_path / "bad.json", [1])
    assert sr.main(["verify", str(bad)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("FAIL: ")
    assert "top-level JSON must be an object" in err


def test_main_verify_failure_on_corrupt_registry(tmp_path, capsys):
    reg = copy.deepcopy(sr.empty_registry())
    reg["authority_transfer"] = True
    path = _write(tmp_path / "reg.json", reg)
    assert sr.main(["verify", str(path)]) == 2
    assert capsys.readouterr().err.strip() == "FAIL: registry authority_transfer must remain false"


def test_main_via_sys_argv(tmp_path, capsys, monkeypatch):
    reg = _write(tmp_path / "reg.json", sr.empty_registry())
    monkeypatch.setattr(sys, "argv", ["side_effect_receipts.py", "verify", str(reg)])
    assert sr.main() == 0
    assert json.loads(capsys.readouterr().out)["transaction_count"] == 0
