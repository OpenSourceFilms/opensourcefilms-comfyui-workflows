"""No-network VHS_LoadVideo generated-media IMAGE path contract regressions."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "qualify_vhs_loadvideo_cpu.py"
spec = importlib.util.spec_from_file_location("osf_vhs_loader_cpu", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class VHSLoadVideoCPUContracts(unittest.TestCase):
    def test_source_is_fixed_two_frames_red_then_blue(self):
        raw = audit.synthetic_video_rgb24()
        self.assertEqual(len(raw), 64 * 64 * 3 * 2)
        self.assertEqual(raw[:3], bytes((255, 0, 0)))
        self.assertEqual(raw[-3:], bytes((0, 0, 255)))
        self.assertEqual(audit.VIDEO_NAME, "osf_generated_vhs_loader_2frame_cpu_probe.mp4")

    def test_prompt_matches_selected_loader_inputs_and_forbids_vae(self):
        graph = audit.build_vhs_upload_probe()
        self.assertEqual(set(graph), {"1", "2"})
        loader = graph["1"]
        self.assertEqual(loader["class_type"], "VHS_LoadVideo")
        self.assertEqual(set(loader["inputs"]), {
            "video", "force_rate", "custom_width", "custom_height",
            "frame_load_cap", "skip_first_frames", "select_every_nth", "format",
        })
        self.assertEqual(loader["inputs"]["format"], "AnimateDiff")
        self.assertEqual(loader["inputs"]["frame_load_cap"], 49)
        self.assertNotIn("vae", loader["inputs"])
        self.assertNotIn("meta_batch", loader["inputs"])
        self.assertEqual(graph["2"]["class_type"], "PreviewImage")
        self.assertEqual(graph["2"]["inputs"]["images"], ["1", 0])

    def test_history_requires_two_safe_temporary_images(self):
        pid = "generated-prompt"
        one = {"filename": "ComfyUI_temp_00001_.png", "type": "temp", "subfolder": ""}
        two = {"filename": "ComfyUI_temp_00002_.png", "type": "temp", "subfolder": ""}
        hist = {pid: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"2": {"images": [one, two]}},
        }}
        self.assertEqual(audit.validate_vhs_loader_history(hist, pid), [one, two])
        bad = {pid: {"status": {"completed": True, "status_str": "success"},
                     "outputs": {"2": {"images": [one]}}}}
        with self.assertRaisesRegex(ValueError, "wrong decoded frame count"):
            audit.validate_vhs_loader_history(bad, pid)
        for changed in (
            {**one, "type": "output"},
            {**one, "filename": "../outside.png"},
            {**one, "filename": "/etc/passwd.png"},
            {**one, "filename": "malformed.jpg"},
            {**one, "subfolder": "../outside"},
        ):
            with self.subTest(image=changed):
                bad[pid]["outputs"]["2"]["images"] = [changed, two]
                with self.assertRaisesRegex(ValueError, "Unsafe VHS"):
                    audit.validate_vhs_loader_history(bad, pid)
        hist[pid]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            audit.validate_vhs_loader_history(hist, pid)

    def test_existing_media_fails_before_ffmpeg_spawn(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / audit.VIDEO_NAME
            dest.write_bytes(b"already-there")
            with mock.patch.object(audit.subprocess, "run") as run:
                with self.assertRaises(FileExistsError):
                    audit._make_mp4("ffmpeg", dest)
                run.assert_not_called()

    def test_actual_runtime_must_report_live_loader_separately(self):
        script = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8",
        )
        self.assertIn("execute_vhs_loadvideo_cpu(", script)
        self.assertIn('"vhs_loadvideo_actual_no_vae_image_decode"', script)
        self.assertIn("vhs_loadvideo_actual_no_vae_image_decode", script)
        self.assertIn("from qualify_vhs_loadvideo_cpu import", script)


if __name__ == "__main__":
    unittest.main()
