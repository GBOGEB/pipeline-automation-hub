"""Behavioural tests for mission-control/golden-thread/rendition_family.py.

Existing golden-thread tests cover the zero-delta happy path and HTML escaping. These cover
the per-format renderers, extraction errors, verification failure branches, the on-disk
family (write/verify_directory) and the CLI.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GT_DIR = ROOT / "mission-control" / "golden-thread"
MOD_PATH = GT_DIR / "rendition_family.py"

if str(GT_DIR) not in sys.path:
    sys.path.insert(0, str(GT_DIR))

_spec = importlib.util.spec_from_file_location("cw_rendition_family_mod", MOD_PATH)
rf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rf)
gt = rf.gt

STEM = "GOLDEN_THREAD_TRUTH"
MANIFEST = STEM + "_RENDITION_MANIFEST.json"


def truth(**extra):
    doc = {
        "schema": "missioncontrol.golden_thread_projection.v1",
        "boundary": "GT-0003",
        "authority_transfer": False,
        "metrics": {"event_count": 3, "occurrence_count": 2, "root_count": 1,
                    "lineage_edge_count": 0, "unknown_needs_reader_count": 4},
        "events_applied": ["GT-0001", "GT-0002", "GT-0003"],
        "note": "a & b <c> é",
    }
    doc.update(extra)
    return doc


# --- renderers -------------------------------------------------------------------------------

def test_json_and_yaml_are_canonical_json_with_newline():
    t = truth()
    expected = json.dumps(t, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    assert rf.render_json(t) == expected
    assert rf.render_yaml(t) == expected


def test_markdown_carries_digest_and_round_trips():
    t = truth()
    md = rf.render_markdown(t)
    assert md.startswith("# Golden Thread Canonical Truth Rendition\n\n")
    assert "Canonical truth digest: `" + gt.digest(t) + "`" in md
    assert rf.extract_rendition("markdown", md) == t


def test_html_payload_is_script_safe_and_round_trips():
    t = truth()
    page = rf.render_html(t)
    payload = rf.HTML_RE.search(page).group("payload")
    assert "<" not in payload and ">" not in payload and "&" not in payload
    assert "\\u0026" in payload and "\\u003c" in payload and "\\u003e" in payload
    assert rf.extract_rendition("html", page) == t
    assert '<meta name="golden-thread-truth-digest" content="' + gt.digest(t) + '">' in page


def test_html_cards_show_metric_values_and_boundary():
    page = rf.render_html(truth())
    assert "<small>Events</small><strong>3</strong>" in page
    assert "<small>Unknown-reader items</small><strong>4</strong>" in page
    assert "<b>Boundary:</b> GT-0003" in page
    assert "<b>Authority transfer:</b> False" in page


def test_html_without_selection_states_no_cutoff_and_lists_applied_events():
    page = rf.render_html(truth())
    assert "No separate recorded-knowledge cutoff is asserted." in page
    assert "Known at:" not in page
    for ev in ("GT-0001", "GT-0002", "GT-0003"):
        assert "<li><code>" + ev + "</code></li>" in page
    assert "more in source payload" not in page


def test_html_non_dict_metrics_and_selection_fall_back_to_unknown():
    t = truth(metrics=[1, 2], temporal_selection="not-a-dict", events_applied="nope")
    page = rf.render_html(t)
    assert page.count("<strong>UNKNOWN</strong>") == 5
    assert "No separate recorded-knowledge cutoff is asserted." in page
    assert "<ul></ul>" in page


def test_html_selection_uses_selected_ids_and_unbounded_occurrence():
    sel = {"known_at_utc": "2026-09-17T00:00:00Z", "occurred_by_utc": None,
           "full_ledger_verified": True, "chain_prefix": "sha256:abc",
           "selected_event_ids": ["SEL-1"]}
    page = rf.render_html(truth(temporal_selection=sel))
    assert "<b>Known at:</b> 2026-09-17T00:00:00Z" in page
    assert "<b>Occurred by:</b> unbounded" in page
    assert "<b>Complete source chain verified:</b> True" in page
    assert "<b>Selected chain prefix:</b> sha256:abc" in page
    assert "<li><code>SEL-1</code></li>" in page
    assert "<li><code>GT-0001</code></li>" not in page


def test_html_selection_without_id_list_uses_events_applied_and_defaults():
    sel = {"occurred_by_utc": "2026-09-01T00:00:00Z", "selected_event_ids": "GT-0001"}
    page = rf.render_html(truth(temporal_selection=sel))
    assert "<b>Known at:</b> UNKNOWN" in page
    assert "<b>Occurred by:</b> 2026-09-01T00:00:00Z" in page
    assert "<b>Selected chain prefix:</b> UNKNOWN" in page
    assert "<li><code>GT-0003</code></li>" in page


def test_html_samples_first_32_events_and_counts_rest():
    events = ["E%03d" % i for i in range(35)]
    page = rf.render_html(truth(events_applied=events))
    assert "<li><code>E031</code></li>" in page
    assert "<li><code>E032</code></li>" not in page
    assert "<li>… 3 more in source payload</li>" in page
    assert rf.extract_rendition("html", page)["events_applied"] == events


def test_html_missing_boundary_and_authority_is_unknown():
    page = rf.render_html({"events_applied": []})
    assert "<b>Boundary:</b> UNKNOWN" in page
    assert "<b>Authority transfer:</b> UNKNOWN" in page


def test_render_family_shape():
    t = truth()
    fam = rf.render_family(t)
    d = gt.digest(t)
    assert fam["schema"] == rf.RENDITION_SCHEMA
    assert fam["canonical_truth_digest"] == d
    assert fam["authority_transfer"] is False
    assert {k: (v["extension"], v["mime"]) for k, v in fam["renditions"].items()} == {
        "json": (".json", "application/json"), "yaml": (".yaml", "application/yaml"),
        "markdown": (".md", "text/markdown"), "html": (".html", "text/html"),
    }
    assert all(v["truth_digest"] == d for v in fam["renditions"].values())


# --- extraction errors -----------------------------------------------------------------------

def test_extract_markdown_without_payload_raises():
    with pytest.raises(gt.GoldenThreadError, match="^markdown rendition lacks canonical JSON payload$"):
        rf.extract_rendition("markdown", "# title only\n")


def test_extract_html_without_script_raises():
    with pytest.raises(gt.GoldenThreadError, match="^HTML rendition lacks canonical truth script$"):
        rf.extract_rendition("html", "<html></html>")


def test_extract_unsupported_kind_raises():
    with pytest.raises(gt.GoldenThreadError, match="^unsupported rendition kind: pdf$"):
        rf.extract_rendition("pdf", "{}")


def test_extract_invalid_json_raises_value_error():
    with pytest.raises(ValueError):
        rf.extract_rendition("json", "{not json")


# --- verify_family ---------------------------------------------------------------------------

def test_verify_family_pass_reports_all_digests():
    t = truth()
    res = rf.verify_family(t, rf.render_family(t))
    d = gt.digest(t)
    assert res["status"] == "PASS"
    assert res["schema"] == "missioncontrol.golden_thread_rendition_verification.v1"
    assert res["rendition_count"] == 4
    assert res["authority_transfer"] is False
    for row in res["results"].values():
        assert row == {"status": "PASS", "expected_truth_digest": d,
                       "observed_truth_digest": d, "declared_truth_digest": d}


@pytest.mark.parametrize("key,value", [
    ("schema", "other.schema"),
    ("canonical_truth_digest", "sha256:0"),
    ("authority_transfer", True),
])
def test_verify_family_header_mismatch_fails_even_if_renditions_pass(key, value):
    t = truth()
    fam = rf.render_family(t)
    fam[key] = value
    res = rf.verify_family(t, fam)
    assert res["status"] == "FAIL"
    assert all(r["status"] == "PASS" for r in res["results"].values())


def test_verify_family_missing_and_non_dict_renditions():
    t = truth()
    fam = rf.render_family(t)
    del fam["renditions"]["yaml"]
    fam["renditions"]["markdown"] = "not a dict"
    res = rf.verify_family(t, fam)
    assert res["status"] == "FAIL"
    assert res["results"]["yaml"] == {"status": "FAIL", "reason": "missing rendition"}
    assert res["results"]["markdown"] == {"status": "FAIL", "reason": "missing rendition"}
    assert res["results"]["json"]["status"] == "PASS"
    assert res["rendition_count"] == 4


def test_verify_family_without_renditions_key_fails_all():
    res = rf.verify_family(truth(), {"schema": rf.RENDITION_SCHEMA})
    assert res["status"] == "FAIL"
    assert set(res["results"]) == {"json", "yaml", "markdown", "html"}
    assert all(r["reason"] == "missing rendition" for r in res["results"].values())


def test_verify_family_extraction_error_records_reason():
    t = truth()
    fam = rf.render_family(t)
    fam["renditions"]["html"]["content"] = "<p>stripped</p>"
    fam["renditions"]["json"]["content"] = "{broken"
    res = rf.verify_family(t, fam)
    assert res["status"] == "FAIL"
    assert res["results"]["html"] == {"status": "FAIL", "reason": "HTML rendition lacks canonical truth script"}
    assert res["results"]["json"]["status"] == "FAIL"
    assert "reason" in res["results"]["json"]


def test_verify_family_declared_digest_mismatch_fails_that_kind():
    t = truth()
    fam = rf.render_family(t)
    fam["renditions"]["markdown"]["truth_digest"] = "sha256:forged"
    res = rf.verify_family(t, fam)
    row = res["results"]["markdown"]
    assert res["status"] == "FAIL"
    assert row["status"] == "FAIL"
    assert row["observed_truth_digest"] == row["expected_truth_digest"] == gt.digest(t)
    assert row["declared_truth_digest"] == "sha256:forged"


# --- write_family / verify_directory ---------------------------------------------------------

def test_write_family_writes_files_and_manifest(tmp_path):
    t = truth()
    out = tmp_path / "nested" / "out"
    fam, manifest = rf.write_family(t, out, stem="X")
    names = sorted(p.name for p in out.iterdir())
    assert names == ["X.html", "X.json", "X.md", "X.yaml", "X_RENDITION_MANIFEST.json"]
    on_disk = json.loads((out / "X_RENDITION_MANIFEST.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert manifest["canonical_truth_digest"] == gt.digest(t)
    assert manifest["authority_transfer"] is False
    for kind, meta in manifest["files"].items():
        content = (out / meta["path"]).read_text(encoding="utf-8")
        assert content == fam["renditions"][kind]["content"]
        assert meta["content_sha256"] == gt.digest(content)
        assert meta["truth_digest"] == gt.digest(t)


def test_verify_directory_round_trip_passes(tmp_path):
    t = truth()
    rf.write_family(t, tmp_path)
    res = rf.verify_directory(t, tmp_path)
    assert res["status"] == "PASS"
    assert res["rendition_count"] == 4


def test_verify_directory_detects_content_tamper(tmp_path):
    t = truth()
    rf.write_family(t, tmp_path)
    p = tmp_path / (STEM + ".md")
    p.write_text(p.read_text(encoding="utf-8") + "extra\n", encoding="utf-8")
    with pytest.raises(gt.GoldenThreadError, match="^rendition content digest mismatch: markdown$"):
        rf.verify_directory(t, tmp_path)


def test_verify_directory_against_other_truth_fails(tmp_path):
    rf.write_family(truth(), tmp_path)
    res = rf.verify_directory(truth(boundary="GT-9999"), tmp_path)
    assert res["status"] == "FAIL"
    assert all(r["status"] == "FAIL" for r in res["results"].values())


def test_verify_directory_custom_manifest_with_missing_kinds(tmp_path):
    t = truth()
    _, manifest = rf.write_family(t, tmp_path, stem="S")
    del manifest["files"]["html"]
    (tmp_path / "partial.json").write_text(json.dumps(manifest), encoding="utf-8")
    res = rf.verify_directory(t, tmp_path, manifest_name="partial.json")
    assert res["status"] == "FAIL"
    assert res["results"]["html"] == {"status": "FAIL", "reason": "missing rendition"}
    assert res["results"]["json"]["status"] == "PASS"


# --- CLI -------------------------------------------------------------------------------------

def _truth_file(tmp_path, doc=None, name="truth.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc if doc is not None else truth()), encoding="utf-8")
    return p


def test_main_render_then_verify(tmp_path, capsys):
    tf = _truth_file(tmp_path)
    out = tmp_path / "out"
    assert rf.main(["render", str(tf), str(out), "--stem", "T"]) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["status"] == "PASS"
    assert res["manifest"]["files"]["json"]["path"] == "T.json"
    assert rf.main(["verify", str(tf), str(out), "--manifest", "T_RENDITION_MANIFEST.json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_main_verify_mismatch_returns_2(tmp_path, capsys):
    out = tmp_path / "out"
    assert rf.main(["render", str(_truth_file(tmp_path)), str(out)]) == 0
    capsys.readouterr()
    other = _truth_file(tmp_path, truth(boundary="GT-0099"), "other.json")
    assert rf.main(["verify", str(other), str(out)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"


def test_main_missing_truth_file_reports_fail(tmp_path, capsys):
    rc = rf.main(["verify", str(tmp_path / "absent.json"), str(tmp_path)])
    assert rc == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("FAIL: ")


def test_main_invalid_truth_json_reports_fail(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert rf.main(["render", str(bad), str(tmp_path / "o")]) == 2
    assert capsys.readouterr().err.startswith("FAIL: ")
    assert not (tmp_path / "o").exists()


def test_main_tampered_directory_reports_digest_mismatch(tmp_path, capsys):
    tf = _truth_file(tmp_path)
    out = tmp_path / "out"
    rf.main(["render", str(tf), str(out)])
    capsys.readouterr()
    (out / (STEM + ".json")).write_text("{}\n", encoding="utf-8")
    assert rf.main(["verify", str(tf), str(out)]) == 2
    assert capsys.readouterr().err.strip() == "FAIL: rendition content digest mismatch: json"


def test_main_requires_subcommand(capsys):
    with pytest.raises(SystemExit) as exc:
        rf.main([])
    assert exc.value.code == 2


def test_script_entrypoint_raises_systemexit_with_status(tmp_path, monkeypatch, capsys):
    tf = _truth_file(tmp_path)
    monkeypatch.setattr(sys, "argv", ["rendition_family.py", "render", str(tf), str(tmp_path / "o")])
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    with pytest.raises(SystemExit) as exc:
        exec(code, {"__name__": "__main__", "__file__": str(tmp_path / "cw_rf_main.py")})
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
