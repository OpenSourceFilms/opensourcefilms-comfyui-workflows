"""Offline, read-only checks of embedded mm_upscale UI subgraph links."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_embedded_group_links.py"
spec = importlib.util.spec_from_file_location("osf_embedded_links", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def valid_group():
    return {
        "id": "6f5ab705-8e1b-4b53-a3f4-a35676bec4e9",
        "inputNode": {"id": -10}, "outputNode": {"id": -20},
        "inputs": [{"linkIds": [1]}], "outputs": [{"linkIds": [3]}],
        "nodes": [
            {"id": 11, "inputs": [{"link": 1}], "outputs": [{"links": [2]}]},
            {"id": 12, "inputs": [{"link": 2}], "outputs": [{"links": [3]}]},
        ],
        "links": [
            {"id": 1, "origin_id": -10, "origin_slot": 0,
             "target_id": 11, "target_slot": 0, "type": "INT"},
            {"id": 2, "origin_id": 11, "origin_slot": 0,
             "target_id": 12, "target_slot": 0, "type": "INT"},
            {"id": 3, "origin_id": 12, "origin_slot": 0,
             "target_id": -20, "target_slot": 0, "type": "INT"},
        ],
    }


class EmbeddedGroupLinkAuditTests(unittest.TestCase):
    def test_valid_active_pseudo_endpoints_and_real_node_slots(self):
        result = audit.inspect_group(valid_group())
        self.assertEqual(result["active_link_count"], 3)
        self.assertTrue(result["active_link_endpoints_consistent"])
        self.assertEqual(result["unresolved_reverse_reference_count"], 0)
        self.assertTrue(result["all_reverse_references_resolved"])
        self.assertFalse(result["ui_group_executable_proven"])
        self.assertFalse(result["api_conversion_proven"])

    def test_stale_node_and_external_refs_are_reported_not_repaired(self):
        graph = valid_group()
        graph["nodes"][0]["outputs"][0]["links"].append(123)
        graph["inputs"][0]["linkIds"].append(124)
        result = audit.inspect_group(graph)
        self.assertEqual(result["unresolved_reverse_reference_count"], 2)
        self.assertEqual(
            result["unresolved_reverse_reference_ids_by_location"]["node_output"], [123]
        )
        self.assertEqual(
            result["unresolved_reverse_reference_ids_by_location"]["group_input"], [124]
        )
        self.assertFalse(result["all_reverse_references_resolved"])
        self.assertEqual(graph["nodes"][0]["outputs"][0]["links"], [2, 123])

    def test_missing_active_origins_or_targets_fail_closed(self):
        for key, bad in (("origin_id", 99), ("target_id", 99),
                         ("origin_slot", 5), ("target_slot", 5)):
            g = valid_group()
            g["links"][1][key] = bad
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    audit.inspect_group(g)

    def test_duplicate_active_links_and_node_ids_fail(self):
        a = valid_group()
        a["links"].append(copy.deepcopy(a["links"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate embedded active"):
            audit.inspect_group(a)
        b = valid_group()
        b["nodes"].append(copy.deepcopy(b["nodes"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate embedded node"):
            audit.inspect_group(b)

    def test_mismatched_active_node_and_pseudo_port_links_fail(self):
        for mutation in (
            lambda g: g["nodes"][0]["outputs"][0].update(links=[]),
            lambda g: g["nodes"][1]["inputs"][0].update(link=None),
            lambda g: g["inputs"][0].update(linkIds=[]),
            lambda g: g["outputs"][0].update(linkIds=[]),
        ):
            g = valid_group()
            mutation(g)
            with self.subTest(mutation=str(mutation)):
                with self.assertRaisesRegex(ValueError, "Active link missing"):
                    audit.inspect_group(g)

    def test_malformed_ref_types_or_duplicate_ref_ids_rejected(self):
        for bad in ("5", False, -1, 0, 1.5):
            g = valid_group()
            g["nodes"][0]["outputs"][0]["links"].append(bad)
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    audit.inspect_group(g)
        g = valid_group()
        g["nodes"][0]["outputs"][0]["links"].append(2)
        with self.assertRaisesRegex(ValueError, "Duplicated"):
            audit.inspect_group(g)

    def test_real_selected_mm_upscale_reports_sixteen_unresolved_refs(self):
        result = audit.audit()
        self.assertEqual(result["schema"], "osf-mm-upscale-embedded-link-preflight-v1")
        self.assertEqual(result["group_count"], 4)
        self.assertEqual(result["total_internal_nodes"], 89)
        self.assertEqual(result["total_active_links"], 171)
        self.assertEqual(result["total_unresolved_reverse_references"], 16)
        self.assertTrue(result["active_links_structurally_consistent"])
        self.assertFalse(result["all_reverse_references_resolved"])
        self.assertFalse(result["embedded_group_runtime_qualified"])
        self.assertFalse(result["eleven_workflows_gpu_qualified"])
        self.assertEqual(
            sorted(x["unresolved_reverse_reference_count"] for x in result["results"]),
            [3, 3, 4, 6],
        )
        self.assertEqual(
            sorted(sum(len(v) for v in x[
                "unresolved_reverse_reference_ids_by_location"].values())
                for x in result["results"]),
            [3, 3, 4, 6],
        )
        serialized = json.dumps(result)
        self.assertNotIn(".safetensors", serialized)
        self.assertNotIn("reference_character", serialized)


if __name__ == "__main__":
    unittest.main()
