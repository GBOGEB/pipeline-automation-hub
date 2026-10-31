"""CODE MAROON runner: dedupe to roots, dispositions, disjoint lanes, coverage gaps, public projection."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maroon as M  # noqa: E402


def dep(n, state, pkg, sev, ghsa, manifest, patched=None, eco="pip"):
    return {"number": n, "state": state,
            "security_advisory": {"severity": sev, "ghsa_id": ghsa},
            "security_vulnerability": {"first_patched_version": {"identifier": patched} if patched else None},
            "dependency": {"package": {"ecosystem": eco, "name": pkg}, "manifest_path": manifest}}


def code(n, state, rule, sev, path, tool="CodeQL", security=True):
    r = {"id": rule, "severity": "warning"}
    if security:
        r["security_severity_level"] = sev
    else:
        r["severity"] = sev
    return {"number": n, "state": state, "rule": r, "tool": {"name": tool},
            "most_recent_instance": {"location": {"path": path, "start_line": 1}}}


RAW = {"owner": "O", "fetched_at": "2026-10-30T00:00:00+00:00", "repos": {
    "O/pub": {"visibility": "public", "sources": {
        "dependabot": {"coverage": "ok", "alerts": [
            dep(1, "open", "pillow", "critical", "GHSA-a", "req.txt", "10.3.0"),
            dep(2, "open", "pillow", "high", "GHSA-b", "req.txt", "11.0.0"),
            dep(3, "fixed", "pillow", "high", "GHSA-c", "req.txt", "9.0.0"),
            dep(4, "dismissed", "requests", "medium", "GHSA-d", "req.txt", "2.32.0"),
            dep(5, "open", "zod", "high", "GHSA-e", "app/package.json", None, eco="npm")]},
        "code_scanning": {"coverage": "ok", "alerts": [
            code(10, "open", "py/xss", "high", "a.py"),
            code(11, "open", "py/xss", "medium", "b.py"),
            code(12, "open", "B101", "note", "a.py", tool="Bandit", security=False)]},
        "secret_scanning": {"coverage": "ok", "alerts": [
            {"number": 20, "state": "resolved", "resolution": "false_positive", "secret_type": "t"}]}}},
    "O/priv": {"visibility": "private", "sources": {
        "dependabot": {"coverage": "ok", "alerts": []},
        "code_scanning": {"coverage": "not_enabled", "error": "Code scanning is not enabled"},
        "secret_scanning": {"coverage": "not_readable", "error": "needs scope"}}}}}


class Roots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = M.build(RAW)
        cls.roots = {x["id"]: x for x in cls.r["roots"]}

    def test_alerts_on_one_package_are_one_root_with_dispositions(self):
        p = self.roots["O/pub|dependabot|pip|pillow"]
        self.assertEqual((p["outstanding"], p["closed"], p["deferred"]), (2, 1, 0))
        self.assertEqual(p["severity"], "critical")
        self.assertEqual(p["fix"], "upgrade pillow to >= 11.0.0")  # highest patched version among open advisories
        self.assertEqual(p["advisories"], ["GHSA-a", "GHSA-b"])

    def test_pip_names_are_one_root_whatever_their_spelling(self):
        raw = json.loads(json.dumps(RAW))
        raw["repos"]["O/pub"]["sources"]["dependabot"]["alerts"].append(dep(6, "open", "Pillow", "low", "GHSA-f", "req.txt"))
        roots = {x["id"]: x for x in M.build(raw)["roots"]}
        self.assertEqual(roots["O/pub|dependabot|pip|pillow"]["outstanding"], 3)
        self.assertNotIn("O/pub|dependabot|pip|Pillow", roots)
        self.assertEqual(M.package_name("pip", "Zope.Interface_x"), "zope-interface-x")
        self.assertEqual(M.package_name("npm", "@Scope/Pkg"), "@Scope/Pkg")

    def test_root_without_open_alerts_has_no_severity_or_fix(self):
        r = self.roots["O/pub|dependabot|pip|requests"]
        self.assertEqual((r["outstanding"], r["deferred"], r["severity"]), (0, 1, None))
        self.assertNotIn("fix", r)

    def test_unpatched_package_says_so(self):
        self.assertIn("no patched zod release", self.roots["O/pub|dependabot|npm|zod"]["fix"])

    def test_code_scanning_root_is_tool_and_rule_with_paths(self):
        x = self.roots["O/pub|code_scanning|CodeQL|py/xss"]
        self.assertEqual((x["outstanding"], x["severity"], x["paths"]), (2, "high", ["a.py", "b.py"]))

    def test_non_revoked_resolved_secret_is_deferred_not_closed(self):
        s = self.roots["O/pub|secret_scanning|secret|t"]
        self.assertEqual((s["closed"], s["deferred"], s["outstanding"]), (0, 1, 0))

    def test_roots_ordered_worst_first(self):
        sev = [x["severity"] for x in self.r["roots"] if x["outstanding"]]
        self.assertEqual(sev, sorted(sev, key=lambda s: -M.RANK[s]))

    def test_totals_count_every_manifestation(self):
        self.assertEqual(self.r["totals"]["dependabot"], {"outstanding": 3, "closed": 1, "deferred": 1})
        self.assertEqual(self.r["roots_outstanding"], 4)

    def test_no_closure_and_no_merge_authority(self):
        self.assertIs(self.r["closes_findings"], False)
        self.assertIs(self.r["merge_authority"], False)


class Lanes(unittest.TestCase):
    def test_lanes_are_repo_and_family_and_never_share_a_manifest(self):
        lanes = M.build(RAW)["lanes"]
        ids = [l["id"] for l in lanes]
        self.assertEqual(sorted(ids), sorted(["pub:deps-pip", "pub:deps-npm", "pub:code-codeql", "pub:code-bandit"]))
        deps = [l for l in lanes if l["source"] == "dependabot"]
        for a in deps:
            for b in deps:
                if a is not b and a["repo"] == b["repo"]:
                    self.assertFalse(set(a["paths"]) & set(b["paths"]))

    def test_lane_ids_are_branch_safe(self):
        raw = json.loads(json.dumps(RAW))
        raw["repos"]["O/pub"]["sources"]["code_scanning"]["alerts"].append(code(13, "open", "r", "low", "c.py", tool="Semgrep OSS"))
        self.assertIn("pub:code-semgrep-oss", [l["id"] for l in M.build(raw)["lanes"]])

    def test_code_lanes_name_shared_files(self):
        lanes = {l["id"]: l for l in M.build(RAW)["lanes"]}
        self.assertEqual(lanes["pub:code-codeql"]["shared_paths"], ["a.py"])
        self.assertEqual(lanes["pub:code-bandit"]["shared_paths"], ["a.py"])


class Coverage(unittest.TestCase):
    def test_gaps_are_recorded_not_zero(self):
        cov = M.build(RAW)["coverage"]["O/priv"]
        self.assertEqual((cov["code_scanning"], cov["secret_scanning"]), ("not_enabled", "not_readable"))

    def test_coverage_of_error_text(self):
        self.assertEqual(M.coverage_of("Secret scanning is disabled on this repository"), "not_enabled")
        self.assertEqual(M.coverage_of('This API operation needs the "admin:repo_hook" scope'), "not_readable")

    def test_fetch_stops_a_source_at_its_first_error(self):
        calls = []

        def gh(args):
            calls.append(args)
            if args[0] == "repo":
                return 0, json.dumps([{"nameWithOwner": "O/x", "visibility": "PUBLIC"}]), ""
            if "code-scanning" in args[-1]:
                return 1, "", "gh: Code scanning is not enabled for this repository (HTTP 404)"
            return 0, "[[]]", ""
        raw = M.fetch("O", gh=gh)
        self.assertEqual(raw["repos"]["O/x"]["sources"]["code_scanning"]["coverage"], "not_enabled")
        self.assertEqual(sum("code-scanning" in c[-1] for c in calls), 1)
        self.assertEqual(raw["repos"]["O/x"]["sources"]["dependabot"], {"alerts": [], "coverage": "ok"})


class Public(unittest.TestCase):
    def test_projection_has_counts_but_no_subjects_paths_or_advisories(self):
        pub = M.public_projection(M.build(RAW))
        text = json.dumps(pub)
        for secret in ("pillow", "zod", "py/xss", "req.txt", "a.py", "GHSA-"):
            self.assertNotIn(secret, text)
        self.assertEqual(pub["repos"]["O/pub"]["dependabot"]["roots_outstanding_by_severity"], {"critical": 1, "high": 1})
        self.assertEqual(pub["repos"]["O/priv"]["code_scanning"]["coverage"], "not_enabled")

    def test_write_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            M.write_outputs(M.build(RAW), Path(tmp))
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["MAROON_FIXLIST.csv", "MAROON_LANES.md", "MAROON_PUBLIC.json", "MAROON_RECEIPT.json"])
            rows = (Path(tmp) / "MAROON_FIXLIST.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1 + 4)  # header + outstanding roots
            self.assertTrue(rows[1].startswith("1,critical,O/pub,dependabot,pip,pillow"))


class Diff(unittest.TestCase):
    def test_fixed_alerts_leave_and_new_ones_join(self):
        old = M.build(RAW)
        raw = json.loads(json.dumps(RAW))
        alerts = raw["repos"]["O/pub"]["sources"]["dependabot"]["alerts"]
        alerts[0]["state"] = alerts[1]["state"] = "fixed"  # a merged PR upgraded pillow
        alerts.append(dep(7, "open", "jinja2", "high", "GHSA-g", "req.txt", "3.1.5"))
        raw["repos"]["O/priv"]["sources"]["code_scanning"] = {"coverage": "not_readable", "error": "x"}
        d = M.diff(old, M.build(raw))
        self.assertEqual((d["alerts_left"], d["alerts_joined"], d["roots_cleared"], d["roots_new"]), (2, 1, 1, 1))
        self.assertEqual(d["left"][0], {"id": "O/pub|dependabot|pip|pillow", "repo": "O/pub", "source": "dependabot",
                                        "alerts": [1, 2], "root_cleared": True})
        self.assertEqual(d["coverage_changes"], [{"repo": "O/priv", "source": "code_scanning",
                                                  "old": "not_enabled", "new": "not_readable"}])
        self.assertIs(d["closes_findings"], False)

    def test_same_receipt_has_no_delta(self):
        r = M.build(RAW)
        d = M.diff(r, r)
        self.assertEqual((d["alerts_left"], d["alerts_joined"], d["left"], d["joined"], d["coverage_changes"]),
                         (0, 0, [], [], []))

    def test_delta_counts_name_no_roots(self):
        old = M.build(RAW)
        raw = json.loads(json.dumps(RAW))
        raw["repos"]["O/pub"]["sources"]["dependabot"]["alerts"][0]["state"] = "fixed"
        text = json.dumps(M.delta_counts(M.diff(old, M.build(raw))))
        for secret in ("pillow", "req.txt", "GHSA-"):
            self.assertNotIn(secret, text)

    def test_diff_command_writes_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "r.json"
            a.write_text(json.dumps(M.build(RAW)), encoding="utf-8")
            self.assertEqual(M.main(["diff", "--old", str(a), "--new", str(a), "--out", tmp]), 0)
            self.assertEqual(json.loads((Path(tmp) / "MAROON_DELTA.json").read_text(encoding="utf-8"))["alerts_left"], 0)


if __name__ == "__main__":
    unittest.main()
