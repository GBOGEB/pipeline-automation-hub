"""#529 G09 controls: the runtime harness observes processes, functions, outputs, errors, immutability."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as h  # noqa: E402

PARENT = '''import subprocess, sys, json
from pathlib import Path
def main():
    a = sys.argv
    out = Path(a[a.index("--output-dir") + 1]); inp = Path(a[a.index("--input-dir") + 1])
    rc = subprocess.run([sys.executable, str(Path(__file__).with_name("child.py")), str(inp), str(out)]).returncode
    (out / "summary.json").write_text(json.dumps({"files": len(list(inp.iterdir())), "rc": rc}))
    return rc
sys.exit(main())
'''
CHILD = '''import sys, json, os
from pathlib import Path
def analyse(p):
    return {"name": p.name, "bytes": len(p.read_bytes())}
def write(out, rows):
    (out / "twins").mkdir(exist_ok=True)
    for r in rows:
        (out / "twins" / (r["name"] + ".json")).write_text(json.dumps(r))
inp, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = [analyse(p) for p in sorted(inp.iterdir())]
write(out, rows)
if os.environ.get("FAIL_CHILD"):
    raise RuntimeError("deliberate child failure for the harness test")
'''


class Harness(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        r = self.repo = Path(self.t.name) / "repo"
        (r / "scripts").mkdir(parents=True)
        (r / "scripts/run_processing.py").write_text(PARENT)
        (r / "scripts/child.py").write_text(CHILD)
        (r / "app/public/master_input").mkdir(parents=True)
        (r / "app/public/outputs/twins").mkdir(parents=True)
        for n in ("a.pptx", "b.pptx"):
            (r / "app/public/master_input" / n).write_bytes(b"PK\x03\x04" + n.encode() * 20)
        (r / "app/public/outputs/twins/a.pptx.json").write_text('{"old": true}')
        (r / "app/public/outputs/stale.txt").write_text("unchanged")
        subprocess.run(["git", "init", "-q", str(r)], check=True)

    def tearDown(self):
        os.environ.pop("FAIL_CHILD", None)
        self.t.cleanup()

    def go(self, in_place=False):
        rep = Path(self.t.name) / "rep"
        rc = h.main(["--repo-root", str(self.repo), "--report-dir", str(rep), "--work-dir", str(Path(self.t.name) / "work")]
                    + (["--in-place"] if in_place else []))
        return rc, json.loads((rep / "receipt.json").read_text()), rep

    def test_sandbox_run_observes_everything_and_leaves_repo_untouched(self):
        before = h.snapshot(self.repo)
        rc, r, rep = self.go()
        self.assertEqual((rc, r["result"], r["exit_code"]), (0, "PASS", 0))
        self.assertEqual(h.snapshot(self.repo), before, "sandbox mode must not modify the repository")
        self.assertEqual(len(r["processes"]), 2)
        child = next(p for p in r["processes"] if "child.py" in " ".join(p["argv"]))
        parent = next(p for p in r["processes"] if "run_processing.py" in " ".join(p["argv"]))
        self.assertEqual(child["ppid"], parent["pid"])
        names = {f["qualname"] for f in child["functions"]}
        self.assertTrue({"analyse", "write"} <= names)
        an = next(f for f in child["functions"] if f["qualname"] == "analyse")
        self.assertEqual(an["calls"], 2)
        self.assertEqual(len(an["file_oid"]), 40)
        self.assertEqual(len(an["file_sha256"]), 64)
        o = r["outputs"]
        self.assertEqual({f["path"] for f in o["created"]}, {"summary.json", "twins/b.pptx.json"})
        mod = {f["path"]: f for f in o["modified"]}
        self.assertIn("twins/a.pptx.json", mod)
        self.assertEqual(mod["twins/a.pptx.json"]["json_keys_changed"], ["bytes", "name", "old"])
        self.assertEqual(o["counts"]["unchanged"], 1)
        self.assertTrue(r["input"]["immutable"])
        self.assertEqual(sum(len(v) for v in r["stray_repo_writes"].values()), 0)
        for f in ("report.html", "sipoc.mmd", "dag.mmd", "spine.mmd", "DIAGRAMS.md"):
            self.assertTrue((rep / f).stat().st_size > 0, f)
        dag = (rep / "dag.mmd").read_text()
        self.assertIn(f"P{parent['pid']} -->|spawns| P{child['pid']}", dag)
        html = (rep / "report.html").read_text()
        for v in ("name", "sha", "oid", "tags"):
            self.assertIn(f'value="{v}"', html)
        self.assertIn(f'data-oid="{an["id"]}"', html)

    def test_child_failure_captured_with_traceback(self):
        os.environ["FAIL_CHILD"] = "1"
        rc, r, _ = self.go()
        self.assertEqual(rc, 1)
        self.assertEqual(r["result"], "FAIL")
        u = r["errors"]["uncaught"]
        self.assertEqual(len(u), 1)
        self.assertEqual(u[0]["type"], "RuntimeError")
        self.assertIn("deliberate child failure", u[0]["traceback"])
        self.assertIn("child.py", u[0]["process"])

    def test_input_mutation_detected(self):
        (self.repo / "scripts/child.py").write_text(CHILD + '\n(inp / "a.pptx").write_bytes(b"tampered")\n')
        rc, r, _ = self.go()
        self.assertFalse(r["input"]["immutable"])
        self.assertEqual([f["path"] for f in r["input"]["changed"]["modified"]], ["a.pptx"])

    def test_in_place_writes_committed_outputs(self):
        rc, r, _ = self.go(in_place=True)
        self.assertEqual(r["mode"], "IN_PLACE")
        self.assertTrue((self.repo / "app/public/outputs/summary.json").exists())


class PowerShellWrapper(unittest.TestCase):
    def test_wrapper_contract(self):
        ps = (HERE / "Run-MasterInputPipeline.ps1").read_text()
        self.assertNotIn("$args", ps, "$args is a PowerShell automatic variable")
        for flag in ("--repo-root", "--report-dir", "--python", "--in-place", "--excel-input", "--input-dir"):
            self.assertIn(flag, ps)
        self.assertIn("exit $code", ps)

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh not installed")
    def test_wrapper_parses(self):
        p = subprocess.run(["pwsh", "-NoProfile", "-Command",
                            "$null=[System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$null,[ref]$e);"
                            "if($e){$e|%%{$_.Message};exit 1}" % (HERE / "Run-MasterInputPipeline.ps1")],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
