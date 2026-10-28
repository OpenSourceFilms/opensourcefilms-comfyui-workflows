"""AST-only tests for exact pinned native SAM3 probe core edges."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    item = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(item)
    return item


core = module("sam3_core_source_only", "audit_sam3_custompkg_core_links.py")
sam3 = module("sam3_external_source_only", "audit_sam3_custompkg_source.py")

CLASSIC = '''
class LoadImage:
    @classmethod
    def INPUT_TYPES(s):
        files = []
        return {"required": {"image": (sorted(files), {"image_upload": True})}}
    RETURN_TYPES = ("IMAGE", "MASK")

class SaveImage:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "images": ("IMAGE", {"tooltip": "Test"}),
            "filename_prefix": ("STRING", {"default": "Test"})
        }, "hidden": {"prompt": "PROMPT"}}
    RETURN_TYPES = ("IMAGE",)
    OUTPUT_NODE = True
'''

MASK = '''
class MaskToImage(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="MaskToImage",
            inputs=[IO.Mask.Input("mask")],
            outputs=[IO.Image.Output()],
        )
'''


class NativeSAM3ProbeEdges(unittest.TestCase):
    def setUp(self):
        self.graph = json.loads((ROOT / sam3.WORKFLOW).read_text(encoding="utf-8"))
        self.thirdparty = {
            name: {
                "inputs": inputs,
                "outputs": outputs,
            }
            for name, (inputs, outputs) in sam3.SCHEMAS.items()
        }
        self.native = {
            **core.parse_classic_core(CLASSIC),
            "MaskToImage": core.parse_mask_to_image(MASK),
        }

    def test_four_edges_typed_including_two_formerly_unverified(self):
        finding = core.check_core_touched_edges(
            self.graph, self.thirdparty, self.native
        )
        self.assertEqual(finding["native_core_node_instances"], 4)
        self.assertEqual(finding["typed_edges_touching_core_nodes"], 4)
        self.assertEqual(finding["previously_unverified_core_source_edges_resolved"], 2)
        self.assertFalse(finding["model_file_io_executed"])
        self.assertFalse(finding["full_graph_executable"])

    def test_classic_node_input_types_and_output_slots_are_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "output types"):
            core.parse_classic_core(
                CLASSIC.replace('("IMAGE", "MASK")', '("MASK", "IMAGE")')
            )
        with self.assertRaisesRegex(ValueError, "socket input type"):
            core.parse_classic_core(
                CLASSIC.replace('"images": ("IMAGE",', '"images": ("MASK",')
            )
        with self.assertRaisesRegex(ValueError, "upload socket schema"):
            core.parse_classic_core(
                CLASSIC.replace('"image_upload": True', '"image_upload": False')
            )
        with self.assertRaisesRegex(ValueError, "Missing or duplicate"):
            core.parse_classic_core(CLASSIC.replace("class LoadImage:", "class WrongLoadImage:"))

    def test_native_mask_schema_requires_real_mask_to_image_contract(self):
        self.assertEqual(core.parse_mask_to_image(MASK)["outputs"], ("IMAGE",))
        for modified in (
            MASK.replace('IO.Mask.Input("mask")', 'IO.Image.Input("mask")'),
            MASK.replace('IO.Image.Output()', 'IO.Mask.Output()'),
            MASK.replace('"MaskToImage"', '"OtherType"'),
        ):
            with self.assertRaisesRegex(ValueError, "MaskToImage"):
                core.parse_mask_to_image(modified)

    def test_wrong_link_slot_and_target_field_fail(self):
        graph = copy.deepcopy(self.graph)
        graph["5"]["inputs"]["image"] = ["2", 1]
        with self.assertRaisesRegex(ValueError, "link changed"):
            core.check_core_touched_edges(graph, self.thirdparty, self.native)
        graph = copy.deepcopy(self.graph)
        graph["7"]["inputs"]["images"] = ["5", 2]
        with self.assertRaisesRegex(ValueError, "link changed"):
            core.check_core_touched_edges(graph, self.thirdparty, self.native)
        schema = copy.deepcopy(self.native)
        schema["SaveImage"]["inputs"]["images"] = "MASK"
        with self.assertRaisesRegex(ValueError, "target socket type"):
            core.check_core_touched_edges(self.graph, self.thirdparty, schema)
        schema = copy.deepcopy(self.native)
        schema["MaskToImage"]["outputs"] = ("MASK",)
        with self.assertRaisesRegex(ValueError, "output slot type"):
            core.check_core_touched_edges(self.graph, self.thirdparty, schema)

    def test_core_commit_is_exact_and_no_missing_source_is_accepted(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "nodes.py").write_text(CLASSIC, encoding="utf-8")
            (root / "comfy_extras").mkdir()
            (root / "comfy_extras/nodes_mask.py").write_text(MASK, encoding="utf-8")
            with mock.patch.object(core.subprocess, "run") as call:
                call.return_value.stdout = core.COMFY_CORE_SHA + "\n"
                finding = core.verify_pinned_core(root, self.graph, self.thirdparty)
                self.assertEqual(finding["core_revision"], core.COMFY_CORE_SHA)
                self.assertEqual(
                    finding["native_binding"]["typed_edges_touching_core_nodes"], 4
                )
                call.return_value.stdout = "0" * 40 + "\n"
                with self.assertRaisesRegex(ValueError, "Wrong ComfyUI core revision"):
                    core.verify_pinned_core(root, self.graph, self.thirdparty)
                call.return_value.stdout = core.COMFY_CORE_SHA + "\n"
                (root / "comfy_extras/nodes_mask.py").unlink()
                with self.assertRaisesRegex(ValueError, "Missing or symlinked"):
                    core.verify_pinned_core(root, self.graph, self.thirdparty)

    def test_docs_and_primary_auditor_require_pinned_core(self):
        primary = (ROOT / "scripts/audit_sam3_custompkg_source.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('parser.add_argument("--core-dir"', primary)
        self.assertIn("verify_pinned_core(core_root, graph, schemas)", primary)
        self.assertIn('"unverified_core_source_edges"] = 0', primary)
        self.assertEqual(len(core.COMFY_CORE_SHA), 40)


if __name__ == "__main__":
    unittest.main()
