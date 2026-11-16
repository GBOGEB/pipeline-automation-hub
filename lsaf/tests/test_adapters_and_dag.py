from lsaf.compiler.adapters import repository_bindings, session_from_census
from lsaf.compiler.dag import compile_dag


def test_session_census_adapter_preserves_unknown_worktree():
    rec = {
        "id": "local_abcdef123456",
        "title": "Lane A replay",
        "created": "2026-11-13 10:00",
        "last": "2026-11-13 11:30",
        "cwd": r"C:\work\candidate",
        "prs_app": ["GBOGEB/pipeline-automation-hub#1231:OPEN"],
        "branches": ["feat/x"],
        "verdict": "PARTIAL",
        "flags": ["no-record"],
    }
    assert repository_bindings(rec) == ["GBOGEB/pipeline-automation-hub"]
    got = session_from_census(rec)
    assert got["allocation_observation"]["physical_worktree"] is None
    assert got["allocation_observation"]["physical_worktree_candidate"] == rec["cwd"]
    assert got["allocation_observation"]["physical_worktree_evidence"] == "UNKNOWN"
    assert got["temporal"]["observed_at"] == "2026-11-13T11:30:00Z"


def test_session_census_adapter_preserves_unknown_timestamp_as_null():
    got = session_from_census({"id": "local_x", "title": "unknown time", "last": "?", "prs_app": []})
    assert got["temporal"]["observed_at"] is None


def test_kahn_is_deterministic_and_orders_dependencies():
    nodes = [
        {"id": "B", "requires": ["A"], "authority": "Hub", "evidence": "SOURCE"},
        {"id": "A", "requires": [], "authority": "Hub", "evidence": "SOURCE"},
        {"id": "C", "requires": ["B"], "authority": "Hub", "evidence": "SOURCE"},
    ]
    one = compile_dag(nodes)
    two = compile_dag(list(reversed(nodes)))
    assert one == two
    assert one["ready"] == ["A"]
    assert one["order"] == ["A", "B", "C"]
    assert one["blocked"] == []


def test_kahn_detects_cycle_without_false_ready():
    got = compile_dag([
        {"id": "A", "requires": ["B"], "authority": "Hub", "evidence": "SOURCE"},
        {"id": "B", "requires": ["A"], "authority": "Hub", "evidence": "SOURCE"},
    ])
    assert got["ready"] == []
    assert got["cycle"] == ["A", "B"]
    assert got["blocked"] == ["A", "B"]


def test_missing_authority_and_evidence_fail_closed():
    got = compile_dag([
        {"id": "A", "requires": [], "authority": "UNKNOWN", "evidence": "SOURCE"},
        {"id": "B", "requires": [], "authority": "Hub", "evidence": "UNKNOWN"},
        {"id": "C", "requires": ["A"], "authority": "Hub", "evidence": "SOURCE"},
    ])
    assert got["ready"] == []
    assert got["missing_authority"] == ["A"]
    assert got["missing_evidence"] == ["B"]
    assert set(got["blocked"]) == {"A", "B", "C"}


def test_blocked_status_propagates_transitively_without_false_cycle():
    got = compile_dag([
        {"id": "A", "requires": [], "authority": "UNKNOWN", "evidence": "SOURCE"},
        {"id": "B", "requires": ["A"], "authority": "Hub", "evidence": "SOURCE"},
        {"id": "C", "requires": ["B"], "authority": "Hub", "evidence": "SOURCE"},
    ])
    assert got["ready"] == []
    assert got["cycle"] == []
    assert got["blocked"] == ["A", "B", "C"]


def test_superseded_and_predicted_evidence_never_enter_ready():
    got = compile_dag([
        {"id": "old", "requires": [], "authority": "Hub", "evidence": "SUPERSEDED"},
        {"id": "forecast", "requires": [], "authority": "Hub", "evidence": "PREDICTED"},
        {"id": "source", "requires": [], "authority": "Hub", "evidence": "SOURCE"},
    ])
    assert got["ready"] == ["source"]
    assert set(got["missing_evidence"]) == {"old", "forecast"}
