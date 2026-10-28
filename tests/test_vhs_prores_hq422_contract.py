"""No-network contracts for the disposable ProRes HQ 4:2:2 preset probe."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "qualify_vhs_prores_hq422.py"
spec = importlib.util.spec_from_file_location("osf_hq422", MODULE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def stock_definition():
    return {
        "extension": "mov",
        "main_pass": ["-n", "-c:v", "prores_ks",
                      "-profile:v", [["$profile"]],
                      "-vf", "scale=out_color_matrix=bt709"],
        "extra_widgets": [[
            "profile", ["lt", "standard", "hq", "4444", "4444xq"],
            {"default": "hq"},
        ]],
    }


class ProResHQ422ContractTests(unittest.TestCase):
    def test_only_new_disposable_preset_gets_forced_pixel_format(self):
        with tempfile.TemporaryDirectory() as td:
            base = (Path(td) / "custom_nodes" / "ComfyUI-VideoHelperSuite"
                    / "video_formats")
            base.mkdir(parents=True)
            original = base / "ProRes.json"
            original.write_text(json.dumps(stock_definition()), encoding="utf-8")
            snapshot = original.read_bytes()
            info = probe.prepare_disposable_hq422_preset(Path(td))
            changed = json.loads((base / (probe.FORMAT_NAME + ".json")).read_text())
            self.assertEqual(original.read_bytes(), snapshot)
            self.assertEqual(changed["main_pass"][-2:],
                             ["-pix_fmt", "yuv422p10le"])
            self.assertEqual(changed["main_pass"][:-2],
                             stock_definition()["main_pass"])
            self.assertTrue(info["upstream_source_unmodified"])
            with self.assertRaisesRegex(ValueError, "Unsafe or missing"):
                probe.prepare_disposable_hq422_preset(Path(td))

    def test_fails_closed_on_changed_stock_format(self):
        with tempfile.TemporaryDirectory() as td:
            base = (Path(td) / "custom_nodes" / "ComfyUI-VideoHelperSuite"
                    / "video_formats")
            base.mkdir(parents=True)
            data = stock_definition()
            data["main_pass"].extend(["-pix_fmt", "yuv444p10le"])
            (base / "ProRes.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unreviewed upstream"):
                probe.prepare_disposable_hq422_preset(Path(td))
            self.assertFalse((base / (probe.FORMAT_NAME + ".json")).exists())

    def test_hq_graph_has_same_synthetic_frames_and_two_prores_outputs(self):
        graph = probe.build_hq422_probe_prompt()
        self.assertEqual(set(graph), {"1", "2", "3", "4", "5"})
        self.assertEqual([graph[k]["class_type"] for k in ("1", "2")],
                         ["EmptyImage", "EmptyImage"])
        self.assertEqual(graph["1"]["inputs"]["color"], 0xFF0000)
        self.assertEqual(graph["2"]["inputs"]["color"], 0x0000FF)
        self.assertEqual(graph["3"]["inputs"],
                         {"image1": ["1", 0], "image2": ["2", 0]})
        for node in ("4", "5"):
            self.assertEqual(graph[node]["inputs"]["profile"], "hq")
            self.assertEqual(graph[node]["inputs"]["images"], ["3", 0])
            self.assertFalse(graph[node]["inputs"]["save_output"])
        self.assertEqual(graph["4"]["inputs"]["format"], "video/ProRes")
        self.assertEqual(graph["5"]["inputs"]["format"],
                         "video/" + probe.FORMAT_NAME)

    def test_history_requires_two_distinct_safe_temporary_movs(self):
        pid = "id"
        def media(name, fmt):
            return {"filename": name, "type": "temp",
                    "subfolder": "", "format": fmt}
        result = {pid: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {
                "4": {"gifs": [media("stock.mov", "video/ProRes")]},
                "5": {"gifs": [media(
                    "variant.mov", "video/" + probe.FORMAT_NAME)]},
            },
        }}
        stock, changed = probe.validate_hq422_history(result, pid)
        self.assertEqual(stock["filename"], "stock.mov")
        self.assertEqual(changed["filename"], "variant.mov")
        result[pid]["outputs"]["5"]["gifs"][0]["filename"] = "../outside.mov"
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            probe.validate_hq422_history(result, pid)
        result[pid]["outputs"]["5"]["gifs"][0]["filename"] = "stock.mov"
        with self.assertRaisesRegex(ValueError, "reused a filename"):
            probe.validate_hq422_history(result, pid)
        result[pid]["outputs"]["5"]["gifs"] = []
        with self.assertRaisesRegex(ValueError, "Missing exactly one"):
            probe.validate_hq422_history(result, pid)
        result[pid]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            probe.validate_hq422_history(result, pid)

    def test_decoded_full_rgb_frames_reject_order_and_single_channel_error(self):
        size = 64 * 64
        red = bytes((255, 0, 0)) * size
        blue = bytes((0, 0, 255)) * size
        good = probe.validate_hq_decoded_rgb(red + blue)
        self.assertEqual(good["maximum_absolute_rgb_error_by_frame"], [0, 0])
        near = bytes((250, 3, 1)) * size + bytes((3, 2, 250)) * size
        self.assertEqual(
            probe.validate_hq_decoded_rgb(near)["maximum_absolute_rgb_error_by_frame"],
            [5, 5],
        )
        for bad in (red, blue + red,
                    bytes((220, 0, 0)) * size + blue):
            with self.subTest(length=len(bad)):
                with self.assertRaisesRegex(ValueError, "ProRes HQ"):
                    probe.validate_hq_decoded_rgb(bad)

    def test_only_exact_approved_output_filenames_and_type_are_allowed(self):
        proper = {"filename": "clip_001.mov", "type": "temp",
                  "format": "video/ProRes", "subfolder": ""}
        self.assertEqual(probe._safe_temp_asset(proper, "video/ProRes"),
                         {"filename": "clip_001.mov", "type": "temp", "subfolder": ""})
        for variant in (
            {**proper, "filename": "other.mp4"},
            {**proper, "filename": "/tmp/clip.mov"},
            {**proper, "filename": "dir/clip.mov"},
            {**proper, "filename": "..\\clip.mov"},
            {**proper, "type": "output"},
            {**proper, "subfolder": "other"},
            {**proper, "format": "video/osf_ci_proreshq422"},
        ):
            with self.subTest(data=variant):
                with self.assertRaises(ValueError):
                    probe._safe_temp_asset(variant, "video/ProRes")


if __name__ == "__main__":
    unittest.main()
