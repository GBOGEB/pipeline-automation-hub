import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("adaptive", Path(__file__).with_name("adaptive.py"))
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def member(**kw):
    base = {"repo": "GBOGEB/R", "path": "x.py", "negative_canary": False,
            "provider_state": "open", "semantic_state": "open"}
    base.update(kw)
    return base


def root(**kw):
    base = {"id": "r1", "repo": "GBOGEB/R", "target_repo": "GBOGEB/R", "branch": "fix/x",
            "member_ids": ["o1"], "state": "OPEN", "attempts": [], "lease": None}
    base.update(kw)
    return base


def finding(recurrence="ONCE"):
    return [{"id": "f1", "recurrence": recurrence}]


def test_canary_wins():
    r = A.route_root(root(), [member(negative_canary=True)], finding(), set())
    assert r["lane"] == "ANALYZE_ONLY_CANARY"


def test_foreign_fork_returns_to_owner():
    r = A.route_root(root(), [member()], finding(), {"NO_PUSH_FORK"})
    assert r["lane"] == "OWNER_RETURN"


def test_provider_resolved_reconciles_without_source_write():
    r = A.route_root(root(), [member(provider_state="resolved")], finding(), set())
    assert r["lane"] == "LEDGER_RECONCILE"
    assert r["writes"] is False


def test_everred_stops_self_repair():
    ev = {("GBOGEB/R", "x.py"): "EVERRED"}
    r = A.route_root(root(), [member()], finding(), set(), ev)
    assert r["lane"] == "PASS_ON_EVERRED"


def test_two_failed_releases_pass_to_root_red():
    attempts = [
        {"released_at": "x", "release_reason": "repair_failed"},
        {"released_at": "y", "release_reason": "verification_failed"},
    ]
    r = A.route_root(root(attempts=attempts), [member()], finding(), set())
    assert r["lane"] == "PASS_ON_ROOT_RED"
    assert r["self_repair_failures"] == 2


def test_stale_default_restack_precedes_repair():
    r = A.route_root(root(), [member()], finding(), set(), source_signals={"DEFAULT_PATH_ABSENT"})
    assert r["lane"] == "RESTACK_FIRST"


def test_bot_branch_folds_back():
    r = A.route_root(root(), [member()], finding(), {"NO_PUSH_BOT_BRANCH"})
    assert r["lane"] == "FOLD_BACK_DEFAULT"


def test_systemic_folds_back():
    r = A.route_root(root(), [member()], finding("SYSTEMIC"), set())
    assert r["lane"] == "FOLD_BACK_DEFAULT"


def test_seen_fixed_reuses_method():
    r = A.route_root(root(), [member()], finding(), {"SEEN_FIXED"})
    assert r["lane"] == "REUSE_METHOD"


def test_once_defaults_to_local_repair():
    r = A.route_root(root(), [member()], finding(), set())
    assert r["lane"] == "PR_LOCAL_REPAIR"


def test_project_reports_grouping_compression_and_disjoint_preview():
    ledger = {
        "observations": {
            "o1": {**member(), "semantic_state": "open"},
            "o2": {**member(path="y.py"), "semantic_state": "open"},
        },
        "roots": {
            "r1": {**root(id="r1", member_ids=["o1"]), "id": "r1"},
            "r2": {**root(id="r2", branch="fix/y", member_ids=["o2"]), "id": "r2"},
        },
    }
    hints = {
        "findings": {"f1": {"recurrence": "ONCE"}, "f2": {"recurrence": "ONCE"}},
        "observations": {
            "o1": {"finding": "f1", "hints": []},
            "o2": {"finding": "f2", "hints": []},
        },
        "proposals": [{"kind": "GROUP_FINDINGS", "item_ids": ["o1", "o2"]}],
    }
    plan = {
        "layers": [["r1:diagnose", "r2:diagnose"]],
        "packets": [
            {"root_id": "r1", "admission_reasons": []},
            {"root_id": "r2", "admission_reasons": []},
        ],
    }
    out = A.project(ledger, hints, queue_plan=plan, max_workers=4)
    assert out["telemetry"]["potential_root_savings_from_grouping"] == 1
    assert out["telemetry"]["potential_compression_ratio"] == 2.0
    assert set(out["dispatch_preview"]["selected_root_ids"]) == {"r1", "r2"}


def test_public_projection_has_no_root_or_path_detail():
    ledger = {"observations": {"o1": {**member(), "semantic_state": "open"}},
              "roots": {"r1": {**root(), "id": "r1"}}}
    hints = {"findings": {"f1": {"recurrence": "ONCE"}},
             "observations": {"o1": {"finding": "f1", "hints": []}}, "proposals": []}
    public = A.public_counts(A.project(ledger, hints))
    blob = str(public)
    assert "x.py" not in blob and "r1" not in blob


def test_without_queue_plan_nothing_is_dispatched():
    ledger = {"observations": {"o1": {**member(), "semantic_state": "open"}},
              "roots": {"r1": {**root(), "id": "r1"}}}
    hints = {"findings": {"f1": {"recurrence": "ONCE"}},
             "observations": {"o1": {"finding": "f1", "hints": []}}, "proposals": []}
    out = A.project(ledger, hints, queue_plan=None)
    assert out["matrix"][0]["admitted_by_kahn"] is False
    assert out["dispatch_preview"]["selected_root_ids"] == []
