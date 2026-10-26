"""G10 native graph visual QA, hostile mutation and source-bound SVG controls."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import re
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
GOGREEN=HERE.parent
REPO=HERE.parents[2]
spec=importlib.util.spec_from_file_location("g10_graph_quality",HERE/"graph_quality.py")
g=importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
g7spec=importlib.util.spec_from_file_location(
    "g7_runner_telemetry", GOGREEN/"success_graph/runner_telemetry.py")
g7=importlib.util.module_from_spec(g7spec)
g7spec.loader.exec_module(g7)
DATA=GOGREEN/"success_graph/samples/native_success_20261017.json"
REGISTRY=REPO/"mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json"
SHA="a"*40


class GraphVisualQANative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=json.loads(DATA.read_text(encoding="utf-8"))
        reg=json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.ground=g7.dag(raw,g7.metrics(raw,reg))

    def setUp(self):
        self.dag=copy.deepcopy(self.ground)

    def invalid(self):
        with self.assertRaises((ValueError,KeyError,TypeError)):
            g.validate(self.dag)

    def test_complete_g7_dag_and_typed_edges(self):
        n=g.validate(self.dag)
        self.assertEqual(len(n["nodes"]),15)
        self.assertEqual(len(self.dag["edges"]),24)

    def test_svg_arrow_types_and_weights(self):
        s=g.svg(self.dag)
        self.assertIn('marker-end="url(#arrow-observed)"',s)
        self.assertIn('marker-end="url(#arrow-declared)"',s)
        self.assertIn('stroke-width="3.0"',s)
        self.assertIn('stroke-width="1.6"',s)

    def test_nodes_zoom_arrows_in_html(self):
        s=g.html_page(self.dag)
        for term in ['id="scale"','id="reset"','id="fit"',
                     'id="native-dag"','aria-label="Graph zoom percentage"',
                     'addEventListener','data-target','data-source']:
            self.assertIn(term,s)
        self.assertNotIn('onmouseover=',s)
        self.assertNotIn('eval(',s)

    def test_svg_scoped_count_matches_edges(self):
        s=g.svg(self.dag)
        self.assertEqual(s.count('class="dag-edge"'),24)
        self.assertEqual(s.count('class="dag-node"'),15)

    def test_role_palette_valid_and_distinct(self):
        self.assertEqual(set(g.ROLE_COLOR),set(g.ROLES))
        self.assertEqual(len(set(g.ROLE_COLOR.values())),5)

    def test_evidence_weights_and_palette_disjoint(self):
        self.assertGreater(g.WEIGHT["OBSERVED"],g.WEIGHT["DECLARED"])
        self.assertNotEqual(g.EDGE_COLOR["OBSERVED"],g.EDGE_COLOR["DECLARED"])

    def test_svg_accessibility_titled_focusable(self):
        s=g.svg(self.dag)
        self.assertIn('role="img"',s)
        self.assertEqual(s.count('tabindex="0"'),39)
        self.assertEqual(s.count("<title>"),15)

    def test_layout_canvas_bounded(self):
        positions,w,h=g.layout(self.dag)
        self.assertEqual((len(positions),w,h),(15,1450,1134))
        self.assertGreater(min(x for x,_ in positions.values()),0)

    def test_all_nodes_have_indegree_reachable(self):
        v=g.validate(self.dag)
        self.assertEqual(v["incoming"]["S"],[])
        self.assertEqual(v["adj"]["C"],[])
        self.assertEqual(set(v["nodes"]),set(v["order"]))

    def test_sipoc_roles(self):
        v=g.validate(self.dag)
        self.assertEqual(v["nodes"]["S"]["role"],"S")
        self.assertEqual(v["nodes"]["C"]["role"],"C")
        self.assertEqual(sum(n["role"]=="P" for n in v["nodes"].values()),11)

    def test_receipt_never_claims_real_visual_browser(self):
        r=g.qa_receipt(self.dag)
        self.assertEqual((r["node_count"],r["edge_count"],r["capability_nodes"]),(15,24,8))
        self.assertTrue(r["directed_arrows_verified"])
        self.assertIsNone(r["browser_visual_inspection"])
        self.assertFalse(r["merge_authorized"])

    def test_html_escape_label_script(self):
        self.dag["nodes"][0]["label"]="<script>alert('hello')</script>"
        s=g.html_page(self.dag)
        self.assertNotIn("<script>alert",s)
        self.assertIn("&lt;script&gt;",s)

    def test_html_escape_svg_title_injection(self):
        self.dag["nodes"][0]["label"]='X</title><script>alert(1)</script>'
        s=g.svg(self.dag)
        self.assertNotIn('</title><script>',s)
        self.assertIn('&lt;script&gt;',s)

    def test_reproducible_artifact_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt,manifest=g.build(self.dag,Path(tmp),SHA)
            for name,expected in manifest["files"].items():
                actual=hashlib.sha256((Path(tmp)/name).read_bytes()).hexdigest()
                self.assertEqual(actual,expected)
            self.assertEqual(receipt["node_count"],15)
            self.assertEqual(manifest["admission"],"HOLD")

    def test_real_cli_visual_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"input.json";src.write_text(json.dumps(self.dag), encoding="utf-8", newline="\n")
            out=Path(tmp)/"out"
            argv=["graph_quality.py","--input",str(src),"--out",str(out),
                  "--source-sha",SHA]
            stdout=io.StringIO()
            with patch.object(sys,"argv",argv),contextlib.redirect_stdout(stdout):
                runpy.run_path(str(HERE/"graph_quality.py"),run_name="__main__")
            self.assertEqual(json.loads(stdout.getvalue())["nodes"],15)
            self.assertTrue((out/"graph.svg").is_file())

    def test_rejects_build_sha_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                g.build(self.dag,Path(tmp),"short")

    def test_rejects_graph_wrong_schema(self):
        self.dag["schema"]="gogreen.sipoc-v2"
        self.invalid()

    def test_rejects_false_merge(self):
        self.dag["merge_authorized"]=True
        self.invalid()

    def test_rejects_false_dispatch(self):
        self.dag["dispatch_authorized"]=True
        self.invalid()

    def test_rejects_authority_transfer(self):
        self.dag["authority_transfer"]=True
        self.invalid()

    def test_rejects_false_green_admission(self):
        self.dag["admission"]="ACCEPTED"
        self.invalid()

    def test_rejects_forged_untyped_node(self):
        self.dag["nodes"][0]["role"]="UNKNOWN"
        self.invalid()

    def test_rejects_empty_owner(self):
        self.dag["nodes"][0]["owner"]=""
        self.invalid()

    def test_rejects_missing_evidence(self):
        self.dag["nodes"][0]["evidence"]=""
        self.invalid()

    def test_rejects_empty_node_label(self):
        self.dag["nodes"][0]["label"]=""
        self.invalid()

    def test_rejects_oversized_node_label(self):
        self.dag["nodes"][0]["label"]="x"*401
        self.invalid()

    def test_rejects_duplicate_node(self):
        self.dag["nodes"].append(copy.deepcopy(self.dag["nodes"][0]))
        self.invalid()

    def test_rejects_missing_source(self):
        self.dag["nodes"]=[n for n in self.dag["nodes"] if n["id"]!="S"]
        self.invalid()

    def test_rejects_missing_C(self):
        self.dag["nodes"]=[n for n in self.dag["nodes"] if n["id"]!="C"]
        self.invalid()

    def test_rejects_base_role_drift(self):
        next(n for n in self.dag["nodes"] if n["id"]=="S")["role"]="P"
        self.invalid()

    def test_rejects_unknown_node_identity(self):
        self.dag["nodes"][0]["id"]="UNKNOWN"
        self.invalid()

    def test_rejects_bad_capability_source(self):
        next(n for n in self.dag["nodes"] if n["id"].startswith("CAP_"))["entrypoint"]=""
        self.invalid()

    def test_rejects_bad_capability_input(self):
        next(n for n in self.dag["nodes"] if n["id"].startswith("CAP_"))["input"]=""
        self.invalid()

    def test_rejects_bad_capability_output(self):
        next(n for n in self.dag["nodes"] if n["id"].startswith("CAP_"))["output"]=""
        self.invalid()

    def test_rejects_dangling_arrow_target(self):
        self.dag["edges"][0]["target"]="CAP_DOES_NOT_EXIST"
        self.invalid()

    def test_rejects_dangling_arrow_source(self):
        self.dag["edges"][0]["source"]="CAP_DOES_NOT_EXIST"
        self.invalid()

    def test_rejects_self_loop(self):
        self.dag["edges"][0]["target"]=self.dag["edges"][0]["source"]
        self.invalid()

    def test_rejects_duplicate_edge_identity(self):
        self.dag["edges"].append(copy.deepcopy(self.dag["edges"][0]))
        self.invalid()

    def test_rejects_unrecognized_edge_evidence(self):
        self.dag["edges"][0]["binding"]="GREEN"
        self.invalid()

    def test_rejects_empty_edge_kind(self):
        self.dag["edges"][0]["kind"]=""
        self.invalid()

    def test_rejects_cycle(self):
        self.dag["edges"].append({"source":"C","target":"P_SOURCE",
                                  "kind":"INCORRECT_RETRY","binding":"DECLARED"})
        self.invalid()

    def test_rejects_supplier_inbound(self):
        self.dag["edges"].append({"source":"P_SOURCE","target":"S",
                                  "kind":"UNSAFE","binding":"DECLARED"})
        self.invalid()

    def test_rejects_disconnected_capability(self):
        ident=next(n["id"] for n in self.dag["nodes"] if n["id"].startswith("CAP_"))
        self.dag["edges"]=[e for e in self.dag["edges"] if e["target"]!=ident]
        self.invalid()

    def test_rejects_missing_required_spine(self):
        self.dag["edges"]=[e for e in self.dag["edges"]
                           if not(e["source"]=="S" and e["target"]=="I")]
        self.invalid()

    def test_rejects_empty_graph(self):
        self.dag["nodes"]=[]
        self.invalid()

    def test_rejects_too_many_edges(self):
        self.dag["edges"]=self.dag["edges"]*11
        self.invalid()

    def test_rejects_type_invalid_graph(self):
        self.dag["nodes"]=None
        self.invalid()

    def test_receipt_counts_reconcile(self):
        r=g.qa_receipt(self.dag)
        self.assertEqual(r["observed_edges"]+r["declared_edges"],24)

    def test_edge_path_is_directed_geometry(self):
        p,w,h=g.layout(self.dag)
        s=g.edge_path("S","I",p)
        self.assertTrue(s.startswith("M "))
        self.assertIn(" C ",s)

    def test_static_html_no_network_dependencies(self):
        page=g.html_page(self.dag)
        self.assertNotIn("<script src=",page)
        self.assertNotIn("<iframe",page)
        self.assertNotIn("fetch(",page)
        self.assertIn("aria-label",page)


    def test_reverse_direction_geometry_metaproperty(self):
        # Visual reverse case is not a causal DAG edge. It tests geometry only.
        positions={"S":(100,130),"C":(1300,120)}
        result=g.edge_path("C","S",positions)
        self.assertTrue(result.startswith("M 1222.0,120.0"))
        self.assertTrue(result.endswith("180.0,130.0"))
        self.assertIn(" C ",result)


if __name__=="__main__":
    unittest.main()
