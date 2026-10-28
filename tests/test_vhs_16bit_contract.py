"""Offline fail-closed contracts for the disposable VHS 8bit/16bit comparison."""
from __future__ import annotations

from array import array
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "qualify_vhs_16bit.py"
spec = importlib.util.spec_from_file_location("osf_vhs16", PATH)
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)


class VHSInputPrecisionTests(unittest.TestCase):
    def test_graph_uses_same_tensor_and_two_unmodified_codec_profiles(self):
        graph = qualifier.build_precision_prompt()
        self.assertEqual(set(graph), {"1", "2", "3"})
        self.assertEqual(graph["1"]["class_type"], "OSFTestPrecisionFrames")
        self.assertEqual(graph["2"]["inputs"]["images"], ["1", 0])
        self.assertEqual(graph["3"]["inputs"]["images"], ["1", 0])
        self.assertEqual(graph["2"]["inputs"]["format"], "video/ProRes")
        self.assertEqual(
            graph["3"]["inputs"]["format"], "video/osf_ci_prores16bit"
        )
        for node in ("2", "3"):
            self.assertEqual(graph[node]["inputs"]["profile"], "4444")
            self.assertFalse(graph[node]["inputs"]["save_output"])
            self.assertEqual(graph[node]["inputs"]["frame_rate"], 2)

    def test_ci_only_preset_differs_by_sole_16bit_override(self):
        with tempfile.TemporaryDirectory() as temp:
            upstream = (Path(temp) / "custom_nodes" /
                        "ComfyUI-VideoHelperSuite" / "video_formats")
            upstream.mkdir(parents=True)
            source = {
                "extension": "mov",
                "main_pass": ["-c:v", "prores_ks"],
                "extra_widgets": [["profile", ["4444"]]],
                "fake_trc": "bt709",
            }
            original = upstream / "ProRes.json"
            original.write_text(json.dumps(source), encoding="utf-8")
            result = qualifier.prepare_disposable_16bit_preset(Path(temp))
            fixture = json.loads(
                (upstream / "osf_ci_prores16bit.json").read_text("utf-8")
            )
            self.assertEqual(fixture, {**source, "input_color_depth": "16bit"})
            self.assertEqual(json.loads(original.read_text("utf-8")), source)
            self.assertTrue(result["upstream_default_8bit_intact"])
            with self.assertRaisesRegex(ValueError, "Unsafe/missing"):
                qualifier.prepare_disposable_16bit_preset(Path(temp))

    def test_fixture_is_controlled_sub8bit_float_tensor_source(self):
        source = (ROOT / "tests" / "fixtures" /
                  "comfy_12bit_source" / "__init__.py").read_text("utf-8")
        self.assertIn("NODE_CLASS_MAPPINGS", source)
        self.assertIn("OSFTestPrecisionFrames", source)
        self.assertIn("value / 4095.0", source)
        self.assertIn("2038 + 32 * frame + 10 * row + 5 * col", source)
        for frame in range(2):
            for row in range(2):
                left = 2038 + 32 * frame + 10 * row
                right = left + 5
                self.assertEqual(int(left * 255 / 4095 + 0.5),
                                 int(right * 255 / 4095 + 0.5))

    def test_history_requires_both_distinct_temp_movs(self):
        ident = "test-prompt"
        def video(filename, fmt):
            return {"filename": filename, "format": fmt,
                    "subfolder": "", "type": "temp"}
        correct = {ident: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {
                "2": {"gifs": [video("control.mov", "video/ProRes")]},
                "3": {"gifs": [video("precise.mov", "video/osf_ci_prores16bit")]},
            },
        }}
        a, b = qualifier.validate_precision_history(correct, ident)
        self.assertEqual(a["filename"], "control.mov")
        self.assertEqual(b["filename"], "precise.mov")
        correct[ident]["outputs"]["3"]["gifs"][0]["filename"] = "../bad.mov"
        with self.assertRaisesRegex(ValueError, "Unsafe precision"):
            qualifier.validate_precision_history(correct, ident)
        correct[ident]["outputs"]["3"]["gifs"][0]["filename"] = "control.mov"
        with self.assertRaisesRegex(ValueError, "reused"):
            qualifier.validate_precision_history(correct, ident)
        correct[ident]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            qualifier.validate_precision_history(correct, ident)

    def test_control_collapse_and_precise_distinctions(self):
        n = 2 * qualifier.FRAME_COMPONENTS
        default = array("H", [2048] * n)
        high = array("H", [2048] * n)
        for frame in range(2):
            for row in range(2):
                offset = (frame * qualifier.FRAME_COMPONENTS
                          + (row * 32 + 16) * 64)
                default[offset + 16] = 2080
                default[offset + 48] = 2080
                high[offset + 16] = 2079
                high[offset + 48] = 2083
        result = qualifier.verify_precision_contrast(default, high)
        self.assertEqual(result["default_8bit_collapsed_pairs"], 4)
        self.assertEqual(result["optin16_preserved_pairs"], 4)
        self.assertEqual(result["optin16_luma_code_level_deltas"], [4] * 4)
        self.assertFalse(result["bit_exact_source_fidelity_qualified"])

    def test_rejects_quantized_precise_input(self):
        n = 2 * qualifier.FRAME_COMPONENTS
        flat = array("H", [2048] * n)
        with self.assertRaisesRegex(ValueError, "did not retain"):
            qualifier.verify_precision_contrast(flat, flat)

    def test_rejects_wrong_default_control_and_outsize_delta(self):
        n = 2 * qualifier.FRAME_COMPONENTS
        default = array("H", [2048] * n)
        precise = array("H", [2048] * n)
        for frame in range(2):
            for row in range(2):
                index = (frame * qualifier.FRAME_COMPONENTS
                         + (row * 32 + 16) * 64)
                precise[index + 48] = 2053
        result = qualifier.verify_precision_contrast(default, precise)
        self.assertEqual(result["optin16_preserved_pairs"], 4)
        default[16 * 64 + 48] = 2053
        with self.assertRaisesRegex(ValueError, "default 8-bit control"):
            qualifier.verify_precision_contrast(default, precise)
        default[16 * 64 + 48] = 2048
        precise[16 * 64 + 48] = 2080
        with self.assertRaisesRegex(ValueError, "did not retain"):
            qualifier.verify_precision_contrast(default, precise)


if __name__ == "__main__":
    unittest.main()
