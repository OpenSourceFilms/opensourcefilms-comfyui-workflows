"""Offline negative contracts for selected four live API socket-link audit."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "osf_live_api_links", ROOT / "scripts" / "audit_selected_four_live_api_links.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def synthetic_registered_schemas(graphs):
    """Test-only registry with one valid synthetic type on every linked edge."""
    registry = {}
    for graph in graphs.values():
        for node in graph.values():
            cls = node["class_type"]
            registry.setdefault(cls, {"input": {"required": {}, "optional": {}},
                                      "output": []})
        for node in graph.values():
            dst_cls = node["class_type"]
            for field, value in node["inputs"].items():
                if not isinstance(value, list):
                    continue
                src_cls = graph[value[0]]["class_type"]
                outputs = registry[src_cls]["output"]
                while len(outputs) <= value[1]:
                    outputs.append("IMAGE")
                registry[dst_cls]["input"]["required"][field] = ["IMAGE", {}]
    return registry


class SelectedFourLiveLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graphs = audit.load_selected_api_graphs()
        cls.registry = synthetic_registered_schemas(cls.graphs)

    def test_actual_four_graph_inventory_has_eighty_two_links(self):
        result = audit.analyze_live_api_links(self.registry, self.graphs)
        self.assertEqual(result["api_nodes"], 60)
        self.assertEqual(result["api_links"], 82)
        self.assertEqual(result["registered_exact_type_links"], 82)
        self.assertEqual(result["incompatible_registered_links"], 0)
        self.assertEqual(result["missing_provider_links_unverified"], 0)
        self.assertFalse(result["all_four_api_graphs_executable"])
        self.assertFalse(result["gpu_or_model_inference_qualified"])

    def test_incompatible_socket_is_explicit_hold_not_a_pass(self):
        registry = deepcopy(self.registry)
        registry["CLIPTextEncode"]["input"]["required"]["clip"] = ["MASK", {}]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["incompatible_registered_links"], 0)
        affected = [x for x in result["workflows"] if x["incompatible_links"]]
        self.assertTrue(affected)
        self.assertTrue(all(not x["api_graph_executed"] for x in affected))
        self.assertTrue(all("source_class" in y for x in affected
                            for y in x["incompatibilities"]))

    def test_uninstalled_custom_provider_never_counts_as_compatible(self):
        registry = deepcopy(self.registry)
        del registry["LoadSAM3Model"]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["missing_provider_links_unverified"], 0)
        self.assertIn("LoadSAM3Model",
                      result["workflows"][0]["unregistered_class_names"])
        self.assertLess(result["registered_exact_type_links"], 82)

    def test_untyped_wildcard_and_enum_are_unverified(self):
        registry = deepcopy(self.registry)
        registry["CLIPTextEncode"]["input"]["required"]["clip"] = ["*", {}]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["dynamic_type_links_unverified"], 0)
        registry["CLIPTextEncode"]["input"]["required"]["clip"] = [
            ["MODEL", "IMAGE"], {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["dynamic_type_links_unverified"], 0)

    def test_only_reviewed_sam3_scail_comma_union_accepts_mask(self):
        registry = deepcopy(self.registry)
        registry["SAM3_Detect"]["output"][0] = "MASK"
        registry["SCAIL2ColoredMask"]["input"]["required"]["ref_track_data"] = [
            "SAM3_TRACK_DATA,MASK", {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertEqual(result["registered_exact_type_links"], 82)
        self.assertEqual(result["incompatible_registered_links"], 0)
        self.assertEqual(result["dynamic_type_links_unverified"], 0)
        registry["CLIPTextEncode"]["input"]["required"]["clip"] = [
            "IMAGE,MASK", {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["dynamic_type_links_unverified"], 0)
        self.assertLess(result["registered_exact_type_links"], 82)

    def test_unreviewed_pipe_union_and_composite_output_remain_unverified(self):
        registry = deepcopy(self.registry)
        # Historically unreviewed input union must never be promoted by
        # matching one member of a textual pipe-separated type.
        registry["CLIPTextEncode"]["input"]["required"]["clip"] = [
            "CLIP|MODEL", {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["dynamic_type_links_unverified"], 0)
        self.assertLess(result["registered_exact_type_links"], 82)
        self.assertEqual(result["incompatible_registered_links"], 0)

        registry = deepcopy(self.registry)
        # Source composite types cannot be treated as one concrete socket.
        registry["CheckpointLoaderSimple"]["output"][1] = "CLIP|MODEL"
        registry["CLIPTextEncode"]["input"]["required"]["clip"] = [
            "CLIP|MODEL", {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["dynamic_type_links_unverified"], 0)
        self.assertLess(result["registered_exact_type_links"], 82)

    def test_reviewed_sam3_scail_pipe_alias_still_matches_mask(self):
        registry = deepcopy(self.registry)
        registry["SAM3_Detect"]["output"][0] = "MASK"
        registry["SCAIL2ColoredMask"]["input"]["required"]["ref_track_data"] = [
            "SAM3_TRACK_DATA|MASK", {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertEqual(result["registered_exact_type_links"], 82)
        self.assertEqual(result["incompatible_registered_links"], 0)
        self.assertEqual(result["dynamic_type_links_unverified"], 0)

        registry["SCAIL2ColoredMask"]["input"]["required"]["ref_track_data"] = [
            "MASK|LATENT", {}
        ]
        result = audit.analyze_live_api_links(registry, self.graphs)
        self.assertGreater(result["dynamic_type_links_unverified"], 0)

    def test_rejects_missing_producer_slot_and_destination_input(self):
        registry = deepcopy(self.registry)
        registry["CheckpointLoaderSimple"]["output"] = ["MODEL"]
        with self.assertRaisesRegex(ValueError, "producer output slot"):
            audit.analyze_live_api_links(registry, self.graphs)
        registry = deepcopy(self.registry)
        del registry["CLIPTextEncode"]["input"]["required"]["clip"]
        with self.assertRaisesRegex(ValueError, "Missing or duplicated linked input"):
            audit.analyze_live_api_links(registry, self.graphs)

    def test_rejects_corrupted_graph_link_source_or_slot(self):
        graphs = deepcopy(self.graphs)
        graphs["step4_5_sam3_mask"]["2"]["inputs"]["clip"] = ["999", 1]
        with self.assertRaisesRegex(ValueError, "Absent API link producer"):
            audit.analyze_live_api_links(self.registry, graphs)
        graphs = deepcopy(self.graphs)
        graphs["step4_5_sam3_mask"]["2"]["inputs"]["clip"] = ["1", True]
        with self.assertRaisesRegex(ValueError, "Invalid selected API link shape"):
            audit.analyze_live_api_links(self.registry, graphs)

    def test_rejects_changed_four_graph_inventory(self):
        graphs = deepcopy(self.graphs)
        del graphs["sam3_custompkg_probe"]
        with self.assertRaisesRegex(ValueError, "exactly four"):
            audit.analyze_live_api_links(self.registry, graphs)
        graphs = deepcopy(self.graphs)
        graphs["sam3_custompkg_probe"]["999"] = {
            "class_type": "SaveImage", "inputs": {}
        }
        with self.assertRaisesRegex(ValueError, "Changed selected-four API node inventory"):
            audit.analyze_live_api_links(self.registry, graphs)


if __name__ == "__main__":
    unittest.main()
