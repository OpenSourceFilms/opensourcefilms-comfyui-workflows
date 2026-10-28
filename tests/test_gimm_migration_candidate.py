"""No-network contracts for the non-deployable GIMM two-name migration plan."""
from __future__ import annotations

import copy
import importlib
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
plan = importlib.import_module("plan_gimm_vfi_class_migration")

GIMM_TYPES = '''
class DownloadAndLoadGIMMVFIModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": (["first.safetensors", "second.safetensors"],)},
                "optional": {"precision": (["fp32", "bf16", "fp16"],),
                             "torch_compile": ("BOOLEAN",)}}
    RETURN_TYPES = ("GIMMVIF_MODEL",)
    RETURN_NAMES = ("gimmvfi_model",)

class GIMMVFI_interpolate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
                    "gimmvfi_model": ("GIMMVIF_MODEL",),
                    "images": ("IMAGE",),
                    "ds_factor": ("FLOAT",),
                    "interpolation_factor": ("INT",),
                    "seed": ("INT",)},
                "optional": {"output_flows": ("BOOLEAN",)}}
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("images", "flow_tensors")
'''


def source_schemas():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "nodes.py"
        path.write_text(GIMM_TYPES, encoding="utf-8")
        return {
            1: plan._source_schema(path, "DownloadAndLoadGIMMVFIModel"),
            2: plan._source_schema(path, "GIMMVFI_interpolate"),
        }


class GimmMigrationContracts(unittest.TestCase):
    def setUp(self):
        import json
        self.graph = json.loads(
            (ROOT / plan.source_audit.GRAPH).read_text(encoding="utf-8")
        )
        self.schemas = source_schemas()

    def test_source_ast_has_exact_reviewed_typed_sockets_and_outputs(self):
        self.assertEqual(self.schemas[1]["socket_types"], {
            "model": "COMBO", "precision": "COMBO", "torch_compile": "BOOLEAN",
        })
        self.assertEqual(self.schemas[2]["socket_types"], {
            "gimmvfi_model": "GIMMVIF_MODEL", "images": "IMAGE",
            "ds_factor": "FLOAT", "interpolation_factor": "INT",
            "seed": "INT", "output_flows": "BOOLEAN",
        })
        self.assertEqual(self.schemas[1]["output_types"], ("GIMMVIF_MODEL",))
        self.assertEqual(self.schemas[2]["output_types"], ("IMAGE", "IMAGE"))

    def test_two_name_candidate_preserves_original_graph(self):
        original = copy.deepcopy(self.graph)
        result = plan.construct_candidate(self.graph, self.schemas)
        self.assertEqual(self.graph, original)
        self.assertEqual(result["changes_count"], 2)
        self.assertEqual([x["node_id"] for x in result["changes"]], [1, 2])
        self.assertEqual(
            [x["pinned_class"] for x in result["changes"]],
            ["DownloadAndLoadGIMMVFIModel", "GIMMVFI_interpolate"],
        )
        self.assertEqual(result["status"], "CANDIDATE_ONLY_HOLD")
        self.assertTrue(result["original_graph_untouched"])
        self.assertTrue(result["link_and_widget_structures_unchanged"])
        self.assertFalse(result["end_to_end_workflow_qualified"])
        self.assertFalse(result["model_weights_downloaded"])
        self.assertEqual(len(result["candidate_canonical_json_sha256"]), 64)

    def test_changed_socket_name_type_and_output_type_fail(self):
        for mutation in ("input_name", "input_type", "output_type", "output_name"):
            graph = copy.deepcopy(self.graph)
            node = next(x for x in graph["nodes"] if x["id"] == 2)
            if mutation == "input_name":
                node["inputs"][0]["name"] = "wrong_name"
            elif mutation == "input_type":
                node["inputs"][0]["type"] = "MASK"
            elif mutation == "output_type":
                node["outputs"][0]["type"] = "MASK"
            else:
                node["outputs"][0]["name"] = "wrong"
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError, "GIMM"):
                    plan.construct_candidate(graph, self.schemas)

    def test_missing_or_reassigned_historical_node_fails(self):
        graph = copy.deepcopy(self.graph)
        node = next(x for x in graph["nodes"] if x["id"] == 1)
        node["type"] = "DownloadAndLoadGIMMVFIModel"
        with self.assertRaisesRegex(ValueError, "class or node id"):
            plan.construct_candidate(graph, self.schemas)
        graph = copy.deepcopy(self.graph)
        graph["nodes"] = [x for x in graph["nodes"] if x["id"] != 1]
        with self.assertRaisesRegex(ValueError, "must exist"):
            plan.construct_candidate(graph, self.schemas)

    def test_provenance_mismatch_fails(self):
        graph = copy.deepcopy(self.graph)
        node = next(x for x in graph["nodes"] if x["id"] == 1)
        node["properties"]["ver"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "provenance"):
            plan.construct_candidate(graph, self.schemas)

    def test_no_unreviewed_dynamic_socket_or_return_source(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nodes.py"
            p.write_text(
                "class DownloadAndLoadGIMMVFIModel:\n"
                "    @classmethod\n"
                "    def INPUT_TYPES(cls):\n"
                "        return dynamically_construct_sockets()\n"
                "    RETURN_TYPES = ('GIMMVIF_MODEL',)\n"
                "    RETURN_NAMES = ('gimmvfi_model',)\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "uniquely literal"):
                plan._source_schema(p, "DownloadAndLoadGIMMVFIModel")

    def test_source_and_model_state_not_promoted(self):
        result = plan.construct_candidate(self.graph, self.schemas)
        self.assertTrue(result["candidate_only_non_deployable"])
        self.assertFalse(result["sgm_gpu_checkpoint_and_rights_qualified"])
        self.assertFalse(result["gimm_gpu_checkpoint_and_rights_qualified"])
        self.assertEqual(result["source_audit_status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
