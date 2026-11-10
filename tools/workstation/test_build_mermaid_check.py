"""Tests for build_mermaid_check.py. Run: python -m pytest -q test_build_mermaid_check.py"""
import json
import re
import socket

import pytest

import build_mermaid_check as bmc

GANTT_W = "gantt\n    dateFormat YYYY-MM-DD\n    axisFormat w%W (%d %b)\n    A :a, 2026-11-09, 3d\n"


def test_backtick_and_tilde_fences_with_line_numbers():
    md = "# t\n\n```mermaid\nflowchart LR\n  a-->b\n```\n\ntext\n~~~ mermaid\nsequenceDiagram\n  A->>B: hi\n~~~\n"
    ds = bmc.extract_markdown(md, "x.md")
    assert [d.line for d in ds] == [3, 9]
    assert ds[0].text == "flowchart LR\n  a-->b\n"
    assert bmc.diagram_type(ds[1].text) == "sequenceDiagram"


def test_other_fences_are_skipped_whole():
    md = "````markdown\n```mermaid\nflowchart LR\n```\n````\n\n```python\nprint(1)\n```\n"
    assert bmc.extract_markdown(md, "x.md") == []


def test_longer_closing_fence_and_attributes():
    md = "```mermaid {init: x}\ngraph TD\n````\n"
    ds = bmc.extract_markdown(md, "x.md")
    assert len(ds) == 1 and ds[0].text == "graph TD\n" and not ds[0].lint


def test_indented_fence_is_dedented():
    md = "  ```mermaid\n    graph TD\n    a-->b\n  ```\n"
    assert bmc.extract_markdown(md, "x.md")[0].text == "  graph TD\n  a-->b\n"


def test_unclosed_fence_is_linted():
    ds = bmc.extract_markdown("```mermaid\ngraph TD\n", "x.md")
    assert len(ds) == 1 and "never closed" in ds[0].lint[0]


def test_diagram_type_skips_front_matter_and_directives():
    text = "---\ntitle: T\n---\n%%{init: {'theme':'base'}}%%\n%% note\ngantt\n"
    assert bmc.diagram_type(text) == "gantt"
    assert bmc.diagram_type("\n\n") == "empty"


def test_percent_w_lint_only_in_gantt():
    assert bmc.lint(GANTT_W, "gantt") and "use %V" in bmc.lint(GANTT_W, "gantt")[0]
    assert bmc.lint(GANTT_W.replace("%W", "%V"), "gantt") == []
    assert bmc.lint("flowchart LR\n%% axisFormat %W\n", "flowchart") == []


def test_iso_week_variant_follows_flagged_gantt(tmp_path):
    f = tmp_path / "plan.md"
    f.write_text("```mermaid\n" + GANTT_W + "```\n```mermaid\ngraph TD\n```\n", encoding="utf-8")
    ds = bmc.with_iso_week_variants(bmc.collect([f]))
    assert [d.variant for d in ds] == ["", "axisFormat %W -> %V", ""]
    assert "w%V" in ds[1].text and "%W" not in ds[1].text and ds[1].lint == []


def test_collect_folder_mmd_and_skip_dirs(tmp_path):
    (tmp_path / "b.mmd").write_text("timeline\n  title T\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("```mermaid\ngraph TD\n```\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("```mermaid\ngraph TD\n```\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "c.md").write_text("```mermaid\ngraph TD\n```\n", encoding="utf-8")
    ds = bmc.collect([tmp_path])
    assert [(d.source.rsplit("/", 1)[-1], d.line, d.dtype) for d in ds] == [("a.md", 1, "graph"), ("b.mmd", 1, "timeline")]


def test_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        bmc.collect([tmp_path / "nope.md"])


def test_page_escapes_script_breakouts():
    d = bmc.Diagram(source="x.md", line=1, text='graph TD\n  a["</script><script>alert(1)</script>"]\n', dtype="graph")
    page = bmc.build_page([d])
    assert page.count("</script>") == 2  # the CDN tag and the page script only
    payload = re.search(r"const CASES = (.*);\n", page).group(1)
    assert json.loads(payload)[0]["text"] == d.text


def test_render_ids_are_namespaced():
    # Regression (10 Nov, Edge): render ids 'm0', 'm1', ... collided with Gantt task ids m1..m4 in the B1
    # handover, so the flowcharts failed with "Cannot read properties of null (reading 'getBoundingClientRect')".
    page = bmc.build_page([bmc.Diagram(source="x.md", line=1, text="graph TD\n", dtype="graph")])
    assert "mermaid.render(NS + i" in page and "'mmdcheck-'" in page
    assert "mermaid.render('m' + i" not in page


def test_version_must_be_exact():
    with pytest.raises(ValueError):
        bmc.build_page([], "11")
    with pytest.raises(ValueError):
        bmc.build_page([], '11.4.1"></script>')


def test_default_input_is_the_wddd_doc(tmp_path):
    out = tmp_path / "page.html"
    assert bmc.DEFAULT_INPUT.name == "WDDD_WEEK_CODES.md"
    assert bmc.main(["-o", str(out)]) == 0
    cases = json.loads(re.search(r"const CASES = (.*);\n", out.read_text(encoding="utf-8")).group(1))
    assert cases and all(not c["lint"] for c in cases)  # the owner doc already uses %V


def test_strict_exit_code(tmp_path):
    f = tmp_path / "g.md"
    f.write_text("```mermaid\n" + GANTT_W + "```\n", encoding="utf-8")
    assert bmc.main([str(f), "-o", str(tmp_path / "p.html")]) == 0
    assert bmc.main([str(f), "-o", str(tmp_path / "p.html"), "--strict"]) == 1
    empty = tmp_path / "none.md"
    empty.write_text("no diagrams\n", encoding="utf-8")
    assert bmc.main([str(empty), "-o", str(tmp_path / "p.html")]) == 1


def test_server_refuses_a_port_in_use():
    holder = bmc._ExclusiveServer(("127.0.0.1", 0), bmc.http.server.SimpleHTTPRequestHandler)
    port = holder.server_address[1]
    try:
        with pytest.raises(OSError):
            bmc._ExclusiveServer(("127.0.0.1", port), bmc.http.server.SimpleHTTPRequestHandler)
    finally:
        holder.server_close()
