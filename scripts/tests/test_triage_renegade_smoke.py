"""Negative controls for scripts/triage_renegade_smoke.py.

The smoke gate only ever ran against the committed registry, so none of its fail-closed
rules had been shown to fire. Each test mutates a copy of the real registry once and
asserts the matching rule rejects it (mutation-style), plus the committed registry passes.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import triage_renegade_smoke as smoke  # noqa: E402

REGISTRY = ROOT / "triage" / "renegade_incubator" / "registry.yaml"


class Smoke(unittest.TestCase):
    def setUp(self):
        self.base = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, data):
        p = Path(self.tmp.name) / "r.yaml"
        p.write_text(yaml.safe_dump(data), encoding="utf-8")
        return smoke.validate(p)

    def mutate(self, fn):
        d = copy.deepcopy(self.base)
        fn(d)
        return self.errors(d)

    def test_committed_registry_passes(self):
        self.assertEqual(smoke.validate(REGISTRY), [])
        self.assertTrue(self.base["candidates"], "registry must hold candidates for the row rules to bite")

    def test_top_level_authority_rules(self):
        cases = {
            "unexpected schema": lambda d: d.update(schema="v0.1"),
            "authority must remain DISCOVERY_ONLY": lambda d: d.update(authority="RELEASE"),
            "release_credit_allowed must be false": lambda d: d.update(release_credit_allowed=True),
            "primary repository set changed": lambda d: d.update(primary_repositories=["GBOGEB/ABACUS"]),
            "unexpected merge rule": lambda d: d["routing_policy"].update(merge_rule="merge_everything"),
            "bulk duplicate merge must be disabled":
                lambda d: d["routing_policy"].update(duplicate_code_bulk_merge_allowed=True),
            "coverage denominator does not match candidate count":
                lambda d: d.setdefault("coverage", {}).update(explored_repositories=len(d["candidates"]) + 1),
        }
        for msg, fn in cases.items():
            with self.subTest(rule=msg):
                self.assertIn(msg, self.mutate(fn))

    def test_candidate_row_rules(self):
        first = lambda d: d["candidates"][0]
        repo = self.base["candidates"][0]["repository"]
        cases = {
            "duplicate or missing repository": lambda d: d["candidates"].append(copy.deepcopy(first(d))),
            f"invalid disposition for {repo}": lambda d: first(d).update(disposition="MERGE_NOW"),
            f"missing integer approx_size_kb for {repo}": lambda d: first(d).update(approx_size_kb="12"),
            f"invalid bridge target for {repo}": lambda d: first(d).update(bridge_to="GBOGEB/elsewhere"),
            f"promotion-capable candidate lacks observed_sha: {repo}":
                lambda d: first(d).update(disposition="MODERNIZE_AND_FEDERATE", observed_sha=None),
        }
        for msg, fn in cases.items():
            with self.subTest(rule=msg):
                self.assertTrue(any(e.startswith(msg) for e in self.mutate(fn)), self.mutate(fn))

    def test_deferred_candidates_may_lack_sha(self):
        errs = self.mutate(lambda d: d["candidates"][0].update(disposition="DEFER", observed_sha=None))
        self.assertFalse([e for e in errs if "observed_sha" in e])

    def test_cli_exit_codes(self):
        self.assertEqual(self._main(str(REGISTRY)), 0)
        d = copy.deepcopy(self.base)
        d["authority"] = "RELEASE"
        p = Path(self.tmp.name) / "bad.yaml"
        p.write_text(yaml.safe_dump(d), encoding="utf-8")
        self.assertEqual(self._main(str(p)), 1)

    def _main(self, path):
        old = sys.argv
        sys.argv = ["smoke", path]
        try:
            return smoke.main()
        finally:
            sys.argv = old


if __name__ == "__main__":
    unittest.main()
