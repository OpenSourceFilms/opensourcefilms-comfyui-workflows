"""No-network contracts for actual pinned VHS_LoadVideo no-VAE IMAGE acceptance."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "qualify_vhs_no_vae_video_cpu.py"
spec = importlib.util.spec_from_file_location("osf_vhs_no_vae_cpu", FILE)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


class VHSNoVAEVideoContract(unittest.TestCase):
    def test_real_loader_graph_requires_no_vae_and_explicit_safe_video(self):
        g = loader.build_no_vae_video_prompt()
        self.assertEqual(set(g), {"1", "2"})
        self.assertEqual(g["1"]["class_type"], "VHS_LoadVideo")
        self.assertEqual(g["1"]["inputs"]["video"], loader.SOURCE_BASENAME)
        self.assertEqual(g["1"]["inputs"]["frame_load_cap"], 2)
        self.assertEqual(g["1"]["inputs"]["format"], "None")
        self.assertEqual(g["1"]["inputs"]["select_every_nth"], 1)
        self.assertNotIn("vae", g["1"]["inputs"])
        self.assertEqual(g["2"], {
            "class_type": "PreviewImage", "inputs": {"images": ["1", 0]}
        })
        self.assertFalse(any("LoadImage" == n["class_type"] for n in g.values()))

    def test_two_actual_rgb_frames_and_codec_error_tolerance(self):
        red = bytes((255, 0, 0)) * (64 * 64)
        blue = bytes((0, 0, 255)) * (64 * 64)
        result = loader.validate_no_vae_rgb_frames([red, blue])
        self.assertEqual(result["maximum_absolute_channel_error"], [0, 0])
        self.assertTrue(result["image_output_accepted_by_native_preview"])
        self.assertFalse(result["vae_input_present"])
        self.assertFalse(result["sam3_inference_qualified"])
        self.assertFalse(result["source_files_uploaded"])
        near = bytes((249, 3, 1)) * (64 * 64)
        next_frame = bytes((2, 1, 252)) * (64 * 64)
        self.assertEqual(
            loader.validate_no_vae_rgb_frames([near, next_frame])[
                "maximum_absolute_channel_error"
            ], [6, 3],
        )

    def test_wrong_frame_count_order_and_any_pixel_error_fail(self):
        red = bytes((255, 0, 0)) * (64 * 64)
        blue = bytes((0, 0, 255)) * (64 * 64)
        corrupted = bytearray(red)
        corrupted[-2] = 45
        for bad in ([red], [blue, red], [red, bytes(corrupted)],
                    [red, blue[:-3]]):
            with self.subTest(count=len(bad)):
                with self.assertRaisesRegex(ValueError, "VHS no-VAE"):
                    loader.validate_no_vae_rgb_frames(bad)

    def test_history_fails_without_completed_video_and_two_temp_previews(self):
        pid = "synthetic"
        entry = lambda name: {
            "filename": name, "type": "temp", "subfolder": ""
        }
        history = {pid: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"2": {"images": [
                entry("first.png"), entry("second.png")
            ]}},
        }}
        self.assertEqual(len(loader.validate_no_vae_video_history(history, pid)), 2)
        with self.assertRaisesRegex(ValueError, "missing"):
            loader.validate_no_vae_video_history({}, pid)
        history[pid]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            loader.validate_no_vae_video_history(history, pid)
        history[pid]["status"]["completed"] = True
        history[pid]["outputs"]["2"]["images"].pop()
        with self.assertRaisesRegex(ValueError, "two previews"):
            loader.validate_no_vae_video_history(history, pid)
        history[pid]["outputs"]["2"]["images"].append(entry("second.png"))
        history[pid]["outputs"]["2"]["images"][1]["type"] = "output"
        with self.assertRaisesRegex(ValueError, "malformed"):
            loader.validate_no_vae_video_history(history, pid)

    def test_missing_and_symlinked_input_directory_rejected_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.dict("sys.modules", {"imageio_ffmpeg": mock.MagicMock()}):
                with self.assertRaisesRegex(ValueError, "missing or symlinked"):
                    loader.prepare_synthetic_video_input(root)
                inp = root / "input"
                inp.symlink_to(root)
                with self.assertRaisesRegex(ValueError, "missing or symlinked"):
                    loader.prepare_synthetic_video_input(root)
                inp.unlink()
                inp.mkdir()
                (inp / loader.SOURCE_BASENAME).write_bytes(b"preexisting")
                with self.assertRaises(FileExistsError):
                    loader.prepare_synthetic_video_input(root)


if __name__ == "__main__":
    unittest.main()
