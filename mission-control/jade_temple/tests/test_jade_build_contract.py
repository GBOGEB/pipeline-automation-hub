"""FOCUS5 H04 for the hub, scoped to mission-control/jade_temple (owner decision 2026-11-01).

Reproducible dependency/build contract of the JADE programme:
  1. Python under jade_temple imports only the standard library, its own modules, and the
     third-party modules declared in THIRD_PARTY, from exactly the files listed there.
  2. The JADE CI path installs coverage and playwright only through the Dependabot-owned
     manifest sprint/requirements-optional.txt (pip -c), never an inline version, so the CI
     install cannot drift from the declared pins; every other install there is pinned ==.
  3. The Python floor is 3.12: every literal python-version on the JADE CI path equals it and
     this interpreter meets it.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JT = ROOT / "mission-control/jade_temple"
MANIFEST = JT / "sprint/requirements-optional.txt"
CI_PATH = (ROOT / ".github/workflows/jade-temple-readonly-qa.yml", ROOT / ".github/workflows/jade-devops-census.yml")
FLOOR = (3, 12)
MANAGED = {"coverage", "playwright"}  # pinned in MANIFEST; Dependabot group pip-jade-sprint-minor-patch

# module -> files allowed to import it (paths relative to jade_temple) and where it is pinned
THIRD_PARTY = {
    "playwright": {"files": {"tools/run_eight_browser_qa.py", "tools/run_gate12_browser_qa.py",
                             "tools/run_nplus1_browser_qa.py", "tools/run_nplus2_browser_qa.py",
                             "tools/run_redtrace_browser_qa.py", "tools/render_redtrace_pdf.py"},
                   "pinned": "sprint/requirements-optional.txt"},
    "yaml": {"files": {"devops/workflows.py"}, "pinned": "jade-devops-census.yml pyyaml=="},
    # local operator tool, not on the CI path; nothing in CI installs or runs it
    "pypdf": {"files": {"tools/render_redtrace_pdf.py"}, "pinned": None},
}
INSTALL = re.compile(r"pip install ([^\n]*?)(?:\\\n|$)", re.M)


def third_party_imports(root=JT):
    std = set(sys.stdlib_module_names) | {"__future__"}
    local = {p.stem for p in root.rglob("*.py")} | {p.name for p in root.rglob("*") if p.is_dir()}
    found = {}
    for f in root.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            else:
                continue
            for m in mods:
                top = m.split(".")[0]
                if top not in std and top not in local:
                    found.setdefault(top, set()).add(f.relative_to(root).as_posix())
    return found


def install_args(text):
    """Package tokens of every pip install on the given workflow text (options dropped)."""
    out = []
    for m in INSTALL.finditer(text):
        toks = m.group(1).split()
        skip = False
        for t in toks:
            if skip:
                skip = False
                continue
            if t in ("-c", "-r", "--constraint", "--requirement"):
                skip = True
                continue
            if not t.startswith("-"):
                out.append(t)
    return out


class JadeBuildContract(unittest.TestCase):
    def test_imports_are_stdlib_local_or_declared(self):
        found = third_party_imports()
        self.assertEqual(set(found), set(THIRD_PARTY), "undeclared or vanished third-party module")
        for mod, spec in THIRD_PARTY.items():
            self.assertEqual(found[mod], spec["files"], mod)

    def test_managed_packages_install_only_through_the_manifest(self):
        pins = dict(line.split("==", 1) for line in MANIFEST.read_text(encoding="utf-8").split())
        self.assertEqual(set(pins), MANAGED)
        for wf in CI_PATH:
            text = wf.read_text(encoding="utf-8")
            for tok in install_args(text):
                name = re.split(r"[=<>!~\[]", tok, maxsplit=1)[0].lower()
                if name in MANAGED:
                    self.assertEqual(tok, name, f"{wf.name}: {tok} must come from the manifest via -c")
                else:
                    self.assertRegex(tok, r"^[A-Za-z0-9_.-]+==\d+(\.\d+)*$", f"{wf.name}: {tok} not pinned ==")
            for line in text.splitlines():
                if "pip install" in line and set(install_args(line)) & MANAGED:
                    self.assertIn("-c mission-control/jade_temple/sprint/requirements-optional.txt", line, wf.name)

    def test_python_floor(self):
        self.assertGreaterEqual(sys.version_info[:2], FLOOR)
        for wf in CI_PATH:
            versions = re.findall(r"python-version:\s*['\"]?(\d+\.\d+)", wf.read_text(encoding="utf-8"))
            self.assertTrue(versions, wf.name)
            self.assertEqual(set(versions), {".".join(map(str, FLOOR))}, wf.name)

    # negative controls: the checks above must reject these
    def test_negative_undeclared_import_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.py").write_text("import requests\nimport json\n", encoding="utf-8", newline="\n")
            self.assertEqual(third_party_imports(Path(d)), {"requests": {"x.py"}})

    def test_negative_inline_managed_pin_is_visible(self):
        self.assertEqual(install_args("python -m pip install --quiet coverage==7.13.3\n"), ["coverage==7.13.3"])
        self.assertEqual(install_args("pip install -c m.txt pyyaml==6.0.3 coverage\n"), ["pyyaml==6.0.3", "coverage"])


if __name__ == "__main__":
    unittest.main()
