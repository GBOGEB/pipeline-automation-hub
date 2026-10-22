import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ztga", ROOT / "zero_test_gate_audit.py")
ztga = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ztga)

BARE = "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n"
CASE = (
    "import unittest\n\nclass Base(unittest.TestCase):\n    def test_one(self):\n        pass\n\n"
    "class Child(Base):\n    def test_two(self):\n        pass\n"
)


def workflow(run: str, wd: str | None = None) -> str:
    step = f"      - run: {run}\n" if wd is None else f"      - working-directory: {wd}\n        run: {run}\n"
    return "name: t\non: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n" + step


class ZeroTestGateAuditTests(unittest.TestCase):
    def repo(self, files: dict[str, str]) -> Path:
        tmp = Path(tempfile.mkdtemp())
        for rel, text in files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return tmp

    def test_bare_pytest_functions_are_zero_tests(self):
        repo = self.repo({
            "t/test_bare.py": BARE,
            ".github/workflows/w.yml": workflow("python -m unittest t/test_bare.py -v"),
        })
        out = ztga.audit(repo)
        self.assertEqual(out["summary"]["zero_test_gates"], 1)
        self.assertIn("2 bare test functions", out["rows"][0]["files"][0]["note"])
        self.assertEqual(ztga.main(["--repo", str(repo)]), 1)

    def test_testcase_inheritance_counts(self):
        repo = self.repo({
            "t/test_case.py": CASE,
            ".github/workflows/w.yml": workflow("python -m unittest t/test_case.py"),
        })
        out = ztga.audit(repo)
        self.assertEqual(out["rows"][0]["state"], "OK")
        self.assertEqual(out["rows"][0]["tests_collectable"], 2)
        self.assertEqual(ztga.main(["--repo", str(repo)]), 0)

    def test_working_directory_and_dotted_module(self):
        repo = self.repo({
            "pkg/tests/__init__.py": "",
            "pkg/tests/test_case.py": CASE,
            ".github/workflows/w.yml": workflow("python -m unittest -v tests.test_case", wd="pkg"),
        })
        self.assertEqual(ztga.audit(repo)["rows"][0]["state"], "OK")

    def test_discover_counts_matching_files_only(self):
        repo = self.repo({
            "d/test_bare.py": BARE,
            "d/check_case.py": CASE,
            ".github/workflows/w.yml": workflow("python -m unittest discover -s d -p 'test_*.py'"),
        })
        self.assertEqual(ztga.audit(repo)["rows"][0]["state"], "ZERO_TESTS")

    def test_shell_variables_are_unresolved_and_strict_is_incomplete(self):
        repo = self.repo({".github/workflows/w.yml": workflow("python -m unittest $TARGET")})
        self.assertEqual(ztga.audit(repo)["summary"]["unresolved_gates"], 1)
        self.assertEqual(ztga.main(["--repo", str(repo)]), 0)
        self.assertEqual(ztga.main(["--repo", str(repo), "--strict"]), 2)

    def test_missing_target_is_unresolved_not_green(self):
        repo = self.repo({".github/workflows/w.yml": workflow("python -m unittest t/test_gone.py")})
        self.assertEqual(ztga.audit(repo)["rows"][0]["state"], "UNRESOLVED")


    def test_tee_log_variable_does_not_poison_unittest_discover(self):
        repo = self.repo({
            "t/test_case.py": CASE,
            ".github/workflows/w.yml": workflow(
                'python -m unittest discover -s t -q 2>&1 | tee "$RUNNER_TEMP/test.log"'
            ),
        })
        result = ztga.audit(repo)
        self.assertEqual(result["summary"]["unresolved_gates"], 0)
        self.assertEqual(result["rows"][0]["state"], "OK")
        self.assertGreater(result["rows"][0]["tests_collectable"], 0)
        self.assertEqual(ztga.main(["--repo", str(repo), "--strict"]), 0)

    def test_unittest_selector_variable_is_still_unresolved(self):
        repo = self.repo({
            "t/test_case.py": CASE,
            ".github/workflows/w.yml": workflow(
                'python -m unittest discover -s "$TEST_ROOT" -q 2>&1 | tee "$RUNNER_TEMP/test.log"'
            ),
        })
        self.assertEqual(ztga.audit(repo)["rows"][0]["state"], "UNRESOLVED")
        self.assertEqual(ztga.main(["--repo", str(repo), "--strict"]), 2)

    def test_literal_live_lossless_discovery_is_static_and_nonzero(self):
        root = "mission-control/v2/handoff/live_lossless"
        repo = self.repo({
            root + "/test_probe.py": CASE,
            ".github/workflows/w.yml": workflow(
                "python -m unittest discover -s " + root + " -p 'test_*.py' -v"
            ),
        })
        result = ztga.audit(repo)
        self.assertEqual(result["summary"]["zero_test_gates"], 0)
        self.assertEqual(result["summary"]["unresolved_gates"], 0)
        self.assertEqual(result["rows"][0]["state"], "OK")
        self.assertEqual(result["rows"][0]["tests_collectable"], 2)
        self.assertEqual(ztga.main(["--repo", str(repo), "--strict"]), 0)

    def test_zero_test_suite_still_fails_with_tee(self):
        repo = self.repo({
            "t/test_bare.py": BARE,
            ".github/workflows/w.yml": workflow(
                'python -m unittest t/test_bare.py -q 2>&1 | tee "$RUNNER_TEMP/test.log"'
            ),
        })
        self.assertEqual(ztga.audit(repo)["rows"][0]["state"], "ZERO_TESTS")
        self.assertEqual(ztga.main(["--repo", str(repo), "--strict"]), 1)

if __name__ == "__main__":
    unittest.main()
