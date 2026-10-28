"""No-weight contracts for VHS RGB-channel 16-bit input fine-detail test."""
from __future__ import annotations

from array import array
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
source = ROOT / "scripts" / "qualify_vhs_chroma_16bit.py"
spec = importlib.util.spec_from_file_location("osf_vhs_chroma", source)
chroma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chroma)


class RGBChromaPrecisionTests(unittest.TestCase):
    def test_source_has_one_sub8bit_rgb_difference_per_frame(self):
        fixture = (ROOT / "tests" / "fixtures" /
                   "comfy_12bit_source" / "__init__.py").read_text("utf-8")
        self.assertIn("OSFTestChromaPrecisionFrames", fixture)
        self.assertIn("range(3)", fixture)
        self.assertIn("image[channel, :, 32:, channel]", fixture)
        left, right = 2038, 2046
        self.assertNotEqual(left, right)
        self.assertEqual(int(left * 255 / 4095 + .5),
                         int(right * 255 / 4095 + .5))

    def test_graph_has_three_frames_and_isolated_default_and_optin_formats(self):
        graph = chroma.build_chroma_precision_prompt()
        self.assertEqual(set(graph), {"1", "2", "3"})
        self.assertEqual(graph["1"]["class_type"], "OSFTestChromaPrecisionFrames")
        self.assertEqual(graph["2"]["inputs"]["images"], ["1", 0])
        self.assertEqual(graph["3"]["inputs"]["images"], ["1", 0])
        self.assertEqual(graph["2"]["inputs"]["format"], "video/ProRes")
        self.assertEqual(graph["3"]["inputs"]["format"],
                         "video/osf_ci_prores16bit")
        for node in ("2", "3"):
            self.assertEqual(graph[node]["inputs"]["profile"], "4444")
            self.assertFalse(graph[node]["inputs"]["save_output"])
            self.assertEqual(graph[node]["inputs"]["frame_rate"], 2)

    @staticmethod
    def _arrays():
        n = chroma.FRAMES * chroma.COMPONENTS_PER_FRAME
        control = array("H", [2048] * n)
        precise = array("H", [2048] * n)
        for frame, plane in enumerate(chroma.PROBED_YUV_PLANES):
            base = frame * chroma.COMPONENTS_PER_FRAME + plane * chroma.PIXELS
            for dy in chroma.INTERIOR_OFFSETS:
                for dx in chroma.INTERIOR_OFFSETS:
                    row = base + dy * chroma.WIDTH
                    precise[row + 32 + dx] = 2053
        return control, precise

    def test_all_rgb_target_channels_pass_27_spatial_checks(self):
        control, precise = self._arrays()
        result = chroma.verify_rgb_chroma_detail(control, precise)
        self.assertEqual(result["control_collapsed_pairs"], 27)
        self.assertEqual(result["optin_preserved_pairs"], 27)
        self.assertEqual(result["source_rgb_channels_checked"], 3)
        self.assertEqual(
            [(x["source_rgb_component"], x["decoded_yuv_component"])
             for x in result["per_channel_grid_results"]],
            [("R", "V"), ("G", "Y"), ("B", "U")],
        )
        self.assertEqual(
            [x["minimum_positive_difference_12bit"]
             for x in result["per_channel_grid_results"]],
            [5, 5, 5],
        )
        self.assertFalse(result["rgb_source_component_accuracy_qualified"])

    def test_rejects_8bit_control_that_retains_differences(self):
        control, precise = self._arrays()
        control[2 * chroma.PIXELS + 8 * chroma.WIDTH + 40] = 2053
        with self.assertRaisesRegex(ValueError, "default 8-bit RGB control"):
            chroma.verify_rgb_chroma_detail(control, precise)

    def test_rejects_optin_quantization_in_each_color(self):
        for frame, plane in enumerate(chroma.PROBED_YUV_PLANES):
            control, precise = self._arrays()
            index = (frame * chroma.COMPONENTS_PER_FRAME
                     + plane * chroma.PIXELS + 8 * chroma.WIDTH + 40)
            precise[index] = 2048
            with self.subTest(frame=frame):
                with self.assertRaisesRegex(ValueError, "lost or reversed"):
                    chroma.verify_rgb_chroma_detail(control, precise)

    def test_rejects_wrong_sign_overshoot_and_sample_length(self):
        for diff in (-2, 33):
            control, precise = self._arrays()
            precise[2 * chroma.PIXELS + 16 * chroma.WIDTH + 48] = 2048 + diff
            with self.subTest(diff=diff):
                with self.assertRaisesRegex(ValueError, "lost or reversed"):
                    chroma.verify_rgb_chroma_detail(control, precise)
        control, precise = self._arrays()
        with self.assertRaisesRegex(ValueError, "sample count incorrect"):
            chroma.verify_rgb_chroma_detail(control[:-1], precise)

    def test_bounded_video_metadata_and_no_commercial_fidelity_claim(self):
        content = source.read_text("utf-8")
        self.assertIn("validate_precision_history(history, ident)", content)
        self.assertIn("_read_mov(port, control)", content)
        self.assertIn("EXPECTED_BYTES", content)
        self.assertIn("yuv444p12le", content)
        self.assertIn('"rgb_source_component_accuracy_qualified": False', content)
        self.assertIn('"binary_outputs_uploaded": False', content)


if __name__ == "__main__":
    unittest.main()
