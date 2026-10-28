"""No-network SGM IMAGE-link and pinned widget value domain contracts."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "sgm_widget_links", ROOT / "scripts" / "audit_sgm_widget_and_image_links.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

SOURCE = '''
class LoadSGMVFIModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model_path": (get_available_sgm_models(), {"default": SGM_DEFAULT_MODEL}),
            "tta": ("BOOLEAN", {"default": False}),
            "num_key_points": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
        }}

class SGMVFIInterpolate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE", {}),
            "model": ("SGM_VFI_MODEL", {}),
            "multiplier": ([2, 4, 8], {"default": 2}),
            "clear_cache_after_n_frames": ("INT", {"min": 1, "max": 100}),
            "keep_device": ("BOOLEAN", {}),
            "all_on_gpu": ("BOOLEAN", {}),
            "batch_size": ("INT", {"min": 1, "max": 64}),
            "chunk_size": ("INT", {"min": 0, "max": 10000}),
            "source_fps": ("FLOAT", {"min": 0.0, "max": 1000.0}),
            "target_fps": ("FLOAT", {"min": 0.0, "max": 1000.0}),
        }, "optional": {"settings": ("VFI_SETTINGS", {})}}

class SGMVFISegmentInterpolate(SGMVFIInterpolate):
    @classmethod
    def INPUT_TYPES(cls):
        base = SGMVFIInterpolate.INPUT_TYPES()
        base["required"]["segment_index"] = ("INT", {"min": 0, "max": 10000})
        base["required"]["segment_size"] = ("INT", {"min": 2, "max": 10000})
        return base
'''


def graph():
    with (ROOT / audit.baseline.GRAPH).open(encoding="utf-8") as fd:
        return json.load(fd)


def selected(g, node_id):
    return next(n for n in g["nodes"] if n["id"] == node_id)


class SgmWidgetAndImageLinkTests(unittest.TestCase):
    def test_current_graph_widget_ranges_and_image_wires(self):
        result = audit.check_sgm_widgets_and_image_links(graph(), SOURCE)
        self.assertEqual(result["status"], "WIDGET_AND_IMAGE_WIRES_SOURCE_ONLY_HOLD")
        self.assertEqual(result["image_links_verified"], [17, 27])
        self.assertEqual(result["total_widgets_checked"], 13)
        self.assertFalse(result["checkpoint_availability_or_licence_qualified"])
        self.assertFalse(result["model_or_gpu_inference_qualified"])

    def test_source_constraints_are_inferred_from_static_ast(self):
        specs = audit._source_widgets(SOURCE)
        self.assertEqual(specs[21]["model_path"]["type"], "COMBO")
        self.assertIsNone(specs[21]["model_path"]["choices"])
        self.assertEqual(specs[21]["num_key_points"]["max"], 1.0)
        self.assertEqual(specs[22]["multiplier"]["choices"], [2, 4, 8])
        self.assertEqual(specs[22]["clear_cache_after_n_frames"]["max"], 100)
        self.assertEqual(specs[22]["segment_size"]["min"], 2)
        self.assertEqual(specs[22]["segment_size"]["max"], 10000)

    def test_reject_widget_out_of_source_bounds(self):
        for node_id, index, bad in ((21, 2, -0.1), (21, 2, 1.1),
                                    (22, 1, 101), (22, 4, 0),
                                    (22, 9, 1), (22, 8, -1)):
            g = graph()
            selected(g, node_id)["widgets_values"][index] = bad
            with self.subTest(node_id=node_id, index=index):
                with self.assertRaisesRegex(ValueError, "outside pinned source bounds"):
                    audit.check_sgm_widgets_and_image_links(g, SOURCE)

    def test_reject_wrong_combo_or_boolean_values(self):
        for node_id, index, bad in ((22, 0, 3), (22, 0, "8"),
                                    (22, 2, 1), (21, 1, 1),
                                    (21, 0, ""), (21, 0, None)):
            g = graph()
            selected(g, node_id)["widgets_values"][index] = bad
            with self.subTest(node_id=node_id, index=index):
                with self.assertRaisesRegex(ValueError, "type/selection invalid"):
                    audit.check_sgm_widgets_and_image_links(g, SOURCE)

    def test_reject_image_link_destination_or_reverse_reference_drift(self):
        g = graph()
        entry = next(x for x in g["links"] if x[0] == 27)
        entry[3] = 4
        with self.assertRaisesRegex(ValueError, "IMAGE link source/destination"):
            audit.check_sgm_widgets_and_image_links(g, SOURCE)
        g = graph()
        selected(g, 31)["inputs"][0]["link"] = None
        with self.assertRaisesRegex(ValueError, "IMAGE port reverse reference"):
            audit.check_sgm_widgets_and_image_links(g, SOURCE)
        g = graph()
        selected(g, 4)["outputs"][0]["links"].remove(17)
        with self.assertRaisesRegex(ValueError, "IMAGE port reverse reference"):
            audit.check_sgm_widgets_and_image_links(g, SOURCE)

    def test_dynamic_unreviewed_widget_getter_is_rejected(self):
        source = SOURCE.replace("get_available_sgm_models()", "download_checkpoint()")
        with self.assertRaisesRegex(ValueError, "Unreviewed dynamic"):
            audit._source_widgets(source)

    def test_missing_widget_source_ranges_rejected(self):
        source = SOURCE.replace(
            '"clear_cache_after_n_frames": ("INT", {"min": 1, "max": 100})',
            '"clear_cache_after_n_frames": ("INT", {"default": 10})',
        )
        with self.assertRaisesRegex(ValueError, "outside pinned source bounds"):
            audit.check_sgm_widgets_and_image_links(graph(), source)

    def test_result_does_not_reveal_model_path_or_selected_widget_values(self):
        result = audit.check_sgm_widgets_and_image_links(graph(), SOURCE)
        rendered = json.dumps(result)
        self.assertNotIn("ours-1-2-points.pkl", rendered)
        self.assertNotIn("sword_test", rendered)
        self.assertTrue(result["all_widget_types_choices_numeric_bounds_verified"])

    def test_baseline_hold_must_pass_before_supplemental_checks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "nodes.py").write_text(SOURCE, encoding="utf-8")
            with mock.patch.object(audit.baseline, "audit") as prior:
                prior.return_value = {"status": "OTHER"}
                with self.assertRaisesRegex(ValueError, "not passed"):
                    audit.audit(ROOT, root)
                prior.assert_called_once_with(ROOT, root)
                prior.return_value = {"status": "SCHEMA_PARITY_SOURCE_ONLY_HOLD"}
                report = audit.audit(ROOT, root)
                self.assertEqual(report["total_widgets_checked"], 13)


if __name__ == "__main__":
    unittest.main()
