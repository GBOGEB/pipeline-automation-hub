"""Behavioral checks for source inspection, typed joins and evidence integrity.

Fixtures are local and intentionally small. Discovered Python/YAML is never
executed; native status and remote capacity are not fabricated by these tests.
"""
from __future__ import annotations

import copy
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("orchestration_main_contract_tests", MODULE_PATH)
atlas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas)
HEAD = "a" * 40


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()  # long form: CI TEMP is 8.3 (RUNNER~1)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        elif isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_bytes(atlas.canonical(value))
        return path

    def port(self, **changes):
        port = {"id": "input", "path": "mission-control/input.json", "kind": "json",
                "schema": "example.input.v1", "required": True,
                "source_scope": "REPOSITORY"}
        port.update(changes)
        return port

    def profile(self):
        # Importing this module would fail. The contract reader must use AST only.
        self.write("src/worker.py", "raise RuntimeError('inspection imported a worker')\ndef emit():\n    return {}\n")
        self.write("mission-control/input.json", {"schema": "example.input.v1", "items": [1]})
        self.write("mission-control/glossary.json", {})
        self.write(".github/workflows/publisher.yml", "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n")
        return {
            "schema": "missioncontrol.orchestration.profile.v1",
            "repository": "example/project", "authority_transfer": False, "remote_dispatch": False,
            "publisher": ".github/workflows/publisher.yml",
            "inherits": {"glossary": "mission-control/glossary.json"},
            "sources": {"input": "mission-control/input.json"},
            "blocks": [
                {"id": "producer", "label": "Producer", "role": "producer", "needs": [],
                 "source_path": "src/worker.py", "entrypoint": "emit",
                 "inputs": [self.port()],
                 "outputs": [self.port(id="result", path="output/result.json",
                                       schema="example.result.v1", source_scope="GENERATED")]},
                {"id": "consumer", "label": "Consumer", "role": "viewer", "needs": ["producer"],
                 "source_path": "src/worker.py", "entrypoint": "emit",
                 "inputs": [self.port(id="result", path="output/result.json",
                                      schema="example.result.v1", source_scope="GENERATED")],
                 "outputs": [self.port(id="page", path="output/index.html", kind="html",
                                       schema=None, source_scope="GENERATED")]},
            ],
            "joins": [{"from": "producer:result", "to": "consumer:result", "join": "ALL",
                       "kind": "ARTIFACT_HANDOFF"}],
        }


class ArtifactBoundaryTests(FixtureCase):
    def test_output_seal_includes_unlisted_support_files_and_manifest_bytes(self):
        self.write("product/index.html", "<html></html>")
        self.write("product/support/app.js", "const version = 1;")
        self.write("product/manifest.json", {"declared": ["index.html"]})
        before = atlas.output_files(self.root / "product")
        self.assertEqual(set(before), {"index.html", "support/app.js", "manifest.json"})
        self.assertEqual(before["manifest.json"], atlas.digest((self.root / "product/manifest.json").read_bytes()))
        self.write("product/support/app.js", "const version = 2;")
        self.assertNotEqual(atlas.output_files(self.root / "product"), before)

    def test_output_seal_rejects_symlinked_files_and_directories(self):
        target = self.write("outside.txt", "outside output authority")
        product = self.root / "product"
        product.mkdir()
        link = product / "linked.txt"
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest("symlink creation unavailable: " + str(exc))
        with self.assertRaisesRegex(ValueError, "symlinked"):
            atlas.output_files(product)
        link.unlink()
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            atlas.output_files(product)

    def test_missing_required_and_optional_artifacts_are_distinct(self):
        with self.assertRaises(ValueError):
            atlas.validate_artifact(self.root, self.port())
        self.assertIsNone(atlas.validate_artifact(self.root, self.port(required=False)))

    def test_malformed_json_is_rejected(self):
        self.write("mission-control/input.json", '{"schema":')
        with self.assertRaises(ValueError):
            atlas.validate_artifact(self.root, self.port())

    def test_schema_and_required_fields_are_checked(self):
        for content in ({"schema": "wrong"}, {"schema": "example.input.v1"}, [1, 2]):
            with self.subTest(content=content):
                self.write("mission-control/input.json", content)
                with self.assertRaises(ValueError):
                    atlas.validate_artifact(self.root, self.port(required_fields=["items"]))
        self.write("mission-control/input.json", {"schema": "example.input.v1", "items": []})
        receipt = atlas.validate_artifact(self.root, self.port(required_fields=["items"]))
        self.assertGreater(receipt["bytes"], 0)

    def test_artifact_hash_binds_actual_bytes(self):
        path = self.write("mission-control/input.json", {"schema": "example.input.v1"})
        expected = atlas.digest(path.read_bytes())
        self.write("mission-control/input.json", {"schema": "example.input.v1", "changed": True})
        with self.assertRaises(ValueError):
            atlas.validate_artifact(self.root, self.port(sha256=expected))

    def test_empty_and_truncated_html_are_rejected(self):
        for content in (b"", b"<html><p>unfinished"):
            with self.subTest(content=content):
                self.write("output.html", content)
                with self.assertRaises(ValueError):
                    atlas.validate_artifact(self.root, self.port(path="output.html", kind="html", schema=None))

    def test_yaml_syntax_is_validated_before_consumption(self):
        self.write("input.yaml", "items: [unclosed\n")
        with self.assertRaises(ValueError):
            atlas.validate_artifact(self.root, self.port(path="input.yaml", kind="yaml", schema=None))

    def test_yaml_schema_and_required_fields_are_validated(self):
        self.write("input.yaml", "schema: wrong\nitems: []\n")
        with self.assertRaises(ValueError):
            atlas.validate_artifact(self.root, self.port(path="input.yaml", kind="yaml"))
        self.write("input.yaml", "schema: example.input.v1\n")
        with self.assertRaises(ValueError):
            atlas.validate_artifact(self.root, self.port(path="input.yaml", kind="yaml", required_fields=["items"]))

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        for name in ("../outside.json", "nested/../../outside.json", "/tmp/outside.json", "nested\\outside.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                atlas.safe_path(self.root, name)

    def test_symlink_escape_cannot_supply_an_artifact(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "input.json"
            target.write_text('{"schema":"example.input.v1"}', encoding="utf-8")
            try:
                (self.root / "link.json").symlink_to(target)
            except OSError as exc:
                self.skipTest("symlinks unavailable: " + str(exc))
            with self.assertRaises(ValueError):
                atlas.validate_artifact(self.root, self.port(path="link.json"))


class TypedContractTests(FixtureCase):
    def setUp(self):
        super().setUp()
        self.contract = self.profile()

    def test_valid_join_is_checked_without_importing_worker(self):
        result = atlas.validate_profile(self.root, self.contract)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["layers"], [["producer"], ["consumer"]])
        self.assertFalse(result["remote_dispatch"])

    def test_missing_or_empty_port_sets_fail_closed(self):
        for direction in ("inputs", "outputs"):
            for missing in (True, False):
                with self.subTest(direction=direction, missing=missing):
                    contract = copy.deepcopy(self.contract)
                    if missing:
                        del contract["blocks"][0][direction]
                    else:
                        contract["blocks"][0][direction] = []
                    with self.assertRaises((ValueError, KeyError, TypeError)):
                        atlas.validate_profile(self.root, contract)

    def test_missing_required_repository_input_is_not_path_prefix_dependent(self):
        self.contract["blocks"][0]["inputs"][0]["path"] = "data/required.json"
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, self.contract)

    def test_unknown_handoff_block_and_port_are_rejected(self):
        for target in ("absent:result", "consumer:missing"):
            with self.subTest(target=target):
                contract = copy.deepcopy(self.contract)
                contract["joins"][0]["to"] = target
                with self.assertRaises(ValueError):
                    atlas.validate_profile(self.root, contract)

    def test_type_schema_and_cardinality_mismatches_are_rejected(self):
        for change in ({"kind": "text"}, {"schema": "example.result.v2"}):
            with self.subTest(change=change):
                contract = copy.deepcopy(self.contract)
                contract["blocks"][1]["inputs"][0].update(change)
                with self.assertRaises(ValueError):
                    atlas.validate_profile(self.root, contract)
        self.contract["blocks"][0]["outputs"][0]["required"] = False
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, self.contract)

    def test_optional_predecessor_does_not_enable_implicit_any_join(self):
        self.contract["joins"][0]["join"] = "ANY"
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, self.contract)

    def test_handoff_requires_its_predecessor(self):
        self.contract["blocks"][1]["needs"] = []
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, self.contract)

    def test_cycles_and_unknown_dependencies_are_rejected(self):
        for needs in (["consumer"], ["missing"]):
            with self.subTest(needs=needs):
                contract = copy.deepcopy(self.contract)
                contract["blocks"][0]["needs"] = needs
                with self.assertRaises(ValueError):
                    atlas.validate_profile(self.root, contract)

    def test_duplicate_identity_and_ports_are_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["blocks"].append(copy.deepcopy(contract["blocks"][0]))
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, contract)
        self.contract["blocks"][0]["inputs"].append(copy.deepcopy(self.contract["blocks"][0]["inputs"][0]))
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, self.contract)

    def test_undefined_entrypoint_is_not_treated_as_executable(self):
        self.contract["blocks"][0]["entrypoint"] = "not_defined"
        with self.assertRaises(ValueError):
            atlas.validate_profile(self.root, self.contract)

    def test_profile_cannot_enable_remote_dispatch_or_authority_transfer(self):
        for field in ("remote_dispatch", "authority_transfer"):
            with self.subTest(field=field):
                contract = copy.deepcopy(self.contract)
                contract[field] = True
                with self.assertRaises(ValueError):
                    atlas.validate_profile(self.root, contract)


class StaticInspectionTests(FixtureCase):
    def test_yaml_on_and_boolean_looking_labels_are_preserved(self):
        path = ".github/workflows/example.yml"
        self.write(path, """name: off
on:
  push:
    branches: [main]
  workflow_dispatch:
jobs:
  build:
    name: yes
    runs-on: ubuntu-latest
    steps:
      - name: first
        run: python script.py
      - name: second
        run: echo done
""")
        row = atlas.workflow_info(self.root, path)
        self.assertEqual(row["errors"], [])
        self.assertIn("push", row["triggers"])
        self.assertIn("workflow_dispatch", row["triggers"])
        self.assertEqual(row["name"], "off")
        self.assertEqual(row["jobs"][0]["label"], "yes")
        self.assertEqual([s["name"] for s in row["jobs"][0]["steps"]], ["first", "second"])

    def test_dynamic_dependencies_remain_unresolved(self):
        path = ".github/workflows/dynamic.yml"
        expression = "${{ inputs.predecessor }}"
        self.write(path, "on: workflow_dispatch\njobs:\n  build:\n    needs: '" + expression + "'\n    runs-on: ubuntu-latest\n    steps: []\n")
        row = atlas.workflow_info(self.root, path)
        self.assertEqual(row["errors"], [])
        self.assertEqual(row["dynamic_dependencies"], 1)
        self.assertEqual(row["jobs"][0]["unresolved_needs"], [expression])
        self.assertEqual(row["evidence_class"], "DECLARED_YAML")

    def test_workflow_cycle_and_dangling_dependency_are_errors(self):
        for value in (
            "jobs:\n  a:\n    needs: b\n  b:\n    needs: a\n",
            "jobs:\n  a:\n    needs: missing\n",
        ):
            with self.subTest(value=value):
                self.write("flow.yml", value)
                self.assertTrue(atlas.workflow_info(self.root, "flow.yml")["errors"])

    def test_malformed_workflow_reports_error_instead_of_success(self):
        self.write("flow.yml", "on: push\njobs: [unterminated\n")
        row = atlas.workflow_info(self.root, "flow.yml")
        self.assertTrue(row["errors"])

    def test_ast_parse_error_is_recorded_without_execution(self):
        self.write("broken.py", "def unfinished(:\n    pass\n")
        row = atlas.python_info(self.root, "broken.py")
        self.assertEqual(row["parse_error"]["line"], 1)
        self.assertEqual(row["functions"], [])
        self.assertEqual(row["evidence_class"], "STATIC_SOURCE_ONLY")

    def test_ast_calls_describe_structure_not_execution(self):
        self.write("script.py", """raise RuntimeError('must not be imported')
def inner():
    return 1
async def outer():
    if False:
        inner()
if __name__ == '__main__':
    outer()
""")
        row = atlas.python_info(self.root, "script.py")
        self.assertIsNone(row["parse_error"])
        self.assertEqual(row["entrypoints"], ["outer"])
        self.assertIn({"from": "outer", "to": "inner"}, row["static_calls"])
        self.assertTrue(next(f for f in row["functions"] if f["name"] == "outer")["async"])

    def test_python_hash_preserves_raw_bom_bytes(self):
        raw = b"\xef\xbb\xbfdef main():\r\n    pass\r\n"
        self.write("bom.py", raw)
        row = atlas.python_info(self.root, "bom.py")
        self.assertEqual(row["sha256"], atlas.digest(raw))
        self.assertIsNone(row["parse_error"])


class GraphAndCohortTests(FixtureCase):
    def graph_profile(self):
        # The graph fixture supplies task identities but does not run adapters.
        blocks = []
        for identity in ("source-contracts", "method-atlas", "burndown", "superstitch",
                         "convergence", "orchestration-view", "pages-portal"):
            blocks.append({"id": identity, "label": identity, "role": "process", "needs": [],
                           "source_path": "src/worker.py", "inputs": [self.port()],
                           "outputs": [self.port(id="output")]})
        sources = {key: key + ".json" for key in ("beams", "lanes", "superstitch", "groups", "queue")}
        sources["federation"] = "federation.yaml"
        self.write("federation.yaml", "nodes: []\nedges: []\n")
        self.write("beams.json", {"beams": [{"id": "A", "title": "Input"}, {"id": "B", "title": "Output"}],
                                  "edges": [{"from": "A", "to": "B", "type": "DEPENDENCY"},
                                            {"from": "B", "to": "A", "type": "FEEDBACK"}]})
        self.write("lanes.json", {"lanes": []})
        self.write("superstitch.json", {"nodes": [], "edges": []})
        self.write("groups.json", {"groups": []})
        self.write("queue.json", {"items": []})
        return {"repository": "example/project", "blocks": blocks, "sources": sources,
                "publisher": ".github/workflows/publish.yml"}

    def test_feedback_is_unrolled_to_new_pulse_identity(self):
        graphs = atlas.graphs(self.root, self.graph_profile(), {"python_modules": [], "workflows": []})
        graph = next(g for g in graphs if g["id"] == "canonical-beams")
        feedback = next(e for e in graph["edges"] if e["kind"] == "FEEDBACK_NEXT_PULSE")
        self.assertEqual(feedback["from"], "B")
        self.assertNotEqual(feedback["to"], "A")
        self.assertIn(feedback["to"], {n["id"] for n in graph["nodes"]})
        self.assertEqual(atlas.layers(graph["nodes"], graph["edges"])[0], ["A"])
        self.assertEqual(graph["runtime_status"], "UNKNOWN")

    def cohort_profile(self, entries):
        self.write("queue.json", {"schema": "example.queue.v1", "open_states": ["TODO", "UNKNOWN_NEEDS_READER"],
                                  "items": [{"id": "same-id", "history": [{"state": "SUPERSEDED", "flow": "TERMINAL"}]}]})
        self.write("series.json", {"entries": entries})
        self.write("jade.json", {"metrics": {"owner_actions_open": 2, "owner_actions_closed": 0},
                                 "evidence_level": "FROZEN", "pulses": [
                                     {"id": "PULSE-1", "metrics": {"accepted_owner_actions": None},
                                      "eligible_denominator": 2, "scope": "JADE_A", "cohort_sha": "a" * 40,
                                      "qualification": "UNKNOWN"},
                                     {"id": "PULSE-2", "metrics": {"accepted_owner_actions": 0},
                                      "eligible_denominator": 2, "scope": "JADE_B", "cohort_sha": "b" * 40,
                                      "qualification": "FROZEN"}]})
        self.write("stitch.json", {"observations": {
            "historical_six_repo_breadth": {"eligible": 42, "observed": 6, "evidence_class": "HISTORICAL"},
            "authenticated_codex_qps_pairs": {"eligible": 1, "observed": None, "evidence_class": "UNKNOWN"}}})
        return {"sources": {"queue": "queue.json", "series": "series.json", "jade": "jade.json", "superstitch": "stitch.json"}}

    def point(self, key, total=5, complete=1, **identity):
        return {"key": key, "tree": HEAD, "evidence_class": "MEASURED",
                "metrics": {"bd_total": total, "bd_complete": complete}, **identity}

    def cpq_series(self, entries):
        data = atlas.burndown(self.root, self.cohort_profile(entries))
        return next(c for c in data["cohorts"] if c["id"] == "CPQ_CANONICAL")["series"]

    def test_equal_denominator_without_cohort_identity_is_not_comparable(self):
        points = self.cpq_series([self.point("N"), self.point("N+1", complete=2)])
        self.assertFalse(points[1]["comparable"])

    def test_changed_cohort_with_equal_size_is_not_comparable(self):
        identity = {"cohort_hash": "a" * 64, "metric_config_hash": "c" * 64,
                    "unit": "ledger items", "metric": "bd_complete"}
        points = self.cpq_series([self.point("N", **identity),
                                  self.point("N+1", **{**identity, "cohort_hash": "b" * 64})])
        self.assertFalse(points[1]["comparable"])

    def test_changed_instrument_is_not_comparable(self):
        identity = {"cohort_hash": "a" * 64, "metric_config_hash": "c" * 64,
                    "unit": "ledger items", "metric": "bd_complete"}
        points = self.cpq_series([self.point("N", **identity),
                                  self.point("N+1", **{**identity, "metric_config_hash": "d" * 64})])
        self.assertFalse(points[1]["comparable"])

    def test_explicit_matched_identity_and_denominator_can_be_compared(self):
        identity = {"cohort_hash": "a" * 64, "metric_config_hash": "c" * 64,
                    "unit": "ledger items", "metric": "bd_complete"}
        points = self.cpq_series([self.point("N", **identity), self.point("N+1", complete=2, **identity)])
        self.assertFalse(points[0]["comparable"])
        self.assertTrue(points[1]["comparable"])

    def test_denominator_change_breaks_comparability_even_if_declared_cohort_matches(self):
        identity = {"cohort_hash": "a" * 64, "metric_config_hash": "c" * 64,
                    "unit": "ledger items", "metric": "bd_complete"}
        points = self.cpq_series([self.point("N", **identity), self.point("N+1", total=6, **identity)])
        self.assertFalse(points[1]["comparable"])

    def test_missing_denominator_remains_a_gap_in_sequence(self):
        points = self.cpq_series([self.point("N"), self.point("N+1", total=None, complete=None),
                                  self.point("N+2", complete=2)])
        self.assertEqual([p["label"] for p in points], ["N", "N+1", "N+2"])
        self.assertIsNone(points[1]["eligible"])
        self.assertIsNone(points[1]["value"])
        self.assertFalse(points[2]["comparable"])

    def test_gap_prevents_a_comparison_bridge_even_for_same_cohort(self):
        identity = {"cohort_hash": "a" * 64, "metric_config_hash": "c" * 64,
                    "unit": "ledger items", "metric": "bd_complete"}
        points = self.cpq_series([self.point("N", **identity), self.point("N+1", complete=None, **identity),
                                  self.point("N+2", complete=2, **identity)])
        self.assertIsNone(points[1]["value"])
        self.assertFalse(points[1]["comparable"])
        self.assertFalse(points[2]["comparable"])

    def test_cohorts_and_unknown_values_are_never_summed_into_global_progress(self):
        data = atlas.burndown(self.root, self.cohort_profile([self.point("N")]))
        self.assertIsNone(data["global_completion_pct"])
        self.assertIsNone(data["accepted_root_closure_delta"])
        pair = next(c for c in data["cohorts"] if c["id"] == "AUTHENTICATED_PAIR")
        self.assertIsNone(pair["done"])
        jade = next(c for c in data["cohorts"] if c["id"] == "JADE_N11_OWNER_ACTIONS")
        self.assertIsNone(jade["series"][0]["value"])
        self.assertNotEqual(jade["series"][0]["cohort_sha"], jade["series"][1]["cohort_sha"])
        self.assertFalse(jade["series"][1]["comparable"])


class BundleIntegrityTests(FixtureCase):
    def setUp(self):
        super().setUp()
        self.source = self.root / "source"
        self.bundle = self.root / "bundle"
        self.source.mkdir()
        self.bundle.mkdir()
        (self.source / "source.json").write_text('{"version":1}\n', encoding="utf-8")
        source_hashes = {"source.json": atlas.digest((self.source / "source.json").read_bytes())}
        self.model = {"schema": atlas.SCHEMA, "source": {"head_sha": HEAD, "dirty": False,
                      "source_files_sha256": source_hashes, "source_digest": atlas.digest(atlas.canonical(source_hashes))},
                      "authority_transfer": False, "remote_dispatch": False, "merge_admission": "HOLD"}
        members = {"index.html": b"<html></html>", "style.css": b"body {}", "app.js": b"'use strict';",
                   "atlas.json": atlas.canonical(self.model), "inventory.json": b"{}\n",
                   "burndown.json": b"{}\n", "broker-plan.json": b"{}\n", "source-check.json": b"{}\n"}
        for name, raw in members.items():
            (self.bundle / name).write_bytes(raw)
        self.manifest = {"schema": atlas.MANIFEST_SCHEMA, "source_sha": HEAD, "source_dirty": False,
                         "source_digest": self.model["source"]["source_digest"],
                         "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY", "authority_transfer": False,
                         "remote_dispatch": False, "merge_admission": "HOLD",
                         "files_sha256": {name: atlas.digest(raw) for name, raw in members.items()},
                         "files_bytes": {name: len(raw) for name, raw in members.items()}}
        self.save_manifest()
        # Every negative mutation starts from a bundle accepted by the verifier.
        atlas.verify_bundle(self.bundle, HEAD)

    def save_manifest(self):
        (self.bundle / "manifest.json").write_bytes(atlas.canonical(self.manifest))

    def reseal_model_member(self):
        raw = atlas.canonical(self.model)
        (self.bundle / "atlas.json").write_bytes(raw)
        self.manifest["files_sha256"]["atlas.json"] = atlas.digest(raw)
        self.manifest["files_bytes"]["atlas.json"] = len(raw)
        self.save_manifest()

    def test_valid_bundle_preserves_declared_identity(self):
        self.assertEqual(atlas.verify_bundle(self.bundle, HEAD)["source_sha"], HEAD)

    def test_changed_member_is_detected(self):
        (self.bundle / "app.js").write_text("changed();", encoding="utf-8")
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)

    def test_missing_and_unmanifested_members_are_detected(self):
        (self.bundle / "unexpected.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)
        (self.bundle / "unexpected.txt").unlink()
        (self.bundle / "style.css").unlink()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)

    def test_manifest_cannot_change_authority_or_head(self):
        self.manifest["remote_dispatch"] = True
        self.save_manifest()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)
        self.manifest["remote_dispatch"] = False
        self.save_manifest()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle, "b" * 40)

    def test_manifest_source_digest_must_match_model(self):
        self.manifest["source_digest"] = "f" * 64
        self.save_manifest()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)

    def test_model_source_map_must_match_its_digest_even_if_member_resealed(self):
        self.model["source"]["source_files_sha256"]["source.json"] = "e" * 64
        self.reseal_model_member()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)

    def test_same_head_source_byte_drift_is_detected(self):
        atlas.verify_bundle(self.bundle, HEAD, source_root=self.source)
        (self.source / "source.json").write_text('{"version":2}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle, HEAD, source_root=self.source)

    def test_manifest_traversal_cannot_read_an_outside_member(self):
        outside = self.root / "outside.txt"
        outside.write_bytes(b"outside")
        self.manifest["files_sha256"]["../outside.txt"] = atlas.digest(b"outside")
        self.manifest["files_bytes"]["../outside.txt"] = 7
        self.save_manifest()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)

    def test_source_map_traversal_is_rejected_even_with_consistent_digest(self):
        self.model["source"]["source_files_sha256"] = {"../outside.txt": atlas.digest(b"outside")}
        self.model["source"]["source_digest"] = atlas.digest(atlas.canonical(self.model["source"]["source_files_sha256"]))
        self.manifest["source_digest"] = self.model["source"]["source_digest"]
        self.reseal_model_member()
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle)

    def test_dirty_source_is_acceptable_for_local_review_but_not_clean_publication(self):
        self.model["source"]["dirty"] = True
        self.manifest["source_dirty"] = True
        self.reseal_model_member()
        atlas.verify_bundle(self.bundle)
        with self.assertRaises(ValueError):
            atlas.verify_bundle(self.bundle, require_clean=True)


class RuntimeIntegrationBoundaryTests(FixtureCase):
    """Narrow integration contracts for themes, snapshot scope and adapters."""

    def test_graph_theme_variants_share_semantics_and_canonical_mermaid_hash(self):
        import xml.etree.ElementTree as ET

        graph = atlas.graph_record("theme-proof", "One semantic graph", "FUNCTIONAL_IO",
            [{"id": "source", "label": "Declared input"},
             {"id": "qualified", "label": "Verified output", "native_qualified": True},
             {"id": "blocked", "label": "Unmet prerequisite", "status": "BLOCKED"}],
            [{"from": "source", "to": "qualified", "kind": "ARTIFACT_HANDOFF", "binding": "LOCAL_CONTRACT"},
             {"from": "source", "to": "blocked", "kind": "DEPENDENCY", "binding": "DECLARED"}],
            "source.json")
        original = copy.deepcopy(graph)
        mermaid = atlas.graph_mermaid(graph)
        expected = atlas.digest(mermaid.encode())
        variants = {theme: ET.fromstring(atlas.graph_svg(graph, theme)) for theme in ("light", "dark")}
        ns = {"svg": "http://www.w3.org/2000/svg"}
        for theme, svg in variants.items():
            metadata = svg.find("svg:metadata", ns).text
            self.assertIn(expected, metadata)
            self.assertIn("theme: " + theme, metadata)
        self.assertNotEqual(variants["light"].find("svg:rect", ns).get("fill"),
                            variants["dark"].find("svg:rect", ns).get("fill"))
        titles = lambda svg: [group.find("svg:title", ns).text for group in svg.findall("svg:g", ns)]
        self.assertEqual(titles(variants["light"]), titles(variants["dark"]))
        self.assertEqual([p.get("d") for p in variants["light"].findall("svg:path", ns)],
                         [p.get("d") for p in variants["dark"].findall("svg:path", ns)])
        self.assertEqual(graph, original)
        self.assertEqual(atlas.graph_mermaid(graph), mermaid)

    def test_mixed_runtime_checkout_is_rejected_before_source_or_output_access(self):
        self.assertEqual(atlas.runtime_root(atlas.ROOT / "."), atlas.ROOT)
        outside_output = self.root / "uncreated-output"
        for operation in (
            lambda: atlas.runtime_root(self.root),
            lambda: atlas.source_model(self.root, HEAD),
            lambda: atlas.build(self.root, outside_output, HEAD),
            lambda: atlas.run_local(self.root, outside_output, HEAD),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "this checkout"):
                operation()
        self.assertFalse(outside_output.exists())

    def snapshot_profile(self):
        profile = self.profile()
        self.write("data/calibration.csv", "name,value\npressure,4\n")
        self.write("data/optional.json", {"value": 2})
        profile["blocks"][0]["inputs"] += [
            self.port(id="calibration", path="data/calibration.csv", kind="text", schema=None),
            self.port(id="optional", path="data/optional.json", required=False, schema=None),
            self.port(id="absent", path="data/absent.json", required=False, schema=None),
        ]
        self.write(atlas.PROFILE, profile)
        return profile

    def test_snapshot_includes_declared_inputs_and_mission_assets_with_explicit_scope(self):
        profile = self.snapshot_profile()
        for name, content in {
            "mission-control/cards/style.css": "body{}",
            "mission-control/cards/icon.bin": b"\x00\x01",
            "tools/entry.py": "def main(): pass\n",
            "docs/sequence.mmd": "flowchart TD\n A-->B\n",
            ".github/workflows/extra.yml": "jobs: {}\n",
            "docs/unrelated.txt": "outside declared snapshot scope",
            "node_modules/ignored.py": "pass\n",
            "mission-control/__pycache__/cache.pyc": b"cache",
        }.items():
            self.write(name, content)
        paths = set(atlas.source_snapshot_paths(self.root, profile))
        self.assertTrue({"data/calibration.csv", "data/optional.json", "mission-control/cards/style.css",
                         "mission-control/cards/icon.bin", "tools/entry.py", "docs/sequence.mmd",
                         ".github/workflows/extra.yml", atlas.PROFILE} <= paths)
        self.assertTrue({"data/absent.json", "docs/unrelated.txt", "node_modules/ignored.py",
                         "mission-control/__pycache__/cache.pyc"}.isdisjoint(paths))

    def test_new_mission_control_source_invalidates_previously_verified_membership(self):
        profile = self.snapshot_profile()
        hashes = {name: atlas.digest((self.root / name).read_bytes())
                  for name in atlas.source_snapshot_paths(self.root, profile)}
        source_digest = atlas.digest(atlas.canonical(hashes))
        model = {"schema": atlas.SCHEMA, "source": {"head_sha": HEAD, "dirty": False,
                 "inventory_policy": atlas.SNAPSHOT_POLICY, "source_files_sha256": hashes,
                 "source_digest": source_digest}, "authority_transfer": False,
                 "remote_dispatch": False, "merge_admission": "HOLD"}
        bundle_directory = tempfile.TemporaryDirectory()
        self.addCleanup(bundle_directory.cleanup)
        bundle = Path(bundle_directory.name)
        members = {"index.html": b"<html></html>", "style.css": b"body{}", "app.js": b"'use strict';",
                   "atlas.json": atlas.canonical(model), "inventory.json": b"{}", "burndown.json": b"{}",
                   "broker-plan.json": b"{}", "source-check.json": b"{}"}
        for name, raw in members.items():
            (bundle / name).write_bytes(raw)
        manifest = {"schema": atlas.MANIFEST_SCHEMA, "source_sha": HEAD, "source_dirty": False,
                    "source_digest": source_digest, "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY",
                    "authority_transfer": False, "remote_dispatch": False, "merge_admission": "HOLD",
                    "files_sha256": {name: atlas.digest(raw) for name, raw in members.items()},
                    "files_bytes": {name: len(raw) for name, raw in members.items()}}
        (bundle / "manifest.json").write_bytes(atlas.canonical(manifest))
        atlas.verify_bundle(bundle, HEAD, source_root=self.root)
        self.write("mission-control/new-source.json", {"new": "evidence"})
        with self.assertRaisesRegex(ValueError, "source inventory membership changed"):
            atlas.verify_bundle(bundle, HEAD, source_root=self.root)

    def test_local_adapter_passes_policy_and_checks_portal_outputs_after_zero_exit(self):
        from types import SimpleNamespace
        from unittest import mock

        class AdapterObserved(RuntimeError):
            """Stop after the real registered adapter; no fake completed DAG."""

        real_read = atlas.read_json
        policy_path = "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json"
        configured = {**real_read(atlas.ROOT, policy_path), "default_max_pending": 3}

        def read_with_policy(root, name):
            return copy.deepcopy(configured) if name == policy_path else real_read(root, name)

        for case, expected in (("valid", AdapterObserved), ("missing-html", ValueError), ("wrong-hash", ValueError)):
            with self.subTest(case=case):
                out = self.root / case

                def local_driver(task_rows, handlers, **options):
                    self.assertEqual(options["policy"], configured)
                    self.assertEqual(options["max_pending"], 3)
                    self.assertEqual(options["workers"], 1)
                    portal_task = next(row for row in task_rows if row["id"] == "portal")
                    self.assertIn("build/assemble", portal_task["read_paths"])
                    handlers["portal"]()
                    raise AdapterObserved("portal callback checked")

                def local_process(command, **options):
                    self.assertEqual(Path(command[1]).name, "pages_portal.py")
                    self.assertEqual(command[command.index("--sha") + 1], HEAD)
                    portal = Path(command[command.index("--out") + 1])
                    portal.mkdir()
                    raw = b"<html>Local package</html>"
                    if case != "missing-html":
                        (portal / "index.html").write_bytes(raw)
                    manifest = {"schema": "codepurple.pages.readonly/v1", "source_git_sha": HEAD,
                                "merge_authorized": False, "security_waiver": False, "qps_owner_decision": "DEFER",
                                "public_files_sha256": {"index.html": "0" * 64 if case == "wrong-hash" else atlas.digest(raw)}}
                    (portal / "site-manifest.json").write_bytes(atlas.canonical(manifest))
                    return SimpleNamespace(returncode=0, stdout="", stderr="")

                with mock.patch.object(atlas, "read_json", side_effect=read_with_policy), \
                     mock.patch.object(atlas, "git", return_value=HEAD), \
                     mock.patch.object(atlas, "module", return_value=SimpleNamespace(run_local=local_driver)), \
                     mock.patch.object(atlas.subprocess, "run", side_effect=local_process):
                    with self.assertRaises(expected):
                        atlas.run_local(atlas.ROOT, out, HEAD, workers=1)


class LocalReceiptBoundaryTests(FixtureCase):
    def measured_receipt(self, fail=False, validator_phase=None):
        """Exercise the real broker; bind its measurements to a fixture source."""
        source = self.write("input.txt", "fixture source v1")
        tasks = [
            {"id": identity, "repo": "example/project", "needs": needs,
             "read_paths": ["input.txt"], "write_paths": ["output/" + identity],
             "estimated_seconds": None, "input_contract": {"required_paths": ["input.txt"]},
             "output_contract": {"required_result_keys": ["status"]}}
            for identity, needs in (("produce", []), ("consume", ["produce"]))
        ]
        def produce():
            if fail:
                raise ValueError("fixture producer failed")
            return {"status": "produced"}
        broker = atlas.module("local_receipt_test_broker", MODULE_PATH.with_name("broker.py"))
        # Exercise the real executor with a strictly advancing logical clock.
        # Windows can report identical monotonic times for these tiny handlers;
        # that would make a purported timestamp corruption a no-op.
        with mock.patch.object(broker.time, "monotonic", new=itertools.count().__next__):
            receipt = broker.run_local(tasks, {"produce": produce, "consume": lambda: {"status": "consumed"}},
                                       workers=2, max_pending=1, root=self.root,
                                       input_validator=(lambda task: False) if validator_phase == "input" else None,
                                       output_validator=(lambda task, result: False) if validator_phase == "output" else None)
        source_digest = atlas.digest(source.read_bytes())
        receipt.update(source_sha=HEAD, source_digest=source_digest, source_changed_during_run=False)
        model = {"source": {"head_sha": HEAD, "source_digest": source_digest}, "broker": {"tasks": tasks}}
        return receipt, model

    def test_actual_successful_and_failed_terminal_receipts_are_accepted(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                receipt, model = self.measured_receipt(fail)
                self.assertIs(atlas.validate_local_receipt(receipt, model), receipt)
                self.assertEqual(receipt["success"], not fail)
                expected_states = {"failed", "blocked"} if fail else {"succeeded"}
                self.assertEqual({row["state"] for row in receipt["tasks"].values()}, expected_states)
                self.assertEqual(receipt["metrics"]["ready_wait_sample_count"], 1 if fail else 2)

    def test_forged_state_counts_percentiles_and_dependencies_are_rejected(self):
        original, model = self.measured_receipt()
        cases = {
            "pending": lambda r: r["tasks"]["produce"].update(state="pending"),
            "sample-count": lambda r: r["metrics"].update(ready_wait_sample_count=99),
            "negative-percentile": lambda r: r["metrics"].update(ready_wait_p95_seconds=-1),
            "nonfinite-percentile": lambda r: r["metrics"].update(ready_wait_p50_seconds=float("nan")),
            "false-success": lambda r: r.update(success=False),
            "false-count": lambda r: r["metrics"].update(succeeded=0),
            "changed-dependency": lambda r: r["tasks"]["consume"].update(needs=[]),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                receipt = copy.deepcopy(original)
                corrupt(receipt)
                with self.assertRaises(ValueError):
                    atlas.validate_local_receipt(receipt, model)

    def test_source_changes_and_explicit_drift_prevent_receipt_attachment(self):
        receipt, original_model = self.measured_receipt()
        changed = self.write("input.txt", "fixture source v2")
        changed_model = copy.deepcopy(original_model)
        changed_model["source"]["source_digest"] = atlas.digest(changed.read_bytes())
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            atlas.validate_local_receipt(receipt, changed_model)
        drifted = copy.deepcopy(receipt)
        drifted["source_changed_during_run"] = True
        with self.assertRaisesRegex(ValueError, "source drift"):
            atlas.validate_local_receipt(drifted, original_model)

    def test_real_input_and_output_contract_failure_timelines_are_accepted(self):
        for phase in ("input", "output"):
            with self.subTest(phase=phase):
                receipt, model = self.measured_receipt(validator_phase=phase)
                self.assertIs(atlas.validate_local_receipt(receipt, model), receipt)
                self.assertEqual(receipt["tasks"]["produce"]["error"]["phase"], phase + "_contract")

    def test_timestamps_must_be_finite_in_run_and_chronological(self):
        original, model = self.measured_receipt()
        for field, value in (("started_at_seconds", float("nan")),
                             ("finished_at_seconds", float("inf")),
                             ("ready_at_seconds", -1),
                             ("verify_started_at_seconds", original["metrics"]["elapsed_seconds"] + 1),
                             ("execution_finished_at_seconds", 0)):
            with self.subTest(field=field, value=value):
                receipt = copy.deepcopy(original)
                receipt["tasks"]["produce"][field] = value
                with self.assertRaises(ValueError):
                    atlas.validate_local_receipt(receipt, model)

    def test_duration_arithmetic_cannot_be_changed_without_timestamps(self):
        original, model = self.measured_receipt()
        for field in ("execution_seconds", "verification_seconds"):
            with self.subTest(field=field):
                receipt = copy.deepcopy(original)
                receipt["tasks"]["consume"][field] += 1
                with self.assertRaisesRegex(ValueError, "duration"):
                    atlas.validate_local_receipt(receipt, model)

    def test_child_cannot_start_before_verified_parent_even_with_coherent_local_timing(self):
        receipt, model = self.measured_receipt()
        child = receipt["tasks"]["consume"]
        shift = child["started_at_seconds"]
        for field in ("started_at_seconds", "execution_finished_at_seconds", "verify_started_at_seconds", "finished_at_seconds"):
            child[field] -= shift
        child["ready_at_seconds"] = 0.0
        child["ready_wait_seconds"] = 0.0
        for event in child["events"]:
            event["at_seconds"] = max(0.0, event["at_seconds"] - shift)
        waits = sorted(row["ready_wait_seconds"] for row in receipt["tasks"].values())
        receipt["metrics"].update(ready_wait_p50_seconds=waits[0], ready_wait_p95_seconds=waits[-1])
        with self.assertRaisesRegex(ValueError, "verified predecessor"):
            atlas.validate_local_receipt(receipt, model)

    def test_trace_events_cannot_be_reordered_relabelled_or_removed(self):
        original, model = self.measured_receipt()
        for change in ("reorder", "relabel", "remove", "terminal-time"):
            with self.subTest(change=change):
                receipt = copy.deepcopy(original)
                events = receipt["tasks"]["produce"]["events"]
                if change == "reorder":
                    events[1], events[2] = events[2], events[1]
                elif change == "relabel":
                    events[-2]["state"] = "running"
                elif change == "remove":
                    events.clear()
                else:
                    events[-1]["at_seconds"] = receipt["metrics"]["elapsed_seconds"]
                with self.assertRaises(ValueError):
                    atlas.validate_local_receipt(receipt, model)

    def test_blocked_task_requires_real_failed_ancestor_and_no_execution(self):
        original, model = self.measured_receipt(fail=True)
        for change in ("no-blocker", "wrong-blocker", "execution", "early-block"):
            with self.subTest(change=change):
                receipt = copy.deepcopy(original)
                child = receipt["tasks"]["consume"]
                if change == "no-blocker":
                    child["error"]["blocked_by"] = []
                elif change == "wrong-blocker":
                    child["error"]["blocked_by"] = ["consume"]
                elif change == "execution":
                    child["started_at_seconds"] = 0.0
                else:
                    child["finished_at_seconds"] = child["events"][-1]["at_seconds"] = 0.0
                with self.assertRaises(ValueError):
                    atlas.validate_local_receipt(receipt, model)

    def test_terminal_result_and_failure_phase_must_match_trace(self):
        receipt, model = self.measured_receipt()
        receipt["tasks"]["produce"]["result"] = {}
        with self.assertRaisesRegex(ValueError, "result contract"):
            atlas.validate_local_receipt(receipt, model)
        receipt, model = self.measured_receipt(fail=True)
        receipt["tasks"]["produce"]["error"]["phase"] = "output_contract"
        with self.assertRaisesRegex(ValueError, "failure phase"):
            atlas.validate_local_receipt(receipt, model)

    def test_real_empty_broker_receipt_has_no_execution_credit(self):
        broker = atlas.module("empty_receipt_broker", MODULE_PATH.with_name("broker.py"))
        receipt = broker.run_local([], {}, root=self.root)
        receipt.update(source_sha=HEAD, source_digest="d" * 64, source_changed_during_run=False)
        model = {"source": {"head_sha": HEAD, "source_digest": "d" * 64}, "broker": {"tasks": []}}
        self.assertIs(atlas.validate_local_receipt(receipt, model), receipt)
        self.assertEqual(receipt["metrics"]["succeeded"], 0)

    def test_reported_concurrency_cannot_understate_real_overlapping_tasks(self):
        import threading
        _, model = self.measured_receipt()
        for task in model["broker"]["tasks"]:
            task["needs"] = []
        barrier = threading.Barrier(2)
        def overlapping():
            barrier.wait(timeout=5)
            return {"status": "produced"}
        broker = atlas.module("overlap_receipt_broker", MODULE_PATH.with_name("broker.py"))
        with mock.patch.object(broker.time, "monotonic", new=itertools.count().__next__):
            receipt = broker.run_local(model["broker"]["tasks"], {"produce": overlapping, "consume": overlapping},
                                       workers=2, max_pending=2, root=self.root)
        receipt.update(source_sha=HEAD, source_digest=model["source"]["source_digest"], source_changed_during_run=False)
        self.assertIs(atlas.validate_local_receipt(receipt, model), receipt)
        self.assertEqual(receipt["metrics"]["max_running"], 2)
        for reported in (0, 1):
            with self.subTest(reported=reported):
                forged = copy.deepcopy(receipt)
                forged["metrics"]["max_running"] = reported
                with self.assertRaisesRegex(ValueError, "concurrency below observed"):
                    atlas.validate_local_receipt(forged, model)


class PortableGraphArtifactTests(FixtureCase):
    def assert_portable_stem(self, stem):
        self.assertIsInstance(stem, str)
        self.assertTrue(stem.isascii())
        self.assertRegex(stem, r"^[A-Za-z0-9_-]+-[0-9a-f]{12}$")
        self.assertLessEqual(len(stem), 80 + 1 + 12)
        self.assertNotRegex(stem, r'[<>:"/\\|?*\x00-\x1f]')
        self.assertFalse(stem.endswith((".", " ")))
        reserved = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)),
                    *("LPT" + str(i) for i in range(1, 10))}
        self.assertNotIn(stem.upper(), reserved)

    def test_awkward_canonical_ids_produce_bounded_portable_artifact_stems(self):
        identities = ["lane-3p*", "name:variant", "a/b", "a\\b", "../escape", "../../",
                      "日本語/JADÉ", "CON", "con.txt", "NUL", "COM1", "LPT9", ".", "..",
                      "trailing...", "trailing ", "line\nbreak", "x" * 400]
        for identity in identities:
            with self.subTest(identity=identity):
                stem = atlas.artifact_stem(identity)
                self.assert_portable_stem(stem)
                for extension in (".mmd", ".light.svg", ".dark.svg"):
                    member = "graphs/" + stem + extension
                    self.assertEqual(atlas.safe_path(self.root, member).parent, self.root / "graphs")
                    self.assertNotRegex(member, r'[<>:"\\|?*\x00-\x1f]')
        for invalid in ("", None, 0, False, {}, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    atlas.artifact_stem(invalid)

    def test_normalized_collisions_case_variants_and_long_ids_stay_distinct(self):
        identities = ["3P*", "3P?", "3P:", "3P/", "3P\\", "3P", "3p", "CON", "con",
                      "é", "e\u0301", ".", "..", "x" * 400 + "a", "x" * 400 + "b"]
        stems = {identity: atlas.artifact_stem(identity) for identity in identities}
        self.assertEqual(len({value.casefold() for value in stems.values()}), len(identities))
        self.assertEqual(stems, {identity: atlas.artifact_stem(identity) for identity in reversed(identities)})
        for stem in stems.values():
            self.assert_portable_stem(stem)

    def test_safe_filenames_preserve_original_3p_star_mermaid_labels_and_identity(self):
        graph = atlas.graph_record("lane-3p*", "Canonical 3P* lane", "LANE",
                                   [{"id": "3P*", "label": "3P*", "role": "source"}], [], "source.json")
        before = atlas.graph_mermaid(graph)
        stem = atlas.artifact_stem(graph["id"])
        self.assertNotIn("*", stem)
        graph["mermaid_path"] = "graphs/" + stem + ".mmd"
        graph["paths"] = {"svg_light": "graphs/" + stem + ".light.svg",
                          "svg_dark": "graphs/" + stem + ".dark.svg"}
        self.assertEqual(graph["id"], "lane-3p*")
        self.assertEqual(graph["nodes"][0]["id"], "3P*")
        self.assertIn("Canonical 3P* lane", before)
        self.assertIn('["3P* · source"]', before)
        self.assertEqual(atlas.graph_mermaid(graph), before)
        expected_hash = atlas.digest(before.encode())
        for theme in ("light", "dark"):
            self.assertIn("canonical Mermaid SHA-256: " + expected_hash, atlas.graph_svg(graph, theme))

    def test_artifact_member_gate_rejects_nonportable_names_before_file_access(self):
        for name in ("graphs/diagram-123.dark.svg", "graphs/CON-safe.svg", "graphs/展示.svg"):
            with self.subTest(valid=name):
                self.assertEqual(atlas.artifact_path(self.root, name), self.root / name)
        invalid_names = ["", ".", "..", "../escape.svg", "/absolute.svg", "C:/absolute.svg",
                         "graphs//empty.svg", "graphs/./dot.svg", "graphs/../escape.svg", "graphs/",
                         "graphs/lane-3p*.svg", "graphs/name:variant.svg", "graphs/name?.svg",
                         "graphs/<name>.svg", "graphs/name|variant.svg", "graphs\\name.svg",
                         "graphs/line\nbreak.svg", "graphs/null\x00.svg", "graphs/file.svg.",
                         "graphs/file.svg ", "graphs/trailing./file.svg", "graphs/trailing /file.svg",
                         "graphs/CON", "graphs/con.svg", "graphs/PRN.txt", "graphs/aux.tar.svg",
                         "graphs/NUL.svg", "graphs/COM1.svg", "graphs/lpt9.dark.svg"]
        for name in invalid_names:
            with self.subTest(invalid=name):
                with self.assertRaises(ValueError):
                    atlas.artifact_path(self.root, name)
        self.assertEqual(list(self.root.iterdir()), [])


class CliPlanIdentityTests(FixtureCase):
    def setUp(self):
        super().setUp()
        policy_path = "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json"
        self.write(policy_path, atlas.read_json(atlas.ROOT, policy_path))
        self.write("src/worker.py", "def emit():\n    return {}\n")
        identities = ("source-contracts", "method-atlas", "burndown", "superstitch",
                      "convergence", "orchestration-view", "pages-portal")
        self.write(atlas.PROFILE, {"repository": "example/project", "blocks": [
            {"id": identity, "source_path": "src/worker.py", "inputs": []} for identity in identities]})

    def test_repeated_no_snapshot_cli_plans_are_identical_without_runtime_timestamp(self):
        from contextlib import redirect_stdout
        import io
        from types import SimpleNamespace
        from unittest import mock

        broker = atlas.module("cli_plan_test_broker", MODULE_PATH.with_name("broker.py"))
        clocks = iter(("2026-10-19T00:00:00Z", "2026-10-20T12:00:00Z"))
        observed_clocks = []

        def clocked_plan(tasks, snapshot, policy):
            self.assertIsNone(snapshot)
            result = broker.plan(tasks, snapshot, policy, now=next(clocks))
            observed_clocks.append(result["generated_at"])
            return result

        outputs = []
        with mock.patch.object(atlas, "ROOT", self.root), mock.patch.object(atlas, "git", return_value=HEAD), \
             mock.patch.object(atlas, "module", return_value=SimpleNamespace(plan=clocked_plan)), \
             redirect_stdout(io.StringIO()):
            for name in ("first", "second"):
                out = self.root / name
                self.assertEqual(atlas.main(["plan", "--root", str(self.root), "--out", str(out), "--head", HEAD]), 0)
                outputs.append((out / "broker-plan.json").read_bytes())
        self.assertNotEqual(*observed_clocks)
        self.assertEqual(*outputs)
        plan = json.loads(outputs[0])
        self.assertIsNone(plan["generated_at"])
        self.assertEqual(plan["time_basis"], "DETERMINISTIC_SOURCE_PLAN_NO_RUNTIME_OBSERVATION")
        self.assertFalse(plan["dispatch_authorized"])

    def test_mismatched_valid_head_is_rejected_before_plan_or_output_creation(self):
        from contextlib import redirect_stderr, redirect_stdout
        import io
        from unittest import mock

        out = self.root / "rejected-plan"
        error = io.StringIO()
        with mock.patch.object(atlas, "ROOT", self.root), mock.patch.object(atlas, "git", return_value=HEAD), \
             mock.patch.object(atlas, "module") as load_broker, \
             redirect_stdout(io.StringIO()), redirect_stderr(error):
            result = atlas.main(["plan", "--root", str(self.root), "--out", str(out), "--head", "b" * 40])
        self.assertEqual(result, 1)
        self.assertIn("checkout/head mismatch", json.loads(error.getvalue())["error"])
        load_broker.assert_not_called()
        self.assertFalse(out.exists())


class MultilanguageInventoryTests(FixtureCase):
    def rows(self):
        result = atlas.inventory(self.root)
        return result, {row["path"]: row for row in result["source_assets"]}

    def test_languages_roles_and_original_inventory_keys_are_preserved(self):
        for suffix in ("js", "jsx", "mjs", "cjs", "ts", "tsx", "sh", "bash", "ps1", "psm1"):
            self.write("src/worker." + suffix, "no code is executed during discovery")
        self.write("src/types.d.ts", "declare const value: string;")
        self.write("tests/worker.test.js", "throw new Error('must not run');")
        self.write("config/settings.toml", "workers = 2\n")
        self.write("config/data.json", {"workers": 2})
        self.write("config/values.yaml", "workers: 2\n")
        self.write("entry.py", "def main(): pass\nif __name__ == '__main__': main()\n")
        inv, rows = self.rows()
        self.assertEqual((inv["python_module_count"], inv["python_with_main"]), (1, 1))
        self.assertEqual(inv["source_asset_count"], 16)
        self.assertEqual(rows["src/worker.ts"]["language"], "typescript")
        self.assertEqual(rows["src/worker.ps1"]["language"], "powershell")
        self.assertEqual(rows["src/types.d.ts"]["role"], "SUPPORT_DECLARATION")
        self.assertEqual(rows["tests/worker.test.js"]["role"], "TEST_SUPPORT")
        self.assertEqual(rows["config/data.json"]["role"], "CONFIG_OR_DATA")
        self.assertTrue(all(row["runtime_reachability"] == "UNKNOWN" for row in rows.values()))

    def test_package_composite_and_workflow_descriptors_remain_declarations(self):
        self.write("package.json", {"scripts": {"build": "node src/build.mjs", "test": "node --test"}})
        self.write(".github/actions/example/action.yml", "runs:\n  using: composite\n  steps:\n    - run: ./tools/task.sh\n      shell: bash\n")
        self.write(".github/workflows/build.yml", "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm run build\n")
        self.write("pyproject.toml", "[project]\nname='sample'\n")
        self.write("src/build.mjs", "throw new Error('discovery must not execute');")
        inv, rows = self.rows()
        self.assertEqual(rows["package.json"]["declared_script_names"], ["build", "test"])
        self.assertEqual(rows[".github/actions/example/action.yml"]["descriptor"], "GITHUB_COMPOSITE_ACTION")
        self.assertEqual(rows["pyproject.toml"]["descriptor"], "PYTHON_PROJECT")
        self.assertEqual(inv["workflow_count"], 1)
        self.assertEqual(rows["src/build.mjs"]["membership"], "STATIC_REFERENCE_CANDIDATE")

    def test_registered_sources_reference_candidates_and_unknown_are_distinct(self):
        profile = self.profile()
        self.write(atlas.PROFILE, profile)
        self.write("src/consumer.ts", "import './peer.ts';\n// Documentation example: src/worker.py\n")
        self.write("src/peer.ts", "export const n = 1;")
        self.write("src/loose.js", "export const n = 2;")
        _, rows = self.rows()
        self.assertEqual(rows["src/worker.py"]["membership"], "REGISTERED_PROCESS_SOURCE")
        self.assertEqual(rows["src/worker.py"]["registered_entrypoints"], [
            {"block_id": "producer", "entrypoint": "emit"}, {"block_id": "consumer", "entrypoint": "emit"}])
        self.assertEqual(rows["src/peer.ts"]["membership"], "STATIC_REFERENCE_CANDIDATE")
        self.assertEqual(rows["src/loose.js"]["membership"], "UNCLASSIFIED_NO_LITERAL_REFERENCE")
        self.assertEqual(rows["src/loose.js"]["runtime_reachability"], "UNKNOWN")

    def test_ambiguous_dynamic_and_escaping_references_do_not_claim_reachability(self):
        self.write("worker.js", "")
        self.write("src/worker.js", "")
        self.write("src/caller.js", "require('worker.js'); import(target); const x = '${where}';\n// ../../../outside.py\n")
        _, rows = self.rows()
        caller = rows["src/caller.js"]
        ref = next(item for item in caller["references"] if item["literal"] == "worker.js")
        self.assertEqual(ref["resolution"], "AMBIGUOUS_LOCAL_LITERAL")
        self.assertEqual(ref["targets"], ["src/worker.js", "worker.js"])
        self.assertGreaterEqual(caller["unresolved_dynamic_markers"], 2)
        escape = next(item for item in caller["references"] if "outside" in item["literal"])
        self.assertEqual(escape["targets"], [])
        self.assertEqual(caller["runtime_reachability"], "UNKNOWN")

    def test_reference_limits_non_utf8_and_bad_descriptors_are_reported(self):
        self.write("big.json", b" " * (atlas.REFERENCE_SCAN_BYTES + 1))
        self.write("binary.js", b"\xff\xfe")
        self.write("many.js", "\n".join("'target%d.js'" % n for n in range(atlas.REFERENCE_SCAN_LIMIT + 1)))
        self.write("package.json", "{broken")
        self.write("action.yml", "runs: [unclosed")
        _, rows = self.rows()
        self.assertEqual(rows["big.json"]["reference_scan"], "SIZE_LIMIT_NOT_SCANNED")
        self.assertEqual(rows["binary.js"]["reference_scan"], "NON_UTF8_NOT_SCANNED")
        self.assertEqual(rows["many.js"]["reference_scan"], "REFERENCE_LIMIT_TRUNCATED")
        self.assertEqual(len(rows["many.js"]["references"]), atlas.REFERENCE_SCAN_LIMIT)
        self.assertIn("descriptor_error", rows["package.json"])
        self.assertIn("descriptor_error", rows["action.yml"])

    def test_every_new_inventory_input_is_bound_by_source_snapshot(self):
        profile = self.profile()
        self.write(atlas.PROFILE, profile)
        for name, contents in {"frontend/entry.ts": "import './support.js'", "frontend/support.js": "",
                               "tools/run.ps1": "Write-Output ok", "config/runtime.toml": "workers=2",
                               "external/settings.json": {"value": 1}, "package.json": {"scripts": {}}}.items():
            self.write(name, contents)
        inv, rows = self.rows()
        before = {name: atlas.digest((self.root / name).read_bytes()) for name in atlas.source_snapshot_paths(self.root, profile)}
        self.assertTrue(set(rows) <= set(before))
        self.assertEqual(inv["reference_policy"]["snapshot_policy"], atlas.SNAPSHOT_POLICY)
        self.write("frontend/support.js", "export const version = 2;")
        after = {name: atlas.digest((self.root / name).read_bytes()) for name in atlas.source_snapshot_paths(self.root, profile)}
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
