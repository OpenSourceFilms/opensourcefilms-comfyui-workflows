"""Offline malformed-input regressions for pinned SAM3 custom-package source audit."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "audit_sam3_custompkg_source.py"
spec = importlib.util.spec_from_file_location("sam3_custom_source", path)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


def fake_schema_source(name: str) -> str:
    inputs, outputs = auditor.SCHEMAS[name]
    declaration = []
    for field, typ in inputs.items():
        receiver = ('io.Custom("%s")' % typ if typ.startswith("SAM3_")
                    else "io." + {"COMBO": "Combo", "BOOLEAN": "Boolean",
                                  "FLOAT": "Float", "INT": "Int",
                                  "IMAGE": "Image", "MASK": "Mask",
                                  "STRING": "String"}[typ])
        kwargs = ', optional=True' if ((name == "LoadSAM3Model")
                                       or (name == "SAM3CombinePoints")
                                       or (name == "SAM3Segmentation" and field not in
                                           ("sam3_model_config", "image"))) else ""
        declaration.append('                %s.Input("%s"%s),' % (receiver, field, kwargs))
    result = []
    for typ in outputs:
        receiver = ('io.Custom("%s")' % typ if typ.startswith("SAM3_")
                    else "io." + {"IMAGE": "Image", "MASK": "Mask",
                                  "STRING": "String"}[typ])
        result.append("                %s.Output()," % receiver)
    return (
        "class " + name + "(io.ComfyNode):\n"
        "    @classmethod\n"
        "    def define_schema(cls):\n"
        "        return io.Schema(\n"
        '            node_id="' + name + '",\n'
        "            inputs=[\n" + "\n".join(declaration) + "\n            ],\n"
        "            outputs=[\n" + "\n".join(result) + "\n            ],\n"
        "        )\n"
    )


class SAM3CustomSourceContractTests(unittest.TestCase):
    def setUp(self):
        self.graph = json.loads((ROOT / auditor.WORKFLOW).read_text(encoding="utf-8"))
        self.schemas = {
            name: auditor.parse_class_schema(fake_schema_source(name), name)
            for name in auditor.SCHEMAS
        }

    def test_all_four_declared_schemas_and_binding_counts(self):
        self.assertEqual(len(self.schemas), 4)
        result = auditor.check_graph_bindings(self.graph, self.schemas)
        self.assertEqual(result["api_node_instances"], 8)
        self.assertEqual(result["third_party_node_instances"], 4)
        self.assertEqual(result["verified_third_party_edges"], 5)
        self.assertEqual(result["unverified_core_source_edges"], 2)
        self.assertFalse(result["full_graph_executable"])
        self.assertEqual(self.schemas["SAM3Segmentation"]["outputs"][2], "IMAGE")

    def test_malformed_upstream_schema_and_missing_class_fail(self):
        content = fake_schema_source("SAM3Segmentation")
        with self.assertRaisesRegex(ValueError, "Missing or duplicate"):
            auditor.parse_class_schema(content, "SAM3CreatePoint")
        with self.assertRaisesRegex(ValueError, "differs"):
            auditor.parse_class_schema(content.replace(
                'io.Mask.Output(),\n                io.Mask.Output(),',
                'io.Image.Output(),\n                io.Mask.Output(),'), "SAM3Segmentation")
        with self.assertRaisesRegex(ValueError, "differs"):
            auditor.parse_class_schema(
                fake_schema_source("LoadSAM3Model").replace(
                    '"compile"', '"unsafe_unknown"'),
                "LoadSAM3Model",
            )

    def test_missing_required_source_link_and_unknown_fields_fail(self):
        broken = copy.deepcopy(self.graph)
        del broken["5"]["inputs"]["image"]
        with self.assertRaisesRegex(ValueError, "required upstream input"):
            auditor.check_graph_bindings(broken, self.schemas)
        broken = copy.deepcopy(self.graph)
        broken["5"]["inputs"]["unknown_weight_url"] = "https://example.com"
        with self.assertRaisesRegex(ValueError, "unreviewed upstream input"):
            auditor.check_graph_bindings(broken, self.schemas)

    def test_reordered_output_and_extra_link_fail(self):
        broken_schemas = copy.deepcopy(self.schemas)
        broken_schemas["SAM3Segmentation"]["outputs"][2] = "MASK"
        with self.assertRaisesRegex(ValueError, "slot/type mismatch"):
            auditor.check_graph_bindings(self.graph, broken_schemas)
        graph = copy.deepcopy(self.graph)
        graph["5"]["inputs"]["positive_points"] = ["3", 0]
        with self.assertRaisesRegex(ValueError, "edge differs"):
            auditor.check_graph_bindings(graph, self.schemas)
        graph = copy.deepcopy(self.graph)
        graph["5"]["inputs"]["negative_points"] = ["4", 0]
        with self.assertRaisesRegex(ValueError, "additional or missing"):
            auditor.check_graph_bindings(graph, self.schemas)

    def test_different_api_node_or_wrong_second_mask_output_fails(self):
        graph = copy.deepcopy(self.graph)
        graph["8"]["class_type"] = "SaveText"
        with self.assertRaisesRegex(ValueError, "class layout"):
            auditor.check_graph_bindings(graph, self.schemas)
        graph = copy.deepcopy(self.graph)
        graph["8"]["inputs"]["images"] = ["5", 0]
        with self.assertRaisesRegex(ValueError, "third-party edge differs"):
            auditor.check_graph_bindings(graph, self.schemas)

    def test_model_loader_auto_download_branch_requires_explicit_re_review(self):
        good = """
class LoadSAM3Model:
    @classmethod
    def execute(cls):
        if not checkpoint_path.exists():
            cls._download_from_huggingface()
    @staticmethod
    def _download_from_huggingface():
        return None
"""
        self.assertTrue(auditor.assert_auto_download_hazard(good))
        with self.assertRaisesRegex(ValueError, "re-review required"):
            auditor.assert_auto_download_hazard(good.replace(
                "cls._download_from_huggingface()", "print('no download')"))

    def test_lock_and_provenance_are_explicitly_pinned(self):
        lock = (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")
        key = auditor.WORKFLOW + ":"
        self.assertIn(key, lock)
        self.assertIn("commit: " + auditor.UPSTREAM_SHA, lock)
        self.assertEqual(len(auditor.UPSTREAM_SHA), 40)
        self.assertEqual(auditor.SOURCES["SAM3Segmentation"], "nodes/segmentation.py")


if __name__ == "__main__":
    unittest.main()
