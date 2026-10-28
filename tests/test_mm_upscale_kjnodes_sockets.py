"""Negative source-bound contracts for embedded mm_upscale KJNodes sockets."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "audit_mm_upscale_kjnodes_sockets.py"
spec = importlib.util.spec_from_file_location("kjnodes_source_sockets", FILE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class KJNodesHistoricalSourceSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(audit.EXPORT.read_text(encoding="utf-8"))

    def node(self, graph, name="ImageBatchMulti"):
        for group in graph["definitions"]["subgraphs"]:
            for node in group["nodes"]:
                if (node.get("type") == name and
                        node.get("properties", {}).get("cnr_id") == audit.PROVIDER):
                    return node
        self.fail("Expected KJNodes source fixture missing")

    def test_all_seven_source_bound_instances_and_explicit_unverified_alias(self):
        report = audit.audit_export(self.graph)
        self.assertEqual(report["embedded_node_instances"], 7)
        self.assertEqual(report["historical_source_sha"], audit.REVIEWED_SOURCE_SHA)
        self.assertEqual(report["classes"], {
            "ImageBatchJoinWithTransition": 2,
            "ImageBatchMulti": 4,
            "ImagePass": 1,
        })
        self.assertEqual(report["export_version_counts"], {
            "1.1.4": 6,
            audit.REVIEWED_SOURCE_SHA: 1,
        })
        self.assertEqual(report["root_license"], "GPL-3.0")
        self.assertTrue(report["input_and_output_names_types_match_reviewed_source"])
        for claim in ("historical_1_1_4_alias_equivalence_proven",
                      "candidate_runtime_import_qualified",
                      "embedded_group_runtime_executable",
                      "nested_dependencies_cleared",
                      "commercial_rights_cleared",
                      "eleven_workflows_qualified"):
            self.assertFalse(report[claim])

    def test_wrong_input_name_or_type_fails(self):
        for attr in ("name", "type"):
            g = deepcopy(self.graph)
            self.node(g)["inputs"][0][attr] = "BAD"
            with self.subTest(attr=attr), self.assertRaisesRegex(ValueError, "input socket"):
                audit.audit_export(g)

    def test_required_source_ports_and_optional_port_are_explicit(self):
        spec = audit.SOURCE_CONTRACTS["ImageBatchMulti"]
        self.assertEqual(spec["required"], (
            ("inputcount", "INT"), ("image_1", "IMAGE"),
        ))
        self.assertEqual(spec["optional"], (("image_2", "IMAGE"),))
        self.assertEqual(spec["ui_inputs"], (
            ("image_1", "IMAGE"), ("image_2", "IMAGE"),
            ("inputcount", "INT"),
        ))
        g = deepcopy(self.graph)
        node = self.node(g)
        node["inputs"][0], node["inputs"][2] = node["inputs"][2], node["inputs"][0]
        with self.assertRaisesRegex(ValueError, "input socket"):
            audit.audit_export(g)

    def test_transition_combo_schema_or_widget_count_change_fails(self):
        g = deepcopy(self.graph)
        t = self.node(g, "ImageBatchJoinWithTransition")
        t["inputs"][3]["type"] = "STRING"
        with self.assertRaisesRegex(ValueError, "input socket"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        t = self.node(g, "ImageBatchJoinWithTransition")
        t["widgets_values"].pop()
        with self.assertRaisesRegex(ValueError, "widget count"):
            audit.audit_export(g)

    def test_wrong_output_type_or_port_name_rejected(self):
        for attr in ("name", "type"):
            g = deepcopy(self.graph)
            self.node(g, "ImagePass")["outputs"][0][attr] = "BAD"
            with self.subTest(attr=attr), self.assertRaisesRegex(ValueError, "output socket"):
                audit.audit_export(g)

    def test_missing_connection_or_widget_and_invalid_link_rejected(self):
        g = deepcopy(self.graph)
        self.node(g, "ImagePass")["inputs"][0]["link"] = None
        with self.assertRaisesRegex(ValueError, "lacks link or named widget"):
            audit.audit_export(g)
        for bad in (-1, "7", True):
            g = deepcopy(self.graph)
            self.node(g)["inputs"][0]["link"] = bad
            with self.subTest(link=bad), self.assertRaisesRegex(ValueError, "link ID"):
                audit.audit_export(g)

    def test_unknown_version_and_source_sha_drift_rejected(self):
        g = deepcopy(self.graph)
        self.node(g)["properties"]["ver"] = "latest"
        with self.assertRaisesRegex(ValueError, "version/provenance"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.node(g, "ImagePass")["properties"]["ver"] = "1.1.4"
        with self.assertRaisesRegex(ValueError, "alias counts"):
            audit.audit_export(g)

    def test_missing_provider_node_and_unreviewed_class_rejected(self):
        g = deepcopy(self.graph)
        self.node(g, "ImagePass")["properties"]["cnr_id"] = "not-kjnodes"
        with self.assertRaisesRegex(ValueError, "class occurrence baseline"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.node(g)["type"] = "UnreviewedKJNode"
        with self.assertRaisesRegex(ValueError, "New/unreviewed"):
            audit.audit_export(g)

    def test_group_omission_and_duplicate_group_names_rejected(self):
        g = deepcopy(self.graph)
        g["definitions"]["subgraphs"].pop()
        with self.assertRaisesRegex(ValueError, "exactly four"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        groups = g["definitions"]["subgraphs"]
        groups[0]["name"] = groups[1]["name"]
        with self.assertRaisesRegex(ValueError, "Duplicate embedded"):
            audit.audit_export(g)


if __name__ == "__main__":
    unittest.main()
