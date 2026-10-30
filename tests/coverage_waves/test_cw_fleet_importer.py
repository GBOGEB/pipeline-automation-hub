"""Coverage-wave behavioural tests for mission-control/golden-thread/fleet_importer.py.

No real network access: urllib.request.urlopen is replaced by a fake for every
test (an autouse guard fails any un-faked call). Tokens are only ever the
literal "test-token" set via monkeypatch.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GT_DIR = REPO_ROOT / "mission-control" / "golden-thread"
if str(GT_DIR) not in sys.path:
    sys.path.insert(0, str(GT_DIR))

_spec = importlib.util.spec_from_file_location("cw_fleet_importer", GT_DIR / "fleet_importer.py")
fi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fi)
gt = fi.gt
FIE = fi.FleetImportError
REPO = "GBOGEB/cw-example"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("real network call attempted")

    monkeypatch.setattr(fi.urllib.request, "urlopen", _blocked)


def scope(**overrides):
    value = {
        "schema": fi.SCOPE_SCHEMA,
        "read_only": True,
        "max_items": 3,
        "include_pull_requests": False,
        "sources": [{"repository": REPO, "issue_numbers": [2, 1]}],
        "classification_credit": 0,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    value.update(overrides)
    return value


def raw_issue(number, *, title=None, pull_request=False, **extra):
    raw = {
        "id": 500 + number,
        "node_id": f"N{number}",
        "number": number,
        "title": title if title is not None else f"Issue {number}",
        "state": "open",
        "state_reason": None,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
        "closed_at": None,
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        "url": f"https://api.github.com/repos/{REPO}/issues/{number}",
        "labels": [{"name": "b"}, {"name": "a"}],
        "assignees": [{"login": "z"}, {"login": "y"}],
        "milestone": None,
        "body": "text",
    }
    if pull_request:
        raw["pull_request"] = {"url": "x"}
    raw.update(extra)
    return raw


def snap(number, **kw):
    return fi.normalize_issue(REPO, raw_issue(number, **kw))


@pytest.fixture()
def ledger():
    return gt.seal({"events": []})


def imported(ledger, snapshots, sc=None):
    sc = sc or scope()
    return fi.import_snapshots(ledger, fi.empty_registry(sc), sc, snapshots, recorded_at="2026-09-03T00:00:00Z")


# ---------------------------------------------------------------- normalize_scope


def test_normalize_scope_sorts_dedupes_and_digests():
    sc = scope(
        sources=[
            {"repository": "GBOGEB/zz", "issue_numbers": [3, 3, 1]},
            {"repository": "GBOGEB/aa", "issue_numbers": [2]},
        ],
        include_pull_requests=1,
    )
    out = fi.normalize_scope(sc)
    assert [s["repository"] for s in out["sources"]] == ["GBOGEB/aa", "GBOGEB/zz"]
    assert out["sources"][1]["issue_numbers"] == [1, 3]
    assert out["include_pull_requests"] is True
    body = dict(out)
    assert body.pop("scope_digest") == gt.digest(body)


def test_normalize_scope_classification_false_is_accepted():
    assert fi.normalize_scope(scope(classification_credit=False))["classification_credit"] == 0


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"schema": "nope"}, "fleet import scope schema mismatch"),
        ({"read_only": False}, "fleet import scope must be read_only=true"),
        ({"authority_transfer": None}, "fleet import scope authority_transfer must remain false"),
        ({"classification_credit": 1}, "fleet importer may not grant classification credit"),
        ({"visual_fidelity_credit": 0}, "fleet importer may not grant visual fidelity credit"),
        ({"max_items": 0}, "scope max_items must be between 1 and 100"),
        ({"max_items": 101}, "scope max_items must be between 1 and 100"),
        ({"max_items": "5"}, "scope max_items must be between 1 and 100"),
        ({"sources": []}, "scope sources must be a non-empty list"),
        ({"sources": {"a": 1}}, "scope sources must be a non-empty list"),
        ({"sources": ["GBOGEB/x"]}, "scope source must be an object"),
        ({"sources": [{"repository": "noslash", "issue_numbers": [1]}]}, "scope repository must be owner/repo"),
        ({"sources": [{"repository": "a/b/c", "issue_numbers": [1]}]}, "scope repository must be owner/repo"),
        ({"sources": [{"repository": "a/b", "issue_numbers": []}]}, "scope issue_numbers must be positive integers"),
        ({"sources": [{"repository": "a/b", "issue_numbers": [0]}]}, "scope issue_numbers must be positive integers"),
        ({"sources": [{"repository": "a/b", "issue_numbers": ["1"]}]}, "scope issue_numbers must be positive integers"),
        ({"max_items": 1}, "scope item count exceeds max_items"),
    ],
)
def test_normalize_scope_rejections(overrides, message):
    with pytest.raises(FIE, match="^" + message + "$"):
        fi.normalize_scope(scope(**overrides))


def test_normalize_scope_rejects_non_dict():
    with pytest.raises(FIE, match="schema mismatch"):
        fi.normalize_scope(["x"])


# ---------------------------------------------------------------- normalize_issue


def test_normalize_issue_rejects_non_object():
    with pytest.raises(FIE, match="^GitHub issue payload must be an object$"):
        fi.normalize_issue(REPO, None)


@pytest.mark.parametrize("number", [None, 0, "3"])
def test_normalize_issue_rejects_bad_number(number):
    with pytest.raises(FIE, match="^GitHub issue number invalid$"):
        raw = raw_issue(1)
        raw["number"] = number
        fi.normalize_issue(REPO, raw)


def test_normalize_issue_fields():
    s = fi.normalize_issue(
        REPO,
        raw_issue(
            4,
            title=None,
            labels=[{"name": "b"}, "junk", {"name": None}, {"name": "a"}],
            assignees=[{"login": "z"}, {"nologin": 1}],
            milestone={"number": 9},
            pull_request=True,
            body=None,
        ),
    )
    assert s["source_key"] == REPO + "#4"
    assert s["labels"] == ["a", "b"]
    assert s["assignees"] == ["z"]
    assert s["milestone_number"] == 9
    assert s["is_pull_request"] is True
    assert s["body_sha256"] is None
    body = {k: v for k, v in s.items() if k != "source_snapshot_digest"}
    assert s["source_snapshot_digest"] == gt.digest(body)


def test_normalize_issue_defaults_and_body_digest():
    s = fi.normalize_issue(REPO, {"number": 5, "title": "", "body": "hi", "labels": None})
    assert s["title"] == ""
    assert s["labels"] == [] and s["assignees"] == []
    assert s["milestone_number"] is None
    assert s["is_pull_request"] is False
    assert s["body_sha256"] == fi._digest_bytes(b"hi")


def test_import_intent_shape():
    s = snap(1)
    intent = fi.import_intent(s)
    assert intent["target"] == REPO + "#1"
    assert intent["payload_digest"] == intent["source_state_digest"] == s["source_snapshot_digest"]
    assert intent["action"] == "GITHUB_ISSUE_IMPORT"


# ---------------------------------------------------------------- import events


def test_first_import_event_falls_back_to_api_url_and_recorded_time(ledger):
    s = fi.normalize_issue(REPO, {"number": 1, "url": "https://api.example/1"})
    sealed, registry, receipt = imported(ledger, [s])
    event = sealed["events"][0]
    assert event["event_type"] == "BOOTSTRAP_RECONSTRUCTED"
    assert event["occurred_at"] == "2026-09-03T00:00:00Z"
    assert event["evidence_refs"] == ["https://api.example/1"]
    assert event["reconstruction_method"] == "live_github_current_state_import"
    assert receipt["before_head_event_digest"] == gt.GENESIS
    assert receipt["after_head_event_digest"] == sealed["head_event_digest"]
    assert event["event_id"] == "GTI-" + receipt["added"][0]["transaction_id"].split(":", 1)[1][:20].upper()


def test_event_ref_falls_back_to_source_key_and_created_at(ledger):
    s = fi.normalize_issue(REPO, {"number": 2, "created_at": "2026-08-01T00:00:00Z"})
    sealed, _, _ = imported(ledger, [s])
    assert sealed["events"][0]["evidence_refs"] == [REPO + "#2"]
    assert sealed["events"][0]["occurred_at"] == "2026-08-01T00:00:00Z"


def test_successor_import_is_observed_event(ledger):
    sealed, registry, _ = imported(ledger, [snap(1)])
    sealed2, registry2, receipt = fi.import_snapshots(
        sealed, registry, scope(), [snap(1, title="changed")], recorded_at="2026-09-04T00:00:00Z"
    )
    assert sealed2["events"][-1]["event_type"] == "OBSERVED"
    assert "reconstruction_method" not in sealed2["events"][-1]
    first_tx = registry["sources"][REPO + "#1"]["current_transaction_id"]
    assert receipt["added"][0]["parent_transaction_id"] == first_tx
    assert receipt["before_head_event_digest"] == sealed["head_event_digest"]
    v = fi.verify_registry(registry2, scope())
    assert (v["source_count"], v["transaction_count"], v["lineage_edge_count"]) == (1, 2, 1)


def test_include_pull_requests_allows_pr_snapshot(ledger):
    sc = scope(include_pull_requests=True)
    _, _, receipt = imported(ledger, [snap(1, pull_request=True)], sc)
    assert receipt["added_event_count"] == 1


def test_import_rejects_too_many_snapshots(ledger):
    sc = scope(max_items=2)
    with pytest.raises(FIE, match="^incoming snapshot count exceeds scope max_items$"):
        imported(ledger, [snap(1), snap(2), snap(1)], sc)


def test_import_rejects_schema_mismatch(ledger):
    s = snap(1)
    s["schema"] = "other"
    with pytest.raises(FIE, match="^incoming snapshot schema mismatch$"):
        imported(ledger, [s])


def test_import_rejects_snapshot_digest_mismatch(ledger):
    s = snap(1)
    s["title"] = "tampered"
    with pytest.raises(FIE, match="^incoming source snapshot digest mismatch$"):
        imported(ledger, [s])


def test_import_rejects_changed_obligation_identity(ledger):
    sealed, registry, _ = imported(ledger, [snap(1)])
    reg = copy.deepcopy(registry)
    src = reg["sources"][REPO + "#1"]
    old = src["obligation_id"]
    fake = "sha256:" + "9" * 64
    src["obligation_id"] = fake
    for row in src["history"]:
        row["obligation_id"] = fake
    reg["obligation_heads"][fake] = reg["obligation_heads"].pop(old)
    reg = fi._seal_registry(reg)
    assert fi.verify_registry(reg, scope())["status"] == "PASS"
    with pytest.raises(FIE, match="^source obligation identity changed unexpectedly$"):
        fi.import_snapshots(sealed, reg, scope(), [snap(1, title="new")], recorded_at="2026-09-04T00:00:00Z")


# ---------------------------------------------------------------- verify_registry


@pytest.fixture()
def populated(ledger):
    sealed, registry, _ = imported(ledger, [snap(1), snap(2)])
    sealed, registry, _ = fi.import_snapshots(
        sealed, registry, scope(), [snap(1, title="v2")], recorded_at="2026-09-04T00:00:00Z"
    )
    return registry


def test_verify_registry_rejects_unsealed_tamper(populated):
    reg = copy.deepcopy(populated)
    reg["sources"][REPO + "#2"]["number"] = 99
    with pytest.raises(FIE, match="^fleet import registry digest mismatch$"):
        fi.verify_registry(reg, scope())


@pytest.mark.parametrize(
    "key, value, message",
    [
        ("schema", "x", "fleet import registry schema mismatch"),
        ("scope_digest", "sha256:0", "fleet import registry scope mismatch"),
        ("authority_transfer", True, "fleet import registry authority_transfer must remain false"),
        ("source_write_count", 2, "fleet importer must remain read-only"),
        ("classification_credit", 1, "fleet importer may not grant classification_credit"),
        ("engineering_credit", 1, "fleet importer may not grant engineering_credit"),
        ("release_credit", True, "fleet importer may not grant release_credit"),
        ("visual_fidelity_credit", None, "fleet importer may not grant visual fidelity credit"),
        ("sources", [], "fleet import registry mappings missing"),
        ("obligation_heads", None, "fleet import registry mappings missing"),
    ],
)
def test_verify_registry_top_level_rejections(populated, key, value, message):
    reg = copy.deepcopy(populated)
    reg[key] = value
    with pytest.raises(FIE, match="^" + message + "$"):
        fi.verify_registry(fi._seal_registry(reg), scope())


def _source_case(populated, mutate):
    reg = copy.deepcopy(populated)
    mutate(reg)
    return fi._seal_registry(reg)


def _src(reg, n=1):
    return reg["sources"][REPO + "#" + str(n)]


def _dup_row(reg):
    _src(reg, 2)["history"].append(copy.deepcopy(_src(reg, 2)["history"][0]))


def _swap_head(reg):
    o1 = _src(reg, 1)["obligation_id"]
    reg["obligation_heads"][o1] = _src(reg, 1)["history"][0]["transaction_id"]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda r: _src(r).__setitem__("source_key", "other#1"), "fleet source registry key mismatch"),
        (lambda r: _src(r).__setitem__("history", []), "fleet source history missing"),
        (lambda r: _src(r).__setitem__("history", None), "fleet source history missing"),
        (_dup_row, "duplicate fleet import transaction/event identity"),
        (lambda r: _src(r)["history"][1].__setitem__("parent_transaction_id", None), "fleet import successor chain mismatch"),
        (lambda r: _src(r)["history"][0].__setitem__("obligation_id", "x"), "fleet import obligation mismatch"),
        (lambda r: _src(r).__setitem__("current_transaction_id", "x"), "fleet source current transaction mismatch"),
        (lambda r: _src(r).__setitem__("current_snapshot_digest", "x"), "fleet source current snapshot mismatch"),
        (_swap_head, "fleet obligation head mismatch"),
    ],
)
def test_verify_registry_source_rejections(populated, mutate, message):
    with pytest.raises(FIE, match="^" + message + "$"):
        fi.verify_registry(_source_case(populated, mutate), scope())


# ---------------------------------------------------------------- GitHub reader (faked HTTP)


class _FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _install_fake(monkeypatch, issues):
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append({"url": request.full_url, "headers": dict(request.header_items()), "timeout": timeout})
        number = int(request.full_url.rsplit("/", 1)[1])
        return _FakeResponse(issues[number])

    monkeypatch.setattr(fi.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_reader_sends_bearer_token_and_parses_json(monkeypatch):
    calls = _install_fake(monkeypatch, {7: {"number": 7, "title": "t"}})
    out = fi.GitHubIssueReader("test-token").get_issue(REPO, 7)
    assert out == {"number": 7, "title": "t"}
    assert calls[0]["url"] == "https://api.github.com/repos/" + REPO + "/issues/7"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0]["headers"]["X-github-api-version"] == "2022-11-28"
    assert calls[0]["timeout"] == 30


def test_reader_without_token_omits_authorization(monkeypatch):
    calls = _install_fake(monkeypatch, {7: {"number": 7}})
    fi.GitHubIssueReader(None).get_issue(REPO, 7)
    assert "Authorization" not in calls[0]["headers"]


def test_reader_http_error_is_wrapped(monkeypatch):
    def fail(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(b'{"message":"Not Found"}'))

    monkeypatch.setattr(fi.urllib.request, "urlopen", fail)
    with pytest.raises(FIE) as info:
        fi.GitHubIssueReader("test-token").get_issue(REPO, 3)
    assert str(info.value) == 'GitHub GET ' + REPO + '#3 failed 404: {"message":"Not Found"}'
    assert isinstance(info.value.__cause__, urllib.error.HTTPError)


def test_fetch_scope_returns_sorted_snapshots(monkeypatch):
    calls = _install_fake(monkeypatch, {1: raw_issue(1), 2: raw_issue(2)})
    out = fi.fetch_scope(scope(), "test-token")
    assert [s["source_key"] for s in out] == [REPO + "#1", REPO + "#2"]
    assert out[0] == snap(1)
    assert len(calls) == 2


def test_fetch_scope_rejects_pull_request(monkeypatch):
    _install_fake(monkeypatch, {1: raw_issue(1, pull_request=True), 2: raw_issue(2)})
    with pytest.raises(FIE, match="^scope source resolved to pull request: " + REPO + "#1$"):
        fi.fetch_scope(scope())


def test_fetch_scope_allows_pull_request_when_enabled(monkeypatch):
    _install_fake(monkeypatch, {1: raw_issue(1, pull_request=True), 2: raw_issue(2)})
    out = fi.fetch_scope(scope(include_pull_requests=True))
    assert out[0]["is_pull_request"] is True


# ---------------------------------------------------------------- CLI


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_main_fetch_uses_default_token_env(tmp_path, monkeypatch):
    calls = _install_fake(monkeypatch, {1: raw_issue(1), 2: raw_issue(2)})
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    sp = _write(tmp_path / "scope.json", scope())
    out = tmp_path / "snap.json"
    assert fi.main(["fetch", str(sp), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["scope"] == fi.normalize_scope(scope())
    assert [s["number"] for s in data["snapshots"]] == [1, 2]
    assert all(c["headers"]["Authorization"] == "Bearer test-token" for c in calls)


def test_main_fetch_missing_token_is_anonymous(tmp_path, monkeypatch):
    calls = _install_fake(monkeypatch, {1: raw_issue(1), 2: raw_issue(2)})
    monkeypatch.delenv("CW_FLEET_TOKEN", raising=False)
    sp = _write(tmp_path / "scope.json", scope())
    out = tmp_path / "snap.json"
    monkeypatch.setattr(
        sys, "argv", ["fleet_importer.py", "fetch", str(sp), "--token-env", "CW_FLEET_TOKEN", "--out", str(out)]
    )
    assert fi.main() == 0
    assert all("Authorization" not in c["headers"] for c in calls)


def test_main_fetch_http_error_returns_2(tmp_path, monkeypatch, capsys):
    def fail(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"rate limited"))

    monkeypatch.setattr(fi.urllib.request, "urlopen", fail)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    sp = _write(tmp_path / "scope.json", scope())
    out = tmp_path / "snap.json"
    assert fi.main(["fetch", str(sp), "--out", str(out)]) == 2
    assert capsys.readouterr().err.strip() == "FAIL: GitHub GET " + REPO + "#1 failed 403: rate limited"
    assert not out.exists()


def test_main_new_registry(tmp_path):
    sp = _write(tmp_path / "scope.json", scope())
    out = tmp_path / "reg.json"
    assert fi.main(["new-registry", str(sp), "--out", str(out)]) == 0
    reg = json.loads(out.read_text(encoding="utf-8"))
    assert reg == fi.empty_registry(scope())
    assert fi.verify_registry(reg, scope())["source_count"] == 0


def test_main_invalid_scope_returns_2(tmp_path, capsys):
    sp = _write(tmp_path / "scope.json", scope(read_only=False))
    assert fi.main(["new-registry", str(sp), "--out", str(tmp_path / "r.json")]) == 2
    assert capsys.readouterr().err.strip() == "FAIL: fleet import scope must be read_only=true"


def test_main_non_object_scope_returns_2(tmp_path, capsys):
    sp = _write(tmp_path / "scope.json", [1])
    assert fi.main(["new-registry", str(sp), "--out", str(tmp_path / "r.json")]) == 2
    assert "top-level JSON must be an object" in capsys.readouterr().err


def test_main_missing_scope_file_returns_2(tmp_path, capsys):
    assert fi.main(["new-registry", str(tmp_path / "absent.json"), "--out", str(tmp_path / "r.json")]) == 2
    assert capsys.readouterr().err.startswith("FAIL: ")


def test_dump_to_stdout(capsys):
    fi._dump({"b": 1, "a": "é"})
    out = capsys.readouterr().out
    assert out.index('"a"') < out.index('"b"')
    assert "é" in out
