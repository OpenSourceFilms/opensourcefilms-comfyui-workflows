"""Negative contracts for the reviewed mm_upscale Essentials source sockets."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "audit_mm_upscale_essentials_sockets.py"
spec = importlib.util.spec_from_file_location("mm_essentials_socket_audit", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EssentialsSocketAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(audit.EXPORT.read_text(encoding="utf-8"))

    def first(self, graph, type_="ImageFromBatch+"):
        for group in graph["definitions"]["subgraphs"]:
            for node in group["nodes"]:
                if node.get("type") == type_ and node.get("properties", {}).get("cnr_id") == audit.PROVIDER:
                    return node
        self.fail("Expected reviewed Essentials fixture node missing")

    def test_actual_ten_source_bound_sockets_with_historical_version_hold(self):
        result = audit.audit_export(self.graph)
        self.assertEqual(result["classes"], {
            "ImageFromBatch+": 9, "SimpleMathSlider+": 1,
        })
        self.assertEqual(result["embedded_node_instances"], 10)
        self.assertEqual(result["candidate_sha"], audit.CANDIDATE_SHA)
        self.assertEqual(result["upstream_root_license"], "MIT")
        self.assertTrue(result["exact_input_and_output_names_and_types_match_reviewed_source"])
        for negative in (
            "historical_1_1_0_version_compatibility_verified",
            "candidate_installed_or_live_registered",
            "embedded_groups_executable",
            "licence_or_transitive_dependencies_cleared",
            "eleven_workflows_qualified",
        ):
            self.assertFalse(result[negative])

    def test_wrong_required_input_name_or_type_fails_closed(self):
        for change in ("name", "type"):
            g = deepcopy(self.graph)
            first = self.first(g)
            first["inputs"][0][change] = "UNREVIEWED"
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "input socket"):
                audit.audit_export(g)

    def test_output_port_reorder_or_type_drift_fails(self):
        for change in ("name", "type"):
            g = deepcopy(self.graph)
            node = self.first(g, "SimpleMathSlider+")
            node["outputs"][0][change] = "BAD"
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "output socket"):
                audit.audit_export(g)

    def test_missing_widget_or_unconnected_required_input_rejected(self):
        g = deepcopy(self.graph)
        node = self.first(g)
        node["widgets_values"].pop()
        with self.assertRaisesRegex(ValueError, "widget count"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        node = self.first(g)
        node["inputs"][0]["link"] = None
        node["inputs"][0].pop("widget", None)
        with self.assertRaisesRegex(ValueError, "no link/widget"):
            audit.audit_export(g)

    def test_unknown_class_or_unpinned_version_fails(self):
        g = deepcopy(self.graph)
        self.first(g)["type"] = "ImageFromBatchPlusUnreviewed"
        with self.assertRaisesRegex(ValueError, "New/unreviewed"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        self.first(g)["properties"]["ver"] = "latest"
        with self.assertRaisesRegex(ValueError, "version/provenance"):
            audit.audit_export(g)

    def test_missing_group_or_provider_instance_fails(self):
        g = deepcopy(self.graph)
        self.first(g)["properties"]["cnr_id"] = "unknown-provider"
        with self.assertRaisesRegex(ValueError, "class occurrence baseline"):
            audit.audit_export(g)
        g = deepcopy(self.graph)
        g["definitions"]["subgraphs"].pop()
        with self.assertRaisesRegex(ValueError, "exactly four"):
            audit.audit_export(g)

    def test_invalid_link_id_rejected(self):
        for link in (-1, "1", True):
            g = deepcopy(self.graph)
            self.first(g)["inputs"][0]["link"] = link
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "link ID"):
                audit.audit_export(g)


if __name__ == "__main__":
    unittest.main()
