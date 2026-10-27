"""Behavioural tests for crew/measured/frontier/temporal/temporal_policy_engine.py."""
from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPORAL_DIR = (
    REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "frontier" / "temporal"
)
TARGET = TEMPORAL_DIR / "temporal_policy_engine.py"
CONFIG_NAME = "TEMPORAL_POLICY_CONFIG_v1.json"
CONTROL_PATH = ".github/workflows/crew-temporal-allocation-policy.yml"
LEARN_PATH = ".github/workflows/crew-pc3-conditional-bt.yml"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


@pytest.fixture
def mod(tmp_path):
    # The module reads its config relative to __file__ at import time; point it at a tmp copy.
    shutil.copy(TEMPORAL_DIR / CONFIG_NAME, tmp_path / CONFIG_NAME)
    spec = importlib.util.spec_from_file_location("cw_temporal_policy_engine", TARGET)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(tmp_path / "engine_under_test.py")
    spec.loader.exec_module(module)
    return module


class FakeResp:
    def __init__(self, body: bytes):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeNet:
    """Replacement for urllib.request.build_opener that routes URLs to canned payloads."""

    def __init__(self, route):
        self.route = route
        self.calls = []

    def build_opener(self, *handlers):
        net = self

        class _Opener:
            def open(self, req, timeout=None):
                net.calls.append(
                    {"url": req.full_url, "headers": dict(req.header_items()), "handlers": handlers, "timeout": timeout}
                )
                value = net.route(req.full_url)
                if isinstance(value, BaseException):
                    raise value
                body = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
                return FakeResp(body)

        return _Opener()


def _http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", hdrs=None, fp=io.BytesIO(b""))


def _analysis(mod, sha, strength=0.8, rex=0, **over):
    doc = {
        "source_sha": sha,
        "task_receipts": 72,
        "accepted": 72,
        "rejected": 0,
        "bt_conditional_by_task_class": {
            tc: {
                "status": "READY_CONDITIONAL_OBSERVED",
                "observed_pairs": 6,
                "nodes": [
                    {"strategy": "ALLOC_SINGLE_CELL", "normalized_strength": strength},
                    {"strategy": "ALLOC_PAIRED_CELL", "normalized_strength": 1.0 - strength},
                ],
            }
            for tc in mod.CONFIG["task_classes"]
        },
        "rex": {"persistent_or_regression_count": rex},
    }
    doc.update(over)
    return doc


def _admission(sha, baseline=5.0, held=3.0, habitats=("linux", "windows", "macos")):
    rows = []
    for h in habitats:
        rows.append({"cell_id": f"{h}-baseline", "habitat": h, "lane": "baseline",
                     "admission_proxy_seconds_from_run_creation": baseline})
        rows.append({"cell_id": f"{h}-held", "habitat": h, "lane": "held",
                     "post_gate_admission_seconds": held})
    return {"source_sha": sha, "rows": rows}


def _run(run_id, created, sha, event="schedule", path=CONTROL_PATH, **over):
    run = {"id": run_id, "created_at": created, "head_sha": sha, "event": event, "path": path,
           "name": "wf", "head_branch": "main", "status": "completed", "conclusion": "success"}
    run.update(over)
    return run


def _window(mod, run_id, created, sha, strength=0.8, event="schedule", rex=0, baseline=5.0):
    return mod.make_window(
        _run(run_id, created, sha, event=event),
        _analysis(mod, sha, strength=strength, rex=rex),
        _admission(sha, baseline=baseline),
        "digest",
        "TEST",
    )


def _hour(h):
    day, hour = divmod(h, 24)
    return f"2026-01-{1 + day:02d}T{hour:02d}:00:00Z"


def _zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, payload in files.items():
            zf.writestr(name, json.dumps(payload))
    return buf.getvalue()


# --------------------------------------------------------------------------- helpers


def test_parse_ts_handles_z_and_empty(mod):
    assert mod.parse_ts("2026-01-01T00:00:00Z").utcoffset().total_seconds() == 0
    assert mod.parse_ts("") is None
    assert mod.parse_ts(None) is None


def test_sha256_matches_hashlib(mod):
    import hashlib

    assert mod.sha256(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_zip_json_finds_nested_and_root_and_missing(mod):
    raw = _zip({"b/X.json": {"v": 2}, "a/X.json": {"v": 1}, "Y.json": {"y": True}})
    data, digest = mod.zip_json(raw, "X.json")
    assert data == {"v": 1}  # sorted first match
    assert len(digest) == 64
    assert mod.zip_json(raw, "Y.json")[0] == {"y": True}
    assert mod.zip_json(raw, "Z.json") is None


@pytest.mark.parametrize(
    "strength,expected",
    [(0.55, "ALLOC_SINGLE_CELL"), (0.9, "ALLOC_SINGLE_CELL"), (0.45, "ALLOC_PAIRED_CELL"),
     (0.1, "ALLOC_PAIRED_CELL"), (0.5, "INDETERMINATE")],
)
def test_direction_from_bt_thresholds(mod, strength, expected):
    bt = {"nodes": [{"strategy": "ALLOC_SINGLE_CELL", "normalized_strength": strength}]}
    assert mod.direction_from_bt(bt) == (expected, strength)


def test_scarcity_observed_and_unproven(mod):
    adm = {"rows": [
        {"cell_id": "l-b", "lane": "baseline", "admission_proxy_seconds_from_run_creation": 31},
        {"cell_id": "l-h", "lane": "held", "post_gate_admission_seconds": 2},
        {"cell_id": "w-h", "lane": "held", "post_gate_admission_seconds": None},
    ]}
    out = mod.scarcity_from_admission(adm)
    assert out["status"] == "SCARCITY_OBSERVED"
    assert out["peak_eligible_seconds"] == 31.0
    assert [m["metric"] for m in out["measurements"]] == [
        "baseline_admission_proxy_seconds_from_run_creation", "held_post_gate_admission_seconds"]
    empty = mod.scarcity_from_admission({})
    assert empty["status"] == "SCARCITY_UNPROVEN"
    assert empty["peak_eligible_seconds"] == 0.0
    assert empty["threshold_seconds"] == 30.0


# --------------------------------------------------------------------------- make_window


def test_make_window_happy_path(mod):
    run = _run(77, "2026-01-01T00:00:00Z", SHA_A, run_attempt=None)
    w = mod.make_window(run, _analysis(mod, SHA_A, strength=0.2), _admission(SHA_A), "dg", "CURRENT")
    assert w["window_id"] == "77"
    assert w["run_attempt"] == 1
    assert w["hosted_runner_classes"] == ["linux", "macos", "windows"]
    assert w["lanes"] == ["baseline", "held"]
    assert w["rex_veto"] is False
    assert w["analysis_digest_sha256"] == "dg"
    tc = w["task_classes"]["short_compute"]
    assert tc["direction"] == "ALLOC_PAIRED_CELL"
    assert tc["paired_normalized_strength"] == pytest.approx(0.8)
    assert tc["observed_pairs"] == 6


def test_make_window_defaults_created_at_and_missing_rex_is_veto(mod):
    run = {"id": 5}
    analysis = _analysis(mod, SHA_A)
    del analysis["rex"]
    w = mod.make_window(run, analysis, _admission(SHA_A), "d", "K")
    assert w["created_at"]  # filled with now()
    assert w["rex_veto"] is True


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda r, a, adm: a.update(source_sha="short"), "invalid source sha"),
        (lambda r, a, adm: a.update(source_sha=None), "invalid source sha"),
        (lambda r, a, adm: adm.update(source_sha=SHA_B), "analysis/admission source mismatch"),
        (lambda r, a, adm: r.update(head_sha=SHA_B), "workflow head/source mismatch"),
        (lambda r, a, adm: a.update(accepted=71), "not 72/72"),
        (lambda r, a, adm: a.update(task_receipts=70), "not 72/72"),
        (lambda r, a, adm: a.update(rejected=1), "not 72/72"),
        (lambda r, a, adm: a["bt_conditional_by_task_class"]["short_compute"].update(status="NOPE"),
         "conditional BT not ready for short_compute"),
        (lambda r, a, adm: a["bt_conditional_by_task_class"]["validation_bundle"].update(observed_pairs=5),
         "conditional BT not ready for validation_bundle"),
    ],
)
def test_make_window_rejects_invalid(mod, mutate, message):
    run = _run(1, "2026-01-01T00:00:00Z", SHA_A)
    analysis = _analysis(mod, SHA_A)
    adm = _admission(SHA_A)
    mutate(run, analysis, adm)
    with pytest.raises(ValueError, match=message):
        mod.make_window(run, analysis, adm, "d", "K")


# --------------------------------------------------------------------------- run selection


def test_select_historical_runs_filters_dedups_and_sorts(mod):
    recent = [
        _run(1, "2026-01-01T00:00:00Z", SHA_A, event="push", path=LEARN_PATH),
        _run(2, "2026-01-02T00:00:00Z", SHA_A, event="push", path=LEARN_PATH, conclusion="failure"),
        _run(3, "2026-01-03T00:00:00Z", SHA_A, event="push", path=LEARN_PATH, status="in_progress"),
        _run(4, "2026-01-04T00:00:00Z", SHA_A, event="push", path=".github/workflows/other.yml"),
        _run(99, "2026-01-05T00:00:00Z", SHA_A, event="push", path=LEARN_PATH),  # current run
        _run(6, "2026-01-06T00:00:00Z", SHA_A),  # scheduled, also present in recent
    ]
    scheduled = [
        _run(6, "2026-01-06T00:00:00Z", SHA_A),
        _run(7, "2026-01-01T00:00:00Z", SHA_A),  # ties with run 1 on created_at; id breaks the tie
        _run(8, "2026-01-07T00:00:00Z", SHA_A, event="workflow_dispatch"),  # not control-eligible
        _run(9, "2026-01-08T00:00:00Z", SHA_A, path=LEARN_PATH),  # wrong control path
    ]
    out = mod.select_historical_runs(recent, scheduled, "99")
    assert [r["id"] for r in out] == [1, 7, 6]


def test_select_historical_runs_respects_limits_independently(mod):
    mod.CONFIG["window_contract"]["historical_learning_window_limit"] = 2
    mod.CONFIG["window_contract"]["historical_control_window_limit"] = 1
    recent = [_run(i, _hour(i), SHA_A, event="push", path=LEARN_PATH) for i in range(10, 15)]
    scheduled = [_run(i, _hour(i - 20), SHA_A) for i in range(20, 23)]
    out = mod.select_historical_runs(recent, scheduled, "0")
    # Learning traffic keeps only the last two; control keeps only its latest, not crowded out.
    assert [r["id"] for r in out] == [22, 13, 14]


# --------------------------------------------------------------------------- network


def test_api_request_json_and_binary(mod, monkeypatch):
    net = FakeNet(lambda url: b"RAW" if url.endswith("zip") else {"ok": 1})
    monkeypatch.setattr(mod.urllib.request, "build_opener", net.build_opener)
    assert mod.api_request("https://api.github.com/x", "test-token") == {"ok": 1}
    assert mod.api_request("https://api.github.com/a.zip", "test-token", binary=True) == b"RAW"
    first, second = net.calls
    assert first["handlers"] == ()
    assert first["timeout"] == 45
    assert first["headers"]["Authorization"] == "Bearer test-token"
    assert first["headers"]["Accept"] == "application/vnd.github+json"
    assert len(second["handlers"]) == 1
    assert isinstance(second["handlers"][0], mod.CrossHostAuthStrippingRedirect)


def _redirect(mod, newurl):
    req = urllib.request.Request("https://api.github.com/repos/o/r/actions/artifacts/1/zip")
    req.add_header("Authorization", "Bearer test-token")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    handler = mod.CrossHostAuthStrippingRedirect()
    return handler.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, newurl)


def test_redirect_cross_host_strips_authorization(mod):
    redirected = _redirect(mod, "https://blob.example.net/sas?sig=1")
    assert redirected.full_url == "https://blob.example.net/sas?sig=1"
    assert not redirected.has_header("Authorization")


def test_redirect_same_host_keeps_authorization(mod):
    redirected = _redirect(mod, "https://api.github.com/other")
    assert redirected.get_header("Authorization") == "Bearer test-token"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "production_defect: remove_header('X-GitHub-Api-Version') misses the header stored by "
        "add_header as 'X-github-api-version', so it is still forwarded cross-host"
    ),
)
def test_redirect_cross_host_strips_api_version_header(mod):
    redirected = _redirect(mod, "https://blob.example.net/sas?sig=1")
    assert not redirected.has_header("X-github-api-version")


def test_collect_historical_paginates(mod, monkeypatch):
    page1 = [_run(i, _hour(i % 24), SHA_A, event="push", path=LEARN_PATH) for i in range(1, 101)]
    page2 = [_run(500, "2026-02-01T00:00:00Z", SHA_A, event="push", path=LEARN_PATH)]
    sched = [_run(600, "2026-02-02T00:00:00Z", SHA_A)]

    def route(url):
        if "/workflows/" in url:
            return {"workflow_runs": sched}
        if url.endswith("page=1"):
            return {"workflow_runs": page1}
        if url.endswith("page=2"):
            return {"workflow_runs": page2}
        raise AssertionError(url)

    net = FakeNet(route)
    monkeypatch.setattr(mod.urllib.request, "build_opener", net.build_opener)
    out = mod.collect_historical("o/r", "test-token", "0")
    urls = [c["url"] for c in net.calls]
    assert urls[0] == "https://api.github.com/repos/o/r/actions/runs?per_page=100&page=1"
    assert urls[1].endswith("page=2")
    assert urls[2] == (
        "https://api.github.com/repos/o/r/actions/workflows/crew-temporal-allocation-policy.yml/runs"
        "?event=schedule&per_page=100&page=1"
    )
    assert len(urls) == 3
    ids = [r["id"] for r in out]
    assert 600 in ids and 500 in ids
    assert len(ids) == 24 + 1  # learning limit 24 plus one control run


def test_window_from_artifact_paths(mod, monkeypatch):
    run = _run(42, "2026-01-01T00:00:00Z", SHA_A)
    good_zip = _zip({
        "x/PC3_CONDITIONAL_BT_RECEIPT.json": _analysis(mod, SHA_A),
        "x/PC3_ADMISSION_TELEMETRY.json": _admission(SHA_A),
    })
    partial_zip = _zip({"PC3_CONDITIONAL_BT_RECEIPT.json": _analysis(mod, SHA_A)})
    state = {"artifacts": [], "zip": good_zip}

    def route(url):
        if url.endswith("/artifacts?per_page=100"):
            return {"artifacts": state["artifacts"]}
        if url.startswith("https://dl/"):
            assert url == "https://dl/new"
            return state["zip"]
        raise AssertionError(url)

    net = FakeNet(route)
    monkeypatch.setattr(mod.urllib.request, "build_opener", net.build_opener)

    assert mod.window_from_artifact("o/r", "test-token", run) is None
    state["artifacts"] = [
        {"name": "unrelated", "archive_download_url": "https://dl/bad"},
        {"name": "crew-pc3-conditional-bt-x", "expired": True, "archive_download_url": "https://dl/bad"},
    ]
    assert mod.window_from_artifact("o/r", "test-token", run) is None
    state["artifacts"] = [
        {"name": "crew-pc3-conditional-bt-1", "created_at": "2026-01-01", "archive_download_url": "https://dl/old"},
        {"name": "crew-temporal-pc3-2", "created_at": "2026-01-02", "archive_download_url": "https://dl/new"},
    ]
    w = mod.window_from_artifact("o/r", "test-token", run)
    assert w["source_kind"] == "HISTORICAL_ACTION_ARTIFACT"
    assert w["window_id"] == "42"
    state["zip"] = partial_zip
    assert mod.window_from_artifact("o/r", "test-token", run) is None


# --------------------------------------------------------------------------- metrics & policy


def test_window_metrics_empty_and_span(mod):
    empty = mod.window_metrics([])
    assert empty["independent_windows"] == 0
    assert empty["temporal_span_seconds"] == 0.0
    ws = [_window(mod, 2, _hour(2), SHA_B), _window(mod, 1, _hour(0), SHA_A, rex=1)]
    m = mod.window_metrics(ws)
    assert m["window_ids"] == ["1", "2"]
    assert m["temporal_span_seconds"] == 7200.0
    assert m["distinct_source_shas"] == 2
    assert m["rex_veto"] is True


def test_class_metrics_indeterminate_and_empty(mod):
    ws = [_window(mod, i, _hour(i), SHA_A, strength=0.5) for i in range(3)]
    m = mod.class_metrics(ws, "short_compute")
    assert m["dominant_direction"] == "INDETERMINATE"
    assert m["direction_consistency"] == 0.0
    assert m["latest_two_directional_windows_agree"] is False
    assert m["pooled_single_strength"] == pytest.approx(0.5)
    empty = mod.class_metrics([], "short_compute")
    assert empty["pooled_single_strength"] == 0.5
    assert empty["observed_pairs_total"] == 0


def test_gate_pass_optional_requirements(mod):
    gate = {"min_independent_windows": 1, "min_distinct_source_shas": 1, "min_temporal_span_seconds": 0,
            "min_directional_windows": 1, "min_direction_consistency": 0.5, "min_pooled_winner_strength": 0.5}
    args = ({"independent_windows": 1}, gate, 1, 0.0, 1, 1.0, 0.9, False, [], set())
    assert mod.gate_pass(*args) is True
    gate2 = dict(gate, latest_two_directional_windows_must_agree=True)
    assert mod.gate_pass(args[0], gate2, *args[2:]) is False
    gate3 = dict(gate, requires_baseline_and_held_lanes=True)
    assert mod.gate_pass(args[0], gate3, *args[2:]) is False
    assert mod.gate_pass(args[0], gate3, 1, 0.0, 1, 1.0, 0.9, False, [], {"baseline", "held"}) is True
    gate4 = dict(gate, min_hosted_runner_classes=2)
    assert mod.gate_pass(args[0], gate4, *args[2:]) is False


def test_build_policy_control_policy(mod):
    shas = [SHA_A, SHA_B, SHA_C]
    ws = [_window(mod, 100 + i, _hour(6 * i), shas[i % 3], strength=0.2) for i in range(6)]
    receipt = mod.build_policy(ws)
    assert receipt["independent_windows"] == 6
    assert receipt["temporal_span_seconds"] == 30 * 3600
    assert receipt["scheduled_control_frontier"]["independent_windows"] == 6
    assert receipt["natural_scarcity"]["status"] == "SCARCITY_UNPROVEN"
    for policy in receipt["policies"].values():
        assert policy["policy_status"] == "CONTROL_POLICY"
        assert policy["allocation_recommendation"] == "ALLOC_PAIRED_CELL"
        assert policy["allocation_policy_promotion"] is True
        assert policy["competency_promotion"] is False
    assert receipt["competency_promotions"] == 0


def test_build_policy_control_fails_on_short_span_falls_to_repeat_stable(mod):
    shas = [SHA_A, SHA_B, SHA_C]
    ws = [_window(mod, 100 + i, _hour(i), shas[i % 3]) for i in range(6)]  # 5h span < 86400
    receipt = mod.build_policy(ws)
    policy = receipt["policies"]["short_compute"]
    assert policy["policy_status"] == "RECOMMEND_REPEAT_STABLE"
    assert policy["allocation_recommendation"] == "ALLOC_SINGLE_CELL"
    assert policy["allocation_policy_promotion"] is False


def test_build_policy_learning_windows_never_count_as_control(mod):
    ws = [_window(mod, i, _hour(i), [SHA_A, SHA_B][i % 2], event="push") for i in range(3)]
    receipt = mod.build_policy(ws)
    assert receipt["scheduled_control_frontier"]["independent_windows"] == 0
    policy = receipt["policies"]["long_compute_contended"]
    assert policy["policy_status"] == "RECOMMEND_REPEAT_STABLE"
    assert policy["control_frontier"]["dominant_direction"] == "INDETERMINATE"


def test_build_policy_direction_unstable(mod):
    strengths = [0.8, 0.2, 0.8]
    ws = [_window(mod, i, _hour(i), [SHA_A, SHA_B][i % 2], strength=s, event="push")
          for i, s in enumerate(strengths)]
    policy = mod.build_policy(ws)["policies"]["short_compute"]
    assert policy["direction_consistency"] == pytest.approx(2 / 3)
    assert policy["policy_status"] == "LEARNING_DIRECTION_UNSTABLE"
    assert policy["allocation_recommendation"] == "NO_POLICY"


def test_build_policy_rex_veto_and_scarcity(mod):
    ws = [
        _window(mod, 1, _hour(0), SHA_A, baseline=45.0),
        _window(mod, 2, _hour(5), SHA_B, rex=2),
    ]
    receipt = mod.build_policy(ws)
    assert receipt["rex_veto"] is True
    assert receipt["natural_scarcity"] == {
        "status": "SCARCITY_OBSERVED", "window_ids": ["1"], "designed_held_gate_excluded": True}
    assert all(p["policy_status"] == "VETO_REX" for p in receipt["policies"].values())


def test_build_policy_single_window_stays_learning(mod):
    receipt = mod.build_policy([_window(mod, 1, _hour(0), SHA_A)])
    assert all(p["policy_status"] == "LEARNING" for p in receipt["policies"].values())
    assert receipt["status"] == "PASS_TEMPORAL_POLICY_LEARNING"


# --------------------------------------------------------------------------- main


def test_main_requires_environment(mod, monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "1")
    monkeypatch.setattr(sys, "argv", ["x", "--current-analysis", "a", "--current-admission", "b",
                                      "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit, match="GITHUB_TOKEN/GITHUB_REPOSITORY/GITHUB_RUN_ID required"):
        mod.main()


def test_main_end_to_end(mod, monkeypatch, tmp_path, capsys):
    current_id = 900
    hist_ok = _run(10, _hour(0), SHA_A, event="push", path=LEARN_PATH)
    hist_http = _run(11, _hour(1), SHA_B, event="push", path=LEARN_PATH)
    hist_badzip = _run(12, _hour(2), SHA_B, event="push", path=LEARN_PATH)
    hist_none = _run(13, _hour(3), SHA_B, event="push", path=LEARN_PATH)
    current = _run(current_id, _hour(4), SHA_C, event="push", path=LEARN_PATH)
    hist_zip = _zip({
        "PC3_CONDITIONAL_BT_RECEIPT.json": _analysis(mod, SHA_A),
        "PC3_ADMISSION_TELEMETRY.json": _admission(SHA_A),
    })
    art = {"name": "crew-pc3-conditional-bt-1", "created_at": "t"}

    def route(url):
        base = "https://api.github.com/repos/o/r/actions/"
        if url == base + f"runs/{current_id}":
            return current
        if url.startswith(base + "runs?per_page=100"):
            return {"workflow_runs": [hist_ok, hist_http, hist_badzip, hist_none, current]}
        if "/workflows/" in url:
            return {"workflow_runs": []}
        if url == base + "runs/10/artifacts?per_page=100":
            return {"artifacts": [dict(art, archive_download_url="https://dl/10")]}
        if url == base + "runs/11/artifacts?per_page=100":
            return _http_error(url, 410)
        if url == base + "runs/12/artifacts?per_page=100":
            return {"artifacts": [dict(art, archive_download_url="https://dl/12")]}
        if url == base + "runs/13/artifacts?per_page=100":
            return {"artifacts": []}
        if url == "https://dl/10":
            return hist_zip
        if url == "https://dl/12":
            return b"not a zip"
        raise AssertionError(url)

    net = FakeNet(route)
    monkeypatch.setattr(mod.urllib.request, "build_opener", net.build_opener)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", str(current_id))
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(_analysis(mod, SHA_C)), encoding="utf-8")
    admission_path = tmp_path / "admission.json"
    admission_path.write_text(json.dumps(_admission(SHA_C)), encoding="utf-8")
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["x", "--current-analysis", str(analysis_path),
                                      "--current-admission", str(admission_path), "--out", str(out)])
    mod.main()

    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["config_schema"] == "missioncontrol.temporal_allocation_policy_config.v1"
    assert [w["window_id"] for w in receipt["windows"]] == ["10", str(current_id)]
    kinds = {w["window_id"]: w["source_kind"] for w in receipt["windows"]}
    assert kinds[str(current_id)] == "CURRENT_EXACT_SHA"
    assert kinds["10"] == "HISTORICAL_ACTION_ARTIFACT"
    errors = {e["run_id"]: e for e in receipt["historical_collection_errors"]}
    assert errors["11"]["error"] == "HTTPError" and errors["11"]["http_code"] == 410
    assert errors["12"]["error"] == "BadZipFile" and errors["12"]["http_code"] is None
    assert "13" not in errors
    assert all(c["headers"]["Authorization"] == "Bearer test-token" for c in net.calls)
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["windows"] == 2
    assert summary["historical_errors"] == 2
    assert summary["promoted_rules"] == 0
    assert set(summary["policies"]) == set(mod.CONFIG["task_classes"])
