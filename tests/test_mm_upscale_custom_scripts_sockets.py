"""Negative and positive contracts for Custom-Scripts embedded source sockets."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "audit_mm_upscale_custom_scripts_sockets.py"
spec = importlib.util.spec_from_file_location("custom_scripts_source_sockets", FILE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CustomScriptsHistoricalSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(audit.EXPORT.read_text(encoding="utf-8"))

    def first(self, graph, node_type="MathExpression|pysssss"):
        for group in graph["definitions"]["subgraphs"]:
            for node in group["nodes"]:
                if (node.get("type") == node_type
                        and node.get("properties", {}).get("cnr_id") == audit.PROVIDER):
                    return node
        self.fail("Missing fixture node " + node_type)

    def test_all_23_instances_and_alias_hold_reported(self):
        r = audit.audit_export(self.graph)
        self.assertEqual(r["embedded_node_instances"], 23)
        self.assertEqual(r["classes"], {
            "MathExpression|pysssss": 21, "StringFunction|pysssss": 2,
        })
        self.assertEqual(r["groups"], {
            "Image Batch Subgraph": 4, "Blend Frames Subgraph": 10,
            "Blend Saved Frames Subgraph": 9,
        })
        self.assertEqual(r["export_version_counts"], {
            "1.2.5": 21, audit.REVIEWED_SHA: 2,
        })
        self.assertEqual(r["root_license"], "MIT")
        self.assertTrue(r["math_expression_source_string_vs_ui_union_difference"])
        for key in (
            "math_expression_1_2_5_alias_equivalence_proven",
            "runtime_api_schema_equivalence_proven",
            "expression_evaluation_or_safety_qualified",
            "external_node_import_qualified",
            "embedded_group_execution_qualified",
            "manifest_source_commit_pinned",
            "transitive_licences_cleared",
            "eleven_workflows_qualified",
        ):
            self.assertFalse(r[key])

    def test_source_contract_acknowledges_string_vs_union_discrepancy(self):
        math = audit.SOURCE_CONTRACTS["MathExpression|pysssss"]
        self.assertEqual(math["source_required"], (("expression", "STRING"),))
        self.assertEqual(
            math["source_optional"],
            (("a", "*"), ("b", "*"), ("c", "*")),
        )
        self.assertEqual(math["ui_inputs"][-1],
                         ("expression", "INT,FLOAT,IMAGE,LATENT"))
        self.assertNotEqual(math["source_required"][0], math["ui_inputs"][-1])
        string = audit.SOURCE_CONTRACTS["StringFunction|pysssss"]
        self.assertEqual(string["source_required"],
                         (("action", "COMBO"), ("tidy_tags", "COMBO")))
        self.assertEqual(len(string["source_optional"]), 3)

    def test_source_bound_wrong_input_name_or_type_fails(self):
        for attr in ("name", "type"):
            g = deepcopy(self.graph)
            self.first(g)["inputs"][0][attr] = "WRONG"
            with self.subTest(attr=attr), self.assertRaisesRegex(ValueError, "input socket"):
                audit.audit_export(g)
            g = deepcopy(self.graph)
            self.first(g, "StringFunction|pysssss")["inputs"][2][attr] = "WRONG"
            with self.subTest(string_attr=attr), self.assertRaisesRegex(ValueError, "input socket"):
                audit.audit_export(g)

    def test_output_socket_changes_rejected(self):
        for name in ("MathExpression|pysssss", "StringFunction|pysssss"):
            for attr in ("name", "type"):
                g = deepcopy(self.graph)
                self.first(g, name)["outputs"][0][attr] = "WRONG"
                with self.subTest(class_name=name, attr=attr), self.assertRaisesRegex(
                        ValueError, "output socket"):
                    audit.audit_export(g)

    def test_math_required_expression_widget_and_string_widgets(self):
        g = deepcopy(self.graph)
        self.first(g)["inputs"][-1]["widget"] = None
        with self.assertRaisesRegex(ValueError, "required expression"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.first(g, "StringFunction|pysssss")["inputs"][0]["widget"] = None
        with self.assertRaisesRegex(ValueError, "lacks link or named widget"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.first(g, "StringFunction|pysssss")["inputs"][0]["widget"]["name"] = "WRONG"
        with self.assertRaisesRegex(ValueError, "named widget"):
            audit.audit_export(g)

    def test_bad_optional_links_and_widget_counts_rejected(self):
        for bad in (-1, "7", True):
            g = deepcopy(self.graph)
            self.first(g)["inputs"][0]["link"] = bad
            with self.subTest(link=bad), self.assertRaisesRegex(ValueError, "link identifier"):
                audit.audit_export(g)
        for name in ("MathExpression|pysssss", "StringFunction|pysssss"):
            g = deepcopy(self.graph)
            self.first(g, name)["widgets_values"].pop()
            with self.subTest(node=name), self.assertRaisesRegex(ValueError, "widget count"):
                audit.audit_export(g)

    def test_unreviewed_classes_and_version_aliases_rejected(self):
        g = deepcopy(self.graph)
        self.first(g)["properties"]["ver"] = "1.2.6"
        with self.assertRaisesRegex(ValueError, "version/source"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.first(g)["type"] = "MathExpression2|pysssss"
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.first(g, "StringFunction|pysssss")["properties"]["ver"] = "1.2.5"
        with self.assertRaisesRegex(ValueError, "version/source"):
            audit.audit_export(g)

    def test_group_and_occurrence_changes_rejected(self):
        g = deepcopy(self.graph)
        g["definitions"]["subgraphs"][0]["name"] = "different"
        with self.assertRaisesRegex(ValueError, "group set"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        g["definitions"]["subgraphs"][0]["nodes"].remove(self.first(g))
        with self.assertRaisesRegex(ValueError, "class occurrence"):
            audit.audit_export(g)

    def test_report_never_publishes_expression_widget_values(self):
        g = deepcopy(self.graph)
        self.first(g)["widgets_values"][0] = "PRIVATE_CANARY_EXPRESSION"
        r = audit.audit_export(g)
        self.assertNotIn("PRIVATE_CANARY_EXPRESSION", json.dumps(r))
        g = deepcopy(self.graph)
        self.first(g, "StringFunction|pysssss")["widgets_values"][2] = "PRIVATE_CANARY_TEXT"
        r = audit.audit_export(g)
        self.assertNotIn("PRIVATE_CANARY_TEXT", json.dumps(r))


if __name__ == "__main__":
    unittest.main()
