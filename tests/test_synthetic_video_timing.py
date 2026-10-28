"""No-network contract tests for synthetic codec presentation timestamp gates."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "qualify_synthetic_video_timing.py"
spec = importlib.util.spec_from_file_location("osf_video_pts", SOURCE)
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


HEADER = "[Parsed_showinfo_0 @ 0x111] config in time_base: 1/16384, frame_rate: 2/1"
FRAME_A = ("[Parsed_showinfo_0 @ 0x111] n:   0 pts:      0 pts_time:0       "
           "duration:   8192 duration_time:0.5     fmt:yuv420p")
FRAME_B = ("[Parsed_showinfo_0 @ 0x111] n:   1 pts:   8192 pts_time:0.5     "
           "duration:   8192 duration_time:0.5     fmt:yuv420p")


def complete(*, header: str = HEADER, first: str = FRAME_A, second: str = FRAME_B):
    return "\n".join((header, first, second))


class SyntheticVideoTimingTests(unittest.TestCase):
    def test_two_frames_exact_half_second_pts_and_durations_pass(self):
        record = timing.validate_video_timing_log(complete())
        self.assertEqual(record["status"], "two_frame_2fps_pts_verified")
        self.assertEqual(record["nominal_frame_rate"], "2/1")
        self.assertEqual(record["decoded_frame_indices"], [0, 1])
        self.assertEqual(record["presentation_times_seconds"], [0, 0.5])
        self.assertEqual(record["frame_durations_seconds"], [0.5, 0.5])
        self.assertEqual(record["total_sampled_duration_seconds"], 1.0)
        self.assertFalse(record["media_bytes_uploaded"])

    def test_rejects_wrong_nominal_frame_rate(self):
        with self.assertRaisesRegex(ValueError, "nominal frame rate"):
            timing.validate_video_timing_log(
                complete(header=HEADER.replace("2/1", "1/1"))
            )

    def test_rejects_missing_or_extra_frames(self):
        with self.assertRaisesRegex(ValueError, "exactly two"):
            timing.validate_video_timing_log("\n".join((HEADER, FRAME_A)))
        with self.assertRaisesRegex(ValueError, "exactly two"):
            timing.validate_video_timing_log(complete() + "\n" + FRAME_B)

    def test_rejects_reordered_duplicate_frame_indices(self):
        for broken in (complete(first=FRAME_B, second=FRAME_A),
                       complete(first=FRAME_A, second=FRAME_A)):
            with self.subTest(broken=broken[-90:]):
                with self.assertRaisesRegex(ValueError, "frame order"):
                    timing.validate_video_timing_log(broken)

    def test_rejects_pts_drift_or_wrong_start(self):
        for broken in (
            complete(second=FRAME_B.replace("pts_time:0.5", "pts_time:0.55")),
            complete(first=FRAME_A.replace("pts_time:0", "pts_time:0.1")),
        ):
            with self.assertRaisesRegex(ValueError, "presentation timestamp"):
                timing.validate_video_timing_log(broken)

    def test_rejects_frame_duration_disagreement(self):
        altered = complete(second=FRAME_B.replace(
            "duration_time:0.5", "duration_time:0.25"))
        with self.assertRaisesRegex(ValueError, "per-frame duration"):
            timing.validate_video_timing_log(altered)

    def test_rejects_missing_duration_or_nonpositive_ticks(self):
        for altered in (
            complete(second=FRAME_B.replace("duration_time:0.5", "")),
            complete(second=FRAME_B.replace("duration:   8192", "duration:   0")),
        ):
            with self.assertRaises(ValueError):
                timing.validate_video_timing_log(altered)

    def test_rejects_empty_and_oversized_timing_logs(self):
        for bad in ("", "x" * 500001, None):
            with self.assertRaises(ValueError):
                timing.validate_video_timing_log(bad)

    def test_binds_all_three_video_codecs_to_real_pts_verification(self):
        s = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text("utf-8")
        for method in ("verify_h264_video", "verify_h265_video",
                       "verify_prores_video"):
            start = s.index("def " + method)
            end = s.find("\ndef ", start + 5)
            definition = s[start:] if end < 0 else s[start:end]
            self.assertIn("verify_video_timing(", definition)
            self.assertIn('"video_timing": timing', definition)


if __name__ == "__main__":
    unittest.main()
