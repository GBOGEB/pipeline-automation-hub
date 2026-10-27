"""Behavioural tests for mission-control/qps-triage-ultra/site/scripts/validate_site.py.

The module is a top-level script: every check runs at import and paths derive from
``__file__``. Each test builds a synthetic repo layout in tmp_path, then executes the
real source file (so coverage attributes to it) with ``__file__`` re-pointed into
tmp_path and ``sys.argv`` monkeypatched.
"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIAGE_REAL = REPO_ROOT / "mission-control" / "qps-triage-ultra"
MOD_PATH = TRIAGE_REAL / "site" / "scripts" / "validate_site.py"

SHA = "0123456789abcdef0123456789abcdef01234567"
PROVIDER_SHA = "fedcba9876543210fedcba9876543210fedcba98"
GATES = ["J1_SOURCE", "J2_GENERATE", "J3_STRUCTURE", "J4_VISUAL", "J5_IDENTITY", "J6_REPEAT"]
CSS_MARKERS = ["qps-state-pass", "qps-state-partial", "qps-state-blocked", "qps-state-held",
               "qps-state-control", "prefers-reduced-motion", "@media print"]
HEADINGS = ["Fleet", "Topology", "Crew", "Execution", "REX", "Historian", "Evidence economics", "PCA / BT"]

_counter = [0]


def _run(fake_file, argv, monkeypatch, capsys):
    """Execute validate_site.py with __file__ = fake_file; return (exit_code, module, stdout)."""
    _counter[0] += 1
    spec = importlib.util.spec_from_file_location("cw_validate_site_mod_%d" % _counter[0], MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(fake_file)
    monkeypatch.setattr(sys, "argv", ["validate_site.py"] + argv)
    code = 0
    try:
        spec.loader.exec_module(mod)
    except SystemExit as exc:
        code = exc.code
    return code, mod, capsys.readouterr().out


def _html(sha=SHA, extra=""):
    return (
        '<html data-qps-ui="1.2" data-release-id="r1" data-source-sha="%s" '
        'data-schema-version="1" data-evidence-state="PASS">%s</html>' % (sha, extra)
    )


def _page(provider_sha=PROVIDER_SHA, figure_ids=("f1", "f2"), extra=""):
    figs = "".join('<div data-figure-id="%s"></div>' % f for f in figure_ids)
    return '<main data-ggmath-provider-sha="%s">%s<script src="assets/js/plotly.js"></script>%s</main>' % (
        provider_sha, figs, extra)


def build(tmp, *, real_contracts=False, browserslist=None, skip=(), html=None, page=None, figures=None):
    repo = tmp / "repo"
    triage = repo / "mission-control" / "qps-triage-ultra"
    site = triage / "site"
    web = triage / "web"
    for d in (site / "scripts", site / "_data", site / "assets" / "css", site / "assets" / "diagrams", web,
              repo / "app" / "lib", repo / "app" / "app" / "qps-ui-contract"):
        d.mkdir(parents=True, exist_ok=True)

    def put(path, text):
        if path.name not in skip:
            path.write_text(text, encoding="utf-8")

    if real_contracts:
        for rel in ("web/QPS_UI_TOKENS_v1.2.json", "web/QPS_WEB_GATE_REGISTRY_v1.json",
                    "web/QPS_BROWSER_SUPPORT_v1.2.md", "site/index.md", "site/assets/css/qps-ui-1.2.css",
                    "site/assets/diagrams/qps-web-architecture.mmd",
                    "site/assets/diagrams/qps-web-architecture.svg",
                    "site/_data/ggmath_bridge_figures.json"):
            shutil.copyfile(TRIAGE_REAL / rel, triage / rel)
    else:
        put(web / "QPS_UI_TOKENS_v1.2.json",
            json.dumps({"schema": "qps.ui.tokens.v1.2", "principles": {"meaning_not_color_alone": True}}))
        put(web / "QPS_WEB_GATE_REGISTRY_v1.json", json.dumps({"gates": [{"id": g} for g in GATES]}))
        put(web / "QPS_BROWSER_SUPPORT_v1.2.md", "# support\n")
        put(site / "assets" / "css" / "qps-ui-1.2.css", "\n".join(CSS_MARKERS))
        put(site / "index.md", "\n".join("## " + h for h in HEADINGS) + "\n![a](qps-web-architecture.svg)\n")
        put(site / "assets" / "diagrams" / "qps-web-architecture.mmd", "graph TD\n")
        put(site / "assets" / "diagrams" / "qps-web-architecture.svg", "<svg/>")
        figs = figures if figures is not None else {
            "authority_transfer": False, "provider": {"sha": PROVIDER_SHA},
            "figures": [{"id": "f1"}, {"id": "f2"}]}
        put(site / "_data" / "ggmath_bridge_figures.json", json.dumps(figs))

    put(repo / "app" / "lib" / "qps-ui-tokens.ts", "import t from './QPS_UI_TOKENS_v1.2.json';\n")
    put(repo / "app" / "app" / "qps-ui-contract" / "page.tsx", "export default 1;\n")
    bl = browserslist if browserslist is not None else [">0.5%", "not IE 11"]
    (repo / "app" / "package.json").write_text(json.dumps({"browserslist": bl}), encoding="utf-8")

    built = tmp / "built"
    built.mkdir(exist_ok=True)
    put(built / "index.html", html if html is not None else _html())
    if real_contracts:
        data = json.loads((site / "_data" / "ggmath_bridge_figures.json").read_text(encoding="utf-8"))
        page = page if page is not None else _page(data["provider"]["sha"], [f["id"] for f in data["figures"]])
    put(built / "ggmath-bridge.html", page if page is not None else _page())
    # Distinct basename: coverage maps frames by __file__ only when basenames match.
    return site / "scripts" / "validate_site_relocated.py", built


def test_pass_on_synthetic_site(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path)
    code, mod, out = _run(fake, [str(built)], monkeypatch, capsys)
    assert code == 0
    assert mod.errors == []
    assert "QPS WEB VALIDATION: PASS" in out
    assert "validated=" + str(built.resolve()) in out
    assert mod.REPO == tmp_path / "repo"


def test_pass_with_real_committed_contracts(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, real_contracts=True)
    code, mod, out = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == []
    assert code == 0


def test_default_built_dir_is_site_underscore_site(tmp_path, monkeypatch, capsys):
    fake, _ = build(tmp_path)
    code, mod, out = _run(fake, [], monkeypatch, capsys)
    site = tmp_path / "repo" / "mission-control" / "qps-triage-ultra" / "site"
    assert mod.BUILT == site / "_site"
    assert code == 1
    assert "built index missing: " + str(site / "_site" / "index.html") in mod.errors
    assert "built gg_MATH bridge page missing: " + str(site / "_site" / "ggmath-bridge.html") in mod.errors
    assert "QPS WEB VALIDATION: FAIL" in out


def test_contract_and_structure_failures(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, skip=("QPS_BROWSER_SUPPORT_v1.2.md", "qps-web-architecture.mmd",
                                       "qps-web-architecture.svg", "page.tsx"))
    triage = tmp_path / "repo" / "mission-control" / "qps-triage-ultra"
    (triage / "web" / "QPS_UI_TOKENS_v1.2.json").write_text(json.dumps({"schema": "old"}), encoding="utf-8")
    (triage / "web" / "QPS_WEB_GATE_REGISTRY_v1.json").write_text(
        json.dumps({"gates": [{"id": "J1_SOURCE"}]}), encoding="utf-8")
    (triage / "site" / "assets" / "css" / "qps-ui-1.2.css").write_text("qps-state-pass", encoding="utf-8")
    (triage / "site" / "index.md").write_text("## Fleet\n", encoding="utf-8")
    code, mod, out = _run(fake, [str(built)], monkeypatch, capsys)
    assert code == 1
    errs = mod.errors
    for msg in ["token schema mismatch", "color-only semantics forbidden", "browser support contract missing",
                "Next token contract route missing", "CSS contract missing @media print",
                "atlas missing PCA / BT view", "canonical Mermaid source missing",
                "durable SVG rendering missing", "durable SVG is not published in atlas"]:
        assert msg in errs, msg
    assert "atlas missing Fleet view" not in errs
    assert any(e.startswith("J1-J6 gate mismatch") for e in errs)
    assert "- token schema mismatch" in out


def test_next_adapter_missing_and_not_consuming_tokens(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, skip=("qps-ui-tokens.ts",))
    code, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == ["Next token adapter missing"]

    fake, built = build(tmp_path / "b")
    (tmp_path / "b" / "repo" / "app" / "lib" / "qps-ui-tokens.ts").write_text("export {}", encoding="utf-8")
    code, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == ["Next adapter does not consume governed token JSON"]


@pytest.mark.parametrize(
    "browserslist, expected",
    [
        (["IE >= 11", "not ie 11"], ["operational app still claims IE11 support"]),
        ([">0.5%"], ["IE11 exclusion is not explicit"]),
        ([], ["IE11 exclusion is not explicit"]),
    ],
)
def test_browserslist_rules(tmp_path, monkeypatch, capsys, browserslist, expected):
    fake, built = build(tmp_path, browserslist=browserslist)
    code, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == expected
    assert code == 1


def test_built_html_identity_failures(tmp_path, monkeypatch, capsys):
    bad_html = ('<html data-source-sha="UNBOUND">'
                '<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script></html>')
    fake, built = build(tmp_path, html=bad_html)
    code, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    errs = mod.errors
    assert 'built HTML missing data-qps-ui="1.2"' in errs
    assert "built HTML missing data-evidence-state=" in errs
    assert "built HTML missing data-source-sha=" not in errs
    assert "built HTML contains UNBOUND provenance" in errs
    assert "source_sha is not an exact 40-character Git SHA" in errs
    assert "CDN Mermaid is forbidden for governed evidence" in errs


def test_short_sha_rejected(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, html=_html(sha="abc123"))
    _, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == ["source_sha is not an exact 40-character Git SHA"]


def test_ggmath_page_failures(tmp_path, monkeypatch, capsys):
    page = _page(provider_sha="1" * 40, figure_ids=("f1",),
                 extra='<script type="module" SRC = "http://evil.example/x.js"></script>')
    figures = {"authority_transfer": True, "provider": {"sha": PROVIDER_SHA}, "figures": [{"id": "f1"}, {"id": "f2"}]}
    fake, built = build(tmp_path, page=page, figures=figures)
    _, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == [
        "gg_MATH figure JSON transfers authority",
        "gg_MATH page lacks exact provider SHA",
        "remote script on gg_MATH page",
        "gg_MATH figure missing",
    ]


def test_ggmath_page_without_provider_attribute(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, page='<main data-figure-id="f1" data-figure-id="f2"></main>')
    _, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == ["gg_MATH page lacks exact provider SHA"]


def test_ggmath_data_missing_skips_page_checks(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, skip=("ggmath_bridge_figures.json",), page="<script src='https://x'></script>")
    _, mod, _ = _run(fake, [str(built)], monkeypatch, capsys)
    assert mod.errors == ["gg_MATH bridge figure JSON missing"]


def test_missing_required_json_contract_raises(tmp_path, monkeypatch, capsys):
    fake, built = build(tmp_path, skip=("QPS_UI_TOKENS_v1.2.json",))
    with pytest.raises(FileNotFoundError):
        _run(fake, [str(built)], monkeypatch, capsys)
