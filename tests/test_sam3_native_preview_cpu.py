"""No-network regression contract for pinned native SAM3 preview CPU smoke."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "qualify_sam3_native_preview_cpu.py"
spec = importlib.util.spec_from_file_location("osf_sam3_preview_cpu", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def example_history():
    return {"synthetic": {
        "status": {"completed": True, "status_str": "success"},
        "outputs": {"2": {"images": [{
            "filename": "sam3_track_preview_0a1b2c3d.mp4",
            "subfolder": "", "type": "temp",
        }], "animated": [True]}},
    }}


def frame_bytes(left=(255, 128, 13), right=(31, 120, 181)):
    frame = bytearray(64 * 64 * 3)
    for x, y, _ in mod.EXPECTED_PROBES:
        color = left if x == 12 else right if x == 46 else (0, 0, 0)
        off = (y * 64 + x) * 3
        frame[off:off + 3] = bytes(color)
    return bytes(frame)


class NativeSAM3PreviewContract(unittest.TestCase):
    def test_fixed_model_free_graph_uses_pinned_native_preview(self):
        self.assertEqual(mod.build_native_sam3_preview_prompt(), {
            "1": {"class_type": "OSF_CI_SCAILTrack", "inputs": {}},
            "2": {"class_type": "SAM3_TrackPreview", "inputs": {
                "track_data": ["1", 0], "opacity": 1.0, "fps": 2,
            }},
        })

    def test_history_requires_success_and_exact_temp_h264_preview(self):
        h = example_history()
        item = mod.validate_sam3_preview_history(h, "synthetic")
        self.assertEqual(item["filename"], "sam3_track_preview_0a1b2c3d.mp4")
        h["synthetic"]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            mod.validate_sam3_preview_history(h, "synthetic")
        h["synthetic"]["status"]["completed"] = True
        h["synthetic"]["outputs"]["2"]["images"].clear()
        with self.assertRaisesRegex(ValueError, "Expected one"):
            mod.validate_sam3_preview_history(h, "synthetic")

    def test_history_rejects_untrusted_names_types_and_missing_animation(self):
        for item in (
            {"filename": "../escape.mp4"},
            {"filename": "other_video.mp4"},
            {"filename": "sam3_track_preview_0a1b2c3d.mp4", "type": "output"},
            {"filename": "sam3_track_preview_0a1b2c3d.mp4", "subfolder": "../out"},
        ):
            with self.subTest(item=item):
                h = example_history()
                h["synthetic"]["outputs"]["2"]["images"][0].update(item)
                with self.assertRaisesRegex(ValueError, "Unsafe native"):
                    mod.validate_sam3_preview_history(h, "synthetic")
        h = example_history()
        h["synthetic"]["outputs"]["2"].pop("animated")
        with self.assertRaisesRegex(ValueError, "not marked animated"):
            mod.validate_sam3_preview_history(h, "synthetic")

    def test_exact_probes_validate_two_distinct_colours_and_black_background(self):
        frame = frame_bytes()
        r = mod.validate_sam3_preview_pixels(frame + frame)
        self.assertEqual(r["colour_probes_checked"], 10)
        self.assertEqual(r["maximum_rgb_channel_error_by_frame"], [0, 0])
        self.assertFalse(r["real_sam3_detection_or_tracking_executed"])
        self.assertFalse(r["video_binary_uploaded"])

    def test_pixel_mismatch_wrong_frame_size_or_swapped_ids_fails(self):
        frame = frame_bytes()
        with self.assertRaisesRegex(ValueError, "decoded frame count"):
            mod.validate_sam3_preview_pixels(frame)
        with self.assertRaisesRegex(ValueError, "mask/background colour"):
            mod.validate_sam3_preview_pixels(frame_bytes(
                left=(31, 120, 181), right=(255, 128, 13)
            ) + frame)
        with self.assertRaisesRegex(ValueError, "mask/background colour"):
            mod.validate_sam3_preview_pixels(frame_bytes(left=(100, 100, 100)) + frame)

    def test_runner_keeps_native_preview_separate_from_model_inference(self):
        code = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("execute_sam3_trackpreview_cpu(", code)
        self.assertIn('"native_sam3_track_preview_cpu"', code)


if __name__ == "__main__":
    unittest.main()
