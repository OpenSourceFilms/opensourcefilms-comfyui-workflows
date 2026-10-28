"""No-network contracts for model-free native SCAIL mask-generation acceptance."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "qualify_scail_native_mask_cpu.py"
spec = importlib.util.spec_from_file_location("osf_scail_cpu", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def history():
    def item(filename):
        return {"filename": filename, "type": "temp", "subfolder": ""}
    return {"synthetic": {
        "status": {"status_str": "success", "completed": True},
        "outputs": {
            "4": {"images": [item("drv0.png"), item("drv1.png")]},
            "5": {"images": [item("refa.png")]},
            "7": {"images": [item("rep0.png"), item("rep1.png")]},
            "8": {"images": [item("refr.png")]},
        },
    }}


class SCAILNativeSyntheticCPUContract(unittest.TestCase):
    def test_exact_native_class_graph_and_no_model_inputs(self):
        graph = mod.build_scail_cpu_prompt()
        self.assertEqual(set(graph), {str(i) for i in range(1, 9)})
        self.assertEqual(
            [graph[str(i)]["class_type"] for i in range(1, 9)],
            ["OSF_CI_SCAILTrack", "OSF_CI_SCAILReferenceMask",
             "SCAIL2ColoredMask", "PreviewImage", "PreviewImage",
             "SCAIL2ColoredMask", "PreviewImage", "PreviewImage"],
        )
        for ident, mode in (("3", False), ("6", True)):
            self.assertEqual(graph[ident]["inputs"], {
                "driving_track_data": ["1", 0],
                "ref_track_data": ["2", 0],
                "object_indices": "",
                "sort_by": "left_to_right",
                "replacement_mode": mode,
            })
        self.assertEqual(graph["4"]["inputs"], {"images": ["3", 0]})
        self.assertEqual(graph["5"]["inputs"], {"images": ["3", 1]})
        self.assertEqual(graph["7"]["inputs"], {"images": ["6", 0]})
        self.assertEqual(graph["8"]["inputs"], {"images": ["6", 1]})
        self.assertFalse(any("Loader" in node["class_type"]
                             or "Sampler" in node["class_type"]
                             or "WanSCAIL" in node["class_type"]
                             for node in graph.values()))

    def test_expected_sort_and_animation_replacement_backgrounds(self):
        def pix(data, x, y):
            n = (y * 64 + x) * 3
            return tuple(data[n:n+3])
        for mode, drive_bg, ref_bg in (
            ("animation", (0, 0, 0), (255, 255, 255)),
            ("replacement", (255, 255, 255), (0, 0, 0)),
        ):
            drive = mod._expected_rgb(mode, "drive")
            ref = mod._expected_rgb(mode, "ref")
            self.assertEqual(len(drive), 64*64*3)
            self.assertEqual(pix(drive, 9, 18), (0, 0, 255))
            self.assertEqual(pix(drive, 42, 18), (255, 0, 0))
            self.assertEqual(pix(drive, 1, 1), drive_bg)
            self.assertEqual(pix(ref, 27, 27), (0, 0, 255))
            self.assertEqual(pix(ref, 1, 1), ref_bg)

    def test_history_requires_completed_six_temp_previews(self):
        self.assertEqual(mod.validate_scail_history(history(), "synthetic"),
                         history()["synthetic"])
        h = history()
        h["synthetic"]["outputs"]["4"]["images"].pop()
        with self.assertRaisesRegex(ValueError, "image count mismatch"):
            mod.validate_scail_history(h, "synthetic")
        h = history()
        h["synthetic"]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            mod.validate_scail_history(h, "synthetic")
        with self.assertRaisesRegex(ValueError, "Missing"):
            mod.validate_scail_history({}, "synthetic")

    def test_fixture_bit_packing_and_no_weight_dependency(self):
        source = (ROOT / "tests" / "fixtures" /
                  "comfy_scail_cpu_source" / "__init__.py").read_text()
        self.assertIn('RETURN_TYPES = ("SAM3_TRACK_DATA",)', source)
        self.assertIn('RETURN_TYPES = ("MASK",)', source)
        self.assertIn("masks.view(2, 2, 64, 8, 8)", source)
        self.assertIn("40:56", source)
        self.assertIn("8:24", source)
        self.assertNotIn("load_model_gpu(", source)

    def test_driver_keeps_native_graph_scope_distinct_from_model_inference(self):
        code = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text()
        self.assertIn('"scail_native_cpu_mask_execution"', code)
        self.assertIn("execute_scail_cpu_graph(", code)
        self.assertIn("gpu_or_model_inference_qualified", code)


if __name__ == "__main__":
    unittest.main()
