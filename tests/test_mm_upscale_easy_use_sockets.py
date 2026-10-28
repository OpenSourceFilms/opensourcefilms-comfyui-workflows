"""Negative contract tests for the source-only Easy-Use embedded socket audit."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "audit_mm_upscale_easy_use_sockets.py"
spec = importlib.util.spec_from_file_location("osf_mm_easy_sockets", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EasyUseEmbeddedSocketContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((ROOT / audit.WORKFLOW).read_text(encoding="utf-8"))

    def node(self, graph, class_id="easy int", group_name=None):
        for group in graph["definitions"]["subgraphs"]:
            if group_name is not None and group["name"] != group_name:
                continue
            for node in group["nodes"]:
                if (node.get("type") == class_id
                        and node.get("properties", {}).get("cnr_id") == audit.PROVIDER):
                    return node
        self.fail("Easy-Use embedded fixture missing " + class_id)

    def test_exact_42_instances_and_8_classes_with_unproven_aliases(self):
        result = audit.audit_export(self.graph)
        self.assertEqual(result["total_instances"], 42)
        self.assertEqual(result["distinct_class_ids"], 8)
        self.assertEqual(result["class_instance_counts"], audit.CLASS_COUNTS)
        self.assertEqual(result["group_instance_counts"], audit.GROUP_COUNTS)
        self.assertEqual(result["historical_export_version_counts"], {
            "1.3.0": 6,
            "1.3.3": 35,
            audit.HISTORICAL_IF_ELSE_SHA: 1,
        })
        self.assertEqual(result["reviewed_source_sha"], audit.REVIEWED_SHA)
        self.assertEqual(result["reviewed_root_license"], "GPL-3.0")
        self.assertEqual(result["observed_ui_vs_source_input_order_differences"],
                         ["easy forLoopStart", "easy ifElse"])
        self.assertTrue(result["exported_ui_socket_shapes_match_reviewed_candidate"])
        for key in ("historical_version_aliases_equivalent_to_reviewed_sha",
                    "actual_runtime_registration_qualified",
                    "loop_execution_qualified", "dependency_manifest_updated",
                    "transitive_licenses_cleared", "eleven_workflows_qualified"):
            self.assertFalse(result[key])
        self.assertNotIn("expression", json.dumps(result))
        self.assertNotIn("filename_prefix", json.dumps(result))

    def test_if_else_ui_order_is_distinct_from_reviewed_runtime_schema(self):
        src = audit.SOURCE_API["easy ifElse"]
        self.assertEqual(src["required"][0], ("boolean", "BOOLEAN"))
        self.assertEqual(src["ui_inputs"][-1], ("boolean", "BOOLEAN"))
        self.assertEqual(set(src["required"]), set(src["ui_inputs"]))
        graph = deepcopy(self.graph)
        n = self.node(graph, "easy ifElse")
        n["inputs"][0], n["inputs"][-1] = n["inputs"][-1], n["inputs"][0]
        with self.assertRaisesRegex(ValueError, "input socket"):
            audit.audit_export(graph)

    def test_for_loop_start_dynamic_optional_input_and_output_contract(self):
        src = audit.SOURCE_API["easy forLoopStart"]
        self.assertEqual(src["required"], (("total", "INT"),))
        self.assertEqual(src["optional"], (
            ("initial_value1", "*"), ("initial_value2", "*"),
        ))
        self.assertEqual(src["ui_inputs"][1], ("total", "INT"))
        self.assertEqual(len(src["outputs"]), 4)
        graph = deepcopy(self.graph)
        self.node(graph, "easy forLoopStart")["outputs"].pop()
        with self.assertRaisesRegex(ValueError, "output socket"):
            audit.audit_export(graph)

    def test_wrong_input_name_and_type_rejected(self):
        for attr in ("name", "type"):
            graph = deepcopy(self.graph)
            self.node(graph, "easy compare")["inputs"][0][attr] = "WRONG"
            with self.subTest(attr=attr), self.assertRaisesRegex(ValueError, "input socket"):
                audit.audit_export(graph)

    def test_wrong_output_name_or_type_and_extra_port_rejected(self):
        for attr in ("name", "type"):
            graph = deepcopy(self.graph)
            self.node(graph, "easy boolean")["outputs"][0][attr] = "WRONG"
            with self.subTest(attr=attr), self.assertRaisesRegex(ValueError, "output socket"):
                audit.audit_export(graph)
        graph = deepcopy(self.graph)
        self.node(graph, "easy imageSave")["outputs"].append({"name": "unexpected", "type": "IMAGE"})
        with self.assertRaisesRegex(ValueError, "output socket"):
            audit.audit_export(graph)

    def test_wrong_widget_count_and_invalid_binding_rejected(self):
        graph = deepcopy(self.graph)
        self.node(graph, "easy int")["widgets_values"].clear()
        with self.assertRaisesRegex(ValueError, "widget count"):
            audit.audit_export(graph)
        graph = deepcopy(self.graph)
        self.node(graph, "easy int")["inputs"][0]["widget"] = "not metadata"
        with self.assertRaisesRegex(ValueError, "widget binding"):
            audit.audit_export(graph)

    def test_bad_link_and_duplicate_sockets_rejected(self):
        for bad in (-1, True, "7"):
            graph = deepcopy(self.graph)
            self.node(graph, "easy compare")["inputs"][0]["link"] = bad
            with self.subTest(link=bad), self.assertRaisesRegex(ValueError, "input link"):
                audit.audit_export(graph)
        graph = deepcopy(self.graph)
        n = self.node(graph, "easy compare")
        n["inputs"].append(deepcopy(n["inputs"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate Easy-Use socket"):
            audit.audit_export(graph)

    def test_unknown_version_or_historical_alias_distribution_rejected(self):
        graph = deepcopy(self.graph)
        self.node(graph)["properties"]["ver"] = "latest"
        with self.assertRaisesRegex(ValueError, "version alias"):
            audit.audit_export(graph)
        graph = deepcopy(self.graph)
        self.node(graph, "easy ifElse", "Settings")["properties"]["ver"] = "1.3.3"
        with self.assertRaisesRegex(ValueError, "version distribution"):
            audit.audit_export(graph)

    def test_missing_provider_instance_and_new_class_rejected(self):
        graph = deepcopy(self.graph)
        self.node(graph)["properties"]["cnr_id"] = "wrong-provider"
        with self.assertRaisesRegex(ValueError, "class counts drifted"):
            audit.audit_export(graph)
        graph = deepcopy(self.graph)
        self.node(graph)["type"] = "easy unknown"
        with self.assertRaisesRegex(ValueError, "Unreviewed embedded"):
            audit.audit_export(graph)

    def test_missing_or_duplicate_groups_rejected(self):
        graph = deepcopy(self.graph)
        graph["definitions"]["subgraphs"].pop()
        with self.assertRaisesRegex(ValueError, "four embedded"):
            audit.audit_export(graph)
        graph = deepcopy(self.graph)
        graph["definitions"]["subgraphs"][1]["name"] = "Settings"
        with self.assertRaisesRegex(ValueError, "Duplicate embedded"):
            audit.audit_export(graph)


if __name__ == "__main__":
    unittest.main()
