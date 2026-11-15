"""Adversarial coverage receipt tests: real runtime arcs are never inferred."""
from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location("n32_coverage",HERE/"n32_coverage_receipt.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
ROOT=HERE.parents[2]
HEAD="a"*40

def cover(branch=4,covered=2):
    files={}
    for path in m.SOURCE:
        files["/source/"+m.SOURCE_PATHS[path]]={"summary":{"num_statements":12,"covered_lines":9,
            "num_branches":branch,"covered_branches":covered}}
    return {"meta":{"branch_coverage":True,"version":"7.13.3"},"files":files}

def dag():
    return {"schema":"method-atlas.warm-broker-pilot.v1","source":{"head":HEAD},
            "plan":{"positive_dag_count":24,"invalid_dag_count":24,
                    "tamper_dag_count":2},
            "rows":[{"accepted_fan_in":True} for _ in range(24)]+
                   [{"accepted_fan_in":False} for _ in range(26)]}

class CoverageAxis(unittest.TestCase):
    def test_real_broker_filenames_not_whole_repo(self):
        rows,missing=m.summarize_pop(cover())
        self.assertFalse(missing)
        self.assertEqual(rows["broker.py"]["branches"]["eligible"],4)
        self.assertIsNone(m.summarize_pop({"files":{}})[0]["broker.py"]["branches"])
        self.assertEqual(rows["broker.py"]["status"],"MEASURED_PARTIAL_OR_FULL")

    def test_unrelated_same_basename_does_not_double_count_source(self):
        raw=cover()
        raw["files"]["/other/untrusted/main.py"]={
            "summary":{"num_statements":999,"covered_lines":999,
                       "num_branches":999,"covered_branches":999}}
        selected,missing=m.summarize_pop(raw)
        self.assertEqual(selected["main.py"]["branches"]["eligible"],4)
        self.assertEqual(missing,[])
        raw["files"]["/duplicate/"+m.SOURCE_PATHS["main.py"]]=raw["files"][
            "/source/"+m.SOURCE_PATHS["main.py"]]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_EXACT_SOURCE_PATH"):
            m.summarize_pop(raw)

    def test_uninstrumented_is_not_zero(self):
        data=cover()
        del data["files"]["/source/"+m.SOURCE_PATHS["broker.py"]]
        rows,missing=m.summarize_pop(data)
        self.assertEqual(rows["broker.py"]["status"],"NOT_INSTRUMENTED_OR_NOT_EXECUTED")
        self.assertIn("broker.py",missing)
        data=cover(4,0)
        rows,_=m.summarize_pop(data)
        self.assertEqual(rows["broker.py"]["status"],"ZERO_INSTRUMENTED")
        data=cover(0,0)
        rows,_=m.summarize_pop(data)
        self.assertEqual(rows["broker.py"]["status"],"BRANCHLESS_NOT_APPLICABLE")

    def test_coverage_tool_or_arcs_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"report.json"
            for bad in ({"meta":{"branch_coverage":False},"files":{"a":{}}},
                        {"meta":{"branch_coverage":True,"version":"x"},"files":{}},
                        {"meta":{"branch_coverage":True,"version":"x"},
                         "files":{"a":{"summary":{"num_statements":1,
                         "covered_lines":2,"num_branches":1,"covered_branches":0}}}}):
                p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    m.load_coverage(p)

    def test_exact_head_is_required(self):
        with self.assertRaisesRegex(ValueError,"EXACT_HEAD_REQUIRED"):
            m.exact_head(ROOT,"broken")

    def test_complete_receipt_is_bounded_not_fleet_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            for path,obj in (("unit.json",cover()),("runtime.json",cover()),
                             ("actual.json",dag())):
                (base/path).write_text(json.dumps(obj))
            with mock.patch.object(m,"exact_head",return_value=None):
                result=m.compare(base/"unit.json",base/"runtime.json",
                                 base/"actual.json",HEAD,ROOT)
            self.assertEqual(result["production_execution_population"]["verified_dags"],50)
            self.assertIsNone(result["whole_repository_coverage"])
            self.assertFalse(result["native_job_readback_authenticated"])
            self.assertFalse(result["merge_authorized"])
            self.assertEqual(result["production_execution_population"]["files"]["broker.py"]["branches"]["pct"],50)

    def test_false_green_missing_runtime_source_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);runtime=cover()
            del runtime["files"]["/source/"+m.SOURCE_PATHS["outcome_flight.py"]]
            for path,obj in (("unit.json",cover()),("runtime.json",runtime),
                             ("actual.json",dag())):
                (base/path).write_text(json.dumps(obj))
            with mock.patch.object(m,"exact_head",return_value=None):
                with self.assertRaisesRegex(ValueError,"PRODUCTION_SOURCE_INSTRUMENTATION_INCOMPLETE"):
                    m.compare(base/"unit.json",base/"runtime.json",base/"actual.json",HEAD,ROOT)

    def test_wrong_dag_population_is_not_coverage_proof(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);wrong=dag();wrong["rows"].pop()
            for path,obj in (("unit.json",cover()),("runtime.json",cover()),
                             ("actual.json",wrong)):
                (base/path).write_text(json.dumps(obj))
            with mock.patch.object(m,"exact_head",return_value=None):
                with self.assertRaisesRegex(ValueError,"ACTUAL_DAG_OUTCOME_POPULATION_INCOMPLETE"):
                    m.compare(base/"unit.json",base/"runtime.json",base/"actual.json",HEAD,ROOT)

    def test_source_bound_wrong_head_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);wrong=dag();wrong["source"]["head"]="b"*40
            for path,obj in (("unit.json",cover()),("runtime.json",cover()),
                             ("actual.json",wrong)):
                (base/path).write_text(json.dumps(obj))
            with mock.patch.object(m,"exact_head",return_value=None):
                with self.assertRaisesRegex(ValueError,"ACTUAL_DAG_SOURCE_HEAD_DRIFT"):
                    m.compare(base/"unit.json",base/"runtime.json",base/"actual.json",HEAD,ROOT)


if __name__=="__main__":
    unittest.main()
